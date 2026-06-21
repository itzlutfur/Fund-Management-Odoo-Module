from odoo import models, fields, api


class NNApprovalHistory(models.Model):
    """Approval History: Audit trail for all approval decisions"""
    _name = 'nn.approval_history'
    _description = 'Approval History'
    _order = 'decision_date desc'

    # Polymorphic reference
    request_type = fields.Selection(
        [('allocation', 'Allocation'), ('requisition', 'Requisition'), ('transfer', 'Transfer')],
        string='Request Type',
        required=True
    )
    allocation_id = fields.Many2one('nn.fund_allocation', string='Allocation')
    requisition_id = fields.Many2one('nn.fund_requisition', string='Requisition')
    transfer_id = fields.Many2one('nn.fund_transfer', string='Transfer')

    approver_id = fields.Many2one('res.users', string='Approver', required=True)
    approval_level = fields.Selection(
        [('gm', 'General Manager'), ('md', 'Managing Director')],
        string='Approval Level',
        required=True
    )
    decision = fields.Selection(
        [('approved', 'Approved'), ('rejected', 'Rejected'), ('commented', 'Commented')],
        string='Decision',
        required=True
    )
    comment = fields.Text(string='Comment')
    decision_date = fields.Datetime(string='Decision Date', default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    _sql_constraints = [
        ('approver_check', 'CHECK(approver_id IS NOT NULL)', 'Approver is required!'),
    ]

    @api.model
    def create_approval_record(self, request_id, request_type, approval_level, decision, comment=''):
        """Helper method to create approval history records"""
        vals = {
            'request_type': request_type,
            'approval_level': approval_level,
            'decision': decision,
            'comment': comment,
            'approver_id': self.env.user.id,
            'decision_date': fields.Datetime.now(),
            'company_id': self.env.company.id,
        }
        
        if request_type == 'allocation':
            vals['allocation_id'] = request_id
        elif request_type == 'requisition':
            vals['requisition_id'] = request_id
        elif request_type == 'transfer':
            vals['transfer_id'] = request_id
        
        return self.create(vals)
