# Dalam file models/team_project_notification.py
from odoo import models, fields, api, _
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class TeamProjectNotification(models.Model):
    _name = 'team.project.notification'
    _description = 'Project Notification'
    _inherit = ['pitcar.notification']
    
    # Field tambahan untuk notifikasi proyek
    project_id = fields.Many2one('team.project', string='Project')
    sender_id = fields.Many2one('hr.employee', string='Sender')
    # recipient_id = fields.Many2one('hr.employee', string='Recipient')
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

    def get_recipient_employee(self):
        self.ensure_one()
        if self.user_id:
            employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.user_id.id)], limit=1)
            return employee
        return False
    
    @api.model
    def create_project_notification(self, model, res_id, type, title, message, 
                                  project_id=False, sender_id=False, user_id=False,
                                  category=False, **kwargs):
        """Create specialized project notification"""
        # Jangan membuat notifikasi jika sender == recipient berdasarkan user_id
        if sender_id and user_id:
            sender_employee = self.env['hr.employee'].sudo().browse(sender_id)
            if sender_employee.exists() and sender_employee.user_id and sender_employee.user_id.id == user_id:
                return False
        
        # Jika user_id tidak diberikan tapi recipient_id diberikan, ambil user_id dari employee
        if not user_id and kwargs.get('recipient_id'):
            employee = self.env['hr.employee'].sudo().browse(kwargs.get('recipient_id'))
            if employee.exists() and employee.user_id:
                user_id = employee.user_id.id
                
        vals = {
            'model': model,
            'res_id': res_id,
            'type': type,
            'title': title,
            'message': message,
            'project_id': project_id,
            'sender_id': sender_id,
            'user_id': user_id,  # Gunakan user_id, bukan recipient_id
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
            ('user_id', '=', user_id)  # Gunakan user_id, bukan recipient_id
        ], limit=1)
        
        if existing:
            existing.write(vals)
            return existing
        else:
            return self.create(vals)