from odoo import models, fields, api, _, exceptions
from odoo.exceptions import ValidationError, AccessError, UserError
import pytz
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
    )

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

            # Format waktu untuk tampilan di chatter
            formatted_time = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Log aktivitas langsung ke chatter
            body = f"""
            <p><strong>Servis dimulai</strong></p>
            <ul>
                <li>Dicatat oleh: {self.env.user.name}</li>
                <li>Waktu catat: {formatted_time} WIB</li>
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
            if self.env.user.pitcar_role != 'controller':
                raise UserError("Hanya Controller yang dapat mengatur estimasi pekerjaan.")
            
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
            if record.controller_estimasi_mulai or record.controller_estimasi_selesai:
                if self.env.user.pitcar_role != 'controller':
                    raise UserError("Hanya Controller yang dapat mengatur estimasi pekerjaan.")
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

            body = f"""
            <p><strong>Servis selesai</strong></p>
            <ul>
                <li>Dicatat oleh: {self.env.user.name}</li>
                <li> Waktu catat:{local_dt.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
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
        self.ensure_one()
        if self.env.user.pitcar_role != 'service_advisor':
            raise UserError("Hanya Service Advisor yang dapat melakukan pencetakan PKB.")
        
        tz = pytz.timezone('Asia/Jakarta')
        local_dt = datetime.now(tz)
        utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

        # Complete service in queue management
        queue_record = self.env['queue.management'].search([
            ('date', '=', fields.Date.today())
        ], limit=1)
        
        if queue_record:
            queue_record.complete_service(self.id)

        self.write({
            'sa_cetak_pkb': utc_dt
        })

        priority_status = "Antrean Prioritas" if self.is_booking else "Antrean Regular"
        body = f"""
        <p><strong>PKB Dicetak</strong></p>
        <ul>
            <li>Tipe Antrean: {priority_status}</li>
            <li>Nomor Antrean: {self.display_queue_number}</li>
            <li>Dicetak oleh: {self.env.user.name}</li>
            <li>Waktu: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} WIB</li>
        </ul>
        """
        self.message_post(body=body, message_type='notification')
        return self.env.ref('pitcar_custom.action_report_work_order').report_action(self)

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
                is_service_time=False
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
                is_service_time=False
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
                is_service_time=False
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

    # 9. LEAD TIME SERVIS
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
    def action_recompute_lead_time(self):
        """
        Method untuk memaksa recompute lead time servis
        Dapat dipanggil dari button di form view atau server action
        """
        orders = self.search([])
        # Paksa compute ulang dengan mengosongkan field
        orders.write({
            'lead_time_servis': 0,
            'total_lead_time_servis': 0,
            'is_overnight': False
        })
        # Trigger compute
        orders._compute_lead_time_servis()
        return True

    @api.depends('controller_mulai_servis', 'controller_selesai',
         'controller_tunggu_konfirmasi_mulai', 'controller_tunggu_konfirmasi_selesai',
         'controller_tunggu_part1_mulai', 'controller_tunggu_part1_selesai',
         'controller_tunggu_part2_mulai', 'controller_tunggu_part2_selesai',
         'controller_tunggu_sublet_mulai', 'controller_tunggu_sublet_selesai',
         'controller_istirahat_shift1_mulai', 'controller_istirahat_shift1_selesai')
    def _compute_lead_time_servis(self):
        for order in self:
            try:
                # Reset nilai default
                order.lead_time_servis = 0
                order.total_lead_time_servis = 0
                order.is_overnight = False

                # Validasi dasar yang lebih ketat
                if not order.controller_mulai_servis or not order.controller_selesai or \
                order.controller_selesai <= order.controller_mulai_servis:
                    continue

                _logger.info(f"""
                    Mulai perhitungan lead time untuk {order.name}:
                    - Mulai Servis: {order.controller_mulai_servis}
                    - Selesai Servis: {order.controller_selesai}
                """)

                # 1. Hitung total lead time servis (waktu kotor)
                total_duration = order.controller_selesai - order.controller_mulai_servis
                order.total_lead_time_servis = total_duration.total_seconds() / 3600

                # 2. Hitung waktu kerja efektif (dalam jam kerja)
                waktu_kerja_efektif = order.hitung_waktu_kerja_efektif(
                    order.controller_mulai_servis,
                    order.controller_selesai,
                    is_service_time=True
                )
                
                # 3. Hitung waktu tunggu dengan validasi overlap
                waktu_tunggu_intervals = []
                waktu_tunggu_dict = {
                    'Tunggu Konfirmasi': (order.controller_tunggu_konfirmasi_mulai, order.controller_tunggu_konfirmasi_selesai),
                    'Tunggu Part 1': (order.controller_tunggu_part1_mulai, order.controller_tunggu_part1_selesai),
                    'Tunggu Part 2': (order.controller_tunggu_part2_mulai, order.controller_tunggu_part2_selesai),
                    'Tunggu Sublet': (order.controller_tunggu_sublet_mulai, order.controller_tunggu_sublet_selesai),
                    'Istirahat Shift 1': (order.controller_istirahat_shift1_mulai, order.controller_istirahat_shift1_selesai)
                }

                total_waktu_tunggu = timedelta()
                
                # Validasi dan sortir interval waktu tunggu
                valid_intervals = []
                for nama_tunggu, (mulai, selesai) in waktu_tunggu_dict.items():
                    if mulai and selesai and selesai > mulai and \
                    mulai >= order.controller_mulai_servis and \
                    selesai <= order.controller_selesai:
                        valid_intervals.append((mulai, selesai, nama_tunggu))
                
                # Sort intervals berdasarkan waktu mulai
                valid_intervals.sort(key=lambda x: x[0])
                
                # Merge overlapping intervals
                if valid_intervals:
                    merged = []
                    current_start, current_end, current_name = valid_intervals[0]
                    
                    for next_start, next_end, next_name in valid_intervals[1:]:
                        if next_start <= current_end:
                            # Ada overlap, ambil waktu terpanjang
                            current_end = max(current_end, next_end)
                            current_name = f"{current_name} + {next_name}"
                        else:
                            # Tidak ada overlap, hitung interval sebelumnya
                            interval_duration = order.hitung_waktu_kerja_efektif(
                                current_start,
                                current_end,
                                is_service_time=False
                            )
                            total_waktu_tunggu += interval_duration
                            _logger.info(f"Waktu tunggu {current_name}: {interval_duration.total_seconds() / 3600} jam")
                            
                            current_start, current_end, current_name = next_start, next_end, next_name
                    
                    # Proses interval terakhir
                    final_interval = order.hitung_waktu_kerja_efektif(
                        current_start,
                        current_end,
                        is_service_time=False
                    )
                    total_waktu_tunggu += final_interval
                    _logger.info(f"Waktu tunggu {current_name}: {final_interval.total_seconds() / 3600} jam")

                # 4. Hitung lead time bersih dengan validasi
                waktu_kerja_seconds = waktu_kerja_efektif.total_seconds()
                waktu_tunggu_seconds = total_waktu_tunggu.total_seconds()
                
                if waktu_kerja_seconds > 0:
                    order.lead_time_servis = max(0, (waktu_kerja_seconds - waktu_tunggu_seconds) / 3600)
                
                # Set flag menginap
                order.is_overnight = (order.controller_selesai.date() - order.controller_mulai_servis.date()).days > 0

                _logger.info(f"""
                    Hasil perhitungan untuk {order.name}:
                    - Total Lead Time: {order.total_lead_time_servis:.2f} jam
                    - Waktu Kerja Efektif: {waktu_kerja_seconds / 3600:.2f} jam
                    - Total Waktu Tunggu: {waktu_tunggu_seconds / 3600:.2f} jam
                    - Lead Time Servis: {order.lead_time_servis:.2f} jam
                    - Menginap: {'Ya' if order.is_overnight else 'Tidak'}
                """)

            except Exception as e:
                _logger.error(f"Error pada perhitungan {order.name}: {str(e)}")
                order.lead_time_servis = 0
                order.total_lead_time_servis = 0

    def hitung_interval(self, mulai, selesai):
        if mulai and selesai and selesai > mulai:
            return self.hitung_waktu_kerja_efektif(mulai, selesai)
        return timedelta()

    def hitung_waktu_kerja_efektif(self, waktu_mulai, waktu_selesai, is_service_time=False):
        """
        Fungsi unified untuk menghitung waktu kerja efektif dengan parameter:
        @param waktu_mulai: datetime - Waktu mulai interval
        @param waktu_selesai: datetime - Waktu selesai interval
        @param is_service_time: boolean - Flag untuk membedakan perhitungan service time vs waktu tunggu
            True: Menghitung waktu service (mempertimbangkan jam kerja 8-17)
            False: Menghitung waktu tunggu (hanya mempertimbangkan jam istirahat)
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

        _logger.info(f"Menghitung waktu efektif dari {waktu_mulai} sampai {waktu_selesai}")
        _logger.info(f"Mode: {'Service Time' if is_service_time else 'Waktu Tunggu'}")

        while current_date <= end_date:
            # Tentukan waktu mulai dan selesai untuk hari ini
            if current_date == waktu_mulai.date():
                start_time = waktu_mulai.time()
            else:
                start_time = BENGKEL_BUKA if is_service_time else time(0, 0)

            if current_date == waktu_selesai.date():
                end_time = waktu_selesai.time()
            else:
                end_time = BENGKEL_TUTUP if is_service_time else time(23, 59, 59)

            # Jika menghitung service time, batasi dengan jam kerja bengkel
            if is_service_time:
                if start_time < BENGKEL_BUKA:
                    start_time = BENGKEL_BUKA
                if end_time > BENGKEL_TUTUP:
                    end_time = BENGKEL_TUTUP

            # Hitung waktu untuk hari ini jika valid
            if start_time < end_time:
                day_start = datetime.combine(current_date, start_time)
                day_end = datetime.combine(current_date, end_time)
                
                work_time = day_end - day_start

                # Kurangi waktu istirahat jika berlaku
                istirahat_start = datetime.combine(current_date, ISTIRAHAT_MULAI)
                istirahat_end = datetime.combine(current_date, ISTIRAHAT_SELESAI)

                if day_start < istirahat_end and day_end > istirahat_start:
                    # Ada overlap dengan waktu istirahat
                    overlap_start = max(day_start, istirahat_start)
                    overlap_end = min(day_end, istirahat_end)
                    istirahat_duration = overlap_end - overlap_start
                    work_time -= istirahat_duration
                    _logger.info(f"Mengurangi istirahat: {istirahat_duration.total_seconds() / 3600} jam")

                waktu_kerja += work_time
                _logger.info(f"Waktu kerja untuk tanggal {current_date}: {work_time.total_seconds() / 3600} jam")

            current_date += timedelta(days=1)

        _logger.info(f"Total waktu efektif: {waktu_kerja.total_seconds() / 3600} jam")
        return waktu_kerja


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