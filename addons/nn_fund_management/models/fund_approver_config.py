from odoo import models, fields, api
from odoo.exceptions import ValidationError


class NNFundApproverConfig(models.Model):
    """Fund Approver Config: Configurable approver assignment per company"""
    _name = 'nn.fund_approver_config'
    _description = 'Fund Approver Configuration'

    company_id = fields.Many2one('res.company', string='Company', required=True)
    
    # GM Approver
    gm_user_id = fields.Many2one('res.users', string='General Manager (User)')
    gm_group_id = fields.Many2one('res.groups', string='General Manager (Group)')
    
    # MD Approver
    md_user_id = fields.Many2one('res.users', string='Managing Director (User)')
    md_group_id = fields.Many2one('res.groups', string='Managing Director (Group)')
    
    can_self_approve = fields.Boolean(string='Allow Self-Approval', default=False)

    _sql_constraints = [
        ('unique_company', 'UNIQUE(company_id)', 'Approver configuration must be unique per company!'),
    ]

    @api.constrains('gm_user_id', 'gm_group_id')
    def _check_gm_config(self):
        for record in self:
            if not record.gm_user_id and not record.gm_group_id:
                raise ValidationError('Please set either a GM user or a GM group!')

    @api.constrains('md_user_id', 'md_group_id')
    def _check_md_config(self):
        for record in self:
            if not record.md_user_id and not record.md_group_id:
                raise ValidationError('Please set either an MD user or an MD group!')

    def get_gm_approvers(self):
        """Get list of GM approver user IDs"""
        approvers = []
        if self.gm_user_id:
            approvers.append(self.gm_user_id.id)
        if self.gm_group_id:
            approvers.extend(self.gm_group_id.users.ids)
        return approvers

    def get_md_approvers(self):
        """Get list of MD approver user IDs"""
        approvers = []
        if self.md_user_id:
            approvers.append(self.md_user_id.id)
        if self.md_group_id:
            approvers.extend(self.md_group_id.users.ids)
        return approvers

    def can_approve_at_level(self, user_id, level):
        """Check if user can approve at given level (gm or md)"""
        if level == 'gm':
            return user_id in self.get_gm_approvers()
        elif level == 'md':
            return user_id in self.get_md_approvers()
        return False
