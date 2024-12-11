# models/hr_attendance.py
from datetime import timedelta
from odoo import models, fields, api
import pytz

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    face_image = fields.Binary('Face Image', attachment=True, help='Compressed face image for verification')
    face_descriptor = fields.Text('Face Descriptor', help='Face encoding data for recognition')

    is_late = fields.Boolean('Is Late', compute='_compute_is_late', store=True)
    late_duration = fields.Float('Late Duration (Minutes)', compute='_compute_late_duration', store=True)

    @api.depends('check_in')
    def _compute_is_late(self):
        for attendance in self:
            if attendance.check_in:
                tz = pytz.timezone('Asia/Jakarta')
                check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                target_time = check_in.replace(hour=8, minute=0, second=0)
                attendance.is_late = check_in > target_time
            else:
                attendance.is_late = False

    @api.depends('check_in', 'is_late')
    def _compute_late_duration(self):
        for attendance in self:
            if attendance.is_late and attendance.check_in:
                tz = pytz.timezone('Asia/Jakarta')
                check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                target_time = check_in.replace(hour=8, minute=0, second=0)
                duration = (check_in - target_time).total_seconds() / 60
                attendance.late_duration = duration
            else:
                attendance.late_duration = 0

    @api.model
    def _clean_old_attendance_photos(self):
        """Cron job untuk membersihkan foto attendance yang lebih dari 30 hari"""
        threshold_date = fields.Date.today() - timedelta(days=30)
        old_records = self.search([
            ('create_date', '<', threshold_date),
            ('face_image', '!=', False)
        ])
        return old_records.write({'face_image': False})