from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
import json
import logging
import pytz

_logger = logging.getLogger(__name__)

class MentorRequest(models.Model):
    _name = 'pitcar.mentor.request'
    _description = 'Mentor Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Request Code', readonly=True, tracking=True, copy=False)
    
    # Core Relations
    sale_order_id = fields.Many2one('sale.order', string='Service Order', required=True, tracking=True)

    # Tambahkan di bagian field-field untuk model MentorRequest
    leader_id = fields.Many2one('pitcar.mechanic.new', string='Team Leader', 
                            domain="[('position_code', '=', 'leader')]", tracking=True)
    leader_response = fields.Text('Leader Response', tracking=True)
    leader_response_datetime = fields.Datetime('Leader Response Time', tracking=True)
    escalated_to_mentor = fields.Boolean('Escalated to Mentor', default=False, tracking=True)
    escalated_to_mentor_datetime = fields.Datetime('Escalated to Mentor Time', tracking=True)
    escalation_notes = fields.Text('Escalation Notes', tracking=True)

    mentor_id = fields.Many2one('hr.employee', string='Mentor', tracking=True)  # Sekarang ke hr.employee
    mechanic_ids = fields.Many2many('pitcar.mechanic.new', string='Mechanics', required=True, tracking=True)

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
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal', required=True, tracking=True)

    # Status & Flow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),  # Mechanic meminta bantuan
        ('leader_assigned', 'Leader Assigned'),  # Leader ditugaskan
        ('leader_responded', 'Leader Responded'),  # Leader merespon
        ('escalated', 'Escalated to Mentor'),  # Dieskalasi ke Kaizen Mentor
        ('in_progress', 'In Progress'),  # Mentor mulai menangani
        ('solved', 'Solved'),  # Masalah diselesaikan
        ('cancelled', 'Cancelled')  # Permintaan dibatalkan
    ], string='Status', default='draft', tracking=True)

    # Tambahkan field untuk mencatat siapa yang menyelesaikan masalah
    resolved_by = fields.Selection([
        ('leader', 'Team Leader'),
        ('mentor', 'Kaizen Mentor')
    ], string='Resolved By', tracking=True)

    leader_response_time = fields.Float('Leader Response Time (Minutes)', compute='_compute_leader_response_time', store=True)

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
        if 'name' not in vals or vals['name'] in ('New', '/', False):
            vals['name'] = self.env['ir.sequence'].next_by_code('mentor.request') or 'MRQ-%s' % datetime.now().strftime('%Y%m%d-%H%M%S')
        return super(MentorRequest, self).create(vals)
    
    # Tambahkan method compute untuk leader_response_time
    @api.depends('request_datetime', 'leader_response_datetime')
    def _compute_leader_response_time(self):
        for record in self:
            if record.request_datetime and record.leader_response_datetime:
                delta = record.leader_response_datetime - record.request_datetime
                record.leader_response_time = delta.total_seconds() / 60
            else:
                record.leader_response_time = 0

    def _send_leader_assignment_notifications(self, leader_id):
        if not self:
            return False
        
        leader = self.env['pitcar.mechanic.new'].browse(leader_id)
        if not leader.exists():
            _logger.warning(f"Leader with ID {leader_id} does not exist")
            return False
        
        # Gunakan context untuk mencegah auto-subscription
        records = self.with_context(mail_create_nosubscribe=True)
        
        notification_type = 'leader_assignment'
        title_template = "Anda Ditugaskan sebagai Leader: {name}"
        message_template = "Anda telah ditugaskan untuk membantu {mechanic_names} dengan {category}"
        
        # Cari semua leader untuk notifikasi
        recipients = self.env['pitcar.mechanic.new'].browse([leader_id])
        
        return self._send_notifications(notification_type, title_template, message_template, recipients)

    def action_submit_request(self):
        for record in self:
            if not record.problem_description:
                raise UserError('Harap isi deskripsi masalah')
                
            # Auto assign team leader jika belum ditentukan
            if not record.leader_id:
                # Ambil leader dari mechanic pertama
                mechanic = record.mechanic_ids[0] if record.mechanic_ids else False
                if mechanic and mechanic.leader_id:
                    record.leader_id = mechanic.leader_id.id
        
        self.write({
            'state': 'requested',
            'request_datetime': fields.Datetime.now()
        })
        
        # Kirim notifikasi ke leader
        for record in self:
            if record.leader_id:
                record._send_leader_assignment_notifications(record.leader_id.id)
        
        self._send_state_change_notifications('requested', self)
        return True
    
    def action_leader_respond(self, response, is_resolved=False):
        """Team leader memberikan respon terhadap permintaan"""
        self.ensure_one()
        values = {
            'leader_response': response,
            'leader_response_datetime': fields.Datetime.now(),
        }
        
        if is_resolved:
            values.update({
                'state': 'solved',
                'resolved_by': 'leader',
                'end_datetime': fields.Datetime.now()
            })
        else:
            values.update({
                'state': 'leader_responded'
            })
            
        self.write(values)
        
        # Kirim notifikasi ke mechanic
        notification_type = 'leader_response'
        title = f"Leader telah merespon permintaan: {self.name}"
        message = f"Leader telah memberikan respon untuk permintaan bantuan Anda"
        
        # Gunakan context untuk mencegah auto-subscription
        self = self.with_context(mail_create_nosubscribe=True)
        
        # Data tambahan untuk notifikasi
        data = {
            'request_id': self.id,
            'leader_id': self.leader_id.id if self.leader_id else False,
            'leader_name': self.leader_id.name if self.leader_id else 'Unknown',
            'response': response,
            'is_resolved': is_resolved,
        }
        
        # Kirim notifikasi ke mechanic
        recipients = self.mechanic_ids
        
        self._send_notifications(notification_type, title, message, recipients, data_extras=data)
        
        return True
    
    def action_escalate_to_mentor(self, mentor_id, escalation_notes=False):
        """Eskalasi permintaan dari leader ke mentor Kaizen"""
        self.ensure_one()
        if self.state != 'leader_responded':
            raise UserError('Permintaan harus dalam status "Leader Responded" untuk dieskalasi')
            
        self.write({
            'mentor_id': mentor_id,
            'escalated_to_mentor': True,
            'escalated_to_mentor_datetime': fields.Datetime.now(),
            'escalation_notes': escalation_notes,
            'state': 'escalated'
        })
        
        # Kirim notifikasi ke mentor
        self._send_mentor_assignment_notifications(mentor_id, self)
        
        # Kirim notifikasi ke mechanic
        notification_type = 'request_escalated'
        title = f"Permintaan dieskalasi ke Mentor: {self.name}"
        message = f"Permintaan bantuan Anda telah dieskalasi ke Mentor Kaizen"
        
        # Data tambahan untuk notifikasi
        data = {
            'request_id': self.id,
            'leader_id': self.leader_id.id if self.leader_id else False,
            'leader_name': self.leader_id.name if self.leader_id else 'Unknown',
            'mentor_id': mentor_id,
            'escalation_notes': escalation_notes,
        }
        
        # Kirim notifikasi ke mechanic
        recipients = self.mechanic_ids
        
        # Gunakan context untuk mencegah auto-subscription
        self = self.with_context(mail_create_nosubscribe=True)
        
        self._send_notifications(notification_type, title, message, recipients, data_extras=data)
        
        return True


    def action_start_mentoring(self):
        for record in self:
            if not record.mentor_id:
                raise UserError('Mentor harus ditentukan sebelum memulai')
        self.write({
            'state': 'in_progress',
            'start_datetime': fields.Datetime.now()
        })
        self._send_state_change_notifications('in_progress', self)
        return True

    def action_mark_solved(self):
        for record in self:
            if not record.resolution_notes:
                raise UserError('Harap isi catatan penyelesaian masalah')
                
            # Set resolved_by jika belum ditentukan
            if not record.resolved_by:
                if record.state == 'leader_responded':
                    record.resolved_by = 'leader'
                elif record.state in ['escalated', 'in_progress']:
                    record.resolved_by = 'mentor'
                    
        self.write({
            'state': 'solved',
            'end_datetime': fields.Datetime.now()
        })
        self._send_state_change_notifications('solved', self)
        return True

    def action_cancel_request(self):
        self.write({'state': 'cancelled'})
        self._send_state_change_notifications('cancelled', self)
        return True

    @api.depends('request_datetime', 'start_datetime')
    def _compute_response_time(self):
        for record in self:
            if record.request_datetime and record.start_datetime:
                delta = record.start_datetime - record.request_datetime
                record.response_time = delta.total_seconds() / 60
            else:
                record.response_time = 0

    @api.depends('start_datetime', 'end_datetime')
    def _compute_resolution_time(self):
        for record in self:
            if record.start_datetime and record.end_datetime:
                delta = record.end_datetime - record.start_datetime
                record.resolution_time = delta.total_seconds() / 60
            else:
                record.resolution_time = 0

    def _send_notifications(self, notification_type, title_template, message_template, recipients, data_extras=None, excluded_recipients=None):
        if not self or not recipients:
            return False
        
        try:
            if excluded_recipients:
                recipients = recipients - excluded_recipients
            if not recipients:
                return False
            
            # Untuk mencegah duplikat follower, gunakan context berikut
            self = self.with_context(mail_create_nosubscribe=True)
            
            result = True
            
            for record in self:
                mechanic_names = ", ".join(record.mechanic_ids.mapped('name')) if record.mechanic_ids else 'Unknown'
                category_name = dict(record._fields['problem_category'].selection).get(record.problem_category)
                
                context = {
                    'record': record,
                    'name': record.name,
                    'mechanic_names': mechanic_names,
                    'category': category_name,
                    'problem_description': record.problem_description,
                    'sale_order': record.sale_order_id.name if record.sale_order_id else '',
                }
                
                title = title_template.format(**context)
                message = message_template.format(**context)
                
                data = {
                    'request_id': record.id,
                    'state': record.state,
                    'category': record.problem_category,
                    'priority': record.priority,
                    'mechanic_names': mechanic_names,
                    'mentor_name': record.mentor_id.name if record.mentor_id else '',
                    'problem_description': record.problem_description,
                    'sale_order': record.sale_order_id.name if record.sale_order_id else '',
                    'total_items': 1
                }
                if data_extras:
                    data.update(data_extras)
                
                # Kirim notifikasi ke bus
                self._publish_notification_to_bus(notification_type, title, message, data)
                
                # Buat notifikasi di pitcar.notification untuk setiap recipient
                for recipient in recipients:
                    if recipient.user_id:
                        try:
                            # Tambahkan recipient_id ke data untuk membedakan notifikasi per recipient
                            notif_data = data.copy()
                            notif_data['recipient_id'] = recipient.id
                            notif_data['recipient_name'] = recipient.name
                            
                            # Buat atau update notifikasi
                            notif = self.env['pitcar.notification'].sudo().create_or_update_notification(
                                model='pitcar.mentor.request',
                                res_id=record.id,
                                type=notification_type,
                                title=title,
                                message=message,
                                request_time=fields.Datetime.now(),
                                data=notif_data
                            )
                            
                            if not notif:
                                _logger.warning(f"Failed to create notification for recipient {recipient.name}")
                                result = False
                        except Exception as e:
                            _logger.error(f"Error creating notification for recipient {recipient.name}: {str(e)}")
                            result = False
                
            return result
        except Exception as e:
            _logger.error(f"Error sending batch notifications: {str(e)}", exc_info=True)
            return False
        
    def message_subscribe(self, partner_ids=None, channel_ids=None, subtype_ids=None):
        """Override method to prevent duplicate followers"""
        if partner_ids:
            for record in self:
                # Periksa existing followers
                existing_partners = self.env['mail.followers'].sudo().search([
                    ('res_model', '=', self._name),
                    ('res_id', '=', record.id),
                    ('partner_id', 'in', partner_ids)
                ]).mapped('partner_id.id')
                
                # Hanya subscribe partner yang belum menjadi follower
                new_partner_ids = [pid for pid in partner_ids if pid not in existing_partners]
                if new_partner_ids:
                    super(MentorRequest, record).message_subscribe(
                        partner_ids=new_partner_ids, 
                        channel_ids=channel_ids, 
                        subtype_ids=subtype_ids
                    )
            return True
        return super().message_subscribe(partner_ids=partner_ids, channel_ids=channel_ids, subtype_ids=subtype_ids)

    def _send_state_change_notifications(self, state, records):
        if not records:
            return
        
        # Gunakan context untuk mencegah auto-subscription
        records = records.with_context(mail_create_nosubscribe=True)
        
        if state == 'requested':
            notification_type = 'new_mentor_request'
            title_template = "Permintaan Bantuan Baru: {name}"
            message_template = "Mekanik {mechanic_names} membutuhkan bantuan untuk {category}"
            position_domain = [('position_code', 'in', ['leader', 'foreman'])]
            recipients = self.env['pitcar.mechanic.new'].search(position_domain)
            excluded_recipients = records.mapped('mechanic_ids')
            return records._send_notifications(
                notification_type, title_template, message_template, recipients, excluded_recipients=excluded_recipients
            )
        
        elif state == 'in_progress':
            notification_type = 'mentor_start'
            title_template = "Bantuan Dimulai: {name}"
            message_template = "Mentor telah mulai menangani permintaan bantuan"
            recipients = records.mapped('mechanic_ids')
            return records._send_notifications(notification_type, title_template, message_template, recipients)
        
        elif state == 'solved':
            notification_type = 'mentor_solved'
            title_template = "Permintaan Bantuan Selesai: {name}"
            message_template = "Mentor telah menyelesaikan permintaan bantuan"
            recipients = records.mapped('mechanic_ids')
            return records._send_notifications(notification_type, title_template, message_template, recipients)
        
        elif state == 'cancelled':
            notification_type = 'mentor_cancelled'
            title_template = "Permintaan Bantuan Dibatalkan: {name}"
            message_template = "Permintaan bantuan telah dibatalkan"
            
            # Dapatkan semua mechanics dan mentor terkait
            mechanics = records.mapped('mechanic_ids')
            
            # Hanya gunakan recipients yang sudah memiliki user dan partner
            recipients = mechanics.filtered(lambda m: m.user_id and m.user_id.partner_id)
            return records._send_notifications(notification_type, title_template, message_template, recipients)

    def _send_mentor_assignment_notifications(self, mentor_id, records):
        if not records:
            return
        
        mentor = self.env['hr.employee'].browse(mentor_id)
        if not mentor.exists():
            _logger.warning(f"Mentor with ID {mentor_id} does not exist")
            return False
        
        # Gunakan context untuk mencegah auto-subscription
        records = records.with_context(mail_create_nosubscribe=True)
        
        notification_type = 'mentor_assignment'
        title_template = "Anda Ditugaskan sebagai Mentor: {name}"
        message_template = "Anda telah ditugaskan untuk membantu {mechanic_names} dengan {category}"
        
        # Coba cari mechanics berdasarkan employee_id
        mechanics = self.env['pitcar.mechanic.new'].search([('employee_id', '=', mentor.id)], limit=1)
        
        if not mechanics:
            # Jika tidak menemukan mechanic, buat notifikasi langsung untuk mentor partner
            if mentor.user_id and mentor.user_id.partner_id:
                _logger.info(f"Creating direct notification for mentor {mentor.name}")
                for record in records:
                    mechanic_names = ", ".join(record.mechanic_ids.mapped('name')) if record.mechanic_ids else 'Unknown'
                    category_name = dict(record._fields['problem_category'].selection).get(record.problem_category)
                    
                    context = {
                        'record': record,
                        'name': record.name,
                        'mechanic_names': mechanic_names,
                        'category': category_name,
                        'problem_description': record.problem_description,
                        'sale_order': record.sale_order_id.name if record.sale_order_id else '',
                    }
                    
                    title = title_template.format(**context)
                    message = message_template.format(**context)
                    
                    data = {
                        'request_id': record.id,
                        'mentor_id': mentor.id,
                        'mentor_name': mentor.name,
                        'mechanic_names': mechanic_names,
                        'category': record.problem_category
                    }
                    
                    self.env['pitcar.notification'].sudo().create_or_update_notification(
                        model='pitcar.mentor.request',
                        res_id=record.id,
                        type=notification_type,
                        title=title,
                        message=message,
                        request_time=fields.Datetime.now(),
                        data=data
                    )
                    
                    # Publish to bus
                    self._publish_notification_to_bus(notification_type, title, message, data)
                    
                return True
            else:
                _logger.warning(f"Mentor {mentor.name} has no user or partner")
                return False
        
        return records._send_notifications(notification_type, title_template, message_template, mechanics)

    def _publish_notification_to_bus(self, notification_type, title, message, data=None):
        try:
            payload = {
                'type': notification_type,
                'title': title,
                'message': message,
                'timestamp': fields.Datetime.now().isoformat(),
                'is_read': False
            }
            if data:
                payload['data'] = data
            message_json = json.dumps(payload)
            bus_service = self.env['bus.bus']
            bus_service.sendone('mentor_request_notifications', message_json)
            return True
        except Exception as e:
            _logger.error(f"Error publishing notification to bus: {str(e)}")
            return False


