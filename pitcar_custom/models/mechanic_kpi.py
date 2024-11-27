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
    
     # Tambahan metrics untuk durasi
    total_estimated_duration = fields.Float('Total Estimated Duration', compute='_compute_metrics', store=True)
    total_actual_duration = fields.Float('Total Actual Duration', compute='_compute_metrics', store=True)
    duration_accuracy = fields.Float('Duration Accuracy (%)', compute='_compute_metrics', store=True)
    average_duration_deviation = fields.Float('Avg Duration Deviation (%)', compute='_compute_metrics', store=True)
    monthly_target = fields.Float('Monthly Target', compute='_compute_monthly_target', store=True)
    revenue_achievement = fields.Float('Achievement (%)', compute='_compute_revenue_achievement', store=True)

    @api.depends('mechanic_id', 'date')  # Hapus dependencies yang tidak ada
    def _compute_metrics(self):
        for record in self:
            if not record.mechanic_id or not record.date:
                continue

            start_date = datetime.combine(record.date, datetime.min.time())
            end_date = datetime.combine(record.date, datetime.max.time())

            # Get paid invoices dengan filter payment_date
            paid_invoices = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', '=', 'paid'),
                ('sale_order_id.car_mechanic_id_new', '=', record.mechanic_id.id),
                ('payment_date', '>=', start_date),
                ('payment_date', '<=', end_date)
            ])

            # Get related orders dari paid invoices
            orders = paid_invoices.mapped('sale_order_id')

            # Log untuk debugging
            _logger.info(f"""
                Computing metrics for {record.mechanic_id.name} on {record.date}:
                Found invoices: {len(paid_invoices)}
                Found orders: {len(orders)}
            """)

            # Update basic metrics
            record.total_revenue = sum(paid_invoices.mapped('amount_total'))
            record.total_orders = len(paid_invoices)
            record.average_order_value = record.total_revenue / record.total_orders if record.total_orders else 0

            # Initialize counters
            completed_on_time = 0
            completion_times = []
            early_starts = 0
            late_starts = 0
            early_completions = 0
            late_completions = 0
            delays = []
            
            # Durasi metrics
            total_estimated = 0
            total_actual = 0
            deviations = []

            for order in orders:
                # Hitung durasi dari order lines
                order_estimated = sum(order.order_line.mapped('service_duration'))
                total_estimated += order_estimated

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

                    # Hitung durasi aktual
                    actual_duration = (actual_end - actual_start).total_seconds() / 3600
                    total_actual += actual_duration
                    completion_times.append(actual_duration)

                    # Hitung deviasi jika ada estimasi
                    if order_estimated:
                        deviation = ((actual_duration - order_estimated) / order_estimated) * 100
                        deviations.append(deviation)

                    # Cek on-time completion
                    if actual_start <= est_start and actual_end <= est_end:
                        completed_on_time += 1

            # Update semua metrics
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
            ratings = orders.filtered(lambda x: x.customer_rating).mapped(lambda x: int(x.customer_rating or '0'))
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
                # Revenue dan target dalam nilai yang sama (rupiah)
                # Tidak perlu konversi ke jutaan karena akan membuat persentase tidak tepat
                achievement = (record.total_revenue / record.monthly_target)
                
                record.revenue_achievement = achievement
            else:
                record.revenue_achievement = 0

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

    last_computed = fields.Datetime(
        'Last Computed',
        readonly=True,
        tracking=True
    )

    def write(self, vals):
        vals['last_computed'] = fields.Datetime.now()
        return super().write(vals)
    
    def force_recompute(self):
        self.invalidate_cache()
        self._compute_metrics()

    @api.model
    def recompute_all_kpi(self):
        kpis = self.search([('date', '=', fields.Date.today())])
        kpis.force_recompute()