# wizards/attendance_export_wizard.py
from odoo import models, fields, api

class AttendanceExportWizard(models.TransientModel):
    _name = 'attendance.export.wizard'
    _description = 'Attendance Export Wizard'

    date_from = fields.Date('Date From', required=True, default=fields.Date.context_today)
    date_to = fields.Date('Date To', required=True, default=fields.Date.context_today)
    department_id = fields.Many2one('hr.department', string='Department')

    def action_export(self):
        return self.env['hr.attendance'].action_custom_export(
            date_from=self.date_from,
            date_to=self.date_to,
            department_id=self.department_id.id if self.department_id else False
        )