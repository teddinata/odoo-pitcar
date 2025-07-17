from odoo import models, fields, api, _, exceptions, tools
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo.tools import split_every
import pytz
from datetime import timedelta, date, datetime, time
import logging
import json

_logger = logging.getLogger(__name__)

READONLY_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'sale', 'done', 'cancel'}
}

# BENGKEL_BUKA = time(8, 0)  # 08:00
# BENGKEL_TUTUP = time(22, 0)  # 22:00
# ISTIRAHAT_1_MULAI = time(12, 0)  # 12:00
# ISTIRAHAT_1_SELESAI = time(13, 0)  # 13:00
# ISTIRAHAT_2_MULAI = time(18, 0)  # 18:00
# ISTIRAHAT_2_SELESAI = time(19, 0)  # 19:00
# JAM_KERJA_PER_HARI = timedelta(hours=14)  # 22:00 - 08:00
# ISTIRAHAT_PER_HARI = timedelta(hours=2)  # (13:00 - 12:00) + (19:00 - 18:00)

# def hitung_waktu_kerja_efektif(waktu_mulai, waktu_selesai):
#     total_waktu = waktu_selesai - waktu_mulai
#     hari_kerja = (waktu_selesai.date() - waktu_mulai.date()).days + 1
#     waktu_kerja = timedelta()
    
#     for hari in range(hari_kerja):
#         hari_ini = waktu_mulai.date() + timedelta(days=hari)
#         mulai_hari_ini = max(datetime.combine(hari_ini, BENGKEL_BUKA), waktu_mulai)
#         selesai_hari_ini = min(datetime.combine(hari_ini, BENGKEL_TUTUP), waktu_selesai)
        
#         if mulai_hari_ini < selesai_hari_ini:
#             waktu_kerja_hari_ini = selesai_hari_ini - mulai_hari_ini
            
#             # Kurangi waktu istirahat
#             if mulai_hari_ini.time() <= ISTIRAHAT_1_MULAI and selesai_hari_ini.time() >= ISTIRAHAT_1_SELESAI:
#                 waktu_kerja_hari_ini -= timedelta(hours=1)
#             if mulai_hari_ini.time() <= ISTIRAHAT_2_MULAI and selesai_hari_ini.time() >= ISTIRAHAT_2_SELESAI:
#                 waktu_kerja_hari_ini -= timedelta(hours=1)
            
#             waktu_kerja += waktu_kerja_hari_ini
    
#     return waktu_kerja

