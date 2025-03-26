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
        ('team_discipline', 'Team Discipline'),
        ('employee_development', 'Pengembangan Karyawan')
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

class MarketingKPIDetail(models.Model):
    _name = 'marketing.kpi.detail'
    _description = 'Marketing KPI Detail'
    _inherit = ['mail.thread']
    
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True, tracking=True)
    period_month = fields.Integer('Period Month', required=True, tracking=True)
    period_year = fields.Integer('Period Year', required=True, tracking=True)
    
    kpi_type = fields.Selection([
        # Design KPIs
        ('design_production', 'Design Production'),
        ('design_time_accuracy', 'Design Time Accuracy'),
        ('design_revision', 'Design Revision Count'),
        ('design_bau', 'Design BAU Days'),
        
        # Video KPIs
        ('video_production', 'Video Production'),
        ('video_time_accuracy', 'Video Time Accuracy'),
        ('video_revision', 'Video Revision Count'),
        ('video_bau', 'Video BAU Days'),
        
        # Social Media KPIs
        ('content_publishing', 'Content Publishing'),
        ('engagement_rate', 'Engagement Rate'),
        ('followers_growth', 'Followers Growth'),
        ('response_rate', 'Response Rate'),
        
        # Digital Marketing KPIs
        ('leads_generation', 'Leads Generation'),
        ('conversion_rate', 'Conversion Rate'),
        ('cost_per_lead', 'Cost Per Lead'),
        ('campaign_engagement', 'Campaign Engagement'),
        
        # Marketing Lead KPIs
        ('team_leads', 'Team Leads'),
        ('team_cpl', 'Team Cost Per Lead'),
        ('leads_conversion', 'Leads Conversion'),
        ('brand_awareness', 'Brand Awareness'),
        ('team_achievement', 'Team Achievement')
    ], string='KPI Type', required=True, tracking=True)
    
    weight = fields.Float('Weight (%)', required=True, tracking=True)
    target = fields.Float('Target', required=True, tracking=True)
    measurement = fields.Text('Measurement', tracking=True)
    actual = fields.Float('Actual Value', tracking=True)
    description = fields.Text('Additional Notes', tracking=True)
    
    _sql_constraints = [
        ('unique_kpi_period', 'unique(employee_id, period_month, period_year, kpi_type)', 
         'KPI must be unique per employee, period, and KPI type!')
    ]