# models/team_project_notification.py
from odoo import models, fields, api, _
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class TeamProjectNotification(models.Model):
    _name = 'team.project.notification'
    _description = 'Project Management Notification'
    _order = 'request_time desc, id desc'
    
    # Core fields
    name = fields.Char('Notification Name', store=True)
    model = fields.Char('Related Model', required=True, index=True)
    res_id = fields.Integer('Resource ID', required=True, index=True)
    type = fields.Char('Notification Type', required=True, index=True)
    title = fields.Char('Notification Title', required=True)
    message = fields.Text('Notification Message', required=True)
    data = fields.Text('Notification Data')
    
    # Time information
    request_time = fields.Datetime('Request Time', default=fields.Datetime.now, index=True)
    expiration = fields.Datetime('Expiration Date')
    
    # Status
    is_read = fields.Boolean('Is Read', default=False, index=True)
    is_actionable = fields.Boolean('Has Action', default=False)
    action_taken = fields.Boolean('Action Taken', default=False)
    
    # Participants - Menggunakan relasi hr.employee untuk sender dan recipient
    sender_id = fields.Many2one('hr.employee', string='Sender', index=True)
    recipient_id = fields.Many2one('hr.employee', string='Recipient', required=True, index=True,
                                  help="The employee who will receive this notification")
    
    # Computed field untuk user_id jika diperlukan untuk backward compatibility
    user_id = fields.Many2one('res.users', string='User', compute='_compute_user_id', store=True, 
                            help="Related user of the recipient employee")
    
    # Source information
    project_id = fields.Many2one('team.project', string='Project', index=True)
    
    # Classification
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
    ], string='Category', required=True, default='system', index=True)
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='normal', index=True)
    
    notification_channel = fields.Selection([
        ('email', 'Email'),
        ('app', 'App Notification'),
        ('sms', 'SMS'),
        ('all', 'All Channels')
    ], string='Notification Channel', default='app')
    
    action_url = fields.Char('Action URL')
    
    _sql_constraints = [
        ('unique_employee_notification', 
         'unique(model, res_id, type, recipient_id, notification_category)', 
         'Duplicate notification is not allowed!')
    ]
    
    # @api.depends('title', 'id')
    # def _compute_name(self):
    #     for notif in self:
    #         if notif.title and notif.id:
    #             notif.name = f"{notif.title} (ID: {notif.id})"
    #         else:
    #             notif.name = "New Notification"
    
    @api.depends('recipient_id')
    def _compute_user_id(self):
        """Compute related user_id dari recipient_id employee"""
        for notif in self:
            notif.user_id = notif.recipient_id.user_id.id if notif.recipient_id and notif.recipient_id.user_id else False

    @api.model
    def create_notifications_batch(self, notifications_data):
        """Create multiple notifications in batch for better performance"""
        created_notifs = []
        for data in notifications_data:
            notif = self.create_project_notification(**data)
            if notif:
                created_notifs.append(notif.id)
        return created_notifs
    
    @api.model
    def create_project_notification(self, model, res_id, notif_type, title, message, 
                          recipient_id, category=False, project_id=False, sender_id=False, **kwargs):
        """Create a notification with improved employee-based targeting"""
        try:
            # Validate required parameters
            if not all([model, res_id, notif_type, title, message, recipient_id]):
                _logger.warning("Missing required parameters for notification creation")
                return False
            
            # Validate recipient employee exists
            recipient = self.env['hr.employee'].sudo().browse(recipient_id)
            if not recipient.exists():
                _logger.warning(f"Cannot create notification: Employee recipient {recipient_id} does not exist")
                return False
                
            # Skip self-notifications
            if sender_id and sender_id == recipient_id:
                _logger.info(f"Skipping self-notification for employee {recipient_id}")
                return False
                
            # Validate sender employee if provided
            if sender_id:
                sender = self.env['hr.employee'].sudo().browse(sender_id)
                if not sender.exists():
                    _logger.warning(f"Invalid sender_id {sender_id}, using system as sender")
                    sender_id = False
                    
            # Prepare notification values
            vals = {
                'model': model,
                'res_id': res_id,
                'type': notif_type,
                'title': title,
                'message': message,
                'recipient_id': recipient_id,
                'sender_id': sender_id,
                'notification_category': category or notif_type,
                'project_id': project_id,
                'request_time': kwargs.get('request_time', fields.Datetime.now()),
                'expiration': kwargs.get('expiration', False),
                'is_actionable': kwargs.get('is_actionable', False),
                'action_url': kwargs.get('action_url', False),
                'priority': kwargs.get('priority', 'normal'),
                'notification_channel': kwargs.get('channel', 'app'),
                'data': json.dumps(kwargs.get('data', {})) if kwargs.get('data') else False,
            }
            
            # Check for duplicate
            domain = [
                ('model', '=', model),
                ('res_id', '=', res_id),
                ('type', '=', notif_type),
                ('recipient_id', '=', recipient_id),
                ('notification_category', '=', vals['notification_category'])
            ]
            
            existing = self.search(domain, limit=1)
            
            if existing:
                # Update existing notification
                existing.write(vals)
                _logger.info(f"Updated existing notification #{existing.id}")
                return existing
            else:
                # Create new notification
                new_notif = self.create(vals)
                _logger.info(f"Created new notification #{new_notif.id} for employee #{recipient_id}")
                return new_notif
                
        except Exception as e:
            _logger.error(f"Error creating notification: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            return False
            
    def mark_as_read(self):
        """Mark notification as read"""
        self.write({'is_read': True})
        
    def mark_action_taken(self):
        """Mark notification action as taken"""
        self.write({'action_taken': True})
        
    def action_send_email(self):
        """Send email notification"""
        # Implementation for sending email
        pass