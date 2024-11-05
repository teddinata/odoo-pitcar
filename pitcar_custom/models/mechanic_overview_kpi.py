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
                WITH monthly_stats AS (
                    SELECT 
                        m.id as mechanic_id,
                        date_trunc('month', so.date_order)::date as date,
                        EXTRACT(MONTH FROM so.date_order)::integer as month,
                        EXTRACT(YEAR FROM so.date_order)::integer as year,
                        COALESCE(SUM(so.amount_total), 0) as total_revenue,
                        COUNT(so.id) as total_orders,
                        -- Hitung rating dari customer_rating (1-5)
                        ROUND(COALESCE(AVG(
                            CASE 
                                WHEN so.customer_rating IS NOT NULL 
                                THEN CAST(so.customer_rating AS INTEGER)
                                ELSE NULL 
                            END
                        ), 0)::numeric, 1) as average_rating,
                        -- Hitung on-time rate berdasarkan completion_time dan promised_time
                        ROUND(COALESCE(
                            COUNT(CASE 
                                WHEN so.controller_selesai <= so.controller_estimasi_selesai 
                                AND so.controller_selesai IS NOT NULL 
                                AND so.controller_estimasi_selesai IS NOT NULL 
                                THEN 1 
                            END)::numeric * 100.0 / 
                            NULLIF(COUNT(CASE 
                                WHEN so.controller_selesai IS NOT NULL 
                                AND so.controller_estimasi_selesai IS NOT NULL 
                                THEN 1 
                            END), 0), 
                            0
                        ), 1) as on_time_rate,
                        -- Hitung average completion time in hours
                        ROUND(COALESCE(AVG(
                            CASE 
                                WHEN so.controller_selesai IS NOT NULL AND so.controller_mulai_servis IS NOT NULL
                                THEN EXTRACT(EPOCH FROM (so.controller_selesai - so.controller_mulai_servis))/3600
                                ELSE NULL
                            END
                        ), 0)::numeric, 1) as average_completion_time
                    FROM 
                        pitcar_mechanic_new m
                    LEFT JOIN 
                        pitcar_mechanic_new_sale_order_rel rel ON rel.pitcar_mechanic_new_id = m.id
                    LEFT JOIN 
                        sale_order so ON so.id = rel.sale_order_id 
                        AND so.state in ('sale', 'done')
                    GROUP BY 
                        m.id,
                        date_trunc('month', so.date_order),
                        EXTRACT(MONTH FROM so.date_order),
                        EXTRACT(YEAR FROM so.date_order)
                )
                SELECT 
                    row_number() OVER () as id,
                    ms.*,
                    %s as currency_id
                FROM monthly_stats ms
                ORDER BY ms.total_revenue DESC
            )
        """ % (self._table, self.env.company.currency_id.id))