from odoo import models, fields, api
from odoo.exceptions import ValidationError


class NNFundAccount(models.Model):
    """Fund Account: Bank, cash, or other financial accounts"""
    _name = 'nn.fund_account'
    _description = 'Fund Account'

    name = fields.Char(string='Account Name', required=True)
    account_type = fields.Selection(
        [('bank', 'Bank'), ('cash', 'Cash'), ('other', 'Other')],
        string='Account Type',
        required=True,
        default='bank'
    )
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    # Relationships
    incoming_fund_ids = fields.One2many('nn.incoming_fund', 'fund_account_id', string='Incoming Funds')
    allocation_ids = fields.One2many('nn.fund_allocation', 'fund_account_id', string='Allocations')

    # Computed Balance Fields (Read-only)
    @api.depends('incoming_fund_ids.state', 'incoming_fund_ids.amount', 'allocation_ids.state', 'allocation_ids.amount')
    def _compute_total_received(self):
        for account in self:
            account.total_received = sum(
                incoming.amount for incoming in account.incoming_fund_ids 
                if incoming.state == 'confirmed'
            )

    @api.depends('total_received', 'on_hold_amount', 'assigned_amount')
    def _compute_unassigned_balance(self):
        for account in self:
            account.unassigned_balance = account.total_received - account.on_hold_amount - account.assigned_amount

    @api.depends('allocation_ids.state', 'allocation_ids.amount')
    def _compute_on_hold_amount(self):
        for account in self:
            account.on_hold_amount = sum(
                alloc.amount for alloc in account.allocation_ids
                if alloc.state in ['submitted', 'gm_approved', 'md_approved']
            )

    @api.depends('allocation_ids.state', 'allocation_ids.amount')
    def _compute_assigned_amount(self):
        for account in self:
            account.assigned_amount = sum(
                alloc.amount for alloc in account.allocation_ids
                if alloc.state == 'approved'
            )

    total_received = fields.Monetary(string='Total Received', compute='_compute_total_received', store=True)
    unassigned_balance = fields.Monetary(string='Unassigned Balance', compute='_compute_unassigned_balance', store=True)
    on_hold_amount = fields.Monetary(string='Amount on Hold', compute='_compute_on_hold_amount', store=True)
    assigned_amount = fields.Monetary(string='Total Assigned', compute='_compute_assigned_amount', store=True)

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ('name_company_unique', 'unique(name, company_id)', 'Account name must be unique per company!'),
    ]
