from odoo import models, fields, api
from odoo.exceptions import ValidationError


class NNFundBalance(models.Model):
    """Fund Balance: Tracks balances for projects and expense heads (polymorphic)"""
    _name = 'nn.fund_balance'
    _description = 'Fund Balance'

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    # Polymorphic fields
    content_type = fields.Selection(
        [('project', 'Project'), ('expense_head', 'Expense Head')],
        string='Type',
        required=True
    )
    project_id = fields.Many2one('project.project', string='Project', ondelete='cascade')
    expense_head_id = fields.Many2one('nn.expense_head', string='Expense Head', ondelete='cascade')
    
    # Relationships
    allocation_ids = fields.One2many('nn.fund_allocation', compute='_get_allocations', string='Allocations')
    requisition_ids = fields.One2many('nn.fund_requisition', compute='_get_requisitions', string='Requisitions')
    bill_ids = fields.One2many('nn.fund_bill', compute='_get_bills', string='Bills')
    transfer_ids_source = fields.One2many('nn.fund_transfer', compute='_get_transfers_source', string='Outgoing Transfers')
    transfer_ids_dest = fields.One2many('nn.fund_transfer', compute='_get_transfers_dest', string='Incoming Transfers')

    # Computed Balance Fields (Read-only)
    @api.depends('content_type', 'project_id', 'expense_head_id')
    def _get_allocations(self):
        for balance in self:
            if balance.content_type == 'project':
                balance.allocation_ids = self.env['nn.fund_allocation'].search([
                    ('project_id', '=', balance.project_id.id),
                    ('state', '=', 'approved')
                ])
            else:
                balance.allocation_ids = self.env['nn.fund_allocation'].search([
                    ('expense_head_id', '=', balance.expense_head_id.id),
                    ('state', '=', 'approved')
                ])

    def _get_requisitions(self):
        for balance in self:
            if balance.content_type == 'project':
                balance.requisition_ids = self.env['nn.fund_requisition'].search([
                    ('project_id', '=', balance.project_id.id)
                ])
            else:
                balance.requisition_ids = self.env['nn.fund_requisition'].search([
                    ('expense_head_id', '=', balance.expense_head_id.id)
                ])

    def _get_bills(self):
        for balance in self:
            if balance.content_type == 'project':
                balance.bill_ids = self.env['nn.fund_bill'].search([
                    ('requisition_id.project_id', '=', balance.project_id.id)
                ])
            else:
                balance.bill_ids = self.env['nn.fund_bill'].search([
                    ('requisition_id.expense_head_id', '=', balance.expense_head_id.id)
                ])

    def _get_transfers_source(self):
        for balance in self:
            domain = [('state', '=', 'approved')]
            if balance.content_type == 'project':
                domain += [('source_type', '=', 'project'), ('source_project_id', '=', balance.project_id.id)]
            else:
                domain += [('source_type', '=', 'expense_head'), ('source_expense_head_id', '=', balance.expense_head_id.id)]
            balance.transfer_ids_source = self.env['nn.fund_transfer'].search(domain)

    def _get_transfers_dest(self):
        for balance in self:
            domain = [('state', '=', 'approved')]
            if balance.content_type == 'project':
                domain += [('destination_type', '=', 'project'), ('destination_project_id', '=', balance.project_id.id)]
            else:
                domain += [('destination_type', '=', 'expense_head'), ('destination_expense_head_id', '=', balance.expense_head_id.id)]
            balance.transfer_ids_dest = self.env['nn.fund_transfer'].search(domain)

    @api.depends('allocation_ids.amount')
    def _compute_total_allocated(self):
        for balance in self:
            balance.total_allocated = sum(a.amount for a in balance.allocation_ids)

    @api.depends('requisition_ids.state', 'requisition_ids.requested_amount')
    def _compute_requisition_hold(self):
        for balance in self:
            balance.requisition_hold = sum(
                req.requested_amount for req in balance.requisition_ids
                if req.state in ['submitted', 'gm_approved', 'md_approved', 'approved']
            )

    @api.depends('transfer_ids_source.state', 'transfer_ids_source.amount')
    def _compute_transfer_hold(self):
        for balance in self:
            balance.transfer_hold = sum(
                trf.amount for trf in balance.transfer_ids_source
                if trf.state in ['submitted', 'gm_approved', 'md_approved']
            )

    @api.depends('bill_ids.state', 'bill_ids.amount')
    def _compute_total_spent(self):
        for balance in self:
            balance.total_spent = sum(
                bill.amount for bill in balance.bill_ids
                if bill.state == 'posted'
            )

    @api.depends('transfer_ids_dest.amount')
    def _compute_incoming_transfers(self):
        for balance in self:
            balance.incoming_transfers = sum(trf.amount for trf in balance.transfer_ids_dest)

    @api.depends('transfer_ids_source.amount')
    def _compute_outgoing_transfers(self):
        for balance in self:
            balance.outgoing_transfers = sum(trf.amount for trf in balance.transfer_ids_source)

    @api.depends('total_allocated', 'requisition_hold', 'transfer_hold', 'total_spent')
    def _compute_available_balance(self):
        for balance in self:
            balance.available_balance = balance.total_allocated - balance.requisition_hold - balance.transfer_hold - balance.total_spent

    @api.depends('requisition_ids.state', 'requisition_ids.requested_amount')
    def _compute_approved_unspent(self):
        for balance in self:
            balance.approved_unspent = sum(
                req.requested_amount for req in balance.requisition_ids
                if req.state == 'approved'
            )

    total_allocated = fields.Monetary(string='Total Allocated', compute='_compute_total_allocated', store=True)
    available_balance = fields.Monetary(string='Available Balance', compute='_compute_available_balance', store=True)
    requisition_hold = fields.Monetary(string='Requisition Hold', compute='_compute_requisition_hold', store=True)
    transfer_hold = fields.Monetary(string='Transfer Hold', compute='_compute_transfer_hold', store=True)
    total_spent = fields.Monetary(string='Total Spent', compute='_compute_total_spent', store=True)
    incoming_transfers = fields.Monetary(string='Incoming Transfers', compute='_compute_incoming_transfers', store=True)
    outgoing_transfers = fields.Monetary(string='Outgoing Transfers', compute='_compute_outgoing_transfers', store=True)
    approved_unspent = fields.Monetary(string='Approved but Unspent', compute='_compute_approved_unspent', store=True)

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ('check_non_negative_balance', 'CHECK(available_balance >= 0)', 'Available balance cannot be negative!'),
    ]

    def _check_balance_constraint(self):
        """Ensure no negative balances"""
        for record in self:
            if record.available_balance < 0:
                raise ValidationError(f'Negative balance not allowed for {record.project_id.name or record.expense_head_id.name}!')
