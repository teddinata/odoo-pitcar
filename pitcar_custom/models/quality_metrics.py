from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class QualityMetrics(models.Model):
    _name = 'quality.metrics'
    _description = 'Quality Metrics'
    _order = 'date desc'

    name = fields.Char('Name', compute='_compute_name', store=True)
    date = fields.Date('Date', default=fields.Date.context_today, required=True)
    
    # Service Time Metrics
    total_orders = fields.Integer('Total Orders', compute='_compute_metrics', store=True)
    average_service_duration = fields.Float('Average SA Service Time (Minutes)', compute='_compute_metrics', store=True,
        help='Average time from SA start service until PKB printed')
    orders_completed_on_time = fields.Integer('On-Time Services', compute='_compute_metrics', store=True,
        help='Services completed within 15 minutes target')
    on_time_completion_rate = fields.Float('On-Time Service Rate (%)', compute='_compute_metrics', store=True,
        help='Percentage of services completed within 15 minutes (SA start to PKB)')
    
    # Customer Return Rate
    return_rate_3_months = fields.Float('3-Month Return Rate (%)', compute='_compute_metrics', store=True)
    return_rate_6_months = fields.Float('6-Month Return Rate (%)', compute='_compute_metrics', store=True)

    # Customer Satisfaction
    average_rating = fields.Float('Average Rating', compute='_compute_metrics', store=True)
    total_complaints = fields.Integer('Total Complaints', compute='_compute_metrics', store=True)
    complaint_resolution_rate = fields.Float('Complaint Resolution Rate (%)', compute='_compute_metrics', store=True)

    # Service Types
    regular_services = fields.Integer('Regular Services', compute='_compute_metrics', store=True)
    priority_services = fields.Integer('Priority Services', compute='_compute_metrics', store=True)
    priority_rate = fields.Float('Priority Service Rate (%)', compute='_compute_metrics', store=True)

    # Revenue Metrics
    total_revenue = fields.Float('Total Revenue', compute='_compute_metrics', store=True)
    average_ticket_value = fields.Float('Average Ticket Value', compute='_compute_metrics', store=True)

    # Customer Engagement
    feedback_rate = fields.Float('Feedback Rate (%)', compute='_compute_metrics', store=True)
    google_review_rate = fields.Float('Google Review Rate (%)', compute='_compute_metrics', store=True)
    instagram_follow_rate = fields.Float('Instagram Follow Rate (%)', compute='_compute_metrics', store=True)

    @api.depends('date')
    def _compute_name(self):
        for record in self:
            record.name = f"Quality Metrics - {record.date}"

    @api.depends('date')
    def _compute_metrics(self):
        for record in self:
            try:
                # Get orders for the day
                start_date = datetime.combine(record.date, datetime.min.time())
                end_date = datetime.combine(record.date, datetime.max.time())
                three_months_ago = record.date - timedelta(days=90)
                six_months_ago = record.date - timedelta(days=180)

                # Today's orders
                orders = self.env['sale.order'].search([
                    ('date_completed', '>=', start_date),
                    ('date_completed', '<=', end_date),
                    ('state', '=', 'sale')
                ])

                # Basic metrics
                record.total_orders = len(orders)
                record.total_revenue = sum(orders.mapped('amount_total'))
                record.average_ticket_value = record.total_revenue / record.total_orders if record.total_orders else 0

                # Service duration and on-time metrics
                durations = []
                completed_on_time = 0
                for order in orders:
                    if order.sa_mulai_penerimaan and order.sa_cetak_pkb:
                        # Hitung durasi dalam menit
                        duration = (order.sa_cetak_pkb - order.sa_mulai_penerimaan).total_seconds() / 60
                        durations.append(duration)
                        if duration <= 15:  # Target 15 menit
                            completed_on_time += 1

                record.average_service_duration = sum(durations) / len(durations) if durations else 0
                record.orders_completed_on_time = completed_on_time
                record.on_time_completion_rate = (completed_on_time / record.total_orders) * 100 if record.total_orders else 0

                # Customer satisfaction
                ratings = orders.filtered(lambda x: x.customer_rating).mapped(lambda x: int(x.customer_rating or '0'))
                record.average_rating = sum(ratings) / len(ratings) if ratings else 0

                complaints = orders.filtered(lambda x: x.customer_satisfaction in ['very_dissatisfied', 'dissatisfied'])
                record.total_complaints = len(complaints)
                resolved_complaints = complaints.filtered(lambda x: x.complaint_status == 'solved')
                # Perbaikan perhitungan persentase
                record.complaint_resolution_rate = (len(resolved_complaints) / len(complaints)) * 100 if complaints else 0

                # Service types
                record.regular_services = len(orders.filtered(lambda x: not x.is_booking))
                record.priority_services = len(orders.filtered(lambda x: x.is_booking))
                # Perbaikan perhitungan persentase
                record.priority_rate = (record.priority_services / len(orders)) * 100 if orders else 0

                # Customer engagement
                feedback_received = len(orders.filtered(lambda x: x.is_willing_to_feedback == 'yes'))
                # Perbaikan perhitungan persentase
                record.feedback_rate = (feedback_received / len(orders)) * 100 if orders else 0
                
                google_reviews = len(orders.filtered(lambda x: x.review_google == 'yes'))
                # Perbaikan perhitungan persentase
                record.google_review_rate = (google_reviews / len(orders)) * 100 if orders else 0
                
                instagram_follows = len(orders.filtered(lambda x: x.follow_instagram == 'yes'))
                # Perbaikan perhitungan persentase
                record.instagram_follow_rate = (instagram_follows / len(orders)) * 100 if orders else 0

                # Return rate calculations
                three_month_customers = set()
                six_month_customers = set()
                return_customers_3_months = set()
                return_customers_6_months = set()

                historical_orders = self.env['sale.order'].search([
                    ('date_completed', '>=', six_months_ago),
                    ('date_completed', '<=', record.date),
                    ('state', '=', 'sale')
                ])

                for order in historical_orders:
                    customer_id = order.partner_id.id
                    order_date = order.date_completed.date()

                    if order_date >= three_months_ago:
                        three_month_customers.add(customer_id)
                        previous_orders = self.env['sale.order'].search_count([
                            ('partner_id', '=', customer_id),
                            ('date_completed', '<', order.date_completed),
                            ('date_completed', '>=', three_months_ago),
                            ('state', '=', 'sale')
                        ])
                        if previous_orders > 0:
                            return_customers_3_months.add(customer_id)

                    six_month_customers.add(customer_id)
                    previous_orders = self.env['sale.order'].search_count([
                        ('partner_id', '=', customer_id),
                        ('date_completed', '<', order.date_completed),
                        ('date_completed', '>=', six_months_ago),
                        ('state', '=', 'sale')
                    ])
                    if previous_orders > 0:
                        return_customers_6_months.add(customer_id)

                total_customers_3_months = len(three_month_customers)
                total_customers_6_months = len(six_month_customers)

                # Perbaikan perhitungan persentase
                record.return_rate_3_months = (len(return_customers_3_months) / total_customers_3_months) * 100 if total_customers_3_months else 0
                record.return_rate_6_months = (len(return_customers_6_months) / total_customers_6_months) * 100 if total_customers_6_months else 0

            except Exception as e:
                _logger.error(f"Error computing quality metrics: {str(e)}")

    @api.model
    def _update_today_metrics(self):
        """Cron job to update today's metrics"""
        try:
            today = fields.Date.today()
            metrics = self.search([('date', '=', today)], limit=1)
            if not metrics:
                metrics = self.create({'date': today})
            else:
                # Trigger recompute
                metrics.write({'date': today})
            _logger.info("Quality metrics updated successfully")
        except Exception as e:
            _logger.error(f"Error updating quality metrics: {str(e)}")

    def _register_hooks(self):
        super()._register_hooks()
        # Add triggers for auto-update
        self.env['sale.order']._inherit_auto_triggers(self._name)