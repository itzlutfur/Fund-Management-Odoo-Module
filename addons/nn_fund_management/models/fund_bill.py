from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class NNFundBill(models.Model):
    """Fund Bill: Records bills posted against approved requisitions"""
    _name = 'nn.fund_bill'
    _description = 'Fund Bill'
    _order = 'bill_date desc'

    # Basic Fields
    name = fields.Char(string='Bill Number', required=True, copy=False, readonly=True, default='New')
    requisition_id = fields.Many2one('nn.fund_requisition', string='Requisition', required=True)
    amount = fields.Monetary(string='Bill Amount', required=True)
    bill_date = fields.Date(string='Bill Date', default=fields.Date.context_today, required=True)
    description = fields.Text(string='Description')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    # Workflow
    state = fields.Selection(
        [('draft', 'Draft'), ('posted', 'Posted'), ('cancelled', 'Cancelled')],
        string='Status',
        default='draft',
        readonly=True
    )

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ('amount_positive', 'CHECK(amount > 0)', 'Bill amount must be positive!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund_bill') or 'BILL/' + datetime.now().strftime('%Y%m%d%H%M%S')
        return super().create(vals)

    def action_post(self):
        """Post bill - marks as spent and updates requisition"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Only draft bills can be posted!')
            
            requisition = record.requisition_id
            
            # Validate requisition state
            if requisition.state != 'approved':
                raise ValidationError('Can only bill against approved requisitions!')
            
            # Validate bill amount
            if record.amount > requisition.remaining_billable_amount:
                raise ValidationError(
                    f'Cannot bill {record.amount}! '
                    f'Remaining billable: {requisition.remaining_billable_amount}'
                )
            
            # Validate project/expense head match
            if requisition.project_id:
                bill_project = record._get_bill_project()
                if bill_project and bill_project.id != requisition.project_id.id:
                    raise ValidationError('Bill project does not match requisition project!')
            
            if requisition.expense_head_id:
                bill_expense = record._get_bill_expense()
                if bill_expense and bill_expense.id != requisition.expense_head_id.id:
                    raise ValidationError('Bill expense head does not match requisition expense head!')
            
            record.write({'state': 'posted'})

    def action_cancel(self):
        """Cancel/reverse bill - returns amount to requisition"""
        for record in self:
            if record.state == 'cancelled':
                raise ValidationError('This bill has already been cancelled!')
            
            record.write({'state': 'cancelled'})

    def _get_bill_project(self):
        """Get project from requisition"""
        return self.requisition_id.project_id

    def _get_bill_expense(self):
        """Get expense head from requisition"""
        return self.requisition_id.expense_head_id
