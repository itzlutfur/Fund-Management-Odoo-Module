from odoo import models, fields, api
from odoo.exceptions import ValidationError


class NNFundApprovalRule(models.Model):
    """Fund Approval Rule (Bonus): Configurable approval routing based on amount"""
    _name = 'nn.fund_approval_rule'
    _description = 'Fund Approval Rule'
    _order = 'company_id, min_amount'

    name = fields.Char(string='Rule Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    request_type = fields.Selection(
        [('allocation', 'Allocation'), ('requisition', 'Requisition'), ('transfer', 'Transfer')],
        string='Request Type',
        required=True
    )
    
    min_amount = fields.Monetary(string='Minimum Amount', default=0, currency_field='currency_id')
    max_amount = fields.Monetary(string='Maximum Amount', currency_field='currency_id')  # Leave blank for unlimited
    
    project_category_id = fields.Many2one('project.project', string='Project (Optional)')
    
    approval_sequence = fields.Selection(
        [('gm_only', 'GM Only'), ('gm_and_md', 'GM and MD'), ('gm_finance_md', 'GM, Finance, and MD'), ('custom', 'Custom')],
        string='Approval Sequence',
        default='gm_and_md'
    )
    
    approver_ids = fields.Many2many('res.users', string='Custom Approvers')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('min_max_order', 'CHECK(max_amount IS NULL OR min_amount <= max_amount)', 'Minimum amount cannot exceed maximum!'),
    ]

    @api.constrains('approval_sequence', 'approver_ids')
    def _check_custom_approvers(self):
        for record in self:
            if record.approval_sequence == 'custom' and not record.approver_ids:
                raise ValidationError('Please select approvers for custom sequence!')

    def get_approval_levels_for_amount(self, amount, request_type):
        """Get approval levels required for given amount and request type"""
        rule = self.search([
            ('company_id', '=', self.env.company.id),
            ('request_type', '=', request_type),
            ('min_amount', '<=', amount),
            ('active', '=', True),
            '|', ('max_amount', '=', False), ('max_amount', '>=', amount)
        ], limit=1)
        
        if not rule:
            # Default to GM and MD if no rule matches
            return ['gm', 'md']
        
        if rule.approval_sequence == 'gm_only':
            return ['gm']
        elif rule.approval_sequence == 'gm_and_md':
            return ['gm', 'md']
        elif rule.approval_sequence == 'gm_finance_md':
            return ['gm', 'finance', 'md']
        elif rule.approval_sequence == 'custom':
            return rule.approver_ids.ids
        
        return ['gm', 'md']  # Default fallback
