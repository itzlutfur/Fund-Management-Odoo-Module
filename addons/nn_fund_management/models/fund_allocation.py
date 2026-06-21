from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError
from datetime import datetime


class NNFundAllocation(models.Model):
    """Fund Allocation: Assigns funds from fund account to project/expense head"""
    _name = 'nn.fund_allocation'
    _description = 'Fund Allocation'
    _order = 'request_date desc'

    # Basic Fields
    name = fields.Char(string='Allocation Number', required=True, copy=False, readonly=True, default='New')
    fund_account_id = fields.Many2one('nn.fund_account', string='Fund Account', required=True)
    project_id = fields.Many2one('project.project', string='Project')
    expense_head_id = fields.Many2one('nn.expense_head', string='Expense Head')
    amount = fields.Monetary(string='Amount', required=True)
    purpose = fields.Text(string='Purpose', required=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, required=True)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, required=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    # Workflow Fields
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
    approval_history_ids = fields.One2many('nn.approval_history', 'allocation_id', string='Approval History')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ('amount_positive', 'CHECK(amount > 0)', 'Amount must be positive!'),
        ('project_or_expense', 'CHECK((project_id IS NOT NULL AND expense_head_id IS NULL) OR (project_id IS NULL AND expense_head_id IS NOT NULL))',
         'Please select either a project or an expense head, not both!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund_allocation') or 'ALLOC/' + datetime.now().strftime('%Y%m%d%H%M%S')
        return super().create(vals)

    def action_submit(self):
        """Submit allocation request - amount placed on hold"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Only draft allocations can be submitted!')
            
            # Validate available balance
            available = record.fund_account_id.unassigned_balance
            if record.amount > available:
                raise ValidationError(f'Insufficient balance! Requested: {record.amount}, Available: {available}')
            
            record.write({
                'state': 'submitted',
                'current_approval_level': 'gm_pending',
            })

    def action_approve_gm(self):
        """GM approval"""
        for record in self:
            if record.state != 'submitted':
                raise ValidationError('Only submitted allocations can be approved!')
            if record.current_approval_level != 'gm_pending':
                raise ValidationError('Allocation is not pending GM approval!')
            
            # Check user permission
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not config.can_approve_at_level(self.env.user.id, 'gm'):
                raise AccessError('You do not have GM approval permission!')
            
            record.write({
                'state': 'gm_approved',
                'current_approval_level': 'md_pending',
            })
            
            # Create approval history
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'allocation', 'gm', 'approved'
            )

    def action_approve_md(self):
        """MD approval - finalizes allocation"""
        for record in self:
            if record.state != 'gm_approved':
                raise ValidationError('Allocation must be GM-approved before MD approval!')
            if record.current_approval_level != 'md_pending':
                raise ValidationError('Allocation is not pending MD approval!')
            
            # Check user permission
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not config.can_approve_at_level(self.env.user.id, 'md'):
                raise AccessError('You do not have MD approval permission!')
            
            record.write({
                'state': 'approved',
                'current_approval_level': 'completed',
            })
            
            # Create approval history
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'allocation', 'md', 'approved'
            )

    def action_reject(self):
        """Reject allocation - returns amount to unassigned balance"""
        for record in self:
            if record.state in ['approved', 'rejected', 'cancelled']:
                raise ValidationError(f'Cannot reject allocation in {record.state} state!')
            
            # Check user permission (GM or MD can reject)
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not (config.can_approve_at_level(self.env.user.id, 'gm') or 
                    config.can_approve_at_level(self.env.user.id, 'md')):
                raise AccessError('You do not have permission to reject allocations!')
            
            record.write({
                'state': 'rejected',
                'current_approval_level': 'rejected',
            })
            
            # Create approval history
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'allocation', record.current_approval_level.split('_')[0] if '_' in record.current_approval_level else 'gm',
                'rejected'
            )

    def action_cancel(self):
        """Cancel allocation"""
        for record in self:
            if record.state in ['approved', 'cancelled']:
                raise ValidationError(f'Cannot cancel allocation in {record.state} state!')
            
            record.write({
                'state': 'cancelled',
                'current_approval_level': 'cancelled',
            })
