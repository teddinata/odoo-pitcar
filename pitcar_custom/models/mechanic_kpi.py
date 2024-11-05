from odoo import models, fields, api
from datetime import datetime, timedelta

class MechanicKPI(models.Model):
    _name = 'mechanic.kpi'
    _description = 'Mechanic KPI'
    _order = 'date desc'

    name = fields.Char('Name', compute='_compute_name', store=True)
    mechanic_id = fields.Many2one(
        'pitcar.mechanic.new',  # Menggunakan model mechanic yang baru
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

    early_starts = fields.Integer('Early Starts', compute='_compute_metrics', store=True,
        help='Number of services started earlier than estimated')
    late_starts = fields.Integer('Late Starts', compute='_compute_metrics', store=True,
        help='Number of services started later than estimated')
    early_completions = fields.Integer('Early Completions', compute='_compute_metrics', store=True,
        help='Number of services completed earlier than estimated')
    late_completions = fields.Integer('Late Completions', compute='_compute_metrics', store=True,
        help='Number of services completed later than estimated')
    average_delay = fields.Float('Average Delay (Minutes)', compute='_compute_metrics', store=True,
        help='Average delay in service completion when late')

    @api.depends('mechanic_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.mechanic_id and record.date:
                record.name = f"{record.mechanic_id.name} - {record.date}"
            else:
                record.name = "New KPI"

    @api.depends('mechanic_id', 'date')
    def _compute_metrics(self):
        for record in self:
            if not record.mechanic_id or not record.date:
                continue

            start_date = datetime.combine(record.date, datetime.min.time())
            end_date = datetime.combine(record.date, datetime.max.time())

            # Get orders for mechanic
            orders = self.env['sale.order'].search([
                ('car_mechanic_id_new', 'in', [record.mechanic_id.id]),
                ('date_completed', '>=', start_date),
                ('date_completed', '<=', end_date),
                ('state', '=', 'sale')
            ])

            # Basic metrics
            record.total_orders = len(orders)
            record.total_revenue = sum(orders.mapped('amount_total'))
            record.average_order_value = record.total_revenue / record.total_orders if record.total_orders else 0

            # Performance Metrics - Perbaikan perhitungan waktu
            completed_on_time = 0
            completion_times = []
            early_starts = 0
            late_starts = 0
            early_completions = 0
            late_completions = 0
            delays = []

            
            for order in orders:
                # Cek estimasi waktu dan aktual waktu
                if (order.controller_estimasi_mulai and order.controller_estimasi_selesai and 
                    order.controller_mulai_servis and order.controller_selesai):
                    
                    # Konversi ke datetime
                    est_start = fields.Datetime.from_string(order.controller_estimasi_mulai)
                    est_end = fields.Datetime.from_string(order.controller_estimasi_selesai)
                    actual_start = fields.Datetime.from_string(order.controller_mulai_servis)
                    actual_end = fields.Datetime.from_string(order.controller_selesai)

                    # Check start time
                    if actual_start < est_start:
                        early_starts += 1
                    elif actual_start > est_start:
                        late_starts += 1
                        
                    # Check completion time
                    if actual_end < est_end:
                        early_completions += 1
                    elif actual_end > est_end:
                        late_completions += 1
                        delay = (actual_end - est_end).total_seconds() / 60
                        delays.append(delay)

                    # Hitung durasi estimasi dan aktual dalam menit
                    est_duration = (est_end - est_start).total_seconds() / 60
                    actual_duration = (actual_end - actual_start).total_seconds() / 60
                    
                    # Cek apakah selesai tepat waktu
                    # 1. Mulai tidak lebih lambat dari estimasi mulai
                    # 2. Selesai tidak lebih lambat dari estimasi selesai
                    if actual_start <= est_start and actual_end <= est_end:
                        completed_on_time += 1
                    
                    # Simpan waktu pengerjaan aktual
                    completion_times.append(actual_duration)

            record.early_starts = early_starts
            record.late_starts = late_starts
            record.early_completions = early_completions
            record.late_completions = late_completions
            record.average_delay = sum(delays) / len(delays) if delays else 0

            # Update metrics
            record.completed_on_time = completed_on_time
            record.on_time_rate = (completed_on_time / record.total_orders) if record.total_orders else 0
            record.average_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0

            # Quality Metrics tetap sama
            ratings = orders.filtered(lambda x: x.customer_rating).mapped(lambda x: int(x.customer_rating or '0'))
            record.average_rating = sum(ratings) / len(ratings) if ratings else 0
            
            complaints = orders.filtered(lambda x: x.customer_satisfaction in ['very_dissatisfied', 'dissatisfied'])
            record.total_complaints = len(complaints)
            record.complaint_rate = (record.total_complaints / record.total_orders) if record.total_orders else 0

    @api.model
    def _update_today_kpi(self):
        """Cron job to update today's KPI"""
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
                # Trigger recompute
                kpi.write({'date': today})