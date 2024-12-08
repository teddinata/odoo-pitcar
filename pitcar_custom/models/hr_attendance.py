# models/hr_attendance.py
from datetime import timedelta
from odoo import models, fields, api

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    face_image = fields.Binary('Face Image', attachment=True, help='Compressed face image for verification')
    face_descriptor = fields.Text('Face Descriptor', help='Face encoding data for recognition')

    @api.model
    def _clean_old_attendance_photos(self):
        """Cron job untuk membersihkan foto attendance yang lebih dari 30 hari"""
        threshold_date = fields.Date.today() - timedelta(days=30)
        old_records = self.search([
            ('create_date', '<', threshold_date),
            ('face_image', '!=', False)
        ])
        return old_records.write({'face_image': False})