# File: models/kpi_detail.py
from odoo import models, fields, api

class KPIDetail(models.Model):
    _name = 'cs.kpi.detail'
    _description = 'KPI Detail Values'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', required=True)
    period_month = fields.Integer('Month')
    period_year = fields.Integer('Year')
    kpi_type = fields.Selection([
        ('team_control', 'Mengontrol Kinerja Tim'),
        ('complaint_handling', 'Penyelesaian Komplain'),
        ('revenue_target', 'Target Revenue'),
        ('team_development', 'Pengembangan Tim'),
        ('operational', 'Kegiatan Operasional'),
        # SA KPIs
        ('customer_service', 'Melayani Customer'),
        ('service_analysis', 'Analisa Jasa'),
        ('service_efficiency', 'Efisiensi Pelayanan'),
        ('sa_revenue', 'Target Revenue SA'),
        ('sop_compliance', 'Kepatuhan SOP'),
        ('discipline', 'Kedisiplinan'),
        # CS KPIs
        ('online_response', 'Response Time Online'),
        ('leads_report', 'Laporan Leads'),
        ('customer_contact', 'Manajemen Kontak Customer'),
        ('service_reminder', 'Reminder Service'),
        ('documentation', 'Dokumentasi'),
        # Add Mechanic KPI types
        ('service_quality', 'Service Quality'),
        ('productivity', 'Productivity'),
        ('sop_compliance', 'SOP Compliance'),
        ('discipline', 'Discipline'),
        ('work_distribution', 'Work Distribution'),
        ('complaint_handling', 'Complaint Handling'),
        ('team_productivity', 'Team Productivity'),
        ('team_discipline', 'Team Discipline')
    ], string='KPI Type')
    
    weight = fields.Float('Bobot')
    target = fields.Float('Target')
    measurement = fields.Text('Tolak Ukur')
    actual = fields.Float('Aktual')
    description = fields.Text('Keterangan')
    
    _sql_constraints = [
        ('unique_kpi_period', 
         'unique(employee_id, period_month, period_year, kpi_type)',
         'KPI detail must be unique per employee, period and type!')
    ]