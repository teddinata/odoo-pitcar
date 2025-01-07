# models/hr_attendance.py
from odoo import models, fields, api
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
    
    def action_custom_export(self):
        """Custom Export Attendance Action"""
        # Create buffer untuk CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Ambil data filter dari context
        context = dict(self._context or {})
        date_from = context.get('date_from', fields.Date.today().replace(day=1))
        date_to = context.get('date_to', fields.Date.today())
        
        # Set timezone
        tz = pytz.timezone('Asia/Jakarta')
        
        # Generate tanggal
        start_date = fields.Date.from_string(date_from)
        end_date = fields.Date.from_string(date_to)
        dates = []
        curr_date = start_date
        while curr_date <= end_date:
            dates.append(curr_date)
            curr_date += timedelta(days=1)
            
        # Write header
        headers = ['Nama Karyawan', 'Departemen']
        for date in dates:
            headers.append(date.strftime('%d/%m'))
        writer.writerow(headers)
        
        # Group attendance by employee
        employees = self.env['hr.employee'].search([('active', '=', True)])
        
        for employee in employees:
            row = [employee.name, employee.department_id.name or '-']
            
            # Get attendance untuk setiap tanggal
            for date in dates:
                attendance = self.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', datetime.combine(date, datetime.min.time())),
                    ('check_in', '<', datetime.combine(date + timedelta(days=1), datetime.min.time()))
                ], limit=1)
                
                if attendance:
                    check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                    check_out = attendance.check_out and pytz.utc.localize(attendance.check_out).astimezone(tz)
                    
                    # Format waktu tanpa spasi
                    check_in_str = check_in.strftime('%H:%M')
                    check_out_str = check_out.strftime('%H:%M') if check_out else '00:00'
                    
                    # Tambah tanda * jika terlambat
                    if attendance.is_late:
                        check_in_str = f"{check_in_str}*"
                    
                    time_str = f"{check_in_str}{check_out_str}"
                    row.append(time_str)
                else:
                    row.append('-')
                    
            writer.writerow(row)
            
        # Add legend
        writer.writerow([])
        writer.writerow(['KETERANGAN:'])
        writer.writerow(['* = Terlambat (>08:00)'])
        writer.writerow(['- = Tidak Hadir'])
        writer.writerow(['Format Waktu = Check-inCheck-out (tanpa spasi)'])
        writer.writerow(['Contoh: 08:0017:00 = Masuk 08:00 Pulang 17:00'])
        
        # Create attachment
        filename = f'absensi_{date_from}_{date_to}.csv'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(output.getvalue().encode('utf-8-sig')),
            'store_fname': filename,
            'type': 'binary'
        })
        
        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}/{filename}?download=true',
            'target': 'self',
        }