from odoo import models, fields, api

class ServiceAdvisor(models.Model):
    _name = 'pitcar.service.advisor'
    _description = 'Service Advisor'

    user_id = fields.Many2one('res.users', string="Service Advisor", required=True)
    color = fields.Integer(string="Color", default=0)

    # Tambahkan computed field untuk nama
    name = fields.Char(string="Service Advisor Name", compute='_compute_name', store=True)

    position_id = fields.Many2one('pitcar.service.advisor.position', string="Position", required=True)
    position_code = fields.Selection(
        related='position_id.code',
        string='Position Code',
        store=True
    )
    leader_id = fields.Many2one(
        'pitcar.service.advisor',
        string='Team Leader',
        domain="[('position_code', '=', 'leader')]"
    )
    team_member_ids = fields.One2many(
        'pitcar.service.advisor',
        'leader_id',
        string='Team Members'
    )
    monthly_target = fields.Float(
        string='Monthly Target',
        store=True
    )
    current_revenue = fields.Float(
        string='Current Revenue',
        compute='_compute_revenue_metrics'
    )
    target_achievement = fields.Float(
        string='Target Achievement (%)',
        compute='_compute_revenue_metrics'
    )

    @api.depends('user_id')
    def _compute_name(self):
        for record in self:
            record.name = record.user_id.name if record.user_id else ''

    @api.depends('position_id', 'team_member_ids')
    def _compute_monthly_target(self):
        for advisor in self:
            if advisor.position_code == 'leader':
                # Sum up the targets of all team members
                advisor.monthly_target = sum(member.monthly_target for member in advisor.team_member_ids)
            else:
                advisor.monthly_target = advisor.position_id.monthly_target

    @api.depends('monthly_target')
    def _compute_revenue_metrics(self):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        
        for advisor in self:
            # Calculate revenue
            if advisor.position_code == 'leader':
                # Include both team members' and leader's orders
                team_ids = advisor.team_member_ids.ids + [advisor.id]
                domain = [
                    ('service_advisor_id', 'in', team_ids),
                    ('date_order', '>=', first_day),
                    ('date_order', '<=', today),
                    ('state', '=', 'sale')
                ]
            else:
                domain = [
                    ('service_advisor_id', '=', advisor.id),
                    ('date_order', '>=', first_day),
                    ('date_order', '<=', today),
                    ('state', '=', 'sale')
                ]

            orders = self.env['sale.order'].search(domain)
            advisor.current_revenue = sum(orders.mapped('amount_total'))
            
            # Calculate achievement percentage
            if advisor.monthly_target:
                advisor.target_achievement = (advisor.current_revenue / advisor.monthly_target) * 100
            else:
                advisor.target_achievement = 0
