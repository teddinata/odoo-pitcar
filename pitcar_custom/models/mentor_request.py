from odoo import models, fields, api
from datetime import datetime
import pytz
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


# Model untuk Request Bantuan Mentor
class MentorRequest(models.Model):
    _name = 'pitcar.mentor.request'
    _description = 'Mentor Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Reference', default='New', readonly=True, tracking=True)
    
    # Core Relations
    sale_order_id = fields.Many2one('sale.order', string='Service Order', required=True, tracking=True)
    mechanic_id = fields.Many2one('pitcar.mechanic.new', string='Mechanic', required=True, tracking=True)
    mentor_id = fields.Many2one('pitcar.mechanic.new', string='Mentor', tracking=True)

    # Request Details
    problem_category = fields.Selection([
        ('engine', 'Engine & Performance'),
        ('electrical', 'Electrical & Electronics'),
        ('transmission', 'Transmission & Drivetrain'),
        ('chassis', 'Chassis & Suspension'),
        ('diagnostic', 'Diagnostic & Troubleshooting'),
        ('other', 'Other Issues')
    ], string='Problem Category', required=True, tracking=True)

    problem_description = fields.Text('Problem Description', required=True, tracking=True)
    priority = fields.Selection([
        ('normal', 'Normal'),
        ('urgent', 'Urgent')
    ], string='Priority', default='normal', required=True, tracking=True)

    # Status & Flow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('in_progress', 'In Progress'),
        ('solved', 'Solved'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    # Resolution Details
    resolution_notes = fields.Text('Resolution Notes', tracking=True)
    learning_points = fields.Text('Learning Points', tracking=True)
    mechanic_rating = fields.Selection([
        ('1', 'Poor'),
        ('2', 'Below Average'),
        ('3', 'Average'),
        ('4', 'Good'),
        ('5', 'Excellent')
    ], string='Mechanic Rating', tracking=True)

    # Time Tracking
    request_datetime = fields.Datetime('Request Time', tracking=True)
    start_datetime = fields.Datetime('Start Time', tracking=True)
    end_datetime = fields.Datetime('End Time', tracking=True)
    response_time = fields.Float('Response Time (Minutes)', compute='_compute_response_time', store=True)
    resolution_time = fields.Float('Resolution Time (Minutes)', compute='_compute_resolution_time', store=True)

    # System Fields
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('mentor.request') or 'New'
        return super(MentorRequest, self).create(vals)

    def action_submit_request(self):
        """Mekanik submit request bantuan"""
        self.ensure_one()
        if not self.problem_description:
            raise UserError('Harap isi deskripsi masalah')
            
        self.write({
            'state': 'requested',
            'request_datetime': fields.Datetime.now()
        })
        
        # Notify available mentors
        self._notify_mentors()

    def action_start_mentoring(self):
        """Mentor mulai menangani request"""
        self.ensure_one()
        if not self.mentor_id:
            raise UserError('Mentor harus ditentukan sebelum memulai')
            
        self.write({
            'state': 'in_progress',
            'start_datetime': fields.Datetime.now()
        })

    def action_mark_solved(self):
        """Mentor menandai request selesai"""
        self.ensure_one()
        if not self.resolution_notes:
            raise UserError('Harap isi catatan penyelesaian masalah')
            
        self.write({
            'state': 'solved',
            'end_datetime': fields.Datetime.now()
        })

    def action_cancel_request(self):
        """Cancel request"""
        self.write({
            'state': 'cancelled'
        })

    @api.depends('request_datetime', 'start_datetime')
    def _compute_response_time(self):
        """Hitung waktu respon dalam menit"""
        for record in self:
            if record.request_datetime and record.start_datetime:
                delta = record.start_datetime - record.request_datetime
                record.response_time = delta.total_seconds() / 60
            else:
                record.response_time = 0

    @api.depends('start_datetime', 'end_datetime')
    def _compute_resolution_time(self):
        """Hitung waktu penyelesaian dalam menit"""
        for record in self:
            if record.start_datetime and record.end_datetime:
                delta = record.end_datetime - record.start_datetime
                record.resolution_time = delta.total_seconds() / 60
            else:
                record.resolution_time = 0

    def _notify_mentors(self):
        """Kirim notifikasi ke mentor yang tersedia"""
        mentors = self.env['pitcar.mechanic.new'].search([])
        
        if not mentors:
            return
            
        # Prepare message
        message = f"""
            <p><strong>Permintaan Bantuan Baru</strong></p>
            <ul>
                <li>Dari: {self.mechanic_id.name}</li>
                <li>Work Order: {self.sale_order_id.name}</li>
                <li>Kategori: {dict(self._fields['problem_category'].selection).get(self.problem_category)}</li>
                <li>Prioritas: {dict(self._fields['priority'].selection).get(self.priority)}</li>
                <li>Deskripsi: {self.problem_description}</li>
            </ul>
        """
        
        # Send notification
        # partner_ids = mentors.mapped('partner_id.id')
        # if partner_ids:
        #     self.message_post(
        #         body=message,
        #         message_type='notification',
        #         partner_ids=partner_ids
        #     )

# Inherit Mechanic Model untuk tambah role mentor
class MechanicInherit(models.Model):
    _inherit = 'pitcar.mechanic.new'

    is_mentor = fields.Boolean('Is Mentor', default=False)
    mentor_request_ids = fields.One2many('pitcar.mentor.request', 'mentor_id', string='Mentor Requests')
    help_request_ids = fields.One2many('pitcar.mentor.request', 'mechanic_id', string='Help Requests')

    # Statistics
    total_mentor_requests = fields.Integer('Total Requests', compute='_compute_mentor_stats')
    solved_requests = fields.Integer('Solved Requests', compute='_compute_mentor_stats')
    avg_response_time = fields.Float('Avg Response Time', compute='_compute_mentor_stats')
    success_rate = fields.Float('Success Rate (%)', compute='_compute_mentor_stats')

    # Learning Progress untuk mekanik
    total_help_requests = fields.Integer('Total Help Requested', compute='_compute_mechanic_stats')
    avg_rating = fields.Float('Average Rating', compute='_compute_mechanic_stats')
    learning_progress = fields.Float('Learning Progress (%)', compute='_compute_mechanic_stats')

    @api.depends('mentor_request_ids', 'mentor_request_ids.state')
    def _compute_mentor_stats(self):
        for record in self:
            total = len(record.mentor_request_ids)
            solved = len(record.mentor_request_ids.filtered(lambda r: r.state == 'solved'))
            
            record.total_mentor_requests = total
            record.solved_requests = solved
            record.success_rate = (solved / total * 100) if total > 0 else 0
            
            # Calculate average response time
            response_times = record.mentor_request_ids.mapped('response_time')
            record.avg_response_time = sum(response_times) / len(response_times) if response_times else 0

    @api.depends('help_request_ids', 'help_request_ids.state', 'help_request_ids.mechanic_rating')
    def _compute_mechanic_stats(self):
        for record in self:
            requests = record.help_request_ids
            total = len(requests)
            record.total_help_requests = total

            # Calculate average rating
            ratings = [int(r.mechanic_rating) for r in requests if r.mechanic_rating]
            record.avg_rating = sum(ratings) / len(ratings) if ratings else 0

            # Calculate learning progress (improvement in ratings over time)
            if len(ratings) >= 2:
                initial_ratings = ratings[:2]  # First 2 ratings
                recent_ratings = ratings[-2:]   # Last 2 ratings
                initial_avg = sum(initial_ratings) / len(initial_ratings)
                recent_avg = sum(recent_ratings) / len(recent_ratings)
                
                if initial_avg > 0:
                    improvement = ((recent_avg - initial_avg) / initial_avg) * 100
                    record.learning_progress = max(0, min(100, improvement))
                else:
                    record.learning_progress = 0
            else:
                record.learning_progress = 0