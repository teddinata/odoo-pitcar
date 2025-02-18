# controllers/leads_analytics_api.py
from odoo import http
from odoo.http import request
import logging
import json
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class LeadsAnalyticsAPI(http.Controller):
    @http.route('/web/v1/leads/dashboard', type='json', auth='user', methods=['POST'])
    def get_dashboard_data(self, **kw):
        """Get dashboard statistics and metrics"""
        try:
            domain = []
            if kw.get('date_from'):
                domain.append(('date', '>=', kw['date_from']))
            if kw.get('date_to'):
                domain.append(('date', '<=', kw['date_to']))

            leads = request.env['cs.leads'].sudo().search(domain)
            
            # Calculate summary metrics
            total_leads = len(leads)
            converted_leads = len(leads.filtered(lambda l: l.is_converted))
            total_revenue = sum(leads.mapped('omzet'))
            
            # Calculate conversion rate
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
            
            # Get funnel data
            funnel = {
                'new': len(leads.filtered(lambda l: l.state == 'new')),
                'contacted': len(leads.filtered(lambda l: l.state == 'contacted')),
                'qualified': len(leads.filtered(lambda l: l.state == 'qualified')),
                'converted': converted_leads,
                'lost': len(leads.filtered(lambda l: l.state == 'lost'))
            }
            
            # Calculate source performance
            source_performance = {}
            for lead in leads:
                source = lead.source or 'undefined'
                if source not in source_performance:
                    source_performance[source] = {
                        'total': 0,
                        'converted': 0,
                        'revenue': 0
                    }
                source_performance[source]['total'] += 1
                if lead.is_converted:
                    source_performance[source]['converted'] += 1
                    source_performance[source]['revenue'] += lead.omzet or 0
            
            # Get CS performance
            cs_performance = {}
            for lead in leads:
                cs_name = lead.cs_id.name
                if cs_name not in cs_performance:
                    cs_performance[cs_name] = {
                        'total': 0,
                        'converted': 0,
                        'revenue': 0
                    }
                cs_performance[cs_name]['total'] += 1
                if lead.is_converted:
                    cs_performance[cs_name]['converted'] += 1
                    cs_performance[cs_name]['revenue'] += lead.omzet or 0

            return {
                'status': 'success',
                'data': {
                    'summary': {
                        'total_leads': total_leads,
                        'conversion_rate': round(conversion_rate, 2),
                        'total_revenue': total_revenue,
                        'avg_response_time': 0,  # TODO: Calculate from followup data
                        'conversion_growth': 0  # TODO: Calculate month-over-month growth
                    },
                    'funnel': funnel,
                    'source_performance': source_performance,
                    'cs_performance': cs_performance
                }
            }

        except Exception as e:
            _logger.error(f"Error getting dashboard data: {str(e)}")
            return {'status': 'error', 'message': str(e)}


    def _calculate_trends(self, daily_data):
        """Calculate trends from daily data"""
        dates = sorted(daily_data.keys())
        if not dates:
            return {}
            
        # Calculate 7-day moving averages
        moving_averages = {
            'leads': [],
            'conversions': [],
            'revenue': []
        }
        
        for i in range(len(dates)):
            window_start = max(0, i-6)
            window = dates[window_start:i+1]
            
            leads_avg = sum(daily_data[d]['leads'] for d in window) / len(window)
            conv_avg = sum(daily_data[d]['conversions'] for d in window) / len(window)
            rev_avg = sum(daily_data[d]['revenue'] for d in window) / len(window)
            
            moving_averages['leads'].append({
                'date': dates[i],
                'value': round(leads_avg, 2)
            })
            moving_averages['conversions'].append({
                'date': dates[i],
                'value': round(conv_avg, 2)
            })
            moving_averages['revenue'].append({
                'date': dates[i],
                'value': round(rev_avg, 2)
            })
        
        # Calculate growth rates
        first_week = sum(daily_data[d]['leads'] for d in dates[:7])
        last_week = sum(daily_data[d]['leads'] for d in dates[-7:])
        
        growth_rates = {
            'leads': ((last_week - first_week) / first_week * 100) if first_week > 0 else 0,
            'conversions': self._calculate_growth_rate(daily_data, dates, 'conversions'),
            'revenue': self._calculate_growth_rate(daily_data, dates, 'revenue')
        }
        
        return {
            'moving_averages': moving_averages,
            'growth_rates': growth_rates
        }

    def _calculate_growth_rate(self, data, dates, metric):
        """Calculate growth rate for a specific metric"""
        if len(dates) < 14:  # Need at least 2 weeks of data
            return 0
            
        first_week = sum(data[d][metric] for d in dates[:7])
        last_week = sum(data[d][metric] for d in dates[-7:])
        
        return ((last_week - first_week) / first_week * 100) if first_week > 0 else 0

    def _calculate_rankings(self, cs_data):
        """Calculate CS rankings based on different metrics"""
        rankings = {
            'conversion_rate': [],
            'total_leads': [],
            'total_revenue': []
        }
        
        # Conversion rate ranking
        conv_rate_list = [(name, data['conversion_rate']) 
                         for name, data in cs_data.items()]
        conv_rate_list.sort(key=lambda x: x[1], reverse=True)
        rankings['conversion_rate'] = [
            {'name': item[0], 'value': round(item[1], 2)}
            for item in conv_rate_list
        ]
        
        # Total leads ranking
        leads_list = [(name, data['total_leads']) 
                     for name, data in cs_data.items()]
        leads_list.sort(key=lambda x: x[1], reverse=True)
        rankings['total_leads'] = [
            {'name': item[0], 'value': item[1]}
            for item in leads_list
        ]
        
        # Revenue ranking
        revenue_list = [(name, data['total_revenue']) 
                       for name, data in cs_data.items()]
        revenue_list.sort(key=lambda x: x[1], reverse=True)
        rankings['total_revenue'] = [
            {'name': item[0], 'value': round(item[1], 2)}
            for item in revenue_list
        ]
        
        return rankings

    @http.route('/web/v1/leads/reports', type='json', auth='user', methods=['POST'])
    def generate_report(self, **kw):
        """Generate detailed performance report"""
        try:
            report_vals = {
                'name': kw.get('name', 'CS Performance Report'),
                'date_from': kw.get('date_from'),
                'date_to': kw.get('date_to'),
                'cs_ids': [(6, 0, kw.get('cs_ids', []))]
            }
            
            report = request.env['cs.performance.report'].sudo().create(report_vals)
            
            if kw.get('format') == 'excel':
                return {
                    'status': 'success',
                    'data': {
                        'report_id': report.id,
                        'download_url': f'/web/content/cs.performance.report/{report.id}/data'
                    }
                }
            else:
                return {
                    'status': 'success',
                    'data': json.loads(report.data)
                }
                
        except Exception as e:
            _logger.error(f"Error generating report: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_conversion_funnel(self, analytics):
        """Generate conversion funnel data"""
        leads_domain = []
        if analytics:
            leads_domain.extend([
                ('date', '>=', min(analytics.mapped('date'))),
                ('date', '<=', max(analytics.mapped('date')))
            ])
        
        leads = request.env['cs.leads'].sudo().search(leads_domain)
        
        funnel_data = {
            'new': len(leads.filtered(lambda l: l.state == 'new')),
            'contacted': len(leads.filtered(lambda l: l.state == 'contacted')),
            'qualified': len(leads.filtered(lambda l: l.state == 'qualified')),
            'converted': len(leads.filtered(lambda l: l.state == 'converted')),
            'lost': len(leads.filtered(lambda l: l.state == 'lost'))
        }
        
        # Calculate conversion rates between stages
        total = funnel_data['new']
        if total > 0:
            funnel_data['contact_rate'] = (funnel_data['contacted'] / total) * 100
            funnel_data['qualification_rate'] = (funnel_data['qualified'] / total) * 100
            funnel_data['conversion_rate'] = (funnel_data['converted'] / total) * 100
            funnel_data['loss_rate'] = (funnel_data['lost'] / total) * 100
        
        # Calculate average time in each stage
        stage_durations = leads.mapped(lambda l: {
            'to_contact': (l.first_contact_date - l.create_date).total_seconds() / 3600 if l.first_contact_date else 0,
            'to_qualify': (l.qualification_date - l.first_contact_date).total_seconds() / 3600 if l.qualification_date else 0,
            'to_convert': (l.conversion_date - l.qualification_date).total_seconds() / 3600 if l.conversion_date else 0
        })
        
        if stage_durations:
            funnel_data['avg_times'] = {
                'to_contact': sum(d['to_contact'] for d in stage_durations) / len(stage_durations),
                'to_qualify': sum(d['to_qualify'] for d in stage_durations) / len(stage_durations),
                'to_convert': sum(d['to_convert'] for d in stage_durations) / len(stage_durations)
            }
        
        return funnel_data