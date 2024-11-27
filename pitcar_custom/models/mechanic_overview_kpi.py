from odoo import models, fields, tools, api

class MechanicOverview(models.Model):
    _name = 'mechanic.overview'
    _description = 'Mechanic Overview'
    _auto = False
    _order = 'total_revenue desc'

    mechanic_id = fields.Many2one('pitcar.mechanic.new', string='Mechanic', readonly=True)
    total_revenue = fields.Float('Total Revenue', readonly=True)
    total_orders = fields.Integer('Total Orders', readonly=True)
    average_rating = fields.Float('Average Rating', readonly=True, digits=(16, 1))
    on_time_rate = fields.Float('On-Time Rate (%)', readonly=True, digits=(16, 1))
    average_completion_time = fields.Float('Avg Completion Time (Hours)', readonly=True, digits=(16, 1))
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    total_estimated_duration = fields.Float('Est. Duration (Hours)', readonly=True)
    total_actual_duration = fields.Float('Actual Duration (Hours)', readonly=True)
    duration_accuracy = fields.Float('Duration Accuracy (%)', readonly=True)
    target_revenue = fields.Float('Target Revenue', readonly=True)
    revenue_achievement = fields.Float('Revenue Achievement (%)', readonly=True)

     # Tambah fields untuk leader
    team_leader_id = fields.Many2one('pitcar.mechanic.new', string='Team Leader', compute='_compute_team_leader', store=True)
    team_revenue = fields.Float('Team Revenue', compute='_compute_team_metrics', store=True)
    team_target = fields.Float('Team Target', compute='_compute_team_metrics', store=True)
    team_achievement = fields.Float('Team Achievement (%)', compute='_compute_team_metrics', store=True)
    
    # Fields untuk filtering
    date = fields.Date('Date', readonly=True)
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='Month', readonly=True)
    year = fields.Integer('Year', readonly=True)

    def init(self):
       tools.drop_view_if_exists(self.env.cr, self._table)
       self.env.cr.execute("""
           CREATE OR REPLACE VIEW %s AS (
               WITH team_metrics AS (
                   SELECT 
                       COALESCE(tm.leader_id, tm.id) as leader_id,
                       date_trunc('month', so.date_order) as month_date,
                       SUM(so.amount_total) as team_revenue,
                       COUNT(DISTINCT tm.id) * 64000000 as team_target
                   FROM pitcar_mechanic_new tm
                   LEFT JOIN pitcar_mechanic_new_sale_order_rel rel ON rel.pitcar_mechanic_new_id = tm.id
                   LEFT JOIN sale_order so ON so.id = rel.sale_order_id
                   WHERE so.state in ('sale', 'done')
                   GROUP BY COALESCE(tm.leader_id, tm.id), date_trunc('month', so.date_order)
               ),
               monthly_stats AS (
                   SELECT 
                       m.id as mechanic_id,
                       l.id as team_leader_id,
                       date_trunc('month', so.date_order)::date as date,
                       EXTRACT(MONTH FROM so.date_order)::integer as month,
                       EXTRACT(YEAR FROM so.date_order)::integer as year,
                       COALESCE(SUM(so.amount_total), 0) as total_revenue,
                       COUNT(so.id) as total_orders,
                       ROUND(COALESCE(AVG(CASE WHEN so.customer_rating IS NOT NULL THEN CAST(so.customer_rating AS INTEGER) ELSE NULL END), 0)::numeric, 1) as average_rating,
                       ROUND(COALESCE(COUNT(CASE WHEN so.controller_selesai <= so.controller_estimasi_selesai AND so.controller_selesai IS NOT NULL AND so.controller_estimasi_selesai IS NOT NULL THEN 1 END)::numeric * 100.0 / NULLIF(COUNT(CASE WHEN so.controller_selesai IS NOT NULL AND so.controller_estimasi_selesai IS NOT NULL THEN 1 END), 0), 0), 1) as on_time_rate,
                       ROUND(COALESCE(AVG(CASE WHEN so.controller_selesai IS NOT NULL AND so.controller_mulai_servis IS NOT NULL THEN EXTRACT(EPOCH FROM (so.controller_selesai - so.controller_mulai_servis))/3600 ELSE NULL END), 0)::numeric, 1) as average_completion_time,
                       ROUND(COALESCE(SUM(CASE WHEN sol.service_duration IS NOT NULL THEN sol.service_duration ELSE 0 END), 0)::numeric, 1) as total_estimated_duration,
                       ROUND(COALESCE(AVG(CASE WHEN so.controller_selesai IS NOT NULL AND so.controller_mulai_servis IS NOT NULL THEN EXTRACT(EPOCH FROM (so.controller_selesai - so.controller_mulai_servis))/3600 ELSE NULL END), 0)::numeric, 1) as total_actual_duration,
                       ROUND(CASE WHEN SUM(COALESCE(sol.service_duration, 0)) > 0 THEN (1 - ABS(SUM(EXTRACT(EPOCH FROM (CASE WHEN so.controller_selesai IS NOT NULL AND so.controller_mulai_servis IS NOT NULL THEN so.controller_selesai - so.controller_mulai_servis ELSE interval '0' END))/3600) - SUM(COALESCE(sol.service_duration, 0))) / SUM(COALESCE(sol.service_duration, 0))) * 100 ELSE 0 END::numeric, 1) as duration_accuracy,
                       CASE WHEN p.code = 'leader' THEN (SELECT COUNT(*) FROM pitcar_mechanic_new WHERE leader_id = m.id) * 64000000 ELSE 64000000 END as target_revenue,
                       CASE WHEN p.code = 'leader' THEN ROUND((COALESCE(SUM(so.amount_total), 0) / NULLIF((SELECT COUNT(*) FROM pitcar_mechanic_new WHERE leader_id = m.id) * 64000000, 0) * 100)::numeric, 1) ELSE ROUND((COALESCE(SUM(so.amount_total), 0) / NULLIF(64000000, 0) * 100)::numeric, 1) END as revenue_achievement,
                       COALESCE(tm.team_revenue, 0) as team_revenue,
                       COALESCE(tm.team_target, 64000000) as team_target,
                       CASE WHEN COALESCE(tm.team_target, 0) > 0 THEN ROUND((COALESCE(tm.team_revenue, 0) * 100.0 / tm.team_target)::numeric, 1) ELSE 0 END as team_achievement
                   FROM pitcar_mechanic_new m
                   LEFT JOIN pitcar_mechanic_new l ON m.leader_id = l.id
                   LEFT JOIN pitcar_position p ON m.position_id = p.id
                   LEFT JOIN pitcar_mechanic_new_sale_order_rel rel ON rel.pitcar_mechanic_new_id = m.id
                   LEFT JOIN sale_order so ON so.id = rel.sale_order_id 
                   LEFT JOIN sale_order_line sol ON sol.order_id = so.id
                   LEFT JOIN team_metrics tm ON (m.leader_id = tm.leader_id OR m.id = tm.leader_id) AND date_trunc('month', so.date_order) = tm.month_date
                   WHERE so.state in ('sale', 'done')
                   GROUP BY 
                       m.id, l.id, p.code,
                       date_trunc('month', so.date_order),
                       EXTRACT(MONTH FROM so.date_order),
                       EXTRACT(YEAR FROM so.date_order),
                       tm.team_revenue, tm.team_target
               )
               SELECT 
                   row_number() OVER () as id,
                   ms.*,
                   %s as currency_id
               FROM monthly_stats ms
               ORDER BY ms.total_revenue DESC
           )
       """ % (self._table, self.env.company.currency_id.id))

        # @api.depends('mechanic_id')
        # def _compute_team_leader(self):
        #     for record in self:
        #         if record.mechanic_id.position_code == 'leader':
        #             record.team_leader_id = record.mechanic_id
        #         else:
        #             record.team_leader_id = record.mechanic_id.leader_id

        # @api.depends('team_leader_id')
        # def _compute_team_metrics(self):
        #     for record in self:
        #         if record.team_leader_id:
        #             team_members = self.env['pitcar.mechanic.new'].search([
        #                 ('leader_id', '=', record.team_leader_id.id)
        #             ])
        #             record.team_target = len(team_members) * 64000000
        #             record.team_revenue = sum(team_members.mapped('current_revenue'))
        #             record.team_achievement = (record.team_revenue / record.team_target * 100) if record.team_target else 0