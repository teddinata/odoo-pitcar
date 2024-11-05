from odoo import models, fields, tools, api

class ServiceAdvisorOverview(models.Model):
    _name = 'service.advisor.overview'
    _description = 'Service Advisor Overview'
    _auto = False
    _order = 'total_revenue DESC'

    service_advisor_id = fields.Many2one('pitcar.service.advisor', string='Service Advisor', readonly=True)
    total_revenue = fields.Float('Total Revenue', readonly=True)
    total_orders = fields.Integer('Total Orders', readonly=True)
    average_rating = fields.Float('Average Rating', readonly=True, digits=(16, 1))
    on_time_rate = fields.Float('On-Time Rate (%)', readonly=True, digits=(16, 1))
    feedback_rate = fields.Float('Feedback Rate (%)', readonly=True, digits=(16, 1))
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
                        sa.id as service_advisor_id,
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
                        -- Hitung on-time rate
                        -- Hitung on-time rate
                        ROUND(COALESCE(
                            COUNT(CASE 
                                WHEN so.sa_cetak_pkb <= (so.sa_mulai_penerimaan + INTERVAL '15 minutes')
                                AND so.sa_cetak_pkb IS NOT NULL 
                                AND so.sa_mulai_penerimaan IS NOT NULL
                                THEN 1 
                            END)::numeric * 100.0 / 
                            NULLIF(COUNT(CASE 
                                WHEN so.sa_cetak_pkb IS NOT NULL 
                                AND so.sa_mulai_penerimaan IS NOT NULL
                                THEN 1 
                            END), 0), 
                            0
                        ), 1) as on_time_rate,
                        -- Hitung feedback rate
                        ROUND(COALESCE(
                            COUNT(CASE 
                                WHEN so.customer_rating IS NOT NULL 
                                THEN 1 
                            END)::numeric * 100.0 / 
                            NULLIF(COUNT(*), 0),
                            0
                        ), 1) as feedback_rate
                    FROM 
                        pitcar_service_advisor sa
                    LEFT JOIN 
                        pitcar_service_advisor_sale_order_rel rel ON rel.pitcar_service_advisor_id = sa.id
                    LEFT JOIN 
                        sale_order so ON so.id = rel.sale_order_id 
                        AND so.state in ('sale', 'done')  -- Filter status di JOIN condition
                    GROUP BY 
                        sa.id,
                        date_trunc('month', so.date_order),
                        EXTRACT(MONTH FROM so.date_order),
                        EXTRACT(YEAR FROM so.date_order)
                )
                SELECT 
                    row_number() OVER () as id,
                    ms.*,
                    %s as currency_id
                FROM monthly_stats ms
                ORDER BY ms.service_advisor_id
            )
        """ % (self._table, self.env.company.currency_id.id))

    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """Override to handle custom sorting"""
        if orderby:
            # Menangani multiple orderby
            orderby_terms = orderby.split(',')
            new_orderby_terms = []
            for term in orderby_terms:
                term = term.strip()
                if 'total_revenue' in term:
                    new_orderby_terms.append('total_revenue ' + ('ASC' if 'asc' in term.lower() else 'DESC'))
                elif 'average_rating' in term:
                    new_orderby_terms.append('average_rating ' + ('ASC' if 'asc' in term.lower() else 'DESC'))
                elif 'total_orders' in term:
                    new_orderby_terms.append('total_orders ' + ('ASC' if 'asc' in term.lower() else 'DESC'))
                else:
                    new_orderby_terms.append(term)
            orderby = ', '.join(new_orderby_terms)
        return super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
