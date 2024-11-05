from odoo import models, fields, api
from datetime import datetime, timedelta

class ServiceAdvisorKPI(models.Model):
    _name = 'service.advisor.kpi'
    _description = 'Service Advisor KPI'
    _order = 'date desc, service_advisor_id'
    _inherit = ['mail.thread']

    name = fields.Char('Name', compute='_compute_name', store=True)
    service_advisor_id = fields.Many2one(
        'pitcar.service.advisor',
        string="Service Advisor",
        required=True
    )
    date = fields.Date('Date', default=fields.Date.context_today, required=True)
    
    # Basic Metrics
    total_orders = fields.Integer('Total Orders', compute='_compute_metrics', store=True)
    total_revenue = fields.Float('Total Revenue', compute='_compute_metrics', store=True)
    average_order_value = fields.Float('Average Order Value', compute='_compute_metrics', store=True)
    
    # Customer Satisfaction Metrics
    average_rating = fields.Float('Average Rating', compute='_compute_metrics', store=True)
    total_complaints = fields.Integer('Total Complaints', compute='_compute_metrics', store=True)
    complaint_rate = fields.Float('Complaint Rate (%)', compute='_compute_metrics', store=True)
    
    # Service Efficiency Metrics
    average_service_time = fields.Float('Avg Service Time (Minutes)', compute='_compute_metrics', store=True,
        help='Average time between SA start service until PKB printed')
    on_time_completion = fields.Integer('On-Time Services', compute='_compute_metrics', store=True,
        help='Number of services completed within 15 minutes (from SA start to PKB)')
    on_time_rate = fields.Float('On-Time Rate (%)', compute='_compute_metrics', store=True,
        help='Percentage of services completed within 15 minutes target')
    
    # Customer Engagement
    feedback_received = fields.Integer('Feedback Received', compute='_compute_metrics', store=True)
    feedback_rate = fields.Float('Feedback Rate (%)', compute='_compute_metrics', store=True)
    google_reviews = fields.Integer('Google Reviews', compute='_compute_metrics', store=True)
    instagram_follows = fields.Integer('Instagram Follows', compute='_compute_metrics', store=True)

    color_class = fields.Selection([
        ('bg-primary', 'Blue'),
        ('bg-success', 'Green'),
        ('bg-info', 'Light Blue'),
        ('bg-warning', 'Yellow')
    ], string='Color', default='bg-primary')

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        # Override untuk mendukung custom ordering dari filter
        if self.env.context.get('order'):
            orderby = self.env.context['order']
        return super(ServiceAdvisorKPI, self).read_group(domain, fields, groupby, offset, limit, orderby, lazy)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        # Override untuk mendukung custom ordering dari filter
        if self.env.context.get('order'):
            order = self.env.context['order']
        return super(ServiceAdvisorKPI, self).search(args, offset=offset, limit=limit, order=order, count=count)

    @api.depends('service_advisor_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.service_advisor_id and record.date:
                record.name = f"{record.service_advisor_id.name} - {record.date}"
            else:
                record.name = "New KPI"

    @api.depends('service_advisor_id', 'date')
    def _compute_metrics(self):
        for record in self:
            if not record.service_advisor_id or not record.date:
                continue

            start_date = datetime.combine(record.date, datetime.min.time())
            end_date = datetime.combine(record.date, datetime.max.time())

            orders = self.env['sale.order'].search([
                ('service_advisor_id', 'in', [record.service_advisor_id.id]),
                ('date_completed', '>=', start_date),
                ('date_completed', '<=', end_date),
                ('state', '=', 'sale')
            ])

            record.total_orders = len(orders)
            record.total_revenue = sum(orders.mapped('amount_total'))
            record.average_order_value = record.total_revenue / record.total_orders if record.total_orders else 0
            
            # Service Efficiency - dengan pembagian yang benar
            completed_orders = orders.filtered(lambda x: x.sa_mulai_penerimaan and x.sa_cetak_pkb)
            service_times = []
            on_time_count = 0
            
            for order in completed_orders:
                if order.sa_mulai_penerimaan and order.sa_cetak_pkb:
                    duration = (order.sa_cetak_pkb - order.sa_mulai_penerimaan).total_seconds() / 60
                    service_times.append(duration)
                    if duration <= 15:  # Target 15 menit
                        on_time_count += 1
                        
            record.average_service_time = sum(service_times) / len(service_times) if service_times else 0
            record.on_time_completion = on_time_count
            # Perbaikan perhitungan persentase
            record.on_time_rate = (on_time_count / len(completed_orders)) if len(completed_orders) else 0
            
            # Customer Satisfaction
            ratings = orders.filtered(lambda x: x.customer_rating).mapped(lambda x: int(x.customer_rating or '0'))
            record.average_rating = sum(ratings) / len(ratings) if ratings else 0.0
            
            complaints = orders.filtered(lambda x: x.customer_satisfaction in ['very_dissatisfied', 'dissatisfied'])
            record.total_complaints = len(complaints)
            # Perbaikan perhitungan persentase
            record.complaint_rate = (record.total_complaints / record.total_orders) if record.total_orders else 0
            
            # Customer Engagement
            feedback_orders = orders.filtered(lambda x: x.is_willing_to_feedback == 'yes')
            record.feedback_received = len(feedback_orders)
            # Perbaikan perhitungan persentase
            record.feedback_rate = (record.feedback_received / record.total_orders) if record.total_orders else 0
            
            record.google_reviews = len(orders.filtered(lambda x: x.review_google == 'yes'))
            record.instagram_follows = len(orders.filtered(lambda x: x.follow_instagram == 'yes'))

    @api.model
    def _update_today_kpi(self):
        """Cron job to update today's KPI"""
        today = fields.Date.today()
        advisors = self.env['pitcar.service.advisor'].search([])
        
        for advisor in advisors:
            kpi = self.search([
                ('service_advisor_id', '=', advisor.id),
                ('date', '=', today)
            ], limit=1)
            
            if not kpi:
                kpi = self.create({
                    'service_advisor_id': advisor.id,
                    'date': today,
                })
            else:
                # Trigger recompute of metrics
                kpi.write({'date': today})

    def _register_hooks(self):
        super()._register_hooks()
        # Add triggers for auto-update
        self.env['sale.order']._inherit_auto_triggers(self._name)
        
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """Override to customize aggregation"""
        res = super(ServiceAdvisorKPI, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        
        if 'service_advisor_id' in groupby:
            for line in res:
                if '__domain' in line:
                    records = self.search(line['__domain'])
                    line['total_revenue'] = sum(records.mapped('total_revenue'))
                    line['total_orders'] = sum(records.mapped('total_orders'))
                    line['average_rating'] = sum(records.mapped('average_rating')) / len(records) if records else 0
                    line['on_time_rate'] = sum(records.mapped('on_time_rate')) / len(records) if records else 0
                    line['feedback_rate'] = sum(records.mapped('feedback_rate')) / len(records) if records else 0
        
        return res

    @api.depends('service_advisor_id')
    def _compute_name(self):
        for record in self:
            if record.service_advisor_id:
                record.name = record.service_advisor_id.name
            else:
                record.name = 'New'

    _group_by_full = {
        'service_advisor_id': lambda self, *args, **kwargs: self.env['pitcar.service.advisor'].search([]),
    }