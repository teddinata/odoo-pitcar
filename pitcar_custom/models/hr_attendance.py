# models/hr_attendance.py
from odoo import models, fields, api
from odoo.http import request
import pytz
import io
import csv
from datetime import datetime, timedelta
import base64

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    face_image = fields.Binary('Face Image', attachment=True, help='Compressed face image for verification')
    face_descriptor = fields.Text('Face Descriptor', help='Face encoding data for recognition')

    is_late = fields.Boolean('Is Late', compute='_compute_is_late', store=True)
    late_duration = fields.Float('Late Duration (Minutes)', compute='_compute_late_duration', store=True)

    actual_worked_hours = fields.Float('Actual Worked Hours', compute='_compute_actual_worked_hours', store=True)

    @api.depends('check_in', 'check_out')
    def _compute_actual_worked_hours(self):
        for attendance in self:
            if not attendance.check_out:
                attendance.actual_worked_hours = 0
                continue
                
            # Convert to local timezone
            tz = pytz.timezone('Asia/Jakarta')
            check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
            check_out = pytz.utc.localize(attendance.check_out).astimezone(tz)
            
            # Calculate total duration
            total_duration = (check_out - check_in).total_seconds() / 3600
            
            # Kurangi 1 jam untuk istirahat jika durasi > 6 jam
            if total_duration > 6:
                total_duration -= 1
                
            attendance.actual_worked_hours = total_duration

    @api.depends('check_in')
    def _compute_is_late(self):
        for attendance in self:
            if attendance.check_in:
                tz = pytz.timezone('Asia/Jakarta')
                check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                target_time = check_in.replace(hour=8, minute=1, second=0)
                attendance.is_late = check_in > target_time
            else:
                attendance.is_late = False

    @api.depends('check_in', 'is_late')
    def _compute_late_duration(self):
        for attendance in self:
            if attendance.is_late and attendance.check_in:
                tz = pytz.timezone('Asia/Jakarta')
                check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                target_time = check_in.replace(hour=8, minute=1, second=0)
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
    
    def action_custom_export(self, date_from=None, date_to=None, department_id=None):
        """Custom Export Attendance dengan filter"""
        if not (date_from and date_to):
            # Jika dipanggil langsung dari button, tampilkan wizard
            action = {
                'type': 'ir.actions.act_window',
                'name': 'Export Attendance',
                'res_model': 'attendance.export.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_date_from': fields.Date.today(),
                    'default_date_to': fields.Date.today(),
                }
            }
            return action

        # Buat file temporary untuk menyimpan CSV
        data = io.StringIO()
        writer = csv.writer(data, delimiter=';')
        
        # Set timezone
        tz = pytz.timezone('Asia/Jakarta')
        
        # Generate dates range
        start_date = fields.Date.from_string(date_from)
        end_date = fields.Date.from_string(date_to)
        dates = []
        curr_date = start_date
        while curr_date <= end_date:
            dates.append(curr_date)
            curr_date += timedelta(days=1)

        # Write headers
        headers = ['Nama Karyawan', 'Departemen']
        for date in dates:
            headers.append(date.strftime('%d/%m'))
        writer.writerow(headers)

        # Get employees dengan filter department
        domain = [('active', '=', True)]
        if department_id:
            domain.append(('department_id', '=', department_id))
        employees = self.env['hr.employee'].search(domain)

        for employee in employees:
            row = [employee.name, employee.department_id.name or '-']
            
            for date in dates:
                attendance = self.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', datetime.combine(date, datetime.min.time())),
                    ('check_in', '<', datetime.combine(date + timedelta(days=1), datetime.min.time()))
                ], limit=1)
                
                if attendance:
                    check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                    check_out = attendance.check_out and pytz.utc.localize(attendance.check_out).astimezone(tz)
                    
                    check_in_str = check_in.strftime('%H:%M')
                    check_out_str = check_out.strftime('%H:%M') if check_out else '00:00'
                    
                    time_str = f"'{check_in_str}{check_out_str}"
                    row.append(time_str)
                else:
                    row.append("'-")
                    
            writer.writerow(row)

        # Generate attachment
        filename = f'absensi_{date_from}_{date_to}.csv'
        csv_data = data.getvalue().encode('utf-8-sig')
        data.close()

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(csv_data),
            'mimetype': 'text/csv',
            'res_model': self._name,
            'res_id': self.id,
        })

        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}/{filename}?download=true',
            'target': 'self',
        }