# Inherit Mechanic Model untuk tambah role mentor
class MechanicInherit(models.Model):
    _inherit = 'pitcar.mechanic.new'

    is_mentor = fields.Boolean('Is Mentor', default=False)
    # mentor_request_ids = fields.One2many('pitcar.mentor.request', 'mentor_id', string='Mentor Requests')
    # help_request_ids masih merujuk ke mechanic_id, tapi field ini sudah dihapus
    help_request_ids = fields.Many2many('pitcar.mentor.request', 'pitcar_mechanic_request_rel', 'mechanic_id', 'request_id', string='Help Requests')

    # Statistics
    total_mentor_requests = fields.Integer('Total Requests', compute='_compute_mentor_stats')
    solved_requests = fields.Integer('Solved Requests', compute='_compute_mentor_stats')
    avg_response_time = fields.Float('Avg Response Time', compute='_compute_mentor_stats')
    success_rate = fields.Float('Success Rate (%)', compute='_compute_mentor_stats')

    # Learning Progress untuk mekanik
    total_help_requests = fields.Integer('Total Help Requested', compute='_compute_mechanic_stats')
    avg_rating = fields.Float('Average Rating', compute='_compute_mechanic_stats')
    learning_progress = fields.Float('Learning Progress (%)', compute='_compute_mechanic_stats')

    @api.depends('employee_id')
    def _compute_mentor_stats(self):
        """Hitung statistik mentor berdasarkan employee_id"""
        for record in self:
            if record.employee_id:
                requests = self.env['pitcar.mentor.request'].search([('mentor_id', '=', record.employee_id.id)])
                total = len(requests)
                solved = len(requests.filtered(lambda r: r.state == 'solved'))
                record.total_mentor_requests = total
                record.solved_requests = solved
                record.success_rate = (solved / total * 100) if total > 0 else 0
                response_times = requests.mapped('response_time')
                record.avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            else:
                record.total_mentor_requests = 0
                record.solved_requests = 0
                record.success_rate = 0
                record.avg_response_time = 0

    # @api.depends('mentor_request_ids', 'mentor_request_ids.state')
    # def _compute_mentor_stats(self):
    #     """Hitung statistik untuk mentor"""
    #     for record in self:
    #         # Hindari multiple read dengan cached value
    #         requests = record.mentor_request_ids
    #         total = len(requests)
    #         solved = len(requests.filtered(lambda r: r.state == 'solved'))
            
    #         record.total_mentor_requests = total
    #         record.solved_requests = solved
    #         record.success_rate = (solved / total * 100) if total > 0 else 0
            
    #         # Optimasi untuk menghitung rata-rata
    #         response_times = requests.mapped('response_time')
    #         record.avg_response_time = sum(response_times) / len(response_times) if response_times else 0

    @api.depends('help_request_ids', 'help_request_ids.state', 'help_request_ids.mechanic_rating')
    def _compute_mechanic_stats(self):
        """Hitung statistik pembelajaran untuk mekanik"""
        for record in self:
            # Hindari multiple read dengan cached value
            requests = record.help_request_ids
            total = len(requests)
            record.total_help_requests = total
            
            # Optimasi untuk rating
            ratings = [int(r.mechanic_rating) for r in requests if r.mechanic_rating]
            record.avg_rating = sum(ratings) / len(ratings) if ratings else 0
            
            # Hitung learning progress
            if len(ratings) >= 2:
                # Bandingkan 2 rating awal dengan 2 rating terakhir
                initial_ratings = ratings[:2]
                recent_ratings = ratings[-2:]
                initial_avg = sum(initial_ratings) / len(initial_ratings)
                recent_avg = sum(recent_ratings) / len(recent_ratings)
                
                if initial_avg > 0:
                    improvement = ((recent_avg - initial_avg) / initial_avg) * 100
                    record.learning_progress = max(0, min(100, improvement))
                else:
                    record.learning_progress = 0
            else:
                record.learning_progress = 0