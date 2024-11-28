from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class MechanicKPI(models.Model):
    _name = 'mechanic.kpi'
    _description = 'Mechanic KPI'
    _order = 'date desc'

    name = fields.Char('Name', compute='_compute_name', store=True)
    mechanic_id = fields.Many2one(
        'pitcar.mechanic.new',
        string="Mechanic",
        required=True
    )
    date = fields.Date('Date', default=fields.Date.context_today, required=True)
    
    # Basic Metrics
    total_orders = fields.Integer('Total Orders', compute='_compute_metrics', store=True)
    total_revenue = fields.Float('Total Revenue', compute='_compute_metrics', store=True)
    average_order_value = fields.Float('Average Order Value', compute='_compute_metrics', store=True)
    
    # Performance Metrics
    completed_on_time = fields.Integer('Completed On Time', compute='_compute_metrics', store=True)
    on_time_rate = fields.Float('On-Time Rate (%)', compute='_compute_metrics', store=True)
    average_completion_time = fields.Float('Avg Completion Time (Hours)', compute='_compute_metrics', store=True)
    
    # Quality Metrics
    average_rating = fields.Float('Average Rating', compute='_compute_metrics', store=True)
    total_complaints = fields.Integer('Total Complaints', compute='_compute_metrics', store=True)
    complaint_rate = fields.Float('Complaint Rate (%)', compute='_compute_metrics', store=True)

    early_starts = fields.Integer('Early Starts', compute='_compute_metrics', store=True)
    late_starts = fields.Integer('Late Starts', compute='_compute_metrics', store=True)
    early_completions = fields.Integer('Early Completions', compute='_compute_metrics', store=True)
    late_completions = fields.Integer('Late Completions', compute='_compute_metrics', store=True)
    average_delay = fields.Float('Average Delay (Minutes)', compute='_compute_metrics', store=True)
    
    # Duration metrics
    total_estimated_duration = fields.Float('Total Estimated Duration', compute='_compute_metrics', store=True)
    total_actual_duration = fields.Float('Total Actual Duration', compute='_compute_metrics', store=True)
    duration_accuracy = fields.Float('Duration Accuracy (%)', compute='_compute_metrics', store=True)
    average_duration_deviation = fields.Float('Avg Duration Deviation (%)', compute='_compute_metrics', store=True)
    monthly_target = fields.Float('Monthly Target', compute='_compute_monthly_target', store=True)
    revenue_achievement = fields.Float('Achievement (%)', compute='_compute_revenue_achievement', store=True)
    
    # Tambahan field untuk filter
    week_number = fields.Integer('Week Number', compute='_compute_week_number', store=True)
    month = fields.Integer('Month', compute='_compute_period', store=True)
    year = fields.Integer('Year', compute='_compute_period', store=True)

    @api.depends('date')
    def _compute_week_number(self):
        for record in self:
            if record.date:
                record.week_number = record.date.isocalendar()[1]

    @api.depends('date')
    def _compute_period(self):
        for record in self:
            if record.date:
                record.month = record.date.month
                record.year = record.date.year

    @api.depends('mechanic_id', 'date')
    def _compute_metrics(self):
        for record in self:
            if not record.mechanic_id or not record.date:
                continue

            start_date = datetime.combine(record.date, datetime.min.time())
            end_date = datetime.combine(record.date, datetime.max.time())

            # Cari sales orders untuk tanggal tersebut
            sales_orders = self.env['sale.order'].search([
                ('car_mechanic_id_new', '=', record.mechanic_id.id),
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', start_date),
                ('date_order', '<=', end_date)
            ])

            # Cari invoice yang sudah dibayar
            paid_invoices = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', '=', 'paid'),
                ('invoice_date', '=', record.date),
                ('invoice_origin', 'in', sales_orders.mapped('name'))
            ])

            # Get related orders dari paid invoices
            orders = sales_orders.filtered(lambda so: so.invoice_ids & paid_invoices)

            # Update basic metrics
            total_revenue = 0
            for invoice in paid_invoices:
                # Hitung revenue berdasarkan invoice line yang terkait dengan mekanik
                for line in invoice.invoice_line_ids:
                    if line.sale_line_ids and line.sale_line_ids[0].order_id in orders:
                        total_revenue += line.price_total

            record.total_revenue = total_revenue
            record.total_orders = len(orders)
            record.average_order_value = record.total_revenue / record.total_orders if record.total_orders else 0

            # Initialize counters
            completed_on_time = 0
            completion_times = []
            early_starts = 0
            late_starts = 0
            early_completions = 0
            late_completions = 0
            delays = []
            
            total_estimated = 0
            total_actual = 0
            deviations = []

            for order in orders:
                if not all([order.controller_estimasi_mulai, order.controller_estimasi_selesai,
                           order.controller_mulai_servis, order.controller_selesai]):
                    continue

                # Konversi ke datetime
                est_start = fields.Datetime.from_string(order.controller_estimasi_mulai)
                est_end = fields.Datetime.from_string(order.controller_estimasi_selesai)
                actual_start = fields.Datetime.from_string(order.controller_mulai_servis)
                actual_end = fields.Datetime.from_string(order.controller_selesai)

                # Hitung estimasi durasi dari order lines
                order_estimated = sum(line.service_duration or 0.0 for line in order.order_line)
                total_estimated += order_estimated

                # Check start time
                if actual_start < est_start:
                    early_starts += 1
                elif actual_start > est_start:
                    late_starts += 1
                    
                # Check completion time
                if actual_end < est_end:
                    early_completions += 1
                    completed_on_time += 1
                elif actual_end > est_end:
                    late_completions += 1
                    delay = (actual_end - est_end).total_seconds() / 60
                    delays.append(delay)

                # Hitung durasi aktual
                actual_duration = (actual_end - actual_start).total_seconds() / 3600
                total_actual += actual_duration
                completion_times.append(actual_duration)

                # Hitung deviasi
                if order_estimated:
                    deviation = ((actual_duration - order_estimated) / order_estimated) * 100
                    deviations.append(deviation)

            # Update metrics
            record.early_starts = early_starts
            record.late_starts = late_starts
            record.early_completions = early_completions
            record.late_completions = late_completions
            record.average_delay = sum(delays) / len(delays) if delays else 0
            record.completed_on_time = completed_on_time
            record.on_time_rate = (completed_on_time / record.total_orders) * 100 if record.total_orders else 0
            record.average_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0

            # Duration metrics
            record.total_estimated_duration = total_estimated
            record.total_actual_duration = total_actual
            if total_estimated:
                record.duration_accuracy = (1 - abs(total_actual - total_estimated) / total_estimated) * 100
            record.average_duration_deviation = sum(deviations) / len(deviations) if deviations else 0

            # Quality Metrics
            ratings = [int(order.customer_rating or '0') for order in orders if order.customer_rating]
            record.average_rating = sum(ratings) / len(ratings) if ratings else 0
            
            complaints = orders.filtered(lambda x: x.customer_satisfaction in ['very_dissatisfied', 'dissatisfied'])
            record.total_complaints = len(complaints)
            record.complaint_rate = (record.total_complaints / record.total_orders) * 100 if record.total_orders else 0

    @api.depends('mechanic_id')
    def _compute_monthly_target(self):
        for record in self:
            if record.mechanic_id.position_code == 'leader':
                team_members = self.env['pitcar.mechanic.new'].search([
                    ('leader_id', '=', record.mechanic_id.id)
                ])
                record.monthly_target = len(team_members) * 64000000
            else:
                record.monthly_target = 64000000

    @api.depends('total_revenue', 'monthly_target')
    def _compute_revenue_achievement(self):
        for record in self:
            if record.monthly_target:
                record.revenue_achievement = (record.total_revenue / record.monthly_target) * 100
            else:
                record.revenue_achievement = 0

    @api.model
    def _update_today_kpi(self):
        today = fields.Date.today()
        mechanics = self.env['pitcar.mechanic.new'].search([])
        
        for mechanic in mechanics:
            kpi = self.search([
                ('mechanic_id', '=', mechanic.id),
                ('date', '=', today)
            ], limit=1)
            
            if not kpi:
                kpi = self.create({
                    'mechanic_id': mechanic.id,
                    'date': today,
                })
            else:
                kpi.write({'date': today})

    def get_week_data(self, date):
        start_of_week = date - timedelta(days=date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return self.search([
            ('date', '>=', start_of_week),
            ('date', '<=', end_of_week)
        ])

    def get_month_data(self, date):
        start_of_month = date.replace(day=1)
        if date.month == 12:
            end_of_month = date.replace(year=date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = date.replace(month=date.month + 1, day=1) - timedelta(days=1)
        return self.search([
            ('date', '>=', start_of_month),
            ('date', '<=', end_of_month)
        ])