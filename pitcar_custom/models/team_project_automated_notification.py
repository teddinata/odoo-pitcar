# File: models/team_project_automated_notification.py
from odoo import models, fields, api, _
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class TeamProjectAutomatedNotification(models.Model):
    _name = 'team.project.automated.notification'
    _description = 'Automated Project Notifications'

    @api.model
    def send_task_deadline_notifications(self):
        """Kirim notifikasi untuk tugas yang mendekati deadline"""
        today = fields.Date.today()
        tomorrow = today + timedelta(days=1)
        upcoming_tasks = self.env['team.project.task'].sudo().search([
            ('planned_date_end', '>=', today),
            ('planned_date_end', '<=', tomorrow),
            ('state', 'not in', ['done', 'cancelled'])
        ])
        
        notification_batch = []
        for task in upcoming_tasks:
            # Notifikasi kepada pengguna yang ditugaskan
            for assignee in task.assigned_to:
                if assignee.user_id:
                    notification_batch.append({
                        'model': 'team.project.task',
                        'res_id': task.id,
                        'notif_type': 'deadline_approaching',
                        'title': f"Deadline Mendekat: {task.name}",
                        'message': f"Tugas '{task.name}' memiliki deadline pada {fields.Date.to_string(task.planned_date_end)}.",
                        'user_id': assignee.user_id.id,
                        'category': 'deadline_approaching',
                        'project_id': task.project_id.id,
                        'data': {
                            'task_id': task.id,
                            'project_id': task.project_id.id,
                            'action': 'view_task',
                            'days_remaining': (task.planned_date_end - today).days
                        },
                        'priority': 'high'
                    })
        
        # Buat notifikasi batch
        if notification_batch:
            self.env['team.project.notification'].sudo().create_notifications_batch(notification_batch)
            return len(notification_batch)
        
        return 0
    
    @api.model
    def _notify_approaching_deadlines(self):
        """Scheduled action untuk mengirim notifikasi deadline yang mendekat"""
        today = fields.Date.today()
        tomorrow = today + timedelta(days=1)
        
        # Ambil tugas yang deadline-nya besok dan belum selesai
        tasks = self.env['team.project.task'].search([
            ('state', 'not in', ['done', 'cancelled']),
            ('planned_date_end', '>=', fields.Datetime.to_string(fields.Datetime.now())),
            ('planned_date_end', '<=', fields.Datetime.to_string(fields.Datetime.now() + timedelta(days=1)))
        ])
        
        for task in tasks:
            # Kirim notifikasi ke semua assignee
            for assignee in task.assigned_to:
                if assignee.user_id:
                    hours_remaining = (fields.Datetime.from_string(task.planned_date_end) - 
                                     fields.Datetime.from_string(fields.Datetime.now())).total_seconds() / 3600
                    
                    self.env['team.project.notification'].create_project_notification(
                        model='team.project.task',
                        res_id=task.id,
                        type='deadline_approaching',
                        title=f"Tenggat Waktu Mendekati: {task.name}",
                        message=f"Tugas '{task.name}' jatuh tempo dalam {int(hours_remaining)} jam.",
                        project_id=task.project_id.id,
                        sender_id=False,  # Ini otomatis sistem
                        recipient_id=assignee.id,
                        category='deadline_approaching',
                        data={
                            'task_id': task.id,
                            'project_id': task.project_id.id,
                            'hours_remaining': hours_remaining,
                            'action': 'view_task'
                        },
                        priority='high'
                    )
    
    @api.model
    def _notify_overdue_tasks(self):
        """Scheduled action untuk mengirim notifikasi tugas yang terlambat"""
        now = fields.Datetime.now()
        
        # Ambil tugas yang sudah melewati deadline dan belum selesai
        tasks = self.env['team.project.task'].search([
            ('state', 'not in', ['done', 'cancelled']),
            ('planned_date_end', '<', fields.Datetime.to_string(now))
        ])
        
        for task in tasks:
            # Notifikasi ke assignee dan project manager
            recipients = task.assigned_to
            
            for recipient in recipients:
                if not recipient.user_id:
                    continue
                    
                # Hitung keterlambatan dalam jam
                hours_overdue = (now - fields.Datetime.from_string(task.planned_date_end)).total_seconds() / 3600
                days_overdue = hours_overdue / 24
                
                self.env['team.project.notification'].create_project_notification(
                    model='team.project.task',
                    res_id=task.id,
                    type='task_overdue',
                    title=f"Tugas Terlambat: {task.name}",
                    message=f"Tugas '{task.name}' telah terlambat selama {int(days_overdue)} hari.",
                    project_id=task.project_id.id,
                    sender_id=False,  # System
                    recipient_id=recipient.id,
                    category='task_overdue',
                    data={
                        'task_id': task.id,
                        'project_id': task.project_id.id,
                        'days_overdue': days_overdue,
                        'hours_overdue': hours_overdue,
                        'action': 'view_task'
                    },
                    priority='urgent'
                )
                
            # Notifikasi ke project manager juga
            if task.project_id.project_manager_id and task.project_id.project_manager_id.user_id:
                pm = task.project_id.project_manager_id
                if pm not in recipients:  # Jangan duplikasi notifikasi
                    hours_overdue = (now - fields.Datetime.from_string(task.planned_date_end)).total_seconds() / 3600
                    days_overdue = hours_overdue / 24
                    
                    self.env['team.project.notification'].create_project_notification(
                        model='team.project.task',
                        res_id=task.id,
                        type='task_overdue',
                        title=f"Overdue Task: {task.name}",
                        message=f"Task '{task.name}' assigned to {', '.join(task.assigned_to.mapped('name'))} is overdue by {int(days_overdue)} days.",
                        project_id=task.project_id.id,
                        sender_id=False,  # System
                        recipient_id=pm.id,
                        category='task_overdue',
                        # user_id=pm.user_id.id,
                        data={
                            'task_id': task.id,
                            'project_id': task.project_id.id,
                            'days_overdue': days_overdue,
                            'hours_overdue': hours_overdue,
                            'action': 'view_task'
                        },
                        priority='high'
                    )
    
    @api.model
    def _notify_meeting_reminders(self):
        """Send meeting reminders"""
        now = fields.Datetime.now()
        reminder_time = now + timedelta(hours=1)  # Send reminders for meetings in the next hour
        
        meetings = self.env['team.project.meeting'].search([
            ('state', 'not in', ['done', 'cancelled']),
            ('start_datetime', '>=', fields.Datetime.to_string(now)),
            ('start_datetime', '<=', fields.Datetime.to_string(reminder_time))
        ])
        
        for meeting in meetings:
            for attendee in meeting.attendee_ids:
                if not attendee.user_id:
                    continue
                    
                minutes_to_start = (fields.Datetime.from_string(meeting.start_datetime) - now).total_seconds() / 60
                
                self.env['team.project.notification'].create_project_notification(
                    model='team.project.meeting',
                    res_id=meeting.id,
                    type='meeting_reminder',
                    title=f"Meeting Reminder: {meeting.name}",
                    message=f"Your meeting '{meeting.name}' starts in {int(minutes_to_start)} minutes.",
                    project_id=meeting.project_id.id if meeting.project_id else False,
                    sender_id=False,  # System
                    recipient_id=attendee.id,
                    category='meeting_reminder',
                    user_id=attendee.user_id.id,
                    data={
                        'meeting_id': meeting.id,
                        'project_id': meeting.project_id.id if meeting.project_id else False,
                        'start_datetime': fields.Datetime.to_string(meeting.start_datetime),
                        'action': 'view_meeting'
                    },
                    priority='high'
                )