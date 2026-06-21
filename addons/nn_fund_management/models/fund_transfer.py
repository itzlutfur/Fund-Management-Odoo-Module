from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError
from datetime import datetime


class NNFundTransfer(models.Model):
    """Fund Transfer: Transfers funds between projects or expense heads"""
    _name = 'nn.fund_transfer'
    _description = 'Fund Transfer'
    _order = 'request_date desc'

    # Basic Fields
    name = fields.Char(string='Transfer Number', required=True, copy=False, readonly=True, default='New')
    amount = fields.Monetary(string='Amount', required=True)
    reason = fields.Text(string='Reason', required=True)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, required=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    # Source (polymorphic)
    source_type = fields.Selection(
        [('project', 'Project'), ('expense_head', 'Expense Head')],
        string='Source Type',
        required=True
    )
    source_project_id = fields.Many2one('project.project', string='Source Project')
    source_expense_head_id = fields.Many2one('nn.expense_head', string='Source Expense Head')

    # Destination (polymorphic)
    destination_type = fields.Selection(
        [('project', 'Project'), ('expense_head', 'Expense Head')],
        string='Destination Type',
        required=True
    )
    destination_project_id = fields.Many2one('project.project', string='Destination Project')
    destination_expense_head_id = fields.Many2one('nn.expense_head', string='Destination Expense Head')

    # Workflow
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('gm_approved', 'GM Approved'),
         ('md_approved', 'MD Approved'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')],
        string='Status',
        default='draft',
        readonly=True
    )
    current_approval_level = fields.Selection(
        [('none', 'None'), ('gm_pending', 'Pending GM'), ('md_pending', 'Pending MD'),
         ('completed', 'Completed'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')],
        string='Current Approval Level',
        default='none',
        readonly=True
    )

    # Relationships
    approval_history_ids = fields.One2many('nn.approval_history', 'transfer_id', string='Approval History')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ('amount_positive', 'CHECK(amount > 0)', 'Amount must be positive!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund_transfer') or 'TRF/' + datetime.now().strftime('%Y%m%d%H%M%S')
        return super().create(vals)

    @api.constrains('source_type', 'source_project_id', 'source_expense_head_id')
    def _check_source(self):
        for record in self:
            if record.source_type == 'project' and not record.source_project_id:
                raise ValidationError('Please select a source project!')
            if record.source_type == 'expense_head' and not record.source_expense_head_id:
                raise ValidationError('Please select a source expense head!')

    @api.constrains('destination_type', 'destination_project_id', 'destination_expense_head_id')
    def _check_destination(self):
        for record in self:
            if record.destination_type == 'project' and not record.destination_project_id:
                raise ValidationError('Please select a destination project!')
            if record.destination_type == 'expense_head' and not record.destination_expense_head_id:
                raise ValidationError('Please select a destination expense head!')

    @api.constrains('source_type', 'source_project_id', 'source_expense_head_id', 'destination_type', 'destination_project_id', 'destination_expense_head_id')
    def _check_same_source_destination(self):
        for record in self:
            if record.source_type == record.destination_type:
                if record.source_type == 'project':
                    if record.source_project_id.id == record.destination_project_id.id:
                        raise ValidationError('Source and destination cannot be the same!')
                elif record.source_type == 'expense_head':
                    if record.source_expense_head_id.id == record.destination_expense_head_id.id:
                        raise ValidationError('Source and destination cannot be the same!')

    def action_submit(self):
        """Submit transfer - amount placed on hold in source"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Only draft transfers can be submitted!')
            
            # Get source balance
            source_balance = self._get_source_balance()
            if not source_balance:
                raise ValidationError('Source project/expense not found!')
            
            available = source_balance.available_balance
            if record.amount > available:
                raise ValidationError(
                    f'Insufficient balance! Requested: {record.amount}, Available: {available}'
                )
            
            record.write({
                'state': 'submitted',
                'current_approval_level': 'gm_pending',
            })

    def action_approve_gm(self):
        """GM approval"""
        for record in self:
            if record.state != 'submitted':
                raise ValidationError('Only submitted transfers can be approved!')
            
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not config.can_approve_at_level(self.env.user.id, 'gm'):
                raise AccessError('You do not have GM approval permission!')
            
            record.write({
                'state': 'gm_approved',
                'current_approval_level': 'md_pending',
            })
            
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'transfer', 'gm', 'approved'
            )

    def action_approve_md(self):
        """MD approval - finalizes transfer"""
        for record in self:
            if record.state != 'gm_approved':
                raise ValidationError('Transfer must be GM-approved before MD approval!')
            
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not config.can_approve_at_level(self.env.user.id, 'md'):
                raise AccessError('You do not have MD approval permission!')
            
            record.write({
                'state': 'approved',
                'current_approval_level': 'completed',
            })
            
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'transfer', 'md', 'approved'
            )

    def action_reject(self):
        """Reject transfer"""
        for record in self:
            if record.state in ['approved', 'rejected', 'cancelled']:
                raise ValidationError(f'Cannot reject transfer in {record.state} state!')
            
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not (config.can_approve_at_level(self.env.user.id, 'gm') or 
                    config.can_approve_at_level(self.env.user.id, 'md')):
                raise AccessError('You do not have permission to reject transfers!')
            
            record.write({
                'state': 'rejected',
                'current_approval_level': 'rejected',
            })
            
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'transfer', 'gm', 'rejected'
            )

    def action_cancel(self):
        """Cancel transfer"""
        for record in self:
            if record.state in ['approved', 'cancelled']:
                raise ValidationError(f'Cannot cancel transfer in {record.state} state!')
            
            record.write({
                'state': 'cancelled',
                'current_approval_level': 'cancelled',
            })

    def _get_source_balance(self):
        """Get source fund balance"""
        if self.source_type == 'project':
            return self.env['nn.fund_balance'].search([
                ('project_id', '=', self.source_project_id.id),
                ('company_id', '=', self.company_id.id)
            ])
        else:
            return self.env['nn.fund_balance'].search([
                ('expense_head_id', '=', self.source_expense_head_id.id),
                ('company_id', '=', self.company_id.id)
            ])

    def _get_destination_balance(self):
        """Get destination fund balance"""
        if self.destination_type == 'project':
            return self.env['nn.fund_balance'].search([
                ('project_id', '=', self.destination_project_id.id),
                ('company_id', '=', self.company_id.id)
            ])
        else:
            return self.env['nn.fund_balance'].search([
                ('expense_head_id', '=', self.destination_expense_head_id.id),
                ('company_id', '=', self.company_id.id)
            ])
