# models/team_project_notification.py
from odoo import models, fields, api, _
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class TeamProjectNotification(models.Model):
    _name = 'team.project.notification'
    _description = 'Project Notification'
    _order = 'request_time desc, id desc'
    
    # Definisi field lengkap
    model = fields.Char('Related Model', required=True)
    res_id = fields.Integer('Resource ID', required=True)
    type = fields.Char('Notification Type', required=True)
    title = fields.Char('Notification Title', required=True)
    message = fields.Text('Notification Message', required=True)
    data = fields.Text('Notification Data')
    request_time = fields.Datetime('Request Time', default=fields.Datetime.now)
    is_read = fields.Boolean('Is Read', default=False)
    
    # Field spesifik untuk notifikasi proyek
    project_id = fields.Many2one('team.project', string='Project')
    sender_id = fields.Many2one('hr.employee', string='Sender')
    # Gunakan kedua field
    user_id = fields.Many2one('res.users', string='Recipient User')
    employee_id = fields.Many2one('hr.employee', string='Recipient Employee')
    
    # Computed fields untuk membantu mencari relasi
    employee_user_id = fields.Many2one('res.users', related='employee_id.user_id', store=True)
    user_employee_id = fields.Many2one('hr.employee', compute='_compute_user_employee', store=True)
    
    notification_channel = fields.Selection([
        ('email', 'Email'),
        ('app', 'App Notification'),
        ('sms', 'SMS'),
        ('all', 'All Channels')
    ], string='Notification Channel', default='app')
    notification_category = fields.Selection([
        ('task_assigned', 'Task Assignment'),
        ('task_updated', 'Task Update'),
        ('task_completed', 'Task Completion'),
        ('task_overdue', 'Task Overdue'),
        ('comment_added', 'New Comment'),
        ('meeting_scheduled', 'Meeting Scheduled'),
        ('meeting_reminder', 'Meeting Reminder'),
        ('document_uploaded', 'Document Uploaded'),
        ('project_update', 'Project Update'),
        ('deadline_approaching', 'Deadline Approaching'),
        ('mention', 'Mention in Comment'),
        ('new_message', 'New Message'),
        ('system', 'System Notification')
    ], string='Category', required=True, default='system')
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='normal')
    action_url = fields.Char('Action URL')
    expiration = fields.Datetime('Expiration')
    is_actionable = fields.Boolean('Has Action', default=False)
    action_taken = fields.Boolean('Action Taken', default=False)

    # Mengaitkan notifikasi dengan res_model dan res_id untuk menghindari duplikat
    _sql_constraints = [
        ('unique_user_notification', 
         'unique(model, res_id, type, user_id)', 
         'Duplicate notification for the same user is not allowed!')
    ]

    @api.depends('user_id')
    def _compute_user_employee(self):
        for record in self:
            if record.user_id:
                employee = self.env['hr.employee'].sudo().search([
                    ('user_id', '=', record.user_id.id)
                ], limit=1)
                record.user_employee_id = employee.id if employee else False
            else:
                record.user_employee_id = False
                
    # Metode untuk mengisi kedua field secara otomatis
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Jika user_id diberikan tapi employee_id tidak
            if vals.get('user_id') and not vals.get('employee_id'):
                employee = self.env['hr.employee'].sudo().search([
                    ('user_id', '=', vals['user_id'])
                ], limit=1)
                if employee:
                    vals['employee_id'] = employee.id
            
            # Jika employee_id diberikan tapi user_id tidak
            elif vals.get('employee_id') and not vals.get('user_id'):
                employee = self.env['hr.employee'].sudo().browse(vals['employee_id'])
                if employee.exists() and employee.user_id:
                    vals['user_id'] = employee.user_id.id
        
        return super(TeamProjectNotification, self).create(vals_list)

    @api.model
    def create_project_notification(self, model, res_id, type, title, message, 
                                project_id=False, sender_id=False, user_id=False, 
                                employee_id=False, category=False, **kwargs):
        """Create specialized project notification with better employee/user handling"""
        # Resolusi sender_id ke user_id
        sender_user_id = False
        if sender_id:
            sender_employee = self.env['hr.employee'].sudo().browse(sender_id)
            if sender_employee.exists() and sender_employee.user_id:
                sender_user_id = sender_employee.user_id.id
        
        # Resolusi employee_id ke user_id dan sebaliknya
        recipient_user_id = user_id
        recipient_employee_id = employee_id
        
        # Jika hanya employee_id yang diberikan, cari user_id-nya
        if recipient_employee_id and not recipient_user_id:
            employee = self.env['hr.employee'].sudo().browse(recipient_employee_id)
            if employee.exists() and employee.user_id:
                recipient_user_id = employee.user_id.id
        
        # Jika hanya user_id yang diberikan, cari employee_id-nya
        elif recipient_user_id and not recipient_employee_id:
            employee = self.env['hr.employee'].sudo().search([
                ('user_id', '=', recipient_user_id)
            ], limit=1)
            if employee:
                recipient_employee_id = employee.id
        
        # Jangan membuat notifikasi jika sender == recipient
        if sender_user_id and recipient_user_id and sender_user_id == recipient_user_id:
            return False
        
        # Jika tidak ada user_id yang valid, tidak bisa membuat notifikasi
        if not recipient_user_id:
            return False
        
        vals = {
            'model': model,
            'res_id': res_id,
            'type': type,
            'title': title,
            'message': message,
            'project_id': project_id,
            'sender_id': sender_id,
            'user_id': recipient_user_id,
            'employee_id': recipient_employee_id,
            'notification_category': category or type,
            'request_time': kwargs.get('request_time', fields.Datetime.now()),
            'data': json.dumps(kwargs.get('data')) if isinstance(kwargs.get('data'), dict) else kwargs.get('data'),
            'is_read': False,
            'priority': kwargs.get('priority', 'normal'),
            'notification_channel': kwargs.get('channel', 'app')
        }
                
        # Cek apakah sudah ada notifikasi yang sama
        existing = self.search([
            ('model', '=', model), 
            ('res_id', '=', res_id), 
            ('type', '=', type),
            ('user_id', '=', recipient_user_id)
        ], limit=1)
        
        if existing:
            existing.write(vals)
            return existing
        else:
            return self.create(vals)