def format_duration(duration_in_hours):
    """
    Convert decimal hours to a human-readable format
    Example: 
    1.5 -> "1 jam 30 menit"
    0.75 -> "45 menit"
    2.25 -> "2 jam 15 menit"
    """
    if not duration_in_hours:
        return "0 menit"
        
    hours = int(duration_in_hours)
    minutes = int((duration_in_hours - hours) * 60)
    
    if hours == 0:
        return f"{minutes} menit"
    elif minutes == 0:
        return f"{hours} jam"
    else:
        return f"{hours} jam {minutes} menit"
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    campaign = fields.Selection(
        [
            ('facebook', 'Facebook'),
            ('instagram', 'Instagram'),
            ('youtube', 'YouTube'),
            ('tiktok', 'TikTok'),
        ],
        string="Campaign",
        help="Select the source of information on how the customer found us",
        tracking=True,
    )
    
    partner_id = fields.Many2one('res.partner', string='Customer', required=False)
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', check_company=True,  # Tariff
        required=False, readonly=False, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="If you change the pricelist, only newly added lines will be affected.")
    partner_invoice_id = fields.Many2one(
        'res.partner', string='Invoice Address',
        readonly=True, required=False,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'sale': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    partner_shipping_id = fields.Many2one(
        'res.partner', string='Delivery Address',
        readonly=True, required=False,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'sale': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    reception_state = fields.Selection([
        ('draft', 'Draft'),
        ('reception_started', 'Reception Started'),
        ('completed', 'Completed')
    ], string='Reception State', default='draft')
    # Field baru untuk Service Advisor yang merujuk ke model 'pitcar.service.advisor'
    service_advisor_id = fields.Many2many(
        'pitcar.service.advisor',
        string="Service Advisors",
        help="Select multiple Service Advisors for this sales order"
    )

    partner_car_id = fields.Many2one(
        'res.partner.car',
        string="Serviced Car",
        tracking=True,
        index=True,
        readonly=False,
        states=READONLY_FIELD_STATES,
    )
    partner_car_brand = fields.Many2one(
        string="Car Brand",
        related="partner_car_id.brand",
        store=True,
    )
    partner_car_brand_type = fields.Many2one(
        string="Car Brand Type",
        related="partner_car_id.brand_type",
        store=True,
    )
    partner_car_year = fields.Char(
        string="Car Year",
        related="partner_car_id.year",
        store=True,
        help="Tahun pembuatan mobil customer"
    )
    partner_car_odometer = fields.Float(
        string="Odometer",
        tracking=True,
    )
    partner_car_transmission = fields.Many2one(
        'res.partner.car.transmission',
        string="Transmission",
        related="partner_car_id.transmission",
        store=True,
    )
    partner_car_engine_type = fields.Selection(
        string="Engine Type",
        related="partner_car_id.engine_type",
        store=True,
    )
    partner_car_engine_number = fields.Char(
        string="Engine Number",
        related="partner_car_id.engine_number",
        store=True,
    )
    partner_car_frame_number = fields.Char(
        string="Frame Number",
        related="partner_car_id.frame_number",
        store=True,
    )
    partner_car_color = fields.Char(
        string="Color",
        related="partner_car_id.color",
        store=True,
    )
    car_mechanic_id = fields.Many2one(
        'pitcar.mechanic',
        string="Mechanic (Old Input)",
        tracking=True,
        index=True,
        readonly=True,
    )
    car_mechanic_id_new = fields.Many2many(
        'pitcar.mechanic.new',
        string="Mechanic",
        tracking=True,
        index=True,
    )
    generated_mechanic_team = fields.Char(
        string="Mechanic",
        compute="_compute_generated_mechanic_team",
        store=True,
    )
    date_completed = fields.Datetime(
        string="Completed Date",
        required=False, readonly=True, copy=False, tracking=True,
        help="date on which invoice is generated",
    )
    car_arrival_time = fields.Datetime(
        string="Jam Kedatangan Mobil",
        help="Record the time when the car arrived",
        required=False,
        tracking=True,
    )
    total_service_duration = fields.Float(
        string='Total Durasi (Jam)',
        compute='_compute_total_duration',
        store=True
    )
    formatted_total_duration = fields.Char(
        string='Total Durasi',
        compute='_compute_formatted_duration',
        store=False
    )
    booking_id = fields.Many2one('pitcar.service.booking', string='Booking Reference', readonly=True)
    is_booking = fields.Boolean('Is From Booking', default=False, readonly=True)

    # Fields untuk recommendation
    recommendation_ids = fields.One2many(
        'sale.order.recommendation',
        'order_id',
        string='Service Recommendations'
    )

    total_recommendation_amount = fields.Monetary(
        string='Total Recommended Services',
        compute='_compute_total_recommendation_amount',
        currency_field='currency_id',
        store=True
    )

    @api.depends('recommendation_ids.total_amount')
    def _compute_total_recommendation_amount(self):
        for order in self:
            order.total_recommendation_amount = sum(order.recommendation_ids.mapped('total_amount'))

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        """Handle perubahan template"""
        if not self.sale_order_template_id:
            self.order_line = [(5, 0, 0)]
            return
        
        lines_data = []
        
        # Get template lines
        for line in self.sale_order_template_id.sale_order_template_line_ids:
            if not line.product_id:
                continue

            line_values = {
                'name': line.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom_id.id,
                'display_type': line.display_type,
                'discount': line.discount,  # Tambahkan diskon disini
            }

            # Add service duration if it's a service product
            if line.product_id.type == 'service':
                line_values['service_duration'] = line.service_duration

            # Get price
            if line.product_id:
                line_values.update({
                    'price_unit': line.price_unit or line.product_id.list_price,
                })

            lines_data.append((0, 0, line_values))
        
        # Clear existing lines and set new ones
        self.order_line = [(5, 0, 0)]
        self.order_line = lines_data

        if self.sale_order_template_id.note:
            self.note = self.sale_order_template_id.note

    def _compute_template_line_values(self, line):
        """Inherit untuk menambahkan service duration dari template"""
        vals = super()._compute_template_line_values(line)
        if line.product_id.type == 'service':
            vals['service_duration'] = line.service_duration
        return vals

    # Computations untuk durasi
    # @api.depends('order_line.service_duration')
    # def _compute_total_duration(self):
    #     """Hitung total durasi dari semua service lines"""
    #     for order in self:
    #         total = sum(line.service_duration for line in order.order_line 
    #                    if not line.display_type and line.sequence < 1000)  # Exclude recommendation lines
    #         order.total_service_duration = total

    # @api.depends('order_line.service_duration')
    # def _compute_total_duration(self):
    #     for order in self:
    #         order.total_service_duration = sum(order.order_line.mapped('service_duration'))
    @api.depends('order_line.service_duration')
    def _compute_total_duration(self):
        """Hitung total durasi dari semua service lines, kecuali display_type dan non-service"""
        for order in self:
            order.total_service_duration = sum(
                line.service_duration for line in order.order_line 
                if not line.display_type and line.product_id.type == 'service'
            )

    @api.depends('total_service_duration')
    def _compute_formatted_duration(self):
        for order in self:
            order.formatted_total_duration = format_duration(order.total_service_duration)

     # Tambahkan field baru untuk tracking performance
    actual_vs_estimated_duration = fields.Float(
        string='Deviasi Durasi (%)',
        compute='_compute_duration_performance',
        store=True,
        help='Persentase deviasi antara estimasi dan aktual durasi'
    )
    
    is_on_time = fields.Boolean(
        string='On Time',
        compute='_compute_duration_performance',
        store=True
    )

    total_estimated_duration = fields.Float(
        string='Total Estimated Duration',
        compute='_compute_total_estimated_duration',
        store=True
    )

    duration_deviation = fields.Float(
        string='Duration Deviation (%)',
        compute='_compute_duration_deviation',
        store=True
    )

    # @api.onchange('order_line')
    # def _onchange_order_line(self):
    #     if self.order_line:
    #         total_duration = sum(line.service_duration for line in self.order_line)
    #         if total_duration:
    #             start_time = fields.Datetime.now()
    #             self.controller_estimasi_mulai = start_time 
    #             self.controller_estimasi_selesai = start_time + timedelta(hours=total_duration)

    @api.onchange('order_line')
    def _onchange_order_line(self):
        """
        Menangani perubahan order_line dengan optimasi performa.
        Hanya menghitung ulang jika diperlukan.
        """
        # Skip computation jika tidak ada order_line atau sedang dalam operasi batch
        if not self.order_line or self.env.context.get('skip_order_line_calculation'):
            return
        
        # Hitung total durasi dari service_duration di order_line
        total_duration = sum(line.service_duration for line in self.order_line 
                            if not line.display_type and line.product_id.type == 'service')
        
        # Jika tidak ada durasi, tidak perlu melanjutkan
        if total_duration <= 0:
            return
        
        # Logic untuk update waktu estimasi
        if not self.controller_estimasi_mulai:
            # Jika belum ada estimasi, set waktu sekarang
            start_time = fields.Datetime.now()
            self.controller_estimasi_mulai = start_time
            self.controller_estimasi_selesai = self._calculate_end_time_optimized(start_time, total_duration)
        else:
            # Jika sudah ada estimasi, hitung perubahan durasi
            old_duration = 0
            if self.controller_estimasi_selesai and self.controller_estimasi_mulai:
                # Gunakan metode cepat untuk menghitung durasi
                old_duration = self._calculate_approx_duration(
                    self.controller_estimasi_mulai, 
                    self.controller_estimasi_selesai
                )
            
            # Hanya update jika durasi berubah signifikan (lebih dari 0.1 jam atau 6 menit)
            if abs(total_duration - old_duration) > 0.1:
                # Gunakan waktu mulai yang ada untuk hitung waktu selesai baru
                self.controller_estimasi_selesai = self._calculate_end_time_optimized(
                    self.controller_estimasi_mulai, 
                    total_duration
                )

    def _calculate_approx_duration(self, start_time, end_time):
        """
        Metode cepat untuk menghitung perkiraan durasi antara dua waktu
        Mengabaikan perhitungan detail untuk performa lebih baik dalam onchange
        """
        if not start_time or not end_time or end_time <= start_time:
            return 0
        
        # Kalkulasi sederhana dalam jam
        delta = (end_time - start_time).total_seconds() / 3600
        
        # Perkiraan pengurangan untuk istirahat (1 jam untuk setiap hari kerja)
        days = (end_time.date() - start_time.date()).days + 1
        lunch_reduction = min(days, delta / 8)  # Asumsi max 1 jam istirahat per 8 jam kerja
        
        return max(0, delta - lunch_reduction)

    def _calculate_end_time_optimized(self, start_time, duration):
        """
        Versi teroptimasi dari _calculate_end_time dengan lazy evaluation
        """
        if not start_time or duration <= 0:
            return start_time
        
        # Konversi waktu mulai ke datetime lokal
        local_tz = pytz.timezone('Asia/Jakarta')
        start_local = pytz.UTC.localize(fields.Datetime.from_string(start_time) 
                    if isinstance(start_time, str) else start_time).astimezone(local_tz)
        
        # Jika durasi pendek (< 3 jam), gunakan perhitungan sederhana
        if duration < 3:
            # Cek apakah durasi melewati jam istirahat
            hour_now = start_local.hour + start_local.minute/60.0
            crosses_lunch = (hour_now < 12 and hour_now + duration >= 12)
            
            # Tambahkan durasi
            end_seconds = duration * 3600
            if crosses_lunch:
                end_seconds += 3600  # Tambah 1 jam untuk istirahat
                
            end_local = start_local + timedelta(seconds=end_seconds)
            
            # Konversi kembali ke UTC
            return end_local.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Untuk durasi yang lebih panjang atau lintas hari, gunakan algoritma lengkap
        current_time = start_local
        remaining_duration = duration
        day_end_hour = 17
        
        # Jadwal kerja dan istirahat
        work_hours = {
            'start': 8,
            'end': 17,
            'lunch_start': 12,
            'lunch_end': 13
        }
        
        # Loop sampai seluruh durasi terhitung
        while remaining_duration > 0:
            current_date = current_time.date()
            current_hour = current_time.hour + current_time.minute/60.0
            
            # Cepat cek apakah sedang dalam jam kerja
            if current_hour < work_hours['start']:
                # Sebelum jam kerja, pindah ke awal jam kerja
                current_time = local_tz.localize(datetime.combine(current_date, time(work_hours['start'], 0)))
                current_hour = work_hours['start']
            elif current_hour >= day_end_hour:
                # Setelah jam kerja, pindah ke hari berikutnya
                next_day = current_date + timedelta(days=1)
                current_time = local_tz.localize(datetime.combine(next_day, time(work_hours['start'], 0)))
                current_hour = work_hours['start']
                continue
            
            # Hitung berapa banyak jam kerja tersisa di hari ini
            available_hours = 0
            
            # Jika saat ini sebelum istirahat
            if current_hour < work_hours['lunch_start']:
                # Jam tersedia sampai istirahat
                available_hours += work_hours['lunch_start'] - current_hour
                # Jam tersedia setelah istirahat
                available_hours += work_hours['end'] - work_hours['lunch_end']
            # Jika saat ini dalam jam istirahat
            elif current_hour >= work_hours['lunch_start'] and current_hour < work_hours['lunch_end']:
                # Pindah ke akhir istirahat
                current_time = local_tz.localize(datetime.combine(current_date, time(work_hours['lunch_end'], 0)))
                current_hour = work_hours['lunch_end']
                # Jam tersedia sampai akhir hari
                available_hours += work_hours['end'] - work_hours['lunch_end']
            # Jika saat ini setelah istirahat
            else:
                # Jam tersedia sampai akhir hari
                available_hours += work_hours['end'] - current_hour
            
            # Jika durasi yang tersisa bisa selesai hari ini
            if remaining_duration <= available_hours:
                # Jika saat ini sebelum istirahat dan akan selesai setelah istirahat
                if current_hour < work_hours['lunch_start'] and (current_hour + remaining_duration) >= work_hours['lunch_start']:
                    # Tambahkan waktu sampai istirahat
                    before_lunch = work_hours['lunch_start'] - current_hour
                    remaining_duration -= before_lunch
                    
                    # Lewati waktu istirahat
                    current_time = local_tz.localize(datetime.combine(current_date, time(work_hours['lunch_end'], 0)))
                    
                    # Tambahkan sisa durasi
                    end_seconds = remaining_duration * 3600
                    current_time = current_time + timedelta(seconds=end_seconds)
                    remaining_duration = 0
                else:
                    # Tambahkan sisa durasi tanpa melewati istirahat
                    end_seconds = remaining_duration * 3600
                    current_time = current_time + timedelta(seconds=end_seconds)
                    remaining_duration = 0
            else:
                # Tambahkan semua waktu yang tersedia hari ini
                remaining_duration -= available_hours
                
                # Pindah ke hari berikutnya
                next_day = current_date + timedelta(days=1)
                current_time = local_tz.localize(datetime.combine(next_day, time(work_hours['start'], 0)))
        
        # Konversi kembali ke UTC
        return current_time.astimezone(pytz.UTC).replace(tzinfo=None)

    @api.depends('controller_mulai_servis', 'controller_selesai', 'order_line.service_duration')
    def _compute_duration_performance(self):
        for order in self:
            if order.controller_mulai_servis and order.controller_selesai:
                # Hitung durasi aktual
                actual_duration = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 3600
                
                # Hitung total estimasi durasi dari order lines
                estimated_duration = sum(order.order_line.mapped('service_duration'))
                
                if estimated_duration:
                    # Hitung deviasi dalam persen
                    deviation = ((actual_duration - estimated_duration) / estimated_duration) * 100
                    order.actual_vs_estimated_duration = deviation
                    
                    # Tentukan apakah on time (misalnya, toleransi 10%)
                    order.is_on_time = deviation <= 10
                else:
                    order.actual_vs_estimated_duration = 0
                    order.is_on_time = False
                    
    @api.depends('order_line.service_duration')
    def _compute_total_estimated_duration(self):
        for order in self:
            order.total_estimated_duration = sum(order.order_line.mapped('service_duration'))

    @api.depends('total_estimated_duration', 'controller_mulai_servis', 'controller_selesai')
    def _compute_duration_deviation(self):
        for order in self:
            if order.total_estimated_duration and order.controller_mulai_servis and order.controller_selesai:
                actual_duration = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 3600
                order.duration_deviation = ((actual_duration - order.total_estimated_duration) / order.total_estimated_duration) * 100
            else:
                order.duration_deviation = 0

    is_willing_to_feedback = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string='Willing to Give Feedback?', help='Apakah customer bersedia memberikan feedback?')

    no_feedback_reason = fields.Text(string='Reason for not giving feedback', help='Alasan customer tidak bersedia memberikan feedback')

    customer_rating = fields.Selection([
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5')
    ], string='Customer Rating',
    help='Rating yang diberikan oleh customer terhadap layanan yang diberikan oleh Pitcar. Rating ini berdasarkan skala 1-5. 1 adalah rating terendah dan 5 adalah rating tertinggi.'
    ) 
    
    customer_satisfaction = fields.Selection([
        ('very_dissatisfied', 'Very Dissatisfied (Sangat Tidak Puas / Komplain)'),
        ('dissatisfied', 'Dissatisfied (Tidak Puas / Komplain)'),
        ('neutral', 'Neutral (Cukup Puas)'),
        ('satisfied', 'Satisfied (Puas)'),
        ('very_satisfied', 'Very Satisfied (Sangat Puas)')
    ], string='Customer Satisfaction', readonly=True)

    customer_feedback = fields.Text(string='Customer Feedback')

    feedback_classification_ids = fields.Many2many(
        'feedback.classification', 
        string='Feedback Classification',
        help='Ini digunakan untuk mengklasifikasikan feedback yang diberikan oleh customer. Misalnya, feedback yang diberikan oleh customer adalah tentang kualitas produk, maka kita bisa mengklasifikasikan feedback tersebut ke dalam kategori "Kualitas Produk"'
    )

    review_google = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], 
    string='Review Google',
    help='Apakah customer bersedia memberikan review di Google?'
    )

    follow_instagram = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], 
    string='Follow Instagram',
    help='Apakah customer bersedia mengikuti akun Instagram Pitcar?'
    )

    complaint_action = fields.Text(
        string='Action Taken for Complaint', 
        help='Tindakan yang diambil oleh Pitcar untuk menyelesaikan komplain yang diberikan oleh customer'
    )
    
    complaint_status = fields.Selection([
        ('solved', 'Solved'),
        ('not_solved', 'Not Solved')
    ], 
    string='Complaint Status',
    help='Status Komplain dari customer apakah berhasil ditangani atau tidak.'
    )

    # New fields for follow-up
    is_follow_up = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string='Follow Up?', help='Apakah customer sudah di-follow up?')

    customer_feedback_follow_up = fields.Text(string='Customer Feedback (Follow Up)')

    notif_follow_up_3_days = fields.Char(
        string="Notif Follow Up (3 Hari)", 
        compute='_compute_notif_follow_up_3_days',
        store=True
    )
    next_follow_up_3_days = fields.Date(
        string="Next Follow Up (3 Days)", 
        compute='_compute_next_follow_up_3_days', 
        store=True
    )

    follow_up_evidence = fields.Text(string='Description')

    no_follow_up_reason = fields.Text(string='Reason for No Follow Up')

    show_complaint_action = fields.Boolean(compute='_compute_show_complaint_action', store=True)
    complaint_action = fields.Text(string="Complaint Action")

    @api.onchange('is_willing_to_feedback')
    def _onchange_is_willing_to_feedback(self):
        if self.is_willing_to_feedback == 'no':
            self.customer_rating = False
            self.customer_satisfaction = False
            self.customer_feedback = False
            self.feedback_classification_ids = [(5, 0, 0)]  # Clear many2many field
            self.review_google = False
            self.follow_instagram = False
        else:
            self.no_feedback_reason = False

    @api.depends('customer_satisfaction')
    def _compute_show_complaint_action(self):
        for task in self:
            task.show_complaint_action = task.customer_satisfaction in ['very_dissatisfied', 'dissatisfied']

    @api.depends('customer_rating')
    def _compute_show_complaint_action(self):
        for order in self:
            order.show_complaint_action = order.customer_rating in ['1', '2']

    @api.onchange('customer_rating')
    def _onchange_customer_rating(self):
        rating_to_satisfaction = {
            '1': 'very_dissatisfied',
            '2': 'dissatisfied',
            '3': 'neutral',
            '4': 'satisfied',
            '5': 'very_satisfied'
        }
        if self.customer_rating:
            self.customer_satisfaction = rating_to_satisfaction.get(self.customer_rating)
            self.show_complaint_action = self.customer_rating in ['1', '2']

    @api.model
    def create(self, vals):
        if 'customer_rating' in vals and 'customer_satisfaction' not in vals:
            rating_to_satisfaction = {
                '1': 'very_dissatisfied',
                '2': 'dissatisfied',
                '3': 'neutral',
                '4': 'satisfied',
                '5': 'very_satisfied'
            }
            vals['customer_satisfaction'] = rating_to_satisfaction.get(vals['customer_rating'])
        return super(SaleOrder, self).create(vals)
    
    detailed_ratings = fields.Json(
        string='Detailed Ratings',
        help='Stores detailed ratings for different categories',
    )
    
    @api.depends('detailed_ratings')
    def _compute_customer_rating(self):
        """Compute overall rating based on detailed ratings"""
        for order in self:
            if order.detailed_ratings:
                try:
                    ratings = [
                        int(order.detailed_ratings.get('service_rating', 0)),
                        int(order.detailed_ratings.get('price_rating', 0)),
                        int(order.detailed_ratings.get('facility_rating', 0))
                    ]
                    if any(ratings):
                        order.customer_rating = str(round(sum(ratings) / len(ratings)))
                except (ValueError, TypeError):
                    _logger.error(f"Error computing customer rating for order {order.id}")
                    order.customer_rating = False

    @api.constrains('detailed_ratings')
    def _check_detailed_ratings(self):
        """Validate detailed ratings data"""
        for order in self:
            if order.detailed_ratings:
                try:
                    ratings = ['service_rating', 'price_rating', 'facility_rating']
                    for rating in ratings:
                        value = order.detailed_ratings.get(rating)
                        if value and not (isinstance(value, int) and 1 <= value <= 5):
                            raise ValidationError(f"Invalid value for {rating}. Must be between 1 and 5.")
                except Exception as e:
                    raise ValidationError(f"Invalid detailed ratings format: {str(e)}")

    # REMINDER AFTER SERVICE 3 DAYS
    # # Fields untuk H+3 Follow-up
    post_service_rating = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')
    ], string='Post-Service Rating',
    help='Penilaian customer terhadap hasil servis setelah 3 hari penggunaan')
    
    post_service_feedback = fields.Text(
        string='Post-Service Feedback',
        help='Feedback customer terhadap hasil servis setelah 3 hari penggunaan'
    )

    # Fields untuk tracking reminder
    reminder_sent = fields.Boolean('Reminder Sent', default=False)
    reminder_sent_date = fields.Datetime('Reminder Sent Date')
    feedback_link_expiry = fields.Datetime('Feedback Link Expiry')
    
    # Fields untuk status follow-up
    post_service_satisfaction = fields.Selection([
        ('very_dissatisfied', 'Very Dissatisfied'),
        ('dissatisfied', 'Dissatisfied'),
        ('neutral', 'Neutral'),
        ('satisfied', 'Satisfied'),
        ('very_satisfied', 'Very Satisfied')
    ], string='Post-Service Satisfaction', compute='_compute_post_service_satisfaction', store=True)

    @api.depends('post_service_rating')
    def _compute_post_service_satisfaction(self):
        for order in self:
            rating_to_satisfaction = {
                '1': 'very_dissatisfied',
                '2': 'dissatisfied',
                '3': 'neutral',
                '4': 'satisfied',
                '5': 'very_satisfied'
            }
            order.post_service_satisfaction = rating_to_satisfaction.get(
                order.post_service_rating, 'neutral'
            )
             
    # Fields for 3 months reminder
    reminder_3_months = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Reminder 3 Bulan?")
    date_follow_up_3_months = fields.Date(string="Date Follow Up (3 Bulan)")
    notif_follow_up_3_months = fields.Char(
        string="Notif Follow Up (3 Bulan)", 
        compute='_compute_notif_follow_up_3_months',
        store=True
    )
     # Ubah field kategori untuk 3 bulan
    category_3_months = fields.Many2many(
        'feedback.classification', 
        string='Reminder Tags (3 Bulan)',
        relation='sale_order_feedback_3_months_rel',
        column1='sale_order_id',
        column2='feedback_classification_id',
        help='Ini digunakan untuk mengklasifikasikan reminder yang diberikan oleh customer setelah 3 bulan.'
    )

    is_response_3_months = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Response? (3 Bulan)")
    feedback_3_months = fields.Text(string="Feedback (3 Bulan)")
    is_booking_3_months = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Booking? (3 Bulan)")
    booking_date_3_months = fields.Date(string="Booking Date (3 Bulan)")
    no_reminder_reason_3_months = fields.Text(string="Reason for No Reminder (3 Bulan)")

    # Fields for 6 months reminder
    reminder_6_months = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Reminder 6 Bulan?")
    date_follow_up_6_months = fields.Date(string="Date Follow Up (6 Bulan)")
    notif_follow_up_6_months = fields.Char(
        string="Notif Follow Up (6 Bulan)", 
        compute='_compute_notif_follow_up_6_months',
        store=True
    )
     # Ubah field kategori untuk 6 bulan
    category_6_months = fields.Many2many(
        'feedback.classification', 
        string='Reminder Tags (6 Bulan)',
        relation='sale_order_feedback_6_months_rel',
        column1='sale_order_id',
        column2='feedback_classification_id',
        help='Ini digunakan untuk mengklasifikasikan reminder yang diberikan oleh customer setelah 6 bulan.'
    )

    is_response_6_months = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Response? (6 Bulan)")
    feedback_6_months = fields.Text(string="Feedback (6 Bulan)")
    is_booking_6_months = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Booking? (6 Bulan)")
    booking_date_6_months = fields.Date(string="Booking Date (6 Bulan)")
    no_reminder_reason_6_months = fields.Text(string="Reason for No Reminder (6 Bulan)")

    next_follow_up_3_months = fields.Date(
        string="Next Reminder (3 Months)", 
        compute='_compute_next_follow_up_3_months', 
        store=True
    )

    next_follow_up_6_months = fields.Date(
        string="Next Reminder (6 Months)", 
        compute='_compute_next_follow_up_6_months', 
        store=True
    )

    @api.depends('date_completed')
    def _compute_notif_follow_up_3_days(self):
        for order in self:
            order.notif_follow_up_3_days = self._compute_notif_follow_up(order.date_completed, 3)

    @api.depends('date_completed')
    def _compute_next_follow_up_3_days(self):
        for order in self:
            order.next_follow_up_3_days = self._compute_next_follow_up(order.date_completed, 3)

    @api.depends('date_completed')
    def _compute_notif_follow_up_3_months(self):
        for order in self:
            order.notif_follow_up_3_months = self._compute_notif_follow_up(order.date_completed, 90)

    @api.depends('date_completed')
    def _compute_next_follow_up_3_months(self):
        for order in self:
            order.next_follow_up_3_months = self._compute_next_follow_up(order.date_completed, 90)

    @api.depends('date_completed')
    def _compute_notif_follow_up_6_months(self):
        for order in self:
            order.notif_follow_up_6_months = self._compute_notif_follow_up(order.date_completed, 180)

    @api.depends('date_completed')
    def _compute_next_follow_up_6_months(self):
        for order in self:
            order.next_follow_up_6_months = self._compute_next_follow_up(order.date_completed, 180)


    def _compute_notif_follow_up(self, date_completed, days):
        try:
            if not date_completed:
                return "Not Set"
            
            today = date.today()
            target_date = date_completed.date() + timedelta(days=days)

            formatted_date = target_date.strftime("%d %B %Y")
            return f"{formatted_date}"
        except Exception as e:
            _logger.error(f"Error in _compute_notif_follow_up: {str(e)}")
            return "Error"
        
    def _compute_next_follow_up(self, date_completed, days):
        try:
            if not date_completed:
                return False
            
            # Calculate the target follow-up date and return it in date format
            target_date = date_completed + timedelta(days=days)
            return target_date
        except Exception as e:
            _logger.error(f"Error in _compute_next_follow_up: {str(e)}")
            return False

    @api.depends('car_mechanic_id_new')
    def _compute_generated_mechanic_team(self):
        for order in self:
            order.generated_mechanic_team = ', '.join(order.car_mechanic_id_new.mapped('name'))
    
    @api.onchange('partner_car_id')
    def _onchange_partner_car_id(self):
        for order in self:
            order.partner_id = order.partner_car_id.partner_id.id
            
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for order in self:
            if order.partner_id:
                return {
                    'domain': {
                        'partner_car_id': [
                            ('partner_id', '=', order.partner_id.id)
                        ]
                    }
                }
            return 
    
    # Copying car information from sales order to delivery data when sales confirmed
    # model : stock.picking
    def _action_confirm(self):
        res = super(SaleOrder, self)._action_confirm()
        for order in self:
            if hasattr(order, 'picking_ids'):
                for picking in order.picking_ids:
                    picking.partner_car_id = order.partner_car_id
                    picking.partner_car_odometer = order.partner_car_odometer
                    picking.car_mechanic_id = order.car_mechanic_id
                    picking.car_mechanic_id_new = order.car_mechanic_id_new
                    picking.generated_mechanic_team = order.generated_mechanic_team
                    picking.service_advisor_id = order.service_advisor_id  
                    picking.car_arrival_time = order.car_arrival_time
        return res

    # Copying car information from sales order to invoice data when invoice created
    # model : account.move
    # def _create_invoices(self, grouped=False, final=False):
    #     res = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
    #     for order in self:
    #         order.date_completed = fields.Datetime.now()
    #         for invoice in order.invoice_ids:
    #             invoice.date_sale_completed = order.date_completed
    #             invoice.date_sale_quotation = order.create_date
    #             invoice.partner_car_id = order.partner_car_id
    #             invoice.partner_car_odometer = order.partner_car_odometer
    #             invoice.car_mechanic_id = order.car_mechanic_id
    #             invoice.car_mechanic_id_new = order.car_mechanic_id_new
    #             invoice.generated_mechanic_team = order.generated_mechanic_team
    #             invoice.service_advisor_id = order.service_advisor_id
    #             invoice.car_arrival_time = order.car_arrival_time
    #     return res


    # def _create_invoices(self, grouped=False, final=False):
    #     # Prepare data sebelum create invoice
    #     self = self.with_context(skip_invoice_onchange=True)
        
    #     # Create invoices with super
    #     res = super()._create_invoices(grouped=grouped, final=final)
        
    #     # Batch update invoices
    #     now = fields.Datetime.now()
    #     invoice_vals = []
    #     for order in self:
    #         order.date_completed = now
    #         for invoice in order.invoice_ids:
    #             invoice_vals.append({
    #                 'id': invoice.id,
    #                 'date_sale_completed': now,
    #                 'date_sale_quotation': order.create_date,
    #                 'partner_car_id': order.partner_car_id.id,
    #                 'partner_car_odometer': order.partner_car_odometer,
    #                 'car_mechanic_id': order.car_mechanic_id.id,
    #                 'car_mechanic_id_new': [(6, 0, order.car_mechanic_id_new.ids)],
    #                 'generated_mechanic_team': order.generated_mechanic_team,
    #                 'service_advisor_id': [(6, 0, order.service_advisor_id.ids)],
    #                 'car_arrival_time': order.car_arrival_time,
    #             })
        
    #     # Batch write dengan raw SQL untuk performa lebih baik
    #     if invoice_vals:
    #         self.env.cr.executemany("""
    #             UPDATE account_move SET 
    #                 date_sale_completed = %(date_sale_completed)s,
    #                 date_sale_quotation = %(date_sale_quotation)s,
    #                 partner_car_id = %(partner_car_id)s,
    #                 partner_car_odometer = %(partner_car_odometer)s
    #             WHERE id = %(id)s
    #         """, invoice_vals)
            
    #     return res

    def _create_invoices(self, grouped=False, final=False):
        res = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
        
        # Set completion date and update invoice data
        now = fields.Datetime.now()
        for order in self:
            order.date_completed = now
            
            # Get values ensuring proper types for foreign keys
            invoice_vals = {
                'date_sale_completed': now,
                'date_sale_quotation': order.create_date,
                'partner_car_id': order.partner_car_id.id if order.partner_car_id else None,
                'partner_car_odometer': order.partner_car_odometer,
                'car_mechanic_id': order.car_mechanic_id.id if order.car_mechanic_id else None,
                'car_arrival_time': order.car_arrival_time
            }
            
            # Only set service_advisor_id and car_mechanic_id_new if they exist
            if order.service_advisor_id:
                invoice_vals['service_advisor_id'] = [(6, 0, order.service_advisor_id.ids)]
                
            if order.car_mechanic_id_new:
                invoice_vals['car_mechanic_id_new'] = [(6, 0, order.car_mechanic_id_new.ids)]
                
            if order.generated_mechanic_team:
                invoice_vals['generated_mechanic_team'] = order.generated_mechanic_team

            # Update each invoice with the prepared values
            order.invoice_ids.write(invoice_vals)

        return res

    
    # ROLE LEAD TIME 
        
    # Fields untuk tracking lead time
    service_category = fields.Selection([
        ('maintenance', 'Perawatan'),
        ('repair', 'Perbaikan')
    ], string="Kategori Servis", store=True, compute='_compute_service_category')
    service_subcategory = fields.Selection([
        # Sub kategori untuk Perawatan
        ('tune_up', 'Tune Up'),
        ('tune_up_addition', 'Tune Up + Addition'),
        ('periodic_service', 'Servis Berkala'),
        ('periodic_service_addition', 'Servis Berkala + Addition'),
        # Sub kategori untuk Perbaikan
        ('general_repair', 'General Repair'),
        ('oil_change', 'Ganti Oli'),
    ], string="Jenis Servis")

    @api.depends('service_subcategory')
    def _compute_service_category(self):
        """
        Menentukan kategori servis berdasarkan sub kategori yang dipilih
        """
        maintenance_types = ['tune_up', 'tune_up_addition', 'periodic_service', 'periodic_service_addition', 'oil_change']
        for record in self:
            if record.service_subcategory in maintenance_types:
                record.service_category = 'maintenance'
            elif record.service_subcategory == 'general_repair':
                record.service_category = 'repair'
            else:
                record.service_category = False
    
    sa_jam_masuk = fields.Datetime(
        "Jam Masuk", 
        help="Time when service advisor recorded the arrival."
    )
    is_arrival_time_set = fields.Boolean(compute='_compute_is_arrival_time_set', store=True)
    sa_mulai_penerimaan = fields.Datetime(string='Mulai Penerimaan')
    is_penerimaan_filled = fields.Boolean(compute='_compute_is_penerimaan_filled', store=True)

    sa_cetak_pkb = fields.Datetime("Cetak PKB")
    
    controller_estimasi_mulai = fields.Datetime("Estimasi Pekerjaan Mulai", tracking=True)
    controller_estimasi_selesai = fields.Datetime("Estimasi Pekerjaan Selesai", tracking=True)
    controller_mulai_servis = fields.Datetime(string="Mulai Servis", readonly=True)
    controller_selesai = fields.Datetime(string="Selesai Servis", readonly=True)
    controller_tunggu_konfirmasi_mulai = fields.Datetime("Tunggu Konfirmasi Mulai")
    controller_tunggu_konfirmasi_selesai = fields.Datetime("Tunggu Konfirmasi Selesai")
    controller_tunggu_part1_mulai = fields.Datetime("Tunggu Part 1 Mulai")
    controller_tunggu_part1_selesai = fields.Datetime("Tunggu Part 1 Selesai")
    controller_tunggu_part2_mulai = fields.Datetime("Tunggu Part 2 Mulai")
    controller_tunggu_part2_selesai = fields.Datetime("Tunggu Part 2 Selesai")

    need_istirahat = fields.Selection([
        ('yes', 'Ya'),
        ('no', 'Tidak')
    ], string="Mobil Tunggu Istirahat (Tidak Normal)?", default='no')
    controller_istirahat_shift1_mulai = fields.Datetime("Istirahat Shift 1 Mulai")
    controller_istirahat_shift1_selesai = fields.Datetime("Istirahat Shift 1 Selesai")

    controller_tunggu_sublet_mulai = fields.Datetime("Tunggu Sublet Mulai")
    controller_tunggu_sublet_selesai = fields.Datetime("Tunggu Sublet Selesai")
    
    fo_unit_keluar = fields.Datetime("Unit Keluar")
    
    lead_time_catatan = fields.Text("Catatan Lead Time")
    
    lead_time_servis = fields.Float(string="Lead Time Servis (jam)", compute="_compute_lead_time_servis", store=True, force_compute=True)
    total_lead_time_servis = fields.Float(string="Total Lead Time Servis (jam)", compute="_compute_lead_time_servis", store=True, force_compute=True)
    is_overnight = fields.Boolean(string="Menginap", compute="_compute_lead_time_servis", store=True, force_compute=True)
    lead_time_progress = fields.Float(string="Lead Time Progress", compute="_compute_lead_time_progress", store=True)
    lead_time_stage = fields.Selection([
        ('not_started', 'Belum Dimulai'),
        ('category_selected', 'Kategori Dipilih'),
        ('check_in', 'Check In'),
        ('reception', 'Penerimaan'),
        ('pkb_printed', 'PKB Dicetak'),
        ('estimation', 'Estimasi'),
        ('waiting_confirmation', 'Menunggu Konfirmasi'),
        ('waiting_parts', 'Menunggu Sparepart'),
        ('in_service', 'Dalam Servis'),
        ('service_done', 'Servis Selesai'),
        ('waiting_pickup', 'Menunggu Pengambilan'),
        ('completed', 'Selesai')
    ], string="Tahapan Servis", compute='_compute_lead_time_stage', store=True)

    need_other_job_stop = fields.Selection([
        ('yes', 'Ya'),
        ('no', 'Tidak')
    ], string="Perlu Job Stop Lain?", default='no')
    controller_job_stop_lain_mulai = fields.Datetime("Job Stop Lain Mulai")
    controller_job_stop_lain_selesai = fields.Datetime("Job Stop Lain Selesai")
    job_stop_lain_keterangan = fields.Text("Keterangan Job Stop Lain")

    # Fields baru untuk lead time sublet dan job stop lain
    lead_time_tunggu_sublet = fields.Float(
        string="Lead Time Tunggu Sublet (hours)", 
        compute="_compute_lead_time_tunggu_sublet", 
        store=True
    )
    
    lead_time_job_stop_lain = fields.Float(
        string="Lead Time Job Stop Lain (hours)", 
        compute="_compute_lead_time_job_stop_lain", 
        store=True
    )

    user_is_controller = fields.Boolean(compute='_compute_user_is_controller')

    @api.depends('user_id')
    def _compute_user_is_controller(self):
        for record in self:
            record.user_is_controller = self.env.user.pitcar_role == 'controller'

    def action_record_car_arrival_time(self):
        self.ensure_one()

        # Get queue management record
        queue_mgmt = self.env['queue.management']
        today = fields.Date.today()
        queue_record = queue_mgmt.search([('date', '=', today)], limit=1)
        if not queue_record:
            queue_record = queue_mgmt.create({
                'date': today,
                'queue_start_time': fields.Datetime.now()
            })

        try:
            # Get queue number and info, considering booking status
            queue_info = queue_record.assign_queue_number(self.id, is_booking=self.is_booking)

            # Set timezone and convert time
            tz = pytz.timezone('Asia/Jakarta')
            local_dt = datetime.now(tz)
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
            
            # Update sale order
            self.write({
                'car_arrival_time': utc_dt,
                'sa_jam_masuk': utc_dt,
            })
            if not self.queue_line_id:
                raise ValidationError("Gagal membuat nomor antrian")
            # Prepare message body
            priority_status = "Antrean Prioritas" if self.is_booking else "Antrean Regular"
            body = f"""
            <p><strong>Informasi Kedatangan & Antrean</strong></p>
            <ul>
                <li>Tipe Antrean: {priority_status}</li>
                <li>Nomor Antrean: {queue_info['display_number']}</li>
                <li>Antrean Saat Ini: {queue_info['current_number']}</li>
                <li>Antrean Di Depan: {queue_info['numbers_ahead']}</li>
                <li>Estimasi Waktu Tunggu: {queue_info['estimated_wait_minutes']} menit</li>
                <li>Estimasi Waktu Pelayanan: {queue_info['estimated_service_time']}</li>
                <li>Dicatat oleh: {self.env.user.name}</li>
                <li>Waktu: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
            </ul>
            """
            self.message_post(body=body, message_type='notification')

            # Trigger dashboard refresh
            if self.queue_line_id and self.queue_line_id.queue_id:
                self.queue_line_id.queue_id._broadcast_queue_update()
                
                # Refresh metrics
                self.env['queue.metric'].sudo().refresh_metrics()
            
            return True

        except ValidationError as e:
            self.message_post(
                body=f"<p><strong>Error Antrean:</strong> {str(e)}</p>",
                message_type='notification'
            )
            raise
    
    @api.depends('car_arrival_time', 'sa_jam_masuk')
    def _compute_is_arrival_time_set(self):
        for record in self:
            record.is_arrival_time_set = bool(record.car_arrival_time or record.sa_jam_masuk)

    @api.onchange('sa_jam_masuk')
    def _onchange_sa_jam_masuk(self):
        if self.sa_jam_masuk and self.sa_jam_masuk != self.car_arrival_time:
            self.car_arrival_time = self.sa_jam_masuk

    @api.onchange('car_arrival_time')
    def _onchange_car_arrival_time(self):
        if self.car_arrival_time and self.car_arrival_time != self.sa_jam_masuk:
            self.sa_jam_masuk = self.car_arrival_time

    def action_mulai_servis(self):
        for record in self:
            if not record.sa_mulai_penerimaan:
                raise exceptions.ValidationError("Tidak dapat memulai servis. Customer belum diterima/dilayani.")
            if not record.sa_cetak_pkb:
                raise exceptions.ValidationError("Tidak dapat memulai servis. PKB belum dicetak.")
            if record.controller_mulai_servis:
                raise exceptions.ValidationError("Servis sudah dimulai sebelumnya.")
            
            # Periksa peran pengguna sebelum melakukan perubahan apa pun
            if self.env.user.pitcar_role != 'controller':
                raise UserError("Hanya Controller yang dapat memulai servis.")
            
            # Menggunakan timezone Asia/Jakarta tapi simpan sebagai naive datetime
            tz = pytz.timezone('Asia/Jakarta')
            local_dt = datetime.now(tz)
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)  # Convert ke UTC dan hapus timezone info
            
            record.controller_mulai_servis = utc_dt

            # Check stall assignment
            if not record.stall_id:
                # Auto assign stall jika berasal dari booking
                if record.booking_id and record.booking_id.stall_id:
                    record.stall_id = record.booking_id.stall_id.id
                    # Create stall history entry
                    self.env['pitcar.stall.history'].create({
                        'sale_order_id': record.id,
                        'stall_id': record.booking_id.stall_id.id,
                        'start_time': utc_dt,
                        'notes': 'Auto assigned from booking'
                    })
                else:
                    # Tampilkan warning bahwa belum ada stall
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Perhatian'),
                            'message': _('Servis dimulai tanpa alokasi stall. Harap alokasikan stall untuk service order ini.'),
                            'sticky': True,
                            'type': 'warning',
                            'next': {
                                'type': 'ir.actions.act_window',
                                'name': _('Pilih Stall'),
                                'res_model': 'assign.stall.wizard',
                                'view_mode': 'form',
                                'target': 'new',
                                'context': {'default_sale_order_id': record.id}
                            }
                        }
                    }
            else:
                # Jika stall sudah ada, create history entry
                self.env['pitcar.stall.history'].create({
                    'sale_order_id': record.id,
                    'stall_id': record.stall_id.id,
                    'start_time': utc_dt,
                    'notes': 'Assigned at service start'
                })

            # Format waktu untuk tampilan di chatter
            formatted_time = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Log aktivitas langsung ke chatter
            body = f"""
            <p><strong>Servis dimulai</strong></p>
            <ul>
                <li>Dicatat oleh: {self.env.user.name}</li>
                <li>Waktu catat: {formatted_time} WIB</li>
                <li>Stall: {record.stall_id.name if record.stall_id else 'Belum dialokasikan'}</li>
            </ul>
            """
            self.message_post(body=body, message_type='notification')

    def write(self, vals):
        # Handle customer rating to satisfaction mapping
        if 'customer_rating' in vals and 'customer_satisfaction' not in vals:
            rating_to_satisfaction = {
                '1': 'very_dissatisfied',
                '2': 'dissatisfied',
                '3': 'neutral',
                '4': 'satisfied',
                '5': 'very_satisfied'
            }
            vals['customer_satisfaction'] = rating_to_satisfaction.get(vals['customer_rating'])

        # Handle estimasi waktu
        if ('controller_estimasi_mulai' in vals or 'controller_estimasi_selesai' in vals):
            # if self.env.user.pitcar_role != 'controller':
            #     raise UserError("Hanya Controller yang dapat mengatur estimasi pekerjaan.")
            
            # Log perubahan dengan format WIB
            tz = pytz.timezone('Asia/Jakarta')
            
            if 'controller_estimasi_mulai' in vals and vals['controller_estimasi_mulai']:
                local_dt = fields.Datetime.from_string(vals['controller_estimasi_mulai'])
                local_dt = pytz.UTC.localize(local_dt).astimezone(tz)
                current_time = datetime.now(tz)
                body = f"""
                <p><strong>Estimasi Waktu Mulai diubah</strong></p>
                <ul>
                    <li>Diubah oleh: {self.env.user.name}</li>
                    <li>Waktu catat: {current_time.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
                    <li>Waktu estimasi mulai: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
                </ul>
                """
                self.message_post(body=body, message_type='notification')
                
            if 'controller_estimasi_selesai' in vals and vals['controller_estimasi_selesai']:
                local_dt = fields.Datetime.from_string(vals['controller_estimasi_selesai'])
                local_dt = pytz.UTC.localize(local_dt).astimezone(tz)
                current_time = datetime.now(tz)
                body = f"""
                <p><strong>Estimasi Waktu Selesai diubah</strong></p>
                <ul>
                    <li>Diubah oleh: {self.env.user.name}</li>
                    <li>Waktu catat: {current_time.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
                    <li>Waktu estimasi selesai: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
                </ul>
                """
                self.message_post(body=body, message_type='notification')

        # Add trigger for KPI updates
        res = super().write(vals)
        
        # Trigger KPI dan Quality Metrics update when relevant fields change
        if any(f in vals for f in ['state', 'date_completed', 'customer_rating', 'customer_satisfaction',
                                'controller_estimasi_mulai', 'controller_estimasi_selesai']):
            self.env['service.advisor.kpi']._update_today_kpi()
            self.env['quality.metrics']._update_today_metrics()
        
        return res

    @api.constrains('controller_estimasi_mulai', 'controller_estimasi_selesai')
    def _check_controller_estimasi(self):
        for record in self:
            # if record.controller_selesai:
            #     raise UserError("Tidak dapat memberikan estimasi karena servis sudah selesai")
            # if record.controller_estimasi_mulai or record.controller_estimasi_selesai:
                # if self.env.user.pitcar_role != 'controller':
                #     raise UserError("Hanya Controller yang dapat mengatur estimasi pekerjaan.")
                if record.controller_estimasi_mulai and record.controller_estimasi_selesai:
                    if record.controller_estimasi_selesai < record.controller_estimasi_mulai:
                        raise UserError("Waktu estimasi selesai tidak boleh lebih awal dari waktu estimasi mulai.")
            
    def action_selesai_servis(self):
        for record in self:
            if not record.controller_mulai_servis:
                raise exceptions.ValidationError("Tidak dapat menyelesaikan servis. Servis belum dimulai.")
            if record.controller_selesai:
                raise exceptions.ValidationError("Servis sudah selesai sebelumnya.")
            
            if self.env.user.pitcar_role != 'controller':
                raise UserError("Hanya Controller yang dapat menyelesaikan servis.")
            
            tz = pytz.timezone('Asia/Jakarta')
            local_dt = datetime.now(tz)
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
            
            record.controller_selesai = utc_dt
            
            # Update stall history jika ada
            if record.stall_id:
                history = self.env['pitcar.stall.history'].search([
                    ('sale_order_id', '=', record.id),
                    ('stall_id', '=', record.stall_id.id),
                    ('end_time', '=', False)
                ], limit=1)
                
                if history:
                    history.end_time = utc_dt
            
            # Log di chatter
            body = f"""
            <p><strong>Servis selesai</strong></p>
            <ul>
                <li>Dicatat oleh: {self.env.user.name}</li>
                <li>Waktu catat: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
                <li>Stall: {record.stall_id.name if record.stall_id else 'Tidak dialokasikan'}</li>
            </ul>
            """
            self.message_post(body=body, message_type='notification')



    @api.depends('sa_jam_masuk', 'sa_mulai_penerimaan', 'sa_cetak_pkb',
                 'controller_estimasi_mulai', 'controller_estimasi_selesai',
                 'controller_mulai_servis', 'controller_selesai',
                 'controller_tunggu_konfirmasi_mulai', 'controller_tunggu_konfirmasi_selesai',
                 'controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai',
                 'controller_tunggu_part2_mulai', 'controller_tunggu_part2_selesai',
                 'controller_istirahat_shift1_mulai', 'controller_istirahat_shift1_selesai',
                 'controller_tunggu_sublet_mulai', 'controller_tunggu_sublet_selesai',
                 'fo_unit_keluar')
    def _compute_lead_time_progress(self):
        for order in self:
            if not order.sa_jam_masuk:
                order.lead_time_progress = 0
                continue

            now = fields.Datetime.now()
            steps = [
                ('sa_jam_masuk', order.sa_jam_masuk),
                ('sa_mulai_penerimaan', order.sa_mulai_penerimaan),
                ('sa_cetak_pkb', order.sa_cetak_pkb),
                ('controller_estimasi_selesai', order.controller_estimasi_selesai),
                ('controller_mulai_servis', order.controller_mulai_servis),
                ('controller_selesai', order.controller_selesai),
                ('fo_unit_keluar', order.fo_unit_keluar)
            ]

            # Add conditional steps
            if order.controller_tunggu_konfirmasi_mulai:
                steps.append(('tunggu_konfirmasi', order.controller_tunggu_konfirmasi_selesai))
            if order.controller_tunggu_part1_mulai:
                steps.append(('tunggu_part1', order.controller_tunggu_part1_selesai))
            if order.controller_tunggu_part2_mulai:
                steps.append(('tunggu_part2', order.controller_tunggu_part2_selesai))
            if order.controller_tunggu_sublet_mulai:
                steps.append(('tunggu_sublet', order.controller_tunggu_sublet_selesai))

            total_steps = len(steps)
            completed_steps = sum(1 for _, value in steps if value)

            # If all steps are completed, set progress to 100%
            if completed_steps == total_steps and order.controller_selesai:
                order.lead_time_progress = 100
            else:
                # Calculate progress
                end_time = order.controller_selesai or now
                total_time = (end_time - order.sa_jam_masuk).total_seconds()
                
                if total_time <= 0:
                    order.lead_time_progress = 0
                    continue

                waiting_time = order.calc_waiting_time().total_seconds()
                active_time = max(total_time - waiting_time, 0)
                
                step_progress = (completed_steps / total_steps) * 100
                time_progress = (active_time / total_time) * 100

                # Combine step progress and time progress, giving more weight to step progress
                order.lead_time_progress = min(max((step_progress * 0.7 + time_progress * 0.3), 0), 99.99)

    def calc_waiting_time(self):
        waiting_time = timedelta()
        waiting_time += self.calc_interval(self.controller_tunggu_konfirmasi_mulai, self.controller_tunggu_konfirmasi_selesai)
        waiting_time += self.calc_interval(self.controller_tunggu_part1_mulai, self.controller_tunggu_part1_selesai)
        waiting_time += self.calc_interval(self.controller_tunggu_part2_mulai, self.controller_tunggu_part2_selesai)
        waiting_time += self.calc_interval(self.controller_istirahat_shift1_mulai, self.controller_istirahat_shift1_selesai)
        waiting_time += self.calc_interval(self.controller_tunggu_sublet_mulai, self.controller_tunggu_sublet_selesai)
        return waiting_time

    @api.model
    def calc_interval(self, start, end):
        if start and end and end > start:
            return end - start
        return timedelta()

    @api.depends('service_category', 'sa_jam_masuk', 'sa_mulai_penerimaan', 'sa_cetak_pkb',
                 'controller_estimasi_mulai', 'controller_estimasi_selesai',
                 'controller_tunggu_konfirmasi_mulai', 'controller_tunggu_konfirmasi_selesai',
                 'controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai',
                 'controller_tunggu_part2_mulai', 'controller_tunggu_part2_selesai',
                 'controller_mulai_servis', 'controller_selesai',
                 'fo_unit_keluar')
    def _compute_lead_time_stage(self):
        for order in self:
            if not order.service_category:
                order.lead_time_stage = 'not_started'
            elif order.service_category and not order.sa_jam_masuk:
                order.lead_time_stage = 'category_selected'
            elif order.sa_jam_masuk and not order.sa_mulai_penerimaan:
                order.lead_time_stage = 'check_in'
            elif order.sa_mulai_penerimaan and not order.sa_cetak_pkb:
                order.lead_time_stage = 'reception'
            elif order.sa_cetak_pkb and not order.controller_estimasi_mulai:
                order.lead_time_stage = 'pkb_printed'
            elif order.controller_estimasi_mulai and not order.controller_estimasi_selesai:
                order.lead_time_stage = 'estimation'
            elif order.controller_estimasi_selesai:
                if order.controller_tunggu_konfirmasi_mulai and not order.controller_tunggu_konfirmasi_selesai:
                    order.lead_time_stage = 'waiting_confirmation'
                elif (order.controller_tunggu_part1_mulai and not order.controller_tunggu_part1_selesai) or \
                     (order.controller_tunggu_part2_mulai and not order.controller_tunggu_part2_selesai):
                    order.lead_time_stage = 'waiting_parts'
                elif order.controller_mulai_servis and not order.controller_selesai:
                    order.lead_time_stage = 'in_service'
                elif order.controller_selesai and not order.fo_unit_keluar:
                    order.lead_time_stage = 'service_done'
                elif order.fo_unit_keluar:
                    order.lead_time_stage = 'completed'
                else:
                    order.lead_time_stage = 'waiting_pickup'
            else:
                order.lead_time_stage = 'waiting_pickup'

    @api.constrains('sa_jam_masuk', 'fo_unit_keluar', 'controller_estimasi_mulai', 'controller_estimasi_selesai')
    def _check_lead_time_order(self):
        for order in self:
            if order.sa_jam_masuk and order.fo_unit_keluar and order.sa_jam_masuk > order.fo_unit_keluar:
                raise ValidationError("Jam masuk tidak boleh lebih besar dari jam unit keluar.")
            if order.controller_estimasi_mulai and order.controller_estimasi_selesai and order.controller_estimasi_mulai > order.controller_estimasi_selesai:
                raise ValidationError("Waktu mulai estimasi tidak boleh lebih besar dari waktu selesai estimasi.")
            if order.sa_jam_masuk and order.fo_unit_keluar and order.sa_jam_masuk > order.fo_unit_keluar:
                raise ValidationError("Waktu mulai SA tidak boleh lebih besar dari waktu selesai FO.")
            if order.controller_selesai:
                if order.sa_jam_masuk and order.controller_selesai < order.sa_jam_masuk:
                    raise ValidationError("Waktu selesai Controller tidak boleh lebih kecil dari waktu mulai SA.")
                if order.fo_unit_keluar and order.controller_selesai > order.fo_unit_keluar:
                    raise ValidationError("Waktu selesai Controller tidak boleh lebih besar dari waktu selesai FO.")

    def action_print_work_order(self):
        """Handle print work order action with better performance"""
        self.ensure_one()
        
        if self.env.user.pitcar_role != 'service_advisor':
            raise UserError("Hanya Service Advisor yang dapat melakukan pencetakan PKB.")
        
        try:
            # Gunakan context untuk bypass pengecekan yang tidak perlu
            self = self.with_context(skip_queue_check=True)
            
            # Hanya catat waktu jika sa_cetak_pkb masih kosong (klik pertama)
            if not self.sa_cetak_pkb:
                # Gunakan Odoo datetime tools dan batch operation
                current_time = fields.Datetime.now()
                values = {
                    'sa_cetak_pkb': current_time,
                    'reception_state': 'completed'  # Update state jika perlu
                }
                self.write(values)

                # Tambahkan notifikasi untuk part purchasing
                self.env['pitcar.notification'].create_or_update_notification(
                    model='sale.order',
                    res_id=self.id,
                    type='pkb_printed',  # Tipe baru untuk Cetak PKB
                    title='PKB Dicetak',
                    message=f"PKB untuk Order #{self.name} telah dicetak",
                    request_time=current_time,
                    data={'total_items': len(self.part_request_items_ids) or 0}
                )
                _logger.info(f"Notification created for PKB printed: Order #{self.name}")

                # Complete queue in background
                self._complete_queue_async()

                # Post message in batch
                self._post_pkb_message()
            else:
                # Jika sudah pernah diklik sebelumnya, hanya log info tanpa mencatat waktu
                _logger.info(f"Printing PKB again for order #{self.name} without updating timestamp")

            # Return report action
            return self.env.ref('pitcar_custom.action_report_work_order').report_action(self)

        except Exception as e:
            _logger.error(f"Error during print work order: {str(e)}")
            raise UserError(f"Gagal mencetak PKB: {str(e)}")

    def _complete_queue_async(self):
        """Handle queue completion asynchronously"""
        try:
            queue_record = self.env['queue.management'].search([
                ('date', '=', fields.Date.today())
            ], limit=1)
            
            if queue_record:
                queue_record.with_context(async_queue=True).complete_service(self.id)
                
        except Exception as e:
            _logger.error(f"Error completing queue: {str(e)}")

    def _post_pkb_message(self):
        """Post PKB message with optimized batch operations"""
        try:
            local_tz = pytz.timezone('Asia/Jakarta')
            local_dt = fields.Datetime.now().astimezone(local_tz)
            formatted_time = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            priority_status = "Antrean Prioritas" if self.is_booking else "Antrean Regular"
            
            message_values = {
                'body': f"""
                    <p><strong>PKB Dicetak</strong></p>
                    <ul>
                        <li>Tipe Antrean: {priority_status}</li>
                        <li>Nomor Antrean: {self.display_queue_number}</li>
                        <li>Dicetak oleh: {self.env.user.name}</li>
                        <li>Waktu: {formatted_time} WIB</li>
                    </ul>
                """,
                'message_type': 'notification'
            }
            
            # Batch post message
            self.with_context(mail_notify_force_send=False).message_post(**message_values)
            
        except Exception as e:
            _logger.error(f"Error posting PKB message: {str(e)}")

    @api.depends('sa_mulai_penerimaan')
    def _compute_is_penerimaan_filled(self):
        for record in self:
            record.is_penerimaan_filled = bool(record.sa_mulai_penerimaan)

    def action_record_sa_mulai_penerimaan(self):
        """Start service and update queue status"""
        self.ensure_one()
        if self.sa_mulai_penerimaan:
            raise UserError("Waktu mulai penerimaan sudah diisi sebelumnya.")

        # Validate queue exists
        # if not self.queue_line_id:
        #     raise UserError("Order ini tidak memiliki nomor antrian.")

        # Get queue record and start service
        queue_record = self.env['queue.management'].search([
            ('date', '=', fields.Date.today())
        ], limit=1)
        
        if not queue_record:
            raise UserError("Tidak ada antrian aktif hari ini.")
            
        try:
            # Start service will validate if this is the next queue
            queue_record.start_service(self.id)
            
            tz = pytz.timezone('Asia/Jakarta')
            local_dt = datetime.now(tz)
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
            
            self.write({
                'sa_mulai_penerimaan': utc_dt,
                'reception_state': 'reception_started',
            })

            # Prepare message
            queue_info = self.queue_line_id
            priority_status = "Antrean Prioritas" if queue_info.is_priority else "Antrean Regular"
            body = f"""
            <p><strong>Mulai Penerimaan</strong></p>
            <ul>
                <li>Tipe Antrean: {priority_status}</li>
                <li>Nomor Antrean: {queue_info.display_number}</li>
                <li>Dicatat oleh: {self.env.user.name}</li>
                <li>Waktu: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
            </ul>
            """
            self.message_post(body=body, message_type='notification')
            
            return True
            
        except Exception as e:
            raise UserError(f"Gagal memulai pelayanan: {str(e)}")
    
    def action_tunggu_part1_mulai(self):
        if self.controller_selesai:
            raise UserError("Tidak dapat memulai tunggu part 1 karena servis sudah selesai.")
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat memulai tunggu part 1.")
        
        self.controller_tunggu_part1_mulai = fields.Datetime.now()

    def action_tunggu_part1_selesai(self):
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat menyelesaikan tunggu part 1.")
        
        self.controller_tunggu_part1_selesai = fields.Datetime.now()

    def action_tunggu_part2_mulai(self):
        if self.controller_selesai:
            raise UserError("Tidak dapat memulai tunggu part 2 karena servis sudah selesai.")
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat memulai tunggu part 2.")
        
        self.controller_tunggu_part2_mulai = fields.Datetime.now()

    def action_tunggu_part2_selesai(self):
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat menyelesaikan tunggu part 2.")
        
        self.controller_tunggu_part2_selesai = fields.Datetime.now()

    def action_istirahat_shift1_mulai(self):
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat memulai istirahat shift 1.")
        self.controller_istirahat_shift1_mulai = fields.Datetime.now()

    def action_istirahat_shift1_selesai(self):
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat menyelesaikan istirahat shift 1.")
        
        self.controller_istirahat_shift1_selesai = fields.Datetime.now()

    def action_tunggu_sublet_mulai(self):
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat memulai tunggu sublet.")
        
        self.controller_tunggu_sublet_mulai = fields.Datetime.now()

    def action_tunggu_sublet_selesai(self):
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat menyelesaikan tunggu sublet.")
        self.controller_tunggu_sublet_selesai = fields.Datetime.now()

    # Aksi untuk memulai tunggu konfirmasi
    def action_tunggu_konfirmasi_mulai(self):
        for record in self:
            if record.controller_selesai:
                raise UserError("Tidak dapat memulai tunggu konfirmasi karena servis sudah selesai.")
            if record.controller_tunggu_konfirmasi_mulai:
                raise ValidationError("Tunggu konfirmasi sudah dimulai sebelumnya.")
            
            # Periksa peran pengguna sebelum melakukan perubahan apa pun
            if self.env.user.pitcar_role != 'controller':
                raise UserError("Hanya Controller yang dapat memulai tunggu konfirmasi.")
            
            record.controller_tunggu_konfirmasi_mulai = fields.Datetime.now()

    # Aksi untuk menyelesaikan tunggu konfirmasi
    def action_tunggu_konfirmasi_selesai(self):
        for record in self:
            if not record.controller_tunggu_konfirmasi_mulai:
                raise ValidationError("Anda tidak dapat menyelesaikan tunggu konfirmasi sebelum memulainya.")
            if record.controller_tunggu_konfirmasi_selesai:
                raise ValidationError("Tunggu konfirmasi sudah diselesaikan sebelumnya.")
            
            # Periksa peran pengguna sebelum melakukan perubahan apa pun
            if self.env.user.pitcar_role != 'controller':
                raise UserError("Hanya Controller yang dapat menyelesaikan tunggu konfirmasi.")
            
            record.controller_tunggu_konfirmasi_selesai = fields.Datetime.now()

    # You might want to add some validation or additional logic
    @api.constrains('controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai')
    def _check_tunggu_part1_times(self):
        for record in self:
            if record.controller_tunggu_part1_mulai and record.controller_tunggu_part1_selesai:
                if record.controller_tunggu_part1_selesai < record.controller_tunggu_part1_mulai:
                    raise ValidationError("Waktu selesai tunggu part 1 tidak boleh lebih awal dari waktu mulai.")
    
    def action_record_fo_unit_keluar(self):
        for record in self:
            if not record.controller_mulai_servis:
                raise exceptions.ValidationError("Tidak dapat mencatat waktu. Servis belum dimulai.")
            if not record.sa_mulai_penerimaan:
                raise exceptions.ValidationError("Tidak dapat mencatat waktu. Customer belum diterima/dilayani.")
            if not record.sa_cetak_pkb:
                raise exceptions.ValidationError("Tidak dapat mencatat waktu. PKB belum dicetak.")
            if not record.controller_selesai:
                raise exceptions.ValidationError("Tidak dapat mencatat waktu. Servis belum selesai.")
            if record.fo_unit_keluar:
                raise exceptions.ValidationError("Waktu unit keluar sudah dicatat sebelumnya.")
            
            self.ensure_one()
            tz = pytz.timezone('Asia/Jakarta')
            local_dt = datetime.now(tz)
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
            
            self.fo_unit_keluar = utc_dt
            
            body = f"""
            <p><strong>Unit Keluar</strong></p>
            <ul>
                <li>Dicatat oleh: {self.env.user.name}</li>
                <li>Waktu catat: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
            </ul>
            """
            self.message_post(body=body, message_type='notification')

    def action_job_stop_lain_mulai(self):
        self.ensure_one()

        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat melakukan job stop lain.")
            
        self.controller_job_stop_lain_mulai = fields.Datetime.now()

    def action_job_stop_lain_selesai(self):
        self.ensure_one()
        # Periksa peran pengguna sebelum melakukan perubahan apa pun
        if self.env.user.pitcar_role != 'controller':
            raise UserError("Hanya Controller yang dapat menyelesaikan job stop lain.")
        
        self.controller_job_stop_lain_selesai = fields.Datetime.now()

    # PERHITUNGAN LEAD TIME
    # 1. LEAD TIME TUNGGU PENERIMAAN
    lead_time_tunggu_penerimaan = fields.Float(string="Lead Time Tunggu Penerimaan (hours)", compute="_compute_lead_time_tunggu_penerimaan", store=True)

    @api.depends('sa_jam_masuk', 'sa_mulai_penerimaan')
    def _compute_lead_time_tunggu_penerimaan(self):
        for order in self:
            if order.sa_jam_masuk and order.sa_mulai_penerimaan:
                delta = order.sa_mulai_penerimaan - order.sa_jam_masuk
                order.lead_time_tunggu_penerimaan = delta.total_seconds() / 3600
            else:
                order.lead_time_tunggu_penerimaan = 0

    # 2. LEAD TIME PENERIMAAN
    lead_time_penerimaan = fields.Float(string="Lead Time Penerimaan (hours)", compute="_compute_lead_time_penerimaan", store=True)

    @api.depends('sa_mulai_penerimaan', 'sa_cetak_pkb')
    def _compute_lead_time_penerimaan(self):
        for order in self:
            if order.sa_mulai_penerimaan and order.sa_cetak_pkb:
                delta = order.sa_cetak_pkb - order.sa_mulai_penerimaan
                order.lead_time_penerimaan = delta.total_seconds() / 3600
            else:
                order.lead_time_penerimaan = 0

    # 3. LEAD TIME TUNGGU SERVIS
    lead_time_tunggu_servis = fields.Float(string="Lead Time Tunggu Servis (hours)", compute="_compute_lead_time_tunggu_servis", store=True)

    @api.depends('sa_cetak_pkb', 'controller_mulai_servis')
    def _compute_lead_time_tunggu_servis(self):
        for order in self:
            if order.sa_cetak_pkb and order.controller_mulai_servis:
                delta = order.controller_mulai_servis - order.sa_cetak_pkb
                order.lead_time_tunggu_servis = delta.total_seconds() / 3600
            else:
                order.lead_time_tunggu_servis = 0

    # 4. LEAD TIME ESTIMASI DURASI PENGERJAAN
    estimasi_durasi_pengerjaan = fields.Float(string="Estimasi Durasi Pengerjaan (hours)", compute="_compute_estimasi_durasi_pengerjaan", store=True)

    @api.depends('controller_estimasi_mulai', 'controller_estimasi_selesai')
    def _compute_estimasi_durasi_pengerjaan(self):
        for order in self:
            if order.controller_estimasi_mulai and order.controller_estimasi_selesai:
                delta = order.controller_estimasi_selesai - order.controller_estimasi_mulai
                order.estimasi_durasi_pengerjaan = delta.total_seconds() / 3600
            else:
                order.estimasi_durasi_pengerjaan = 0

    # 5. LEAD TIME TUNGGU KONFIRMASI 
    lead_time_tunggu_konfirmasi = fields.Float(string="Lead Time Tunggu Konfirmasi (hours)", compute="_compute_lead_time_tunggu_konfirmasi", store=True)

    @api.depends('controller_tunggu_konfirmasi_mulai', 'controller_tunggu_konfirmasi_selesai')
    def _compute_lead_time_tunggu_konfirmasi(self):
        for order in self:
            waktu_tunggu = order.hitung_waktu_kerja_efektif(
                order.controller_tunggu_konfirmasi_mulai,
                order.controller_tunggu_konfirmasi_selesai,
                is_normal_break=False  # Ganti is_service_time menjadi is_normal_break
            )
            order.lead_time_tunggu_konfirmasi = waktu_tunggu.total_seconds() / 3600

    # 6. LEAD TIME TUNGGU PART 1
    lead_time_tunggu_part1 = fields.Float(string="Lead Time Tunggu Part 1 (hours)", compute="_compute_lead_time_tunggu_part1", store=True)

    @api.depends('controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai')
    def _compute_lead_time_tunggu_part1(self):
        for order in self:
            waktu_tunggu = order.hitung_waktu_kerja_efektif(
                order.controller_tunggu_part1_mulai,
                order.controller_tunggu_part1_selesai,
                is_normal_break=False  # Ganti is_service_time menjadi is_normal_break
            )
            order.lead_time_tunggu_part1 = waktu_tunggu.total_seconds() / 3600

    # 7. LEAD TIME TUNGGU PART 2
    lead_time_tunggu_part2 = fields.Float(string="Lead Time Tunggu Part 2 (hours)", compute="_compute_lead_time_tunggu_part2", store=True)

    @api.depends('controller_tunggu_part2_mulai', 'controller_tunggu_part2_selesai')
    def _compute_lead_time_tunggu_part2(self):
        for order in self:
            waktu_tunggu = order.hitung_waktu_kerja_efektif(
                order.controller_tunggu_part2_mulai,
                order.controller_tunggu_part2_selesai,
                is_normal_break=False  # Ganti is_service_time menjadi is_normal_break
            )
            order.lead_time_tunggu_part2 = waktu_tunggu.total_seconds() / 3600

    # 8. LEAD TIME ISTIRAHAT SHIFT 1
    lead_time_istirahat = fields.Float(string="Lead Time Istirahat (hours)", compute="_compute_lead_time_istirahat", store=True)

    @api.depends('controller_istirahat_shift1_mulai', 'controller_istirahat_shift1_selesai')
    def _compute_lead_time_istirahat(self):
        for order in self:
            if order.controller_istirahat_shift1_mulai and order.controller_istirahat_shift1_selesai:
                delta = order.controller_istirahat_shift1_selesai - order.controller_istirahat_shift1_mulai
                order.lead_time_istirahat = delta.total_seconds() / 3600
            else:
                order.lead_time_istirahat = 0

    # 9. LEAD TIME TUNGGU SUBLET DAN JOB STOP LAIN
     # Compute methods untuk field baru
    @api.depends('controller_tunggu_sublet_mulai', 'controller_tunggu_sublet_selesai')
    def _compute_lead_time_tunggu_sublet(self):
        for order in self:
            if order.controller_tunggu_sublet_mulai and order.controller_tunggu_sublet_selesai:
                waktu_tunggu = order.hitung_waktu_kerja_efektif(
                    order.controller_tunggu_sublet_mulai,
                    order.controller_tunggu_sublet_selesai,
                    is_normal_break=False
                )
                order.lead_time_tunggu_sublet = waktu_tunggu.total_seconds() / 3600
            else:
                order.lead_time_tunggu_sublet = 0

    @api.depends('need_other_job_stop', 'controller_job_stop_lain_mulai', 'controller_job_stop_lain_selesai')
    def _compute_lead_time_job_stop_lain(self):
        for order in self:
            if order.need_other_job_stop == 'yes' and \
               order.controller_job_stop_lain_mulai and \
               order.controller_job_stop_lain_selesai:
                waktu_tunggu = order.hitung_waktu_kerja_efektif(
                    order.controller_job_stop_lain_mulai,
                    order.controller_job_stop_lain_selesai,
                    is_normal_break=False
                )
                order.lead_time_job_stop_lain = waktu_tunggu.total_seconds() / 3600
            else:
                order.lead_time_job_stop_lain = 0

    # 10. LEAD TIME SERVIS
    overall_lead_time = fields.Float(string="Overall Lead Time (jam)", compute="_compute_overall_lead_time", store=True)

    @api.depends('sa_jam_masuk', 'fo_unit_keluar', 'controller_selesai')
    def _compute_overall_lead_time(self):
        for order in self:
            try:
                if not order.sa_jam_masuk:
                    order.overall_lead_time = 0
                    continue
                    
                # Tentukan waktu selesai berdasarkan prioritas:
                # 1. fo_unit_keluar (jika ada)
                # 2. controller_selesai (sebagai fallback)
                waktu_selesai = order.fo_unit_keluar or order.controller_selesai
                
                if waktu_selesai:
                    # Hitung selisih waktu
                    delta = waktu_selesai - order.sa_jam_masuk
                    order.overall_lead_time = delta.total_seconds() / 3600
                    
                    _logger.info(f"""
                        Perhitungan Overall Lead Time untuk {order.name}:
                        - Waktu Masuk: {order.sa_jam_masuk}
                        - Waktu Selesai: {waktu_selesai}
                        - Menggunakan: {'Unit Keluar' if order.fo_unit_keluar else 'Controller Selesai'}
                        - Overall Lead Time: {order.overall_lead_time:.2f} jam
                    """)
                else:
                    order.overall_lead_time = 0
                    
            except Exception as e:
                _logger.error(f"Error dalam compute overall lead time: {str(e)}")
                order.overall_lead_time = 0
    # def action_recompute_lead_time(self):
    #     """
    #     Method untuk memaksa recompute semua lead time
    #     Dapat dipanggil dari button di form view atau server action
    #     """
    #     orders = self.search([])
    #     # Paksa compute ulang dengan mengosongkan semua field terkait
    #     orders.write({
    #         'lead_time_servis': 0,
    #         'total_lead_time_servis': 0,
    #         'lead_time_tunggu_konfirmasi': 0,
    #         'lead_time_tunggu_part1': 0, 
    #         'lead_time_tunggu_part2': 0,
    #         'lead_time_istirahat': 0,
    #         'overall_lead_time': 0,
    #         'is_overnight': False
    #     })
        
    #     # Trigger compute untuk semua field terkait
    #     for order in orders:
    #         order._compute_lead_time_tunggu_konfirmasi()
    #         order._compute_lead_time_tunggu_part1()
    #         order._compute_lead_time_tunggu_part2()
    #         order._compute_lead_time_istirahat()
    #         order._compute_lead_time_servis()
    #         order._compute_overall_lead_time()
            
    #         _logger.info(f"""
    #             Recompute selesai untuk {order.name}:
    #             - Lead Time Servis: {order.lead_time_servis:.2f} jam
    #             - Total Lead Time: {order.total_lead_time_servis:.2f} jam
    #             - Tunggu Konfirmasi: {order.lead_time_tunggu_konfirmasi:.2f} jam
    #             - Tunggu Part 1: {order.lead_time_tunggu_part1:.2f} jam
    #             - Tunggu Part 2: {order.lead_time_tunggu_part2:.2f} jam
    #             - Istirahat: {order.lead_time_istirahat:.2f} jam
    #             - Overall Lead Time: {order.overall_lead_time:.2f} jam
    #         """)
    #     return True
    
    def action_recompute_single_order(self):
        """
        Method untuk recompute satu order saja
        Dapat dipanggil dari button di form view
        """
        self.ensure_one()
        # Reset semua field terkait
        self.write({
            'lead_time_servis': 0,
            'total_lead_time_servis': 0,
            'lead_time_tunggu_konfirmasi': 0,
            'lead_time_tunggu_part1': 0,
            'lead_time_tunggu_part2': 0,
            'lead_time_istirahat': 0,
            'overall_lead_time': 0,
            'is_overnight': False
        })
        
        # Compute ulang
        self._compute_lead_time_tunggu_konfirmasi()
        self._compute_lead_time_tunggu_part1()
        self._compute_lead_time_tunggu_part2()
        self._compute_lead_time_istirahat()
        self._compute_lead_time_servis()
        self._compute_overall_lead_time()
        
        _logger.info(f"""
            Recompute selesai untuk {self.name}:
            - Lead Time Servis: {self.lead_time_servis:.2f} jam
            - Total Lead Time: {self.total_lead_time_servis:.2f} jam
            - Tunggu Konfirmasi: {self.lead_time_tunggu_konfirmasi:.2f} jam
            - Tunggu Part 1: {self.lead_time_tunggu_part1:.2f} jam
            - Tunggu Part 2: {self.lead_time_tunggu_part2:.2f} jam
            - Istirahat: {self.lead_time_istirahat:.2f} jam
            - Overall Lead Time: {self.overall_lead_time:.2f} jam
        """)
        return True


    # @api.depends('controller_mulai_servis', 'controller_selesai',
    #      'controller_tunggu_konfirmasi_mulai', 'controller_tunggu_konfirmasi_selesai',
    #      'controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai',
    #      'controller_tunggu_part2_mulai', 'controller_tunggu_part2_selesai',
    #      'controller_tunggu_sublet_mulai', 'controller_tunggu_sublet_selesai',
    #      'controller_istirahat_shift1_mulai', 'controller_istirahat_shift1_selesai')
    # def _compute_lead_time_servis(self):
    #     for order in self:
    #         try:
    #             # Reset nilai default
    #             order.lead_time_servis = 0
    #             order.total_lead_time_servis = 0
    #             order.is_overnight = False

    #             # Validasi dasar
    #             if not order.controller_mulai_servis or not order.controller_selesai or \
    #             order.controller_selesai <= order.controller_mulai_servis:
    #                 _logger.info(f"{order.name}: Waktu mulai/selesai tidak valid")
    #                 continue

    #             _logger.info(f"""
    #                 Mulai perhitungan lead time untuk {order.name}:
    #                 Mulai Servis: {order.controller_mulai_servis}
    #                 Selesai Servis: {order.controller_selesai}
    #             """)

    #             # 1. Hitung total waktu dalam jam kerja (08:00-17:00)
    #             total_waktu = timedelta()
    #             current_date = order.controller_mulai_servis.date()
    #             end_date = order.controller_selesai.date()

    #             while current_date <= end_date:
    #                 # Set jam kerja untuk hari ini
    #                 day_start = datetime.combine(current_date, time(8, 0))  # 08:00
    #                 day_end = datetime.combine(current_date, time(17, 0))   # 17:00
                    
    #                 # Tentukan waktu efektif start dan end untuk hari ini
    #                 effective_start = max(day_start, order.controller_mulai_servis) if current_date == order.controller_mulai_servis.date() else day_start
    #                 effective_end = min(day_end, order.controller_selesai) if current_date == order.controller_selesai.date() else day_end
                    
    #                 if effective_end > effective_start:
    #                     total_waktu += (effective_end - effective_start)
                    
    #                 current_date += timedelta(days=1)

    #             order.total_lead_time_servis = total_waktu.total_seconds() / 3600
    #             _logger.info(f"Total waktu efektif: {order.total_lead_time_servis} jam")

    #             # 2. Hitung total waktu job stop dalam jam kerja
    #             total_job_stop = timedelta()
                
    #             # Dictionary untuk semua job stop
    #             job_stops = {
    #                 'Tunggu Konfirmasi': (order.controller_tunggu_konfirmasi_mulai, order.controller_tunggu_konfirmasi_selesai),
    #                 'Tunggu Part 1': (order.controller_tunggu_part1_mulai, order.controller_tunggu_part1_selesai),
    #                 'Tunggu Part 2': (order.controller_tunggu_part2_mulai, order.controller_tunggu_part2_selesai),
    #                 'Tunggu Sublet': (order.controller_tunggu_sublet_mulai, order.controller_tunggu_sublet_selesai),
    #                 'Istirahat': (order.controller_istirahat_shift1_mulai, order.controller_istirahat_shift1_selesai)
    #             }

    #             # Hitung setiap job stop dalam jam kerja
    #             for job_name, (start, end) in job_stops.items():
    #                 if start and end and end > start:
    #                     job_total = timedelta()
    #                     current = start.date()
    #                     job_end_date = end.date()
                        
    #                     while current <= job_end_date:
    #                         day_start = datetime.combine(current, time(8, 0))
    #                         day_end = datetime.combine(current, time(17, 0))
                            
    #                         job_effective_start = max(day_start, start) if current == start.date() else day_start
    #                         job_effective_end = min(day_end, end) if current == end.date() else day_end
                            
    #                         if job_effective_end > job_effective_start:
    #                             job_total += (job_effective_end - job_effective_start)
                            
    #                         current += timedelta(days=1)
                            
    #                     total_job_stop += job_total
    #                     _logger.info(f"{job_name}: {job_total.total_seconds() / 3600} jam")

    #             # 3. Hitung waktu istirahat otomatis (12:00-13:00)
    #             # Hanya jika tidak ada istirahat manual yang diinput
    #             if not (order.controller_istirahat_shift1_mulai and order.controller_istirahat_shift1_selesai):
    #                 current_date = order.controller_mulai_servis.date()
    #                 end_date = order.controller_selesai.date()
    #                 istirahat_auto = timedelta()

    #                 while current_date <= end_date:
    #                     istirahat_start = datetime.combine(current_date, time(12, 0))
    #                     istirahat_end = datetime.combine(current_date, time(13, 0))
                        
    #                     # Hanya hitung istirahat jika dalam rentang jam kerja dan overlap dengan waktu servis
    #                     if (order.controller_mulai_servis <= istirahat_end and 
    #                         order.controller_selesai >= istirahat_start):
    #                         overlap_start = max(order.controller_mulai_servis, istirahat_start)
    #                         overlap_end = min(order.controller_selesai, istirahat_end)
    #                         if overlap_end > overlap_start:
    #                             istirahat_auto += (overlap_end - overlap_start)
    #                             _logger.info(f"Istirahat otomatis pada {current_date}: {(overlap_end - overlap_start).total_seconds() / 3600} jam")
                        
    #                     current_date += timedelta(days=1)

    #                 total_job_stop += istirahat_auto

    #             # 4. Hitung lead time bersih
    #             total_seconds = total_waktu.total_seconds()
    #             job_stop_seconds = total_job_stop.total_seconds()
                
    #             # Lead time bersih = Total waktu efektif - Total job stop
    #             order.lead_time_servis = max(0, (total_seconds - job_stop_seconds) / 3600)

    #             # Set flag menginap
    #             order.is_overnight = (order.controller_selesai.date() - order.controller_mulai_servis.date()).days > 0

    #             _logger.info(f"""
    #                 Hasil akhir {order.name}:
    #                 - Total Lead Time Efektif: {order.total_lead_time_servis:.2f} jam
    #                 - Total Job Stop: {job_stop_seconds / 3600:.2f} jam
    #                 - Lead Time Bersih: {order.lead_time_servis:.2f} jam
    #                 - Menginap: {order.is_overnight}
    #             """)

    #         except Exception as e:
    #             _logger.error(f"Error pada perhitungan {order.name}: {str(e)}")
    #             order.lead_time_servis = 0
    #             order.total_lead_time_servis = 0

    @api.depends('controller_mulai_servis', 'controller_selesai',
             'controller_tunggu_konfirmasi_mulai', 'controller_tunggu_konfirmasi_selesai',
             'controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai',
             'controller_tunggu_part2_mulai', 'controller_tunggu_part2_selesai',
             'controller_tunggu_sublet_mulai', 'controller_tunggu_sublet_selesai',
             'controller_job_stop_lain_mulai', 'controller_job_stop_lain_selesai')  # Tambahkan dependency job stop lain
    def _compute_lead_time_servis(self):
        for order in self:
            try:
                if not order.controller_mulai_servis or not order.controller_selesai:
                    order.lead_time_servis = 0
                    order.total_lead_time_servis = 0
                    order.is_overnight = False
                    continue

                # Set timezone dan convert waktu
                tz = pytz.timezone('Asia/Jakarta')
                mulai_local = pytz.utc.localize(fields.Datetime.from_string(order.controller_mulai_servis)).astimezone(tz)
                selesai_local = pytz.utc.localize(fields.Datetime.from_string(order.controller_selesai)).astimezone(tz)

                _logger.info(f"""
                    Mulai hitung lead time untuk {order.name}:
                    Mulai: {mulai_local.strftime('%Y-%m-%d %H:%M:%S')}
                    Selesai: {selesai_local.strftime('%Y-%m-%d %H:%M:%S')}
                """)

                total_duration = timedelta()
                current_date = mulai_local.date()
                end_date = selesai_local.date()

                # Loop untuk setiap hari
                while current_date <= end_date:
                    # Set waktu awal dan akhir untuk hari ini
                    if current_date == mulai_local.date():
                        day_start = max(mulai_local, tz.localize(datetime.combine(current_date, time(8, 0))))
                    else:
                        day_start = tz.localize(datetime.combine(current_date, time(8, 0)))

                    if current_date == selesai_local.date():
                        day_end = min(selesai_local, tz.localize(datetime.combine(current_date, time(17, 0))))
                    else:
                        day_end = tz.localize(datetime.combine(current_date, time(17, 0)))

                    # Set waktu istirahat untuk hari ini
                    break_start = tz.localize(datetime.combine(current_date, time(12, 0)))
                    break_end = tz.localize(datetime.combine(current_date, time(13, 0)))

                    # Validasi waktu kerja valid
                    if day_start.time() < time(8, 0):
                        day_start = tz.localize(datetime.combine(current_date, time(8, 0)))
                    if day_end.time() > time(17, 0):
                        day_end = tz.localize(datetime.combine(current_date, time(17, 0)))

                    # Hitung durasi kerja efektif
                    if day_end > day_start:
                        # Case 1: Overlap dengan istirahat
                        if day_start < break_start and day_end > break_end:
                            morning_duration = break_start - day_start
                            afternoon_duration = day_end - break_end
                            total_duration += morning_duration + afternoon_duration
                            
                        # Case 2: Hanya overlap dengan akhir istirahat
                        elif day_start < break_end and day_end > break_end:
                            duration = day_end - break_end
                            total_duration += duration

                        # Case 3: Hanya overlap dengan awal istirahat
                        elif day_start < break_start and day_end > break_start:
                            duration = break_start - day_start
                            total_duration += duration

                        # Case 4: Tidak overlap dengan istirahat
                        else:
                            duration = day_end - day_start
                            total_duration += duration

                    current_date += timedelta(days=1)

                # Calculate job stops including 'job stop lain'
                job_stops = []
                
                # Helper function untuk menghitung waktu efektif job stop
                def calculate_stop_duration(start, end):
                    if not start or not end:
                        return 0
                    
                    start_dt = pytz.utc.localize(fields.Datetime.from_string(start))
                    end_dt = pytz.utc.localize(fields.Datetime.from_string(end))
                    
                    start_local = start_dt.astimezone(tz)
                    end_local = end_dt.astimezone(tz)
                    
                    stop_duration = timedelta()
                    current = start_local.date()
                    stop_end_date = end_local.date()
                    
                    while current <= stop_end_date:
                        # Get day's boundaries
                        if current == start_local.date():
                            day_start = max(start_local, tz.localize(datetime.combine(current, time(8, 0))))
                        else:
                            day_start = tz.localize(datetime.combine(current, time(8, 0)))

                        if current == end_local.date():
                            day_end = min(end_local, tz.localize(datetime.combine(current, time(17, 0))))
                        else:
                            day_end = tz.localize(datetime.combine(current, time(17, 0)))

                        # Adjust for lunch break
                        break_start = tz.localize(datetime.combine(current, time(12, 0)))
                        break_end = tz.localize(datetime.combine(current, time(13, 0)))

                        if day_end > day_start:
                            if day_start < break_start and day_end > break_end:
                                morning = break_start - day_start
                                afternoon = day_end - break_end
                                stop_duration += morning + afternoon
                            elif day_start < break_end and day_end > break_end:
                                stop_duration += day_end - break_end
                            elif day_start < break_start and day_end > break_start:
                                stop_duration += break_start - day_start
                            else:
                                stop_duration += day_end - day_start

                        current += timedelta(days=1)
                    
                    return stop_duration.total_seconds() / 3600

                # Calculate each job stop
                stops_to_calculate = [
                    ('Tunggu Konfirmasi', order.controller_tunggu_konfirmasi_mulai, order.controller_tunggu_konfirmasi_selesai),
                    ('Tunggu Part 1', order.controller_tunggu_part1_mulai, order.controller_tunggu_part1_selesai),
                    ('Tunggu Part 2', order.controller_tunggu_part2_mulai, order.controller_tunggu_part2_selesai),
                    ('Tunggu Sublet', order.controller_tunggu_sublet_mulai, order.controller_tunggu_sublet_selesai),
                    ('Job Stop Lain', order.controller_job_stop_lain_mulai, order.controller_job_stop_lain_selesai)  # Tambahkan job stop lain
                ]

                for stop_name, start, end in stops_to_calculate:
                    if start and end:
                        duration = calculate_stop_duration(start, end)
                        job_stops.append(duration)
                        _logger.info(f"{stop_name}: {duration:.2f} jam")

                # Convert total durasi ke jam
                total_hours = total_duration.total_seconds() / 3600
                total_stops = sum(job_stops)

                # Set final values
                order.total_lead_time_servis = total_hours
                order.lead_time_servis = max(0, total_hours - total_stops)
                order.is_overnight = end_date > mulai_local.date()

                _logger.info(f"""
                    Hasil akhir {order.name}:
                    - Total Lead Time: {total_hours:.2f} jam
                    - Total Job Stops: {total_stops:.2f} jam
                    - Lead Time Bersih: {order.lead_time_servis:.2f} jam
                    - Menginap: {order.is_overnight}
                """)

            except Exception as e:
                _logger.error(f"Error menghitung lead time untuk {order.name}: {str(e)}")
                order.lead_time_servis = 0
                order.total_lead_time_servis = 0
                order.is_overnight = False

    def calculate_effective_hours(self, start_dt, end_dt):
        """
        Hitung jam efektif antara dua waktu, dengan mempertimbangkan:
        - Jam kerja (08:00-17:00)
        - Waktu istirahat (12:00-13:00)
        """
        if not start_dt or not end_dt or end_dt <= start_dt:
            return 0

        tz = pytz.timezone('Asia/Jakarta')
        start_local = pytz.utc.localize(start_dt).astimezone(tz)
        end_local = pytz.utc.localize(end_dt).astimezone(tz)

        total_hours = 0
        current_date = start_local.date()
        end_date = end_local.date()

        while current_date <= end_date:
            # Set waktu untuk hari ini
            if current_date == start_local.date():
                day_start = start_local
            else:
                day_start = tz.localize(datetime.combine(current_date, time(8, 0)))

            if current_date == end_local.date():
                day_end = end_local
            else:
                day_end = tz.localize(datetime.combine(current_date, time(17, 0)))

            # Set waktu istirahat
            break_start = tz.localize(datetime.combine(current_date, time(12, 0)))
            break_end = tz.localize(datetime.combine(current_date, time(13, 0)))

            # Hitung jam efektif
            if day_start < break_start and day_end > break_end:
                # Ada 2 periode: sebelum dan sesudah istirahat
                morning_hours = (break_start - day_start).total_seconds() / 3600
                afternoon_hours = (day_end - break_end).total_seconds() / 3600
                total_hours += morning_hours + afternoon_hours
            elif day_start < break_end and day_end > break_end:
                # Hanya periode setelah istirahat
                total_hours += (day_end - break_end).total_seconds() / 3600
            elif day_start < break_start and day_end > break_start:
                # Hanya periode sebelum istirahat
                total_hours += (break_start - day_start).total_seconds() / 3600
            else:
                # Tidak overlap dengan istirahat
                total_hours += (day_end - day_start).total_seconds() / 3600

            current_date += timedelta(days=1)

        return total_hours

    def recompute_productive_hours(self):
        """
        Hitung ulang productive hours untuk setiap mekanik dalam order
        """
        if not self.controller_mulai_servis or not self.controller_selesai:
            return {}

        result = {}
        
        for mechanic in self.car_mechanic_id_new:
            if not mechanic.employee_id:
                continue

            # Ambil attendance untuk periode servis
            attendances = self.env['hr.attendance'].sudo().search([
                ('employee_id', '=', mechanic.employee_id.id),
                ('check_in', '<=', self.controller_selesai),
                ('check_out', '>=', self.controller_mulai_servis),
                ('check_out', '!=', False)
            ])

            productive_hours = 0
            for attendance in attendances:
                # Hitung overlap antara waktu servis dan attendance
                overlap_start = max(self.controller_mulai_servis, attendance.check_in)
                overlap_end = min(self.controller_selesai, attendance.check_out)
                
                # Hitung jam efektif
                effective_hours = self.calculate_effective_hours(overlap_start, overlap_end)
                productive_hours += effective_hours

            result[mechanic.id] = productive_hours

        return result



    # Di model sale.order, tambahkan method:
    def action_recompute_lead_time(self):
        """Method untuk memaksa recompute lead time servis"""
        self.ensure_one()
        try:
            # Catat nilai sebelum recompute untuk logging
            old_total = self.total_lead_time_servis
            old_net = self.lead_time_servis

            # Force recompute dengan invalidate cache
            self.invalidate_cache(['lead_time_servis', 'total_lead_time_servis'])
            self._compute_lead_time_servis()

            # Log perubahan ke chatter
            message = f"""
                <p><strong>Lead Time Re-calculation Result</strong></p>
                <ul>
                    <li>Total Lead Time: {old_total:.2f} → {self.total_lead_time_servis:.2f} jam</li>
                    <li>Lead Time Bersih: {old_net:.2f} → {self.lead_time_servis:.2f} jam</li>
                    <li>Recomputed by: {self.env.user.name}</li>
                </ul>
            """
            self.message_post(body=message, message_type='notification')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Lead time berhasil dihitung ulang',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f"Error in recompute lead time for {self.name}: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Gagal menghitung ulang lead time: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    # Tambahkan method untuk recompute batch/multiple orders
    def action_recompute_lead_time_batch(self):
        """Method untuk recompute multiple orders sekaligus"""
        success_count = 0
        error_count = 0
        
        for order in self:
            try:
                order.invalidate_cache(['lead_time_servis', 'total_lead_time_servis'])
                order._compute_lead_time_servis()
                success_count += 1
            except Exception as e:
                _logger.error(f"Error recomputing lead time for order {order.name}: {str(e)}")
                error_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Recompute Complete',
                'message': f'Successfully recomputed {success_count} orders. {error_count} errors.',
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_recompute_all_orders(self):
        """Recompute lead time untuk semua order yang ditampilkan di list view"""
        for order in self:
            order.action_recompute_lead_time()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Successfully recomputed {len(self)} orders',
                'type': 'success',
                'sticky': False,
            }
        }

    def hitung_waktu_kerja_efektif(self, waktu_mulai, waktu_selesai, is_normal_break=True):
        """
        Menghitung waktu kerja efektif dengan mempertimbangkan istirahat
        @param waktu_mulai: datetime - Waktu mulai
        @param waktu_selesai: datetime - Waktu selesai
        @param is_normal_break: boolean - True jika menggunakan perhitungan istirahat normal
        """
        if not waktu_mulai or not waktu_selesai or waktu_selesai <= waktu_mulai:
            return timedelta()

        BENGKEL_BUKA = time(8, 0)
        BENGKEL_TUTUP = time(17, 0)
        ISTIRAHAT_MULAI = time(12, 0)
        ISTIRAHAT_SELESAI = time(13, 0)

        waktu_kerja = timedelta()
        current_date = waktu_mulai.date()
        end_date = waktu_selesai.date()

        while current_date <= end_date:
            # Tentukan waktu mulai dan selesai untuk hari ini
            if current_date == waktu_mulai.date():
                start_time = waktu_mulai.time()
            else:
                start_time = BENGKEL_BUKA if is_normal_break else time(0, 0)

            if current_date == waktu_selesai.date():
                end_time = waktu_selesai.time()
            else:
                end_time = BENGKEL_TUTUP if is_normal_break else time(23, 59, 59)

            # Batasi dengan jam kerja bengkel jika menggunakan istirahat normal
            if is_normal_break:
                if start_time < BENGKEL_BUKA:
                    start_time = BENGKEL_BUKA
                if end_time > BENGKEL_TUTUP:
                    end_time = BENGKEL_TUTUP

            if start_time < end_time:
                day_start = datetime.combine(current_date, start_time)
                day_end = datetime.combine(current_date, end_time)
                
                work_time = day_end - day_start

                # Kurangi waktu istirahat jika perlu
                if is_normal_break:
                    istirahat_start = datetime.combine(current_date, ISTIRAHAT_MULAI)
                    istirahat_end = datetime.combine(current_date, ISTIRAHAT_SELESAI)

                    if day_start < istirahat_end and day_end > istirahat_start:
                        overlap_start = max(day_start, istirahat_start)
                        overlap_end = min(day_end, istirahat_end)
                        istirahat_duration = overlap_end - overlap_start
                        work_time -= istirahat_duration

                waktu_kerja += work_time

            current_date += timedelta(days=1)

        return waktu_kerja

     # Fields yang dipertahankan
    lead_time_calculation_details = fields.Text(
        "Detail Perhitungan Lead Time", 
        compute='_compute_lead_time_calculation_details',
        help="Menampilkan detail rumus dan perhitungan lead time"
    )
    
    should_show_calculation = fields.Boolean(
        "Tampilkan Detail Perhitungan",
        default=False,
        help="Toggle untuk menampilkan/menyembunyikan detail perhitungan"
    )

    # Method yang dipertahankan dengan sedikit modifikasi
    @api.depends(
        'lead_time_servis',
        'total_lead_time_servis',
        'controller_mulai_servis',
        'controller_selesai',
        'controller_tunggu_konfirmasi_mulai',
        'controller_tunggu_konfirmasi_selesai',
        'controller_tunggu_part1_mulai',
        'controller_tunggu_part1_selesai',
        'controller_tunggu_part2_mulai',
        'controller_tunggu_part2_selesai',
        'controller_istirahat_shift1_mulai',
        'controller_istirahat_shift1_selesai'
    )
    def _compute_lead_time_calculation_details(self):
        for order in self:
            if not order.should_show_calculation:
                order.lead_time_calculation_details = False
                continue

            # Format helper functions (dipertahankan)
            def format_time(dt):
                if not dt:
                    return "-"
                return dt.strftime("%H:%M")

            def format_duration(hours):
                if not hours:
                    return "0:00"
                hours_int = int(hours)
                minutes = int((hours - hours_int) * 60)
                return f"{hours_int}:{minutes:02d}"

            # Detail calculation text (dipertahankan)
            details = f"""
📊 DETAIL PERHITUNGAN LEAD TIME

1️⃣ Total Lead Time Unit:
   • Mulai Servis: {format_time(order.controller_mulai_servis)}
   • Selesai Servis: {format_time(order.controller_selesai)}
   • Total Waktu: {format_duration(order.total_lead_time_servis)}

2️⃣ Waktu Job Stop:
   A. Tunggu Konfirmasi:
      • Mulai: {format_time(order.controller_tunggu_konfirmasi_mulai)}
      • Selesai: {format_time(order.controller_tunggu_konfirmasi_selesai)}
      • Durasi: {format_duration(order.lead_time_tunggu_konfirmasi)}

   B. Tunggu Part 1:
      • Mulai: {format_time(order.controller_tunggu_part1_mulai)}
      • Selesai: {format_time(order.controller_tunggu_part1_selesai)}
      • Durasi: {format_duration(order.lead_time_tunggu_part1)}

   C. Tunggu Part 2:
      • Mulai: {format_time(order.controller_tunggu_part2_mulai)}
      • Selesai: {format_time(order.controller_tunggu_part2_selesai)}
      • Durasi: {format_duration(order.lead_time_tunggu_part2)}

   D. Istirahat:
      • Mulai: {format_time(order.controller_istirahat_shift1_mulai)}
      • Selesai: {format_time(order.controller_istirahat_shift1_selesai)}
      • Durasi: {format_duration(order.lead_time_istirahat)}

3️⃣ Rumus Perhitungan:
   Lead Time Servis = Total Lead Time - Total Job Stop - Istirahat Otomatis
   {format_duration(order.lead_time_servis)} = {format_duration(order.total_lead_time_servis)} - (Job Stops + Istirahat)

ℹ️ Catatan:
• Istirahat otomatis (12:00-13:00) dihitung jika tidak ada input manual
• Semua job stop yang overlap dihitung sekali
• Waktu dihitung dalam jam kerja (08:00-17:00)
            """
            order.lead_time_calculation_details = details

    def toggle_calculation_details(self):
        """Toggle tampilan detail perhitungan"""
        self.should_show_calculation = not self.should_show_calculation
        return True

    # Method baru untuk timeline
    def _get_timeline_events(self):
        """
        Method baru untuk menghitung events timeline
        """
        self.ensure_one()
        events = []
        
        # Hanya proses jika ada waktu mulai dan selesai
        if not self.controller_mulai_servis or not self.controller_selesai:
            return events

        # Hitung total durasi untuk posisi relatif
        total_duration = (self.controller_selesai - self.controller_mulai_servis).total_seconds()
        
        # Fungsi helper untuk menghitung posisi
        def calculate_position(time):
            if not time:
                return 0
            time_diff = (time - self.controller_mulai_servis).total_seconds()
            return min(100, max(0, (time_diff / total_duration) * 100))

        # Tambahkan events
        events.append({
            'time': self.controller_mulai_servis,
            'type': 'start',
            'label': 'Mulai Servis',
            'position': 0
        })

        # Job stops
        if self.controller_tunggu_konfirmasi_mulai:
            events.append({
                'time': self.controller_tunggu_konfirmasi_mulai,
                'type': 'konfirmasi',
                'label': 'Tunggu Konfirmasi',
                'duration': self.lead_time_tunggu_konfirmasi,
                'position': calculate_position(self.controller_tunggu_konfirmasi_mulai)
            })

        if self.controller_tunggu_part1_mulai:
            events.append({
                'time': self.controller_tunggu_part1_mulai,
                'type': 'part',
                'label': 'Tunggu Part 1',
                'duration': self.lead_time_tunggu_part1,
                'position': calculate_position(self.controller_tunggu_part1_mulai)
            })

        if self.controller_tunggu_part2_mulai:
            events.append({
                'time': self.controller_tunggu_part2_mulai,
                'type': 'part',
                'label': 'Tunggu Part 2',
                'duration': self.lead_time_tunggu_part2,
                'position': calculate_position(self.controller_tunggu_part2_mulai)
            })

        if self.controller_istirahat_shift1_mulai:
            events.append({
                'time': self.controller_istirahat_shift1_mulai,
                'type': 'break',
                'label': 'Istirahat',
                'duration': self.lead_time_istirahat,
                'position': calculate_position(self.controller_istirahat_shift1_mulai)
            })

        events.append({
            'time': self.controller_selesai,
            'type': 'end',
            'label': 'Selesai Servis',
            'position': 100
        })

        return events
    
    # DASHBOARD
    # Tambahkan field untuk dashboard di sini
    # Field untuk agregasi dashboard
    # total_orders = fields.Integer(
    #     string='Total Orders',
    #     compute='_compute_dashboard_data',
    #     store=True
    # )
    
    # total_revenue = fields.Monetary(
    #     string='Total Revenue',
    #     compute='_compute_dashboard_data',
    #     store=True
    # )
    
    # average_lead_time = fields.Float(
    #     string='Average Lead Time',
    #     compute='_compute_dashboard_data',
    #     store=True
    # )
    
    # # Compute method untuk dashboard
    # @api.depends('state', 'amount_total', 'lead_time_servis')
    # def _compute_dashboard_data(self):
    #     for record in self:
    #         record.total_orders = 1  # Akan diagregasi di dashboard
    #         record.total_revenue = record.amount_total
    #         record.average_lead_time = record.lead_time_servis or 0.0

    # # Method untuk mendapatkan data dashboard
    # @api.model
    # def get_dashboard_data(self):
    #     """Method untuk mengambil data dashboard"""
    #     domain = [('state', '!=', 'cancel')]
        
    #     # Data berdasarkan Service Advisor
    #     sa_data = self.read_group(
    #         domain=domain,
    #         fields=['service_advisor_id', 'total_orders:count', 'total_revenue:sum', 'average_lead_time:avg'],
    #         groupby=['service_advisor_id']
    #     )

    #     # Data berdasarkan Mechanic
    #     mechanic_data = self.read_group(
    #         domain=domain,
    #         fields=['car_mechanic_id_new', 'total_orders:count', 'total_revenue:sum', 'average_lead_time:avg'],
    #         groupby=['car_mechanic_id_new']
    #     )

    #     return {
    #         'service_advisor_data': sa_data,
    #         'mechanic_data': mechanic_data,
    #     }

    # LOG
    def _log_activity(self, message, time):
        """ Centralized method to log activity to chatter """
        body = f"""
        <p><strong>{message}</strong></p>
        <ul>
            <li>Dicatat oleh: {self.env.user.name}</li>
            <li>Waktu: {time}</li>
        </ul>
        """
        self.message_post(body=body, message_type='notification')

    # QUEUE 
    queue_number = fields.Integer(string='Nomor Antrean', readonly=True)
    queue_line_id = fields.Many2one('queue.management.line', string='Queue Line', readonly=True)
    queue_status = fields.Selection(related='queue_line_id.status', store=True, string='Status Antrean')
    display_queue_number = fields.Char(related='queue_line_id.display_number', store=True, string='Nomor Antrean Display')
    is_booking = fields.Boolean(string='Is Booking', default=False)
     # Tambahkan computed fields untuk informasi antrian
    current_queue_number = fields.Integer(
        string='Nomor Antrean Saat Ini',
        compute='_compute_queue_info',
        store=False
    )
    numbers_ahead = fields.Integer(
        string='Sisa Antrean',
        compute='_compute_queue_info',
        store=False
    )

    @api.depends('queue_line_id', 'queue_line_id.queue_id.current_number')
    def _compute_queue_info(self):
        for record in self:
            if record.queue_line_id and record.queue_line_id.queue_id:
                # Format current number seperti format display_number
                current_num = record.queue_line_id.queue_id.current_number or 0
                record.current_queue_number = f"{current_num:03d}"

                # Format numbers ahead
                numbers_ahead = record.queue_line_id.get_numbers_ahead() or 0
                record.numbers_ahead = f"{numbers_ahead:03d}"
            else:
                record.current_queue_number = "000"
                record.numbers_ahead = "000"

    # Tambahkan index menggunakan SQL
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Order Reference must be unique!')
    ]

    # Cache untuk data yang sering diakses
    @tools.ormcache('self.id')
    def get_print_data(self):
        return {
            'partner_data': self.partner_id.read(['name', 'phone', 'email']),
            'car_data': self.partner_car_id.read(['brand', 'model', 'year']),
            'lines_data': self.order_line.read(['product_id', 'quantity', 'price_unit'])
        }

    # Clear cache ketika data berubah
    def write(self, vals):
        result = super().write(vals)
        # Clear cache jika field yang di-cache berubah
        if any(f in vals for f in ['partner_id', 'partner_car_id', 'order_line']):
            self.clear_caches()
        return result

    # Batch processing
    @api.model
    def process_print_queue(self, ids, batch_size=100):
        """Process print queue in batches to avoid memory issues"""
        if not isinstance(ids, list):
            ids = list(ids)
            
        for batch_ids in split_every(batch_size, ids):
            try:
                orders = self.browse(batch_ids)
                # Process batch
                orders._prepare_print_data()
                self.env.cr.commit()
            except Exception as e:
                _logger.error(f"Error processing batch {batch_ids}: {str(e)}")
                self.env.cr.rollback()
                continue

    def _prepare_print_data(self):
        """Helper method untuk mempersiapkan data print"""
        self.ensure_one()
        return {
            'print_data': self.get_print_data(),
            'timestamp': fields.Datetime.now(),
            'user': self.env.user.name
        }
    
    # KPI 
    sop_sampling_ids = fields.One2many('pitcar.sop.sampling', 'sale_order_id', 'SOP Sampling')
    sampling_count = fields.Integer('Jumlah Sampling', compute='_compute_sampling_count')
    
    @api.depends('sop_sampling_ids')
    def _compute_sampling_count(self):
        for record in self:
            record.sampling_count = len(record.sop_sampling_ids)

    def action_view_sampling(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'SOP Sampling',
            'res_model': 'pitcar.sop.sampling',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)]
        }
    
    # REQUEST PART
    part_purchase_ids = fields.One2many('part.purchase.leadtime', 'sale_order_id',
                                       string='Part Purchases')
    part_purchase_count = fields.Integer(string='Part Purchases',
                                       compute='_compute_part_purchase_count')
    
    need_part_purchase = fields.Selection([
        ('yes', 'Ya'),
        ('no', 'Tidak')
    ], string='Perlu Beli Part?', default='no', tracking=True)
    
    part_purchase_status = fields.Selection([
        ('not_needed', 'Tidak Perlu'),
        ('pending', 'Menunggu'),
        ('in_progress', 'Dalam Proses'),
        ('completed', 'Selesai')
    ], string='Status Beli Part', compute='_compute_part_purchase_status', store=True)

    # Fields baru untuk tracking request part
    # Tambahkan field part_request_time di sini, bersama fields lainnya
    part_request_time = fields.Datetime(
        'Waktu Request Part',
        compute='_compute_part_request_time', 
        store=True,  # Penting untuk menyimpan nilai
        readonly=False,  # Bisa diubah manual jika perlu
        tracking=True
    )
    part_request_notes = fields.Text('Catatan Umum Request Part', tracking=True)
    
    # One2many ke items yang direquest
    part_request_items_ids = fields.One2many(
        'sale.order.part.item', 
        'sale_order_id', 
        string='Items yang Diminta'
    )
    
    # Computed fields untuk status
    total_requested_items = fields.Integer(
        compute='_compute_items_status',
        string='Total Items Diminta'
    )
    total_fulfilled_items = fields.Integer(
        compute='_compute_items_status',
        string='Total Items Terpenuhi'
    )
    all_items_fulfilled = fields.Boolean(
        compute='_compute_items_status',
        string='Semua Items Terpenuhi'
    )
    part_request_state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('completed', 'Completed')
    ], string='Part Request State', default='draft', tracking=True)

    notification_ids = fields.One2many('pitcar.notification', compute='_compute_notification_ids')
    part_request_items_ids = fields.One2many('sale.order.part.item', 'sale_order_id', string='Items yang Diminta')

    def _compute_notification_ids(self):
        for order in self:
            order.notification_ids = self.env['pitcar.notification'].search([
                ('model', '=', 'sale.order'),
                ('res_id', '=', order.id)
            ])

    # Tambahkan compute method di sini, setelah semua fields
    @api.depends('need_part_purchase', 'part_request_items_ids')
    def _compute_part_request_time(self):
        """Compute part request time based on need_part_purchase"""
        for record in self:
            if record.need_part_purchase == 'yes' and not record.part_request_time:
                record.part_request_time = fields.Datetime.now()
            elif record.need_part_purchase == 'no':
                record.part_request_time = False

    # Di model sale.order
    @api.onchange('need_part_purchase')
    def _onchange_need_part_purchase(self):
        if self.need_part_purchase == 'yes':
            warning = {
                'title': 'Konfirmasi Request Part',
                'message': 'Anda akan membuat request part ke Tim Part. Lanjutkan?'
            }
            vals = {
                'part_request_state': 'draft',
                'part_request_time': fields.Datetime.now(),
                'part_purchase_status': 'pending'
            }
            self.write(vals)
            self.env['pitcar.notification'].create_or_update_notification(
                model='sale.order',
                res_id=self.id,
                type='new_request',
                title='Request Part Baru',
                message=f"Order #{self.name} memerlukan part",
                request_time=self.part_request_time,
                data={'total_items': self.total_requested_items or 0}
            )
            return {'warning': warning}
        elif self.need_part_purchase == 'no':
            vals = {
                'part_request_state': False,
                'part_request_time': False,
                'part_purchase_status': 'not_needed'
            }
            self.write(vals)
            if self.part_request_items_ids:
                return {
                    'warning': {
                        'title': 'Konfirmasi Batalkan Request',
                        'message': 'Request part yang sudah dibuat akan dibatalkan. Lanjutkan?'
                    }
                }

    def action_request_part(self):
        self.ensure_one()
        if not self.part_request_items_ids:
            raise ValidationError(_("Mohon tambahkan item part yang dibutuhkan"))
        current_time = fields.Datetime.now()
        vals = {
            'need_part_purchase': 'yes',
            'part_purchase_status': 'pending',
            'part_request_time': current_time,
            'part_request_state': 'requested'
        }
        self.write(vals)
        self.env['pitcar.notification'].create_or_update_notification(
            model='sale.order',
            res_id=self.id,
            type='new_request',
            title='Request Part Baru',
            message=f"Order #{self.name} memerlukan part",
            request_time=current_time,
            data={'total_items': self.total_requested_items or 0}
        )

    @api.onchange('part_request_items_ids')
    def _onchange_part_request_items(self):
        if self.need_part_purchase == 'yes' and self.part_request_items_ids:
            current_time = fields.Datetime.now()
            self.env['pitcar.notification'].create_or_update_notification(
                model='sale.order',
                res_id=self.id,
                type='new_request',
                title='Request Part Baru',
                message=f"Order #{self.name} memerlukan part (Item diperbarui)",
                request_time=current_time,
                data={
                    'total_items': len(self.part_request_items_ids),
                    'updated_items': [
                        {
                            'product_name': item.part_name or item.product_id.name,
                            'quantity': item.quantity,
                            'notes': item.notes or ''
                        } for item in self.part_request_items_ids
                    ]
                }
            )
            _logger.info(f"Notification updated for order {self.name} due to item change")

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        if 'part_request_items_ids' in vals and self.need_part_purchase == 'yes':
            current_time = fields.Datetime.now()
            self.env['pitcar.notification'].create_or_update_notification(
                model='sale.order',
                res_id=self.id,
                type='new_request',
                title='Request Part Baru',
                message=f"Order #{self.name} memerlukan part (Item diperbarui)",
                request_time=current_time,
                data={
                    'total_items': len(self.part_request_items_ids),
                    'updated_items': [
                        {
                            'product_name': item.part_name or item.product_id.name,
                            'quantity': item.quantity,
                            'notes': item.notes or ''
                        } for item in self.part_request_items_ids
                    ]
                }
            )
            _logger.info(f"Notification updated for order {self.name} after write")
        return res

    # def action_request_part(self):
    #     """SA memulai request part"""
    #     _logger.info("action_request_part called")
        
    #     self.ensure_one()
    #     if not self.part_request_items_ids:
    #         raise ValidationError(_("Mohon tambahkan item part yang dibutuhkan"))
        
    #     current_time = fields.Datetime.now()
    #     _logger.info(f"Setting values: need_part_purchase=yes, part_request_time={current_time}")
        
    #     vals = {
    #         'need_part_purchase': 'yes',
    #         'part_purchase_status': 'pending',
    #         'part_request_time': current_time,
    #         'part_request_state': 'requested'
    #     }
    #     self.write(vals)
        
        # Verify after write
        # self.invalidate_cache()
        # _logger.info(f"After write - part_request_time: {self.part_request_time}")

    @api.depends('part_request_items_ids', 'part_request_items_ids.is_fulfilled')
    def _compute_items_status(self):
        for order in self:
            total = len(order.part_request_items_ids)
            fulfilled = len(order.part_request_items_ids.filtered('is_fulfilled'))
            order.total_requested_items = total
            order.total_fulfilled_items = fulfilled
            order.all_items_fulfilled = total > 0 and total == fulfilled
            
            # Update state jika semua item fulfilled
            if order.all_items_fulfilled:
                order.part_request_state = 'completed'

    @api.depends('need_part_purchase', 'part_request_items_ids', 'part_request_items_ids.is_fulfilled') 
    def _compute_part_purchase_status(self):
        for order in self:
            if order.need_part_purchase == 'no':
                order.part_purchase_status = 'not_needed'
            elif not order.part_request_items_ids:
                order.part_purchase_status = 'pending'
            else:
                fulfilled = all(item.is_fulfilled for item in order.part_request_items_ids)
                order.part_purchase_status = 'completed' if fulfilled else 'in_progress'

    @api.depends('need_part_purchase', 'part_purchase_ids', 'part_purchase_ids.state')
    def _compute_part_purchase_status(self):
        for order in self:
            if order.need_part_purchase == 'no':
                order.part_purchase_status = 'not_needed'
            else:
                if not order.part_purchase_ids:
                    order.part_purchase_status = 'pending'
                else:
                    # Check latest part purchase
                    latest_purchase = order.part_purchase_ids.sorted('create_date', reverse=True)[0]
                    if latest_purchase.state == 'returned':
                        order.part_purchase_status = 'completed'
                    elif latest_purchase.state in ['draft', 'departed']:
                        order.part_purchase_status = 'in_progress'
                    else:
                        order.part_purchase_status = 'pending'

    @api.depends('part_request_items_ids.is_fulfilled', 'part_request_items_ids.state')
    def _compute_items_status(self):
        for order in self:
            total = len(order.part_request_items_ids)
            fulfilled = len(order.part_request_items_ids.filtered(
                lambda x: x.state == 'approved'  # Gunakan state sebagai patokan
            ))
            
            order.total_requested_items = total
            order.total_fulfilled_items = fulfilled
            order.all_items_fulfilled = total > 0 and total == fulfilled
            
            # Update part_request_state berdasarkan state items
            if total == 0:
                order.part_request_state = 'draft'
            elif fulfilled == total:
                order.part_request_state = 'completed'
            else:
                order.part_request_state = 'requested'

    def action_need_part_purchase(self):
        self.write({'need_part_purchase': 'yes'})
        
    def action_no_part_purchase(self):
        self.write({'need_part_purchase': 'no'})

    def action_view_part_purchases(self):
        self.ensure_one()
        return {
            'name': _('Part Purchases'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'part.purchase.leadtime',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id}
        }
    
     # Field baru untuk tracking efisiensi waktu servis
    service_time_efficiency = fields.Float(
        string='Efisiensi Waktu Servis (%)', 
        compute='_compute_service_time_efficiency',
        store=True
    )

    @api.depends('total_estimated_duration', 'controller_mulai_servis', 'controller_selesai')
    def _compute_service_time_efficiency(self):
        for order in self:
            if order.total_estimated_duration and order.controller_mulai_servis and order.controller_selesai:
                actual_duration = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 3600
                # Hitung efisiensi (100% jika sesuai/lebih cepat, kurang jika lebih lama)
                order.service_time_efficiency = min(100, (order.total_estimated_duration / actual_duration) * 100) if actual_duration else 0
            else:
                order.service_time_efficiency = 0

     # Tambahkan fields baru untuk tracking realisasi rekomendasi
    recommendation_realization_rate = fields.Float(
        string='Realisasi Rekomendasi (%)',
        compute='_compute_kpi_metrics',
        store=True
    )
    total_recommendations = fields.Integer(
        string='Total Rekomendasi',
        compute='_compute_kpi_metrics',
        store=True
    )
    realized_recommendations = fields.Integer(
        string='Rekomendasi Terealisasi',
        compute='_compute_kpi_metrics',
        store=True
    )

    @api.depends('recommendation_ids', 'recommendation_ids.state')
    def _compute_kpi_metrics(self):
        for order in self:
            if order.recommendation_ids:
                total_recs = len(order.recommendation_ids)
                # Hitung rekomendasi yang sudah direalisasikan
                realized_recs = len(order.recommendation_ids.filtered(lambda r: 
                    r.state in ['scheduled']  # atau status lain yang menandakan realisasi
                ))
                realization_rate = (realized_recs / total_recs * 100) if total_recs else 0
                
                order.total_recommendations = total_recs
                order.realized_recommendations = realized_recs
                order.recommendation_realization_rate = realization_rate
            else:
                order.total_recommendations = 0
                order.realized_recommendations = 0
                order.recommendation_realization_rate = 0

    mentor_request_ids = fields.One2many(
        'pitcar.mentor.request', 
        'sale_order_id', 
        string='Mentor Requests',
        readonly=True
    )
    has_mentor_request = fields.Boolean(
        string='Has Mentor Request',
        compute='_compute_mentor_requests',
        store=True,
        help="Indicates if this sale order has an associated mentor request."
    )
    mentor_request_count = fields.Integer(
        string='Mentor Request Count',
        compute='_compute_mentor_requests',
        store=True,
        help="Number of mentor requests associated with this sale order."
    )

    @api.depends('mentor_request_ids')
    def _compute_mentor_requests(self):
        for order in self:
            order.has_mentor_request = bool(order.mentor_request_ids)
            order.mentor_request_count = len(order.mentor_request_ids)

    # STALL INTEGRATION
    # Tambahkan di model sale.order setelah fields yang ada
    stall_id = fields.Many2one(
        'pitcar.service.stall', 
        string='Service Stall',
        tracking=True,
        index=True,
        help="Stall tempat service dilakukan"
    )

    # Fields terkait stall untuk reporting
    stall_code = fields.Char(related='stall_id.code', string='Stall Code', readonly=True, store=True)
    stall_name = fields.Char(related='stall_id.name', string='Stall Name', readonly=True, store=True)

    # Field untuk menunjukkan history stall
    stall_history_ids = fields.One2many(
        'pitcar.stall.history',
        'sale_order_id',
        string='Stall History',
        readonly=True
    )

    # Tambahkan action di SaleOrder
    def action_assign_stall(self):
        """Open wizard to assign stall"""
        self.ensure_one()
        return {
            'name': _('Assign Stall'),
            'type': 'ir.actions.act_window',
            'res_model': 'assign.stall.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id}
        }

    def action_view_stall_history(self):
        """View stall assignment history"""
        self.ensure_one()
        return {
            'name': _('Stall History'),
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.stall.history',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id}
        }

    def action_release_stall(self):
        """Release currently assigned stall"""
        self.ensure_one()
        
        if not self.stall_id:
            raise UserError(_("No stall assigned to release"))
        
        # Close current assignment in history
        history = self.env['pitcar.stall.history'].search([
            ('sale_order_id', '=', self.id),
            ('stall_id', '=', self.stall_id.id),
            ('end_time', '=', False)
        ], limit=1)
        
        if history:
            history.end_time = fields.Datetime.now()
        
        # Save old stall info for message
        old_stall_name = self.stall_id.name
        
        # Release stall
        self.stall_id = False
        
        # Log in chatter
        body = f"""
        <p><strong>Stall Released</strong></p>
        <ul>
            <li>Stall: {old_stall_name}</li>
            <li>Released by: {self.env.user.name}</li>
            <li>Time: {fields.Datetime.now()}</li>
        </ul>
        """
        self.message_post(body=body, message_type='notification')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _(f"Stall {old_stall_name} released successfully"),
                'sticky': False,
                'type': 'success'
            }
        }
    
    # 3. FIELD SUMBER INFO CUSTOMER (relasi dengan customer)
    customer_sumber_info = fields.Selection([
        ('loyal', 'Loyal'),
        ('fb_ads', 'FB Ads'),
        ('referral', 'Referral'),
        ('all_b2b', 'All B2B'),
        ('ig_ads', 'IG Ads'),
        ('google_maps', 'Google Maps'),
        ('tiktok_ads', 'Tiktok Ads'),
        ('ig_organic', 'IG Organic'),
        ('beli_part', 'Beli Part'),
        ('web_paid_ads', 'Web - Paid Ads'),
        ('web_organic', 'Web - Organic'),
        ('workshop', 'Workshop'),
        ('relation', 'Relation'),
        ('youtube', 'Youtube'),
        ('tidak_dapat_info', 'Tidak Dapat Info'),
    ], 
    string="Customer Source", 
    compute='_compute_customer_sumber_info',
    store=True,
    readonly=True,
    help="Sumber informasi customer"
    )

    customer_tags = fields.Many2many(
        'res.partner.category',
        string="Customer Tags",
        compute='_compute_customer_tags',
        store=True,
        readonly=True,
        help="Tags customer"
    )

    # Field untuk display tags sebagai text
    customer_tags_display = fields.Char(
        string="Customer Tags Text",
        compute='_compute_customer_tags_display',
        store=True
    )

    # ========== COMPUTE METHODS ==========

    @api.depends('partner_id', 'partner_id.sumber_info_id')
    def _compute_customer_sumber_info(self):
        """
        Compute customer source - TIDAK BERUBAH meskipun customer jadi loyal
        """
        for order in self:
            if order.partner_id and order.partner_id.sumber_info_id:
                # Ambil dari customer sumber info yang pertama
                order.customer_sumber_info = order.partner_id.sumber_info_id[0].sumber
            else:
                order.customer_sumber_info = False
    
    @api.depends('partner_id', 'create_date')
    def _compute_customer_transaction_sequence(self):
        """
        Compute urutan transaksi untuk customer ini
        Menggunakan create_date untuk menentukan urutan
        """
        for order in self:
            if order.partner_id and order.create_date:
                # Hitung berapa sale order customer ini yang create_date-nya <= order ini
                sequence = self.env['sale.order'].search_count([
                    ('partner_id', '=', order.partner_id.id),
                    ('create_date', '<=', order.create_date),
                    ('state', 'in', ('draft', 'sent', 'sale', 'done'))  # Semua kecuali cancel
                ])
                order.customer_transaction_sequence = sequence
            else:
                order.customer_transaction_sequence = 0

    @api.depends('partner_id', 'partner_id.category_id')
    def _compute_customer_tags(self):
        for order in self:
            if order.partner_id and order.partner_id.category_id:
                order.customer_tags = [(6, 0, order.partner_id.category_id.ids)]
            else:
                order.customer_tags = [(5, 0, 0)]

    @api.depends('customer_tags')
    def _compute_customer_tags_display(self):
        for order in self:
            if order.customer_tags:
                order.customer_tags_display = ', '.join(order.customer_tags.mapped('name'))
            else:
                order.customer_tags_display = ''

    is_loyal_customer = fields.Boolean(
        string='Loyal Customer',
        compute='_compute_customer_loyalty_info',
        store=True,
        help="Indicates if the customer has more than one transaction"
    )

    customer_transaction_count = fields.Integer(
        string='Transaction Count',
        compute='_compute_customer_loyalty_info',
        store=True,
        help="Total number of confirmed sale orders for this customer"
    )

    customer_level = fields.Selection([
            ('new', 'New Customer'),
            ('loyal', 'Loyal Customer'),
        ], 
        string="Customer Level",
        compute='_compute_customer_loyalty_info',
        store=True,
        readonly=True,
        help="Level customer berdasarkan jumlah transaksi"
        )

    customer_level_display = fields.Char(
        string='Level Customer',
        compute='_compute_customer_level_display',
        store=True,
        help="Display customer level: Loyal or New"
    )

    # 3. SEQUENCE TRANSAKSI - field baru untuk efisiensi
    customer_transaction_sequence = fields.Integer(
        string='Transaction Sequence',
        compute='_compute_customer_transaction_sequence',
        store=True,
        help="Ini adalah transaksi ke-berapa untuk customer ini"
    )


    @api.depends('customer_level', 'customer_transaction_count', 'customer_transaction_sequence')
    def _compute_customer_level_display(self):
        """
        Display customer level dengan informasi sequence
        """
        for order in self:
            if not order.partner_id:
                order.customer_level_display = ''
            elif order.customer_level == 'loyal':
                order.customer_level_display = f"🏆 Loyal Customer (Transaksi ke-{order.customer_transaction_sequence} dari {order.customer_transaction_count})"
            else:
                order.customer_level_display = f"✨ New Customer (Transaksi ke-{order.customer_transaction_sequence})"

    @api.depends('partner_id', 'customer_transaction_sequence')
    def _compute_customer_loyalty_info(self):
        """
        Compute customer loyalty berdasarkan jumlah transaksi
        TIDAK MENGUBAH customer_sumber_info
        """
        # Batch compute untuk performa - kumpulkan partner_ids
        partner_ids = set()
        for order in self:
            if order.partner_id:
                partner_ids.add(order.partner_id.id)

        # Hitung transaction_count untuk semua partner sekaligus
        transaction_counts = {}
        if partner_ids:
            transaction_counts = {
                partner_id: self.env['sale.order'].search_count([
                    ('partner_id', '=', partner_id),
                    ('state', 'in', ('sale', 'done')),  # Hanya yang confirmed
                ]) for partner_id in partner_ids
            }

        for order in self:
            if order.partner_id:
                count = transaction_counts.get(order.partner_id.id, 0)
                order.customer_transaction_count = count
                order.is_loyal_customer = count > 1
                
                # Set customer level berdasarkan count
                if count > 1:
                    order.customer_level = 'loyal'
                else:
                    order.customer_level = 'new'
                
                # *** TIDAK MENGUBAH customer_sumber_info ***
                # Ini yang dihapus dari kode sebelumnya:
                # if order.is_loyal_customer and not order.customer_sumber_info:
                #     order.customer_sumber_info = 'loyal'
                
            else:
                order.customer_transaction_count = 0
                order.is_loyal_customer = False
                order.customer_level = 'new'


    # ==================== UTILITY METHODS ====================
    def action_recompute_customer_loyalty(self):
        """
        Manual recompute customer loyalty untuk testing/debugging
        """
        self.ensure_one()
        try:
            # Force recompute
            self.invalidate_cache([
                'customer_sumber_info', 
                'customer_level', 
                'is_loyal_customer', 
                'customer_transaction_count',
                'customer_transaction_sequence'
            ])
            
            self._compute_customer_sumber_info()
            self._compute_customer_transaction_sequence()
            self._compute_customer_loyalty_info()

            # Log hasil ke chatter
            message = f"""
                <p><strong>Customer Info Recomputed</strong></p>
                <ul>
                    <li>Customer: {self.partner_id.name}</li>
                    <li>Customer Source: {self.customer_sumber_info or 'Not Set'}</li>
                    <li>Customer Level: {self.customer_level}</li>
                    <li>Transaction Sequence: {self.customer_transaction_sequence}</li>
                    <li>Transaction Count: {self.customer_transaction_count}</li>
                    <li>Is Loyal: {'Yes' if self.is_loyal_customer else 'No'}</li>
                    <li>Recomputed by: {self.env.user.name}</li>
                </ul>
            """
            self.message_post(body=message, message_type='notification')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Customer info recomputed. Level: {self.customer_level}, Source: {self.customer_sumber_info}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to recompute: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_show_customer_transactions(self):
        """
        Show all transactions for this customer with transaction sequence
        """
        self.ensure_one()
        if not self.partner_id:
            raise UserError("No customer selected")
        
        return {
            'name': f'Transaction History - {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {
                'search_default_partner_id': self.partner_id.id,
                'default_partner_id': self.partner_id.id,
                'search_default_group_transaction_sequence': 1
            },
            'help': f"""
                <p class="o_view_nocontent_smiling_face">
                    Customer Transaction History
                </p>
                <p>
                    All transactions for: {self.partner_id.name}<br/>
                    Current customer level: {self.customer_level}<br/>
                    This is transaction #{self.customer_transaction_sequence}
                </p>
            """
        }

    def action_view_customer_source_detail(self):
        """
        View detailed customer source information (non-redundant)
        Only accessible from detail tab
        """
        self.ensure_one()
        
        if not self.partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Customer',
                    'message': 'No customer selected for this order',
                    'type': 'warning'
                }
            }
        
        # Collect customer source info
        source_info = []
        
        # From partner master data
        if self.partner_id.sumber_info_id:
            source_info.append(f"🎯 Master Source: {self.partner_id.sumber_info_id[0].sumber}")
        
        if self.partner_id.source:
            source_info.append(f"📋 Backup Source: {self.partner_id.source.name}")
        
        if self.partner_id.category_id:
            tags = ', '.join(self.partner_id.category_id.mapped('name'))
            source_info.append(f"🏷️ Customer Tags: {tags}")
        
        # Current order info
        source_info.append(f"📊 Order Source: {self.customer_sumber_info or 'Not Set'}")
        source_info.append(f"🏆 Customer Level: {self.customer_level}")
        source_info.append(f"📈 Transaction #{self.customer_transaction_sequence} of {self.customer_transaction_count}")
        
        # Additional info
        if self.is_loyal_customer:
            source_info.append(f"✨ Status: Loyal Customer")
        else:
            source_info.append(f"🆕 Status: New Customer")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'Customer Source Detail - {self.partner_id.name}',
                'message': '\n'.join(source_info),
                'type': 'info',
                'sticky': True,
            }
        }

    @api.model
    def validate_customer_data_consistency(self):
        """
        Validate that customer data is consistent and non-redundant
        Safe method that won't cause errors
        """
        issues = []
        
        try:
            # Check for missing transaction sequences
            orders_without_sequence = self.search([
                ('partner_id', '!=', False),
                ('customer_transaction_sequence', '=', 0)
            ])
            
            for order in orders_without_sequence:
                issues.append({
                    'type': 'missing_sequence',
                    'order_id': order.id,
                    'order_name': order.name,
                    'customer': order.partner_id.name,
                    'issue': 'Missing transaction sequence'
                })
            
            # Check for inconsistent sequences
            customers = self.env['res.partner'].search([('customer_rank', '>', 0)])
            
            for customer in customers:
                customer_orders = self.search([
                    ('partner_id', '=', customer.id),
                    ('customer_transaction_sequence', '>', 0)
                ], order='create_date')
                
                expected_sequence = 1
                for order in customer_orders:
                    if order.customer_transaction_sequence != expected_sequence:
                        issues.append({
                            'type': 'sequence_inconsistency',
                            'order_id': order.id,
                            'order_name': order.name,
                            'customer': customer.name,
                            'expected_sequence': expected_sequence,
                            'actual_sequence': order.customer_transaction_sequence,
                            'issue': f'Expected sequence {expected_sequence}, got {order.customer_transaction_sequence}'
                        })
                    expected_sequence += 1
            
        except Exception as e:
            _logger.error(f"Error in validation: {e}")
            issues.append({
                'type': 'validation_error',
                'issue': f'Validation error: {str(e)}'
            })
        
        return {
            'total_issues': len(issues),
            'issues': issues,
            'validation_passed': len(issues) == 0
        }

    @api.model
    def cleanup_redundant_customer_data(self):
        """
        Safe cleanup of redundant customer data
        """
        _logger.info("Starting safe cleanup of customer data...")
        
        try:
            # Fix missing transaction sequences
            orders_to_fix = self.search([
                ('partner_id', '!=', False),
                ('customer_transaction_sequence', '=', 0)
            ])
            
            fixed_count = 0
            for order in orders_to_fix:
                try:
                    # Recompute transaction sequence
                    partner_orders = self.search([
                        ('partner_id', '=', order.partner_id.id),
                        ('create_date', '<=', order.create_date)
                    ], order='create_date')
                    
                    sequence = len(partner_orders)
                    order.customer_transaction_sequence = sequence
                    
                    # Recompute customer level
                    confirmed_orders = self.search([
                        ('partner_id', '=', order.partner_id.id),
                        ('state', 'in', ('sale', 'done'))
                    ])
                    
                    order.customer_transaction_count = len(confirmed_orders)
                    order.is_loyal_customer = len(confirmed_orders) > 1
                    order.customer_level = 'loyal' if len(confirmed_orders) > 1 else 'new'
                    
                    fixed_count += 1
                    
                except Exception as e:
                    _logger.error(f"Error fixing order {order.name}: {e}")
                    continue
            
            _logger.info(f"Safe cleanup completed. Fixed {fixed_count} orders.")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cleanup Complete',
                    'message': f'Successfully fixed {fixed_count} orders',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in cleanup: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cleanup Error',
                    'message': f'Error during cleanup: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    @api.model
    def get_customer_summary_stats(self):
        """
        Get summary statistics for customer analysis (safe version)
        """
        try:
            # Safe queries with error handling
            total_customers = self.env['res.partner'].search_count([
                ('customer_rank', '>', 0)
            ])
            
            # Customer level distribution
            level_stats = self.read_group(
                domain=[('state', 'in', ('sale', 'done'))],
                fields=['customer_level'],
                groupby=['customer_level']
            )
            
            # Transaction sequence distribution
            sequence_stats = self.read_group(
                domain=[
                    ('state', 'in', ('sale', 'done')),
                    ('customer_transaction_sequence', '>', 0)
                ],
                fields=['customer_transaction_sequence'],
                groupby=['customer_transaction_sequence']
            )
            
            return {
                'total_customers': total_customers,
                'level_statistics': level_stats or [],
                'sequence_statistics': sequence_stats or [],
                'total_orders': self.search_count([('state', 'in', ('sale', 'done'))]),
                'status': 'success'
            }
            
        except Exception as e:
            _logger.error(f"Error getting customer stats: {e}")
            return {
                'total_customers': 0,
                'level_statistics': [],
                'sequence_statistics': [],
                'total_orders': 0,
                'status': 'error',
                'error_message': str(e)
            }


    
    # ========== PERFORMANCE OPTIMIZATION ==========
    
    @api.model
    def _recompute_transaction_sequences_batch(self):
        """
        Batch recompute transaction sequences untuk performa
        Bisa dijadwalkan sebagai cron job jika perlu
        """
        try:
            # Ambil semua order yang perlu di-recompute
            orders = self.search([
                ('customer_transaction_sequence', '=', 0),
                ('partner_id', '!=', False)
            ])
            
            # Group by partner untuk efisiensi
            partner_orders = {}
            for order in orders:
                if order.partner_id.id not in partner_orders:
                    partner_orders[order.partner_id.id] = []
                partner_orders[order.partner_id.id].append(order)
            
            # Process each partner's orders
            for partner_id, partner_orders_list in partner_orders.items():
                # Sort by create_date
                partner_orders_list.sort(key=lambda x: x.create_date)
                
                # Assign sequence
                for idx, order in enumerate(partner_orders_list, 1):
                    order.customer_transaction_sequence = idx
                    
            self.env.cr.commit()
            
        except Exception as e:
            _logger.error(f"Error in batch recompute: {str(e)}")
            self.env.cr.rollback()
