from odoo import models, fields, api
from odoo.exceptions import ValidationError


class NNExpenseHead(models.Model):
    """Expense head for budget allocation (e.g., Office Rent, Salary, Utilities)"""
    _name = 'nn.expense_head'
    _description = 'Expense Head'
    _sql_constraints = [
        ('code_company_unique', 'unique(code, company_id)', 'Code must be unique per company!'),
    ]

    name = fields.Char(string='Expense Head Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    created_date = fields.Datetime(default=fields.Datetime.now)
