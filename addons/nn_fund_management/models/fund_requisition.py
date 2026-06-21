from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError
from datetime import datetime


class NNFundRequisition(models.Model):
    """Fund Requisition: Requests funds from approved allocation"""
    _name = 'nn.fund_requisition'
    _description = 'Fund Requisition'
    _order = 'request_date desc'

    # Basic Fields
    name = fields.Char(string='Requisition Number', required=True, copy=False, readonly=True, default='New')
    project_id = fields.Many2one('project.project', string='Project')
    expense_head_id = fields.Many2one('nn.expense_head', string='Expense Head')
    requested_amount = fields.Monetary(string='Requested Amount', required=True)
    purpose = fields.Text(string='Purpose', required=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, required=True)
    required_date = fields.Date(string='Required Date', required=True)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, required=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    # Workflow Fields
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('gm_approved', 'GM Approved'),
         ('md_approved', 'MD Approved'), ('approved', 'Approved'), ('rejected', 'Rejected'),
         ('cancelled', 'Cancelled'), ('closed', 'Closed')],
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
    bill_ids = fields.One2many('nn.fund_bill', 'requisition_id', string='Bills')
    approval_history_ids = fields.One2many('nn.approval_history', 'requisition_id', string='Approval History')

    # Computed Fields
    @api.depends('bill_ids.state', 'bill_ids.amount')
    def _compute_remaining_billable(self):
        for requisition in self:
            billed = sum(bill.amount for bill in requisition.bill_ids if bill.state == 'posted')
            requisition.remaining_billable_amount = requisition.requested_amount - billed

    remaining_billable_amount = fields.Monetary(string='Remaining Billable', compute='_compute_remaining_billable', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ('amount_positive', 'CHECK(requested_amount > 0)', 'Amount must be positive!'),
        ('project_or_expense', 'CHECK((project_id IS NOT NULL AND expense_head_id IS NULL) OR (project_id IS NULL AND expense_head_id IS NOT NULL))',
         'Please select either a project or an expense head, not both!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund_requisition') or 'REQ/' + datetime.now().strftime('%Y%m%d%H%M%S')
        return super().create(vals)

    def action_submit(self):
        """Submit requisition - amount placed on hold"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Only draft requisitions can be submitted!')
            
            # Get balance and validate
            if record.project_id:
                fund_balance = self.env['nn.fund_balance'].search([
                    ('project_id', '=', record.project_id.id),
                    ('company_id', '=', record.company_id.id)
                ])
            else:
                fund_balance = self.env['nn.fund_balance'].search([
                    ('expense_head_id', '=', record.expense_head_id.id),
                    ('company_id', '=', record.company_id.id)
                ])
            
            if not fund_balance:
                raise ValidationError('No allocation found for this project/expense head!')
            
            available = fund_balance.available_balance
            if record.requested_amount > available:
                raise ValidationError(f'Insufficient balance! Requested: {record.requested_amount}, Available: {available}')
            
            record.write({
                'state': 'submitted',
                'current_approval_level': 'gm_pending',
            })

    def action_approve_gm(self):
        """GM approval"""
        for record in self:
            if record.state != 'submitted':
                raise ValidationError('Only submitted requisitions can be approved!')
            
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not config.can_approve_at_level(self.env.user.id, 'gm'):
                raise AccessError('You do not have GM approval permission!')
            
            record.write({
                'state': 'gm_approved',
                'current_approval_level': 'md_pending',
            })
            
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'requisition', 'gm', 'approved'
            )

    def action_approve_md(self):
        """MD approval"""
        for record in self:
            if record.state != 'gm_approved':
                raise ValidationError('Requisition must be GM-approved before MD approval!')
            
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not config.can_approve_at_level(self.env.user.id, 'md'):
                raise AccessError('You do not have MD approval permission!')
            
            record.write({
                'state': 'approved',
                'current_approval_level': 'completed',
            })
            
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'requisition', 'md', 'approved'
            )

    def action_reject(self):
        """Reject requisition"""
        for record in self:
            if record.state in ['approved', 'rejected', 'cancelled', 'closed']:
                raise ValidationError(f'Cannot reject requisition in {record.state} state!')
            
            config = self.env['nn.fund_approver_config'].search([('company_id', '=', self.env.company.id)])
            if not (config.can_approve_at_level(self.env.user.id, 'gm') or 
                    config.can_approve_at_level(self.env.user.id, 'md')):
                raise AccessError('You do not have permission to reject requisitions!')
            
            record.write({
                'state': 'rejected',
                'current_approval_level': 'rejected',
            })
            
            self.env['nn.approval_history'].create_approval_record(
                record.id, 'requisition', 'gm', 'rejected'
            )

    def action_close(self):
        """Close requisition - only when fully billed or unused amount released"""
        for record in self:
            if record.state != 'approved':
                raise ValidationError('Only approved requisitions can be closed!')
            
            if record.remaining_billable_amount > 0:
                raise ValidationError(f'Cannot close: {record.remaining_billable_amount} still billable!')
            
            record.state = 'closed'

    def action_cancel(self):
        """Cancel requisition"""
        for record in self:
            if record.state in ['approved', 'cancelled', 'closed']:
                raise ValidationError(f'Cannot cancel requisition in {record.state} state!')
            
            record.write({
                'state': 'cancelled',
                'current_approval_level': 'cancelled',
            })
