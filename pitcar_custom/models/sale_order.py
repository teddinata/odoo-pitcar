from odoo import models, fields, api, _, exceptions
from odoo.exceptions import ValidationError
from datetime import timedelta, date, datetime, time
import logging

_logger = logging.getLogger(__name__)

READONLY_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'sale', 'done', 'cancel'}
}

BENGKEL_BUKA = time(8, 0)  # 08:00
BENGKEL_TUTUP = time(22, 0)  # 22:00
ISTIRAHAT_1_MULAI = time(12, 0)  # 12:00
ISTIRAHAT_1_SELESAI = time(13, 0)  # 13:00
ISTIRAHAT_2_MULAI = time(18, 0)  # 18:00
ISTIRAHAT_2_SELESAI = time(19, 0)  # 19:00
JAM_KERJA_PER_HARI = timedelta(hours=14)  # 22:00 - 08:00
ISTIRAHAT_PER_HARI = timedelta(hours=2)  # (13:00 - 12:00) + (19:00 - 18:00)

def hitung_waktu_kerja_efektif(waktu_mulai, waktu_selesai):
    total_waktu = waktu_selesai - waktu_mulai
    hari_kerja = (waktu_selesai.date() - waktu_mulai.date()).days + 1
    waktu_kerja = timedelta()
    
    for hari in range(hari_kerja):
        hari_ini = waktu_mulai.date() + timedelta(days=hari)
        mulai_hari_ini = max(datetime.combine(hari_ini, BENGKEL_BUKA), waktu_mulai)
        selesai_hari_ini = min(datetime.combine(hari_ini, BENGKEL_TUTUP), waktu_selesai)
        
        if mulai_hari_ini < selesai_hari_ini:
            waktu_kerja_hari_ini = selesai_hari_ini - mulai_hari_ini
            
            # Kurangi waktu istirahat
            if mulai_hari_ini.time() <= ISTIRAHAT_1_MULAI and selesai_hari_ini.time() >= ISTIRAHAT_1_SELESAI:
                waktu_kerja_hari_ini -= timedelta(hours=1)
            if mulai_hari_ini.time() <= ISTIRAHAT_2_MULAI and selesai_hari_ini.time() >= ISTIRAHAT_2_SELESAI:
                waktu_kerja_hari_ini -= timedelta(hours=1)
            
            waktu_kerja += waktu_kerja_hari_ini
    
    return waktu_kerja
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
        inverse="_inverse_car_arrival_time"
    )
    def action_record_car_arrival_time(self):
        current_time = fields.Datetime.now()
        self.write({
            'car_arrival_time': current_time,
            'sa_jam_masuk': current_time
        })
        return True

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

    def write(self, vals):
        if 'customer_rating' in vals and 'customer_satisfaction' not in vals:
            rating_to_satisfaction = {
                '1': 'very_dissatisfied',
                '2': 'dissatisfied',
                '3': 'neutral',
                '4': 'satisfied',
                '5': 'very_satisfied'
            }
            vals['customer_satisfaction'] = rating_to_satisfaction.get(vals['customer_rating'])
        return super(SaleOrder, self).write(vals)
    
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
    def _create_invoices(self, grouped=False, final=False):
        res = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
        for order in self:
            order.date_completed = fields.Datetime.now()
            for invoice in order.invoice_ids:
                invoice.date_sale_completed = order.date_completed
                invoice.date_sale_quotation = order.create_date
                invoice.partner_car_id = order.partner_car_id
                invoice.partner_car_odometer = order.partner_car_odometer
                invoice.car_mechanic_id = order.car_mechanic_id
                invoice.car_mechanic_id_new = order.car_mechanic_id_new
                invoice.generated_mechanic_team = order.generated_mechanic_team
                invoice.service_advisor_id = order.service_advisor_id
                invoice.car_arrival_time = order.car_arrival_time
        return res
    
    # ROLE LEAD TIME 
        
    # Fields untuk tracking lead time
    service_category = fields.Selection([
        ('maintenance', 'Perawatan'),
        ('repair', 'Perbaikan')
    ], string="Kategori Servis", required=True, default='maintenance')
    sa_jam_masuk = fields.Datetime("Jam Masuk", inverse="_inverse_sa_jam_masuk")
    sa_mulai_penerimaan = fields.Datetime(string='Mulai Penerimaan')
    is_penerimaan_filled = fields.Boolean(compute='_compute_is_penerimaan_filled', store=True)

    sa_cetak_pkb = fields.Datetime("Cetak PKB")
    
    controller_estimasi_mulai = fields.Datetime("Estimasi Pekerjaan Mulai")
    controller_estimasi_selesai = fields.Datetime("Estimasi Pekerjaan Selesai")
    controller_mulai_servis = fields.Datetime(string="Mulai Servis", readonly=True)
    controller_selesai = fields.Datetime(string="Selesai Servis", readonly=True)
    controller_tunggu_konfirmasi_mulai = fields.Datetime("Tunggu Konfirmasi Mulai")
    controller_tunggu_konfirmasi_selesai = fields.Datetime("Tunggu Konfirmasi Selesai")
    controller_tunggu_part1_mulai = fields.Datetime("Tunggu Part 1 Mulai")
    controller_tunggu_part1_selesai = fields.Datetime("Tunggu Part 1 Selesai")
    controller_tunggu_part2_mulai = fields.Datetime("Tunggu Part 2 Mulai")
    controller_tunggu_part2_selesai = fields.Datetime("Tunggu Part 2 Selesai")
    controller_istirahat_shift1_mulai = fields.Datetime("Istirahat Shift 1 Mulai")
    controller_istirahat_shift1_selesai = fields.Datetime("Istirahat Shift 1 Selesai")
    controller_tunggu_sublet_mulai = fields.Datetime("Tunggu Sublet Mulai")
    controller_tunggu_sublet_selesai = fields.Datetime("Tunggu Sublet Selesai")
    
    fo_unit_keluar = fields.Datetime("Unit Keluar")
    
    lead_time_catatan = fields.Text("Catatan Lead Time")
    
    lead_time_servis = fields.Float(string="Lead Time Servis (jam)", compute="_compute_lead_time_servis", store=True)
    total_lead_time_servis = fields.Float(string="Total Lead Time Servis (jam)", compute="_compute_lead_time_servis", store=True)
    is_overnight = fields.Boolean(string="Menginap", compute="_compute_lead_time_servis", store=True)
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

    @api.onchange('sa_jam_masuk')
    def _onchange_sa_jam_masuk(self):
        if self.sa_jam_masuk and not self.car_arrival_time:
            self.car_arrival_time = self.sa_jam_masuk

    @api.depends('sa_mulai_penerimaan')
    def _compute_is_penerimaan_filled(self):
        for record in self:
            record.is_penerimaan_filled = bool(record.sa_mulai_penerimaan)

    def action_record_sa_mulai_penerimaan(self):
        self.ensure_one()
        self.sa_mulai_penerimaan = fields.Datetime.now()
        self.reception_state = 'reception_started'  # Assuming you have this state
        return True

    @api.onchange('car_arrival_time')
    def _onchange_car_arrival_time(self):
        if self.car_arrival_time and not self.sa_jam_masuk:
            self.sa_jam_masuk = self.car_arrival_time

    def _inverse_sa_jam_masuk(self):
        for record in self:
            if record.sa_jam_masuk and record.sa_jam_masuk != record.car_arrival_time:
                record.car_arrival_time = record.sa_jam_masuk

    def _inverse_car_arrival_time(self):
        for record in self:
            if record.car_arrival_time and record.car_arrival_time != record.sa_jam_masuk:
                record.sa_jam_masuk = record.car_arrival_time

    def action_mulai_servis(self):
        for record in self:
            if not record.sa_jam_masuk:
                raise exceptions.ValidationError("Tidak dapat memulai servis. Mobil belum masuk.")
            if not record.sa_mulai_penerimaan:
                raise exceptions.ValidationError("Tidak dapat memulai servis. Customer belum diterima/dilayani.")
            if not record.sa_cetak_pkb:
                raise exceptions.ValidationError("Tidak dapat memulai servis. PKB belum dicetak.")
            if record.controller_mulai_servis:
                raise exceptions.ValidationError("Servis sudah dimulai sebelumnya.")
            
            record.controller_mulai_servis = fields.Datetime.now()

    def action_selesai_servis(self):
        for record in self:
            if not record.controller_mulai_servis:
                raise exceptions.ValidationError("Tidak dapat menyelesaikan servis. Servis belum dimulai.")
            if record.controller_selesai:
                raise exceptions.ValidationError("Servis sudah selesai sebelumnya.")
            
            record.controller_selesai = fields.Datetime.now()

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
            if completed_steps == total_steps and order.fo_unit_keluar:
                order.lead_time_progress = 100
            else:
                # Calculate progress
                end_time = order.fo_unit_keluar or now
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
        self.write({
            'sa_cetak_pkb': fields.Datetime.now()
        })
        return self.env.ref('pitcar_custom.action_report_work_order').report_action(self)

    def action_record_time(self, field_name):
        self.ensure_one()
        self.write({field_name: fields.Datetime.now()})

    def action_record_sa_jam_masuk(self):
        self.sa_jam_masuk = fields.Datetime.now()

    def action_record_sa_mulai_penerimaan(self):
        self.ensure_one()
        self.sa_mulai_penerimaan = fields.Datetime.now()
        self.reception_state = 'reception_started'
        
        # Set default invoice and shipping address if not set
        if self.partner_id:
            if not self.partner_invoice_id:
                self.partner_invoice_id = self.partner_id.address_get(['invoice'])['invoice']
            if not self.partner_shipping_id:
                self.partner_shipping_id = self.partner_id.address_get(['delivery'])['delivery']
        
        return True

    def action_record_sa_cetak_pkb(self):
        return self.action_record_time('sa_cetak_pkb')
    
    def action_tunggu_part1_mulai(self):
        self.controller_tunggu_part1_mulai = fields.Datetime.now()

    def action_tunggu_part1_selesai(self):
        self.controller_tunggu_part1_selesai = fields.Datetime.now()

    def action_tunggu_part2_mulai(self):
        self.controller_tunggu_part2_mulai = fields.Datetime.now()

    def action_tunggu_part2_selesai(self):
        self.controller_tunggu_part2_selesai = fields.Datetime.now()

    def action_istirahat_shift1_mulai(self):
        self.controller_istirahat_shift1_mulai = fields.Datetime.now()

    def action_istirahat_shift1_selesai(self):
        self.controller_istirahat_shift1_selesai = fields.Datetime.now()

    def action_tunggu_sublet_mulai(self):
        self.controller_tunggu_sublet_mulai = fields.Datetime.now()

    def action_tunggu_sublet_selesai(self):
        self.controller_tunggu_sublet_selesai = fields.Datetime.now()

    # Aksi untuk memulai tunggu konfirmasi
    def action_tunggu_konfirmasi_mulai(self):
        for record in self:
            if record.controller_tunggu_konfirmasi_mulai:
                raise ValidationError("Tunggu konfirmasi sudah dimulai sebelumnya.")
            record.controller_tunggu_konfirmasi_mulai = fields.Datetime.now()

    # Aksi untuk menyelesaikan tunggu konfirmasi
    def action_tunggu_konfirmasi_selesai(self):
        for record in self:
            if not record.controller_tunggu_konfirmasi_mulai:
                raise ValidationError("Anda tidak dapat menyelesaikan tunggu konfirmasi sebelum memulainya.")
            if record.controller_tunggu_konfirmasi_selesai:
                raise ValidationError("Tunggu konfirmasi sudah diselesaikan sebelumnya.")
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
            record.fo_unit_keluar = fields.Datetime.now()

    def action_job_stop_lain_mulai(self):
        self.ensure_one()
        self.controller_job_stop_lain_mulai = fields.Datetime.now()

    def action_job_stop_lain_selesai(self):
        self.ensure_one()
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
            if order.controller_tunggu_konfirmasi_mulai and order.controller_tunggu_konfirmasi_selesai:
                delta = order.controller_tunggu_konfirmasi_selesai - order.controller_tunggu_konfirmasi_mulai
                order.lead_time_tunggu_konfirmasi = delta.total_seconds() / 3600
            else:
                order.lead_time_tunggu_konfirmasi = 0

    # 6. LEAD TIME TUNGGU PART 1
    lead_time_tunggu_part1 = fields.Float(string="Lead Time Tunggu Part 1 (hours)", compute="_compute_lead_time_tunggu_part1", store=True)

    @api.depends('controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai')
    def _compute_lead_time_tunggu_part1(self):
        for order in self:
            if order.controller_tunggu_part1_mulai and order.controller_tunggu_part1_selesai:
                delta = order.controller_tunggu_part1_selesai - order.controller_tunggu_part1_mulai
                order.lead_time_tunggu_part1 = delta.total_seconds() / 3600
            else:
                order.lead_time_tunggu_part1 = 0

    # 7. LEAD TIME TUNGGU PART 2
    lead_time_tunggu_part2 = fields.Float(string="Lead Time Tunggu Part 2 (hours)", compute="_compute_lead_time_tunggu_part2", store=True)

    @api.depends('controller_tunggu_part2_mulai', 'controller_tunggu_part2_selesai')
    def _compute_lead_time_tunggu_part2(self):
        for order in self:
            if order.controller_tunggu_part2_mulai and order.controller_tunggu_part2_selesai:
                delta = order.controller_tunggu_part2_selesai - order.controller_tunggu_part2_mulai
                order.lead_time_tunggu_part2 = delta.total_seconds() / 3600
            else:
                order.lead_time_tunggu_part2 = 0

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

    # 9. LEAD TIME SERVIS
    overall_lead_time = fields.Float(string="Overall Lead Time (jam)", compute="_compute_overall_lead_time", store=True)

    @api.depends('sa_jam_masuk', 'fo_unit_keluar')
    def _compute_overall_lead_time(self):
        for order in self:
            if order.sa_jam_masuk and order.fo_unit_keluar:
                # Hitung selisih waktu antara mobil masuk dan unit keluar
                delta = order.fo_unit_keluar - order.sa_jam_masuk
                
                # Konversi selisih waktu ke jam
                order.overall_lead_time = delta.total_seconds() / 3600
            else:
                order.overall_lead_time = 0
    
    # 10. LEAD TIME BERSIH dan KOTOR
    @api.depends('sa_jam_masuk', 'controller_selesai',
                 'controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai',
                 'controller_tunggu_part2_mulai', 'controller_tunggu_part2_selesai',
                 'controller_istirahat_shift1_mulai', 'controller_istirahat_shift1_selesai',
                 'controller_tunggu_konfirmasi_mulai', 'controller_tunggu_konfirmasi_selesai')
    def _compute_lead_time_servis(self):
        for order in self:
            if not order.sa_jam_masuk or not order.controller_selesai:
                order.lead_time_servis = 0
                order.total_lead_time_servis = 0
                order.is_overnight = False
                continue

            # Hitung waktu kerja efektif
            waktu_kerja_efektif = order.hitung_waktu_kerja_efektif(order.sa_jam_masuk, order.controller_selesai)

            # Hitung total lead time servis (kotor)
            total_lead_time_servis = order.controller_selesai - order.sa_jam_masuk
            order.total_lead_time_servis = total_lead_time_servis.total_seconds() / 3600  # Konversi ke jam

            # Hitung waktu tunggu
            waktu_tunggu = timedelta()
            waktu_tunggu += order.hitung_interval(order.controller_tunggu_part1_mulai, order.controller_tunggu_part1_selesai)
            waktu_tunggu += order.hitung_interval(order.controller_tunggu_part2_mulai, order.controller_tunggu_part2_selesai)
            waktu_tunggu += order.hitung_interval(order.controller_istirahat_shift1_mulai, order.controller_istirahat_shift1_selesai)
            waktu_tunggu += order.hitung_interval(order.controller_tunggu_konfirmasi_mulai, order.controller_tunggu_konfirmasi_selesai)

            # Hitung lead time servis bersih
            lead_time_servis_bersih = max(waktu_kerja_efektif - waktu_tunggu, timedelta())

            order.lead_time_servis = lead_time_servis_bersih.total_seconds() / 3600  # Konversi ke jam
            order.is_overnight = (order.controller_selesai.date() - order.sa_jam_masuk.date()).days > 0

    def hitung_interval(self, mulai, selesai):
        if mulai and selesai and selesai > mulai:
            return self.hitung_waktu_kerja_efektif(mulai, selesai)
        return timedelta()

    def hitung_waktu_kerja_efektif(self, waktu_mulai, waktu_selesai):
        BENGKEL_BUKA = time(8, 0)
        BENGKEL_TUTUP = time(22, 0)
        ISTIRAHAT_1_MULAI = time(12, 0)
        ISTIRAHAT_1_SELESAI = time(13, 0)
        ISTIRAHAT_2_MULAI = time(18, 0)
        ISTIRAHAT_2_SELESAI = time(19, 0)

        total_waktu = waktu_selesai - waktu_mulai
        hari_kerja = (waktu_selesai.date() - waktu_mulai.date()).days + 1
        waktu_kerja = timedelta()
        
        for hari in range(hari_kerja):
            hari_ini = waktu_mulai.date() + timedelta(days=hari)
            mulai_hari_ini = max(datetime.combine(hari_ini, BENGKEL_BUKA), waktu_mulai)
            selesai_hari_ini = min(datetime.combine(hari_ini, BENGKEL_TUTUP), waktu_selesai)
            
            if mulai_hari_ini < selesai_hari_ini:
                waktu_kerja_hari_ini = selesai_hari_ini - mulai_hari_ini
                
                # Kurangi waktu istirahat
                if mulai_hari_ini.time() <= ISTIRAHAT_1_MULAI and selesai_hari_ini.time() >= ISTIRAHAT_1_SELESAI:
                    waktu_kerja_hari_ini -= timedelta(hours=1)
                if mulai_hari_ini.time() <= ISTIRAHAT_2_MULAI and selesai_hari_ini.time() >= ISTIRAHAT_2_SELESAI:
                    waktu_kerja_hari_ini -= timedelta(hours=1)
                
                waktu_kerja += waktu_kerja_hari_ini
        
        return waktu_kerja
