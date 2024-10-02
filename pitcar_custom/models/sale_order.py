from odoo import models, fields, api, _, exceptions
from datetime import timedelta, date, datetime
import logging

_logger = logging.getLogger(__name__)

READONLY_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'sale', 'done', 'cancel'}
}

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
        string="Mechanic (New input)",
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
        string="Car Arrival Time",
        help="Record the time when the car arrived",
        required=False,  # Tidak wajib diisi
        tracking=True,   # Jika ingin melacak perubahan field ini
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
    