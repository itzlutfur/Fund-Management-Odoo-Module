from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class NNIncomingFund(models.Model):
    """Incoming Fund: Records incoming transactions into fund accounts"""
    _name = 'nn.incoming_fund'
    _description = 'Incoming Fund'
    _order = 'date desc'

    name = fields.Char(string='Fund Reference', required=True, copy=False, readonly=True, default='New')
    fund_account_id = fields.Many2one('nn.fund_account', string='Fund Account', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    amount = fields.Monetary(string='Amount', required=True)
    transaction_reference = fields.Char(string='Transaction Reference', required=True)
    sender_source = fields.Char(string='Sender/Source', required=True)
    description = fields.Text(string='Description')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed')],
        string='Status',
        default='draft',
        readonly=True
    )
    
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    confirmed_date = fields.Datetime(string='Confirmed Date')
    confirmed_by = fields.Many2one('res.users', string='Confirmed By')

    _sql_constraints = [
        ('amount_positive', 'CHECK(amount > 0)', 'Amount must be positive!'),
        ('transaction_ref_unique', 'unique(transaction_reference, fund_account_id)', 'Transaction reference must be unique per fund account!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('nn.incoming_fund') or 'INF/' + datetime.now().strftime('%Y%m%d%H%M%S')
        return super().create(vals)

    def action_confirm(self):
        """Confirm incoming fund - amount added to fund account's unassigned balance"""
        for record in self:
            if record.state == 'confirmed':
                raise ValidationError('This incoming fund has already been confirmed!')
            record.write({
                'state': 'confirmed',
                'confirmed_date': fields.Datetime.now(),
                'confirmed_by': self.env.user.id,
            })

    def action_draft(self):
        """Move back to draft state (only if not locked)"""
        for record in self:
            if record.fund_account_id.allocation_ids.filtered(lambda a: a.state != 'cancelled'):
                raise ValidationError('Cannot move back to draft: this fund has active allocations!')
            record.state = 'draft'
