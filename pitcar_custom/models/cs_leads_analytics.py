# models/cs_leads_analytics.py
from odoo import models, fields, api, _, tools
from datetime import datetime, timedelta
import json
import io
import xlsxwriter

class CSLeadsAnalytics(models.Model):
    _name = 'cs.leads.analytics'
    _description = 'CS Leads Analytics'
    _auto = False

    # Dimensions
    cs_id = fields.Many2one('hr.employee', string='CS Staff')
    date = fields.Date('Date')
    source = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('website', 'Website'),
        ('other', 'Other')
    ], string='Source')
    
    # Metrics
    total_leads = fields.Integer('Total Leads')
    converted_leads = fields.Integer('Converted Leads')
    conversion_rate = fields.Float('Conversion Rate (%)')
    avg_response_time = fields.Float('Avg Response Time (hours)')
    avg_conversion_time = fields.Float('Avg Conversion Time (days)')
    
    # Revenue Metrics (for converted leads)
    total_revenue = fields.Float('Total Revenue')
    avg_deal_size = fields.Float('Average Deal Size')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () as id,
                    l.cs_id,
                    l.date,
                    l.source,
                    COUNT(l.id) as total_leads,
                    COUNT(CASE WHEN l.is_converted THEN 1 END) as converted_leads,
                    CASE 
                        WHEN COUNT(l.id) > 0 
                        THEN (COUNT(CASE WHEN l.is_converted THEN 1 END)::float / COUNT(l.id) * 100)
                        ELSE 0 
                    END as conversion_rate,
                    AVG(EXTRACT(EPOCH FROM (l.conversion_date - l.create_date))/3600) as avg_response_time,
                    AVG(EXTRACT(EPOCH FROM (l.conversion_date - l.create_date))/86400) as avg_conversion_time,
                    SUM(COALESCE(so.amount_total, 0)) as total_revenue,
                    CASE 
                        WHEN COUNT(CASE WHEN l.is_converted THEN 1 END) > 0 
                        THEN SUM(COALESCE(so.amount_total, 0)) / COUNT(CASE WHEN l.is_converted THEN 1 END)
                        ELSE 0 
                    END as avg_deal_size
                FROM cs_leads l
                LEFT JOIN sale_order so ON l.sale_order_id = so.id
                GROUP BY l.cs_id, l.date, l.source
            )
        """ % self._table)

class CSPerformanceReport(models.Model):
    _name = 'cs.performance.report'
    _description = 'CS Performance Report'
    
    name = fields.Char('Report Name', required=True)
    date_from = fields.Date('From Date', required=True)
    date_to = fields.Date('To Date', required=True)
    cs_ids = fields.Many2many('hr.employee', string='CS Staff')
    
    # Report Data
    data = fields.Text('Report Data', compute='_compute_report_data')
    
    @api.depends('date_from', 'date_to', 'cs_ids')
    def _compute_report_data(self):
        for report in self:
            domain = [
                ('date', '>=', report.date_from),
                ('date', '<=', report.date_to)
            ]
            if report.cs_ids:
                domain.append(('cs_id', 'in', report.cs_ids.ids))
                
            analytics = self.env['cs.leads.analytics'].search(domain)
            
            # Prepare data structure
            cs_data = {}
            for record in analytics:
                cs_name = record.cs_id.name
                if cs_name not in cs_data:
                    cs_data[cs_name] = {
                        'total_leads': 0,
                        'converted_leads': 0,
                        'conversion_rate': 0,
                        'total_revenue': 0,
                        'avg_response_time': 0,
                        'source_distribution': {},
                        'daily_performance': {}
                    }
                
                # Update metrics
                cs_data[cs_name]['total_leads'] += record.total_leads
                cs_data[cs_name]['converted_leads'] += record.converted_leads
                cs_data[cs_name]['total_revenue'] += record.total_revenue
                cs_data[cs_name]['avg_response_time'] = (
                    cs_data[cs_name]['avg_response_time'] + record.avg_response_time
                ) / 2
                
                # Update source distribution
                if record.source not in cs_data[cs_name]['source_distribution']:
                    cs_data[cs_name]['source_distribution'][record.source] = 0
                cs_data[cs_name]['source_distribution'][record.source] += record.total_leads
                
                # Update daily performance
                date_str = record.date.strftime('%Y-%m-%d')
                if date_str not in cs_data[cs_name]['daily_performance']:
                    cs_data[cs_name]['daily_performance'][date_str] = {
                        'leads': 0,
                        'conversions': 0,
                        'revenue': 0
                    }
                cs_data[cs_name]['daily_performance'][date_str]['leads'] += record.total_leads
                cs_data[cs_name]['daily_performance'][date_str]['conversions'] += record.converted_leads
                cs_data[cs_name]['daily_performance'][date_str]['revenue'] += record.total_revenue
            
            # Calculate final conversion rates
            for cs_name in cs_data:
                if cs_data[cs_name]['total_leads'] > 0:
                    cs_data[cs_name]['conversion_rate'] = (
                        cs_data[cs_name]['converted_leads'] / cs_data[cs_name]['total_leads'] * 100
                    )
            
            report.data = json.dumps(cs_data)

    def generate_excel_report(self):
        """Generate Excel report with detailed analysis"""
        self.ensure_one()
        
        # Create workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Add Summary worksheet
        self._create_summary_worksheet(workbook)
        
        # Add CS Performance worksheet
        self._create_cs_performance_worksheet(workbook)
        
        # Add Daily Trends worksheet
        self._create_daily_trends_worksheet(workbook)
        
        workbook.close()
        
        # Return the generated file
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/cs.performance.report/%s/data/%s?download=true' % (
                self.id,
                'CS_Performance_Report_%s.xlsx' % fields.Date.today()
            ),
            'target': 'self',
        }