import logging
import csv
from io import StringIO
from datetime import datetime, timedelta
from odoo import http, _, fields
from odoo.http import request, Response
import pytz
import re

_logger = logging.getLogger(__name__)

class MarketingKPIOverview(http.Controller):
    @http.route('/web/v2/kpi/marketing', type='json', auth='user', methods=['POST'], csrf=False)
    def get_marketing_kpi(self, **kw):
        """Get KPI data for Marketing Department"""
        try:
            # Debug log input parameters
            _logger.info(f"Received marketing KPI request: {kw}")

            # Extract and validate parameter 
            employee_id = kw.get('employee_id')
            if not employee_id:
                return {'status': 'error', 'message': 'Employee ID is required'}

            # Get and validate month/year
            current_date = datetime.now()
            month = int(kw.get('month', current_date.month))
            year = int(kw.get('year', current_date.year))

            # Validate range
            if not (1 <= month <= 12):
                return {'status': 'error', 'message': 'Month must be between 1 and 12'}
                
            if year < 2000 or year > 2100:
                return {'status': 'error', 'message': 'Invalid year'}

            # Get employee
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            if not employee.exists():
                return {'status': 'error', 'message': 'Employee not found'}

            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Calculate date range in local timezone
            local_start = datetime(year, month, 1)
            if month == 12:
                local_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                local_end = datetime(year, month + 1, 1) - timedelta(days=1)
                
            # Set time components
            local_start = local_start.replace(hour=0, minute=0, second=0)
            local_end = local_end.replace(hour=23, minute=59, second=59)
            
            # Convert to timezone-aware datetime
            start_date = tz.localize(local_start)
            end_date = tz.localize(local_end)
            
            # Convert to UTC for database queries
            start_date_utc = start_date.astimezone(pytz.UTC)
            end_date_utc = end_date.astimezone(pytz.UTC)

            # Get stored KPI details
            kpi_details = request.env['marketing.kpi.detail'].sudo().search([
                ('employee_id', '=', employee_id),
                ('period_month', '=', month),
                ('period_year', '=', year)
            ])
            
            # Create map of stored values
            kpi_values = {
                detail.kpi_type: {
                    'weight': detail.weight,
                    'target': detail.target,
                    'measurement': detail.measurement,
                    'actual': detail.actual,
                    'description': detail.description
                }
                for detail in kpi_details
            }

            # Get job position
            job_title = employee.job_title if employee.job_title else "Unknown"
            _logger.info(f"Employee job title: {job_title}")
            
            department = employee.department_id.name if employee.department_id else "Marketing Department"
            
            kpi_scores = []

            # Define KPI templates based on role
            # Desain Grafis KPI Template
            design_kpi_template = [
                {
                    'no': 1,
                    'name': 'Jumlah konten desain grafis yang diproduksi sesuai target',
                    'type': 'design_production',
                    'weight': 30,
                    'target': 90,
                    'measurement': 'Jumlah konten desain yang diproduksi / target bulanan',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': 'Jumlah produksi konten desain grafis sesuai target waktu',
                    'type': 'design_time_accuracy',
                    'weight': 25,
                    'target': 95,
                    'measurement': 'Persentase konten yang diproduksi tepat waktu',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Jumlah dari konten melakukan revisi maksimal 2x',
                    'type': 'design_revision',
                    'weight': 25,
                    'target': 90,
                    'measurement': 'Persentase konten dengan revisi maksimal 2x',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Jumlah hari mengerjakan BAU sesuai target',
                    'type': 'design_bau',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Hari pengerjaan BAU / target hari',
                    'include_in_calculation': True
                }
            ]

            # Videografer KPI Template
            video_kpi_template = [
                {
                    'no': 1,
                    'name': 'Jumlah konten video yang diproduksi sesuai target',
                    'type': 'video_production',
                    'weight': 30,
                    'target': 90,
                    'measurement': 'Jumlah konten video yang diproduksi / target bulanan',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': 'Jumlah produksi konten video sesuai target waktu',
                    'type': 'video_time_accuracy',
                    'weight': 25,
                    'target': 95,
                    'measurement': 'Persentase konten video yang diproduksi tepat waktu',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Jumlah dari konten melakukan revisi maksimal 2x',
                    'type': 'video_revision',
                    'weight': 25,
                    'target': 90,
                    'measurement': 'Persentase konten video dengan revisi maksimal 2x',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Jumlah hari mengerjakan BAU sesuai target',
                    'type': 'video_bau',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Hari pengerjakan BAU / target hari',
                    'include_in_calculation': True
                }
            ]

            # Select appropriate KPI template based on job title
            if 'Graphic Design' in job_title:
                kpi_template = design_kpi_template
                
                # Get content tasks for this employee in the period
                design_tasks = request.env['content.task'].sudo().search([
                    ('assigned_to', 'in', [employee.id]),
                    ('content_type', '=', 'design'),
                    ('planned_date_start', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                    ('planned_date_end', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S'))
                ])
                
                # Get BAU activities
                bau_activities = request.env['content.bau'].sudo().search([
                    ('creator_id', '=', employee.id),
                    ('activity_type', '=', 'design'),
                    ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                    ('date', '<=', end_date_utc.strftime('%Y-%m-%d'))
                ])
                
                # Target values (could be moved to configuration or employee record)
                monthly_design_target = 30  # Target number of designs per month
                max_revision_threshold = 2   # Maximum number of revisions before considered excessive
                bau_days_target = 20         # Target BAU days per month
                
                # Calculate KPIs based on data
                for kpi in kpi_template:
                    actual = 0
                    
                    if kpi['type'] == 'design_production':
                        # If stored value exists, use it; otherwise calculate from data
                        if 'design_production' in kpi_values:
                            actual = kpi_values['design_production'].get('actual', 0)
                            kpi['measurement'] = kpi_values['design_production'].get('measurement', kpi['measurement'])
                        else:
                            total_designs = len(design_tasks)
                            actual = (total_designs / monthly_design_target * 100) if monthly_design_target > 0 else 0
                            kpi['measurement'] = f"Desain diproduksi: {total_designs} dari target {monthly_design_target} ({actual:.1f}%)"
                    
                    elif kpi['type'] == 'design_time_accuracy':
                        if 'design_time_accuracy' in kpi_values:
                            actual = kpi_values['design_time_accuracy'].get('actual', 0)
                            kpi['measurement'] = kpi_values['design_time_accuracy'].get('measurement', kpi['measurement'])
                        else:
                            completed_tasks = design_tasks.filtered(lambda t: t.state == 'done')
                            on_time_tasks = completed_tasks.filtered(
                                lambda t: t.actual_date_end and t.planned_date_end and 
                                          t.actual_date_end <= fields.Datetime.from_string(t.planned_date_end)
                            )
                            
                            total_completed = len(completed_tasks)
                            total_on_time = len(on_time_tasks)
                            
                            actual = (total_on_time / total_completed * 100) if total_completed > 0 else 0
                            kpi['measurement'] = f"Desain tepat waktu: {total_on_time} dari {total_completed} ({actual:.1f}%)"
                    
                    elif kpi['type'] == 'design_revision':
                        if 'design_revision' in kpi_values:
                            actual = kpi_values['design_revision'].get('actual', 0)
                            kpi['measurement'] = kpi_values['design_revision'].get('measurement', kpi['measurement'])
                        else:
                            completed_tasks = design_tasks.filtered(lambda t: t.state == 'done')
                            low_revision_tasks = completed_tasks.filtered(lambda t: t.revision_count <= max_revision_threshold)
                            
                            total_completed = len(completed_tasks)
                            total_low_revision = len(low_revision_tasks)
                            
                            actual = (total_low_revision / total_completed * 100) if total_completed > 0 else 0
                            kpi['measurement'] = f"Desain dengan revisi ≤{max_revision_threshold}x: {total_low_revision} dari {total_completed} ({actual:.1f}%)"
                    
                    elif kpi['type'] == 'design_bau':
                        if 'design_bau' in kpi_values:
                            actual = kpi_values['design_bau'].get('actual', 0)
                            kpi['measurement'] = kpi_values['design_bau'].get('measurement', kpi['measurement'])
                        else:
                            # Count unique days with BAU activities
                            bau_days = len(set(bau_activities.mapped('date')))
                            
                            actual = (bau_days / bau_days_target * 100) if bau_days_target > 0 else 0
                            kpi['measurement'] = f"Hari BAU: {bau_days} dari target {bau_days_target} hari ({actual:.1f}%)"
                    
                    # Calculate weighted score
                    weighted_score = actual * (kpi['weight'] / 100)
                    achievement = weighted_score
                    
                    # Add to KPI scores
                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,
                        'weighted_score': weighted_score
                    })

            elif 'Videografer' in job_title:
                kpi_template = video_kpi_template
                
                # Get content tasks for this employee in the period
                video_tasks = request.env['content.task'].sudo().search([
                    ('assigned_to', 'in', [employee.id]),
                    ('content_type', '=', 'video'),
                    ('planned_date_start', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                    ('planned_date_end', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S'))
                ])
                
                # Get BAU activities
                bau_activities = request.env['content.bau'].sudo().search([
                    ('creator_id', '=', employee.id),
                    ('activity_type', '=', 'video'),
                    ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                    ('date', '<=', end_date_utc.strftime('%Y-%m-%d'))
                ])
                
                # Target values
                monthly_video_target = 15  # Target number of videos per month (typically lower than design)
                max_revision_threshold = 2  # Maximum number of revisions before considered excessive
                bau_days_target = 20        # Target BAU days per month
                
                # Calculate KPIs based on data
                for kpi in kpi_template:
                    actual = 0
                    
                    if kpi['type'] == 'video_production':
                        # If stored value exists, use it; otherwise calculate from data
                        if 'video_production' in kpi_values:
                            actual = kpi_values['video_production'].get('actual', 0)
                            kpi['measurement'] = kpi_values['video_production'].get('measurement', kpi['measurement'])
                        else:
                            total_videos = len(video_tasks)
                            actual = (total_videos / monthly_video_target * 100) if monthly_video_target > 0 else 0
                            kpi['measurement'] = f"Video diproduksi: {total_videos} dari target {monthly_video_target} ({actual:.1f}%)"
                    
                    elif kpi['type'] == 'video_time_accuracy':
                        if 'video_time_accuracy' in kpi_values:
                            actual = kpi_values['video_time_accuracy'].get('actual', 0)
                            kpi['measurement'] = kpi_values['video_time_accuracy'].get('measurement', kpi['measurement'])
                        else:
                            completed_tasks = video_tasks.filtered(lambda t: t.state == 'done')
                            on_time_tasks = completed_tasks.filtered(
                                lambda t: t.actual_date_end and t.planned_date_end and 
                                          t.actual_date_end <= fields.Datetime.from_string(t.planned_date_end)
                            )
                            
                            total_completed = len(completed_tasks)
                            total_on_time = len(on_time_tasks)
                            
                            actual = (total_on_time / total_completed * 100) if total_completed > 0 else 0
                            kpi['measurement'] = f"Video tepat waktu: {total_on_time} dari {total_completed} ({actual:.1f}%)"
                    
                    elif kpi['type'] == 'video_revision':
                        if 'video_revision' in kpi_values:
                            actual = kpi_values['video_revision'].get('actual', 0)
                            kpi['measurement'] = kpi_values['video_revision'].get('measurement', kpi['measurement'])
                        else:
                            completed_tasks = video_tasks.filtered(lambda t: t.state == 'done')
                            low_revision_tasks = completed_tasks.filtered(lambda t: t.revision_count <= max_revision_threshold)
                            
                            total_completed = len(completed_tasks)
                            total_low_revision = len(low_revision_tasks)
                            
                            actual = (total_low_revision / total_completed * 100) if total_completed > 0 else 0
                            kpi['measurement'] = f"Video dengan revisi ≤{max_revision_threshold}x: {total_low_revision} dari {total_completed} ({actual:.1f}%)"
                    
                    elif kpi['type'] == 'video_bau':
                        if 'video_bau' in kpi_values:
                            actual = kpi_values['video_bau'].get('actual', 0)
                            kpi['measurement'] = kpi_values['video_bau'].get('measurement', kpi['measurement'])
                        else:
                            # Count unique days with BAU activities
                            bau_days = len(set(bau_activities.mapped('date')))
                            
                            actual = (bau_days / bau_days_target * 100) if bau_days_target > 0 else 0
                            kpi['measurement'] = f"Hari BAU: {bau_days} dari target {bau_days_target} hari ({actual:.1f}%)"
                    
                    # Calculate weighted score
                    weighted_score = actual * (kpi['weight'] / 100)
                    achievement = weighted_score
                    
                    # Add to KPI scores
                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,
                        'weighted_score': weighted_score
                    })
            
            # Calculate summary data
            total_weight = sum(kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            total_score = sum(kpi['weighted_score'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            avg_target = sum(kpi['target'] * kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True)) / total_weight if total_weight else 0
            
            
            
            # Validate total weight
            if total_weight != 100:
                _logger.warning(f"Total weight ({total_weight}) is not 100% for employee {employee.name}")
            
            # Return response
            return {
                'status': 'success',
                'data': {
                    'employee': {
                        'id': employee.id,
                        'name': employee.name,
                        'position': job_title,
                        'department': department
                    },
                    'period': {
                        'month': month,
                        'year': year
                    },
                    'kpi_scores': kpi_scores,
                    'summary': {
                        'total_weight': total_weight,
                        'target': avg_target,
                        'total_score': total_score,
                        'achievement_status': 'Achieved' if total_score >= avg_target else 'Below Target'
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_marketing_kpi: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kpi/marketing/export_pdf', type='http', auth='user', methods=['POST'], csrf=False)
    def export_marketing_kpi_pdf(self, **kw):
        """Export KPI data for Marketing to PDF format"""
        try:
            # Get and validate month/year
            current_date = datetime.now()
            month = int(kw.get('month', current_date.month))
            year = int(kw.get('year', current_date.year))

            # Validate range
            if not (1 <= month <= 12):
                return Response('Month must be between 1 and 12', status=400)
            if year < 2000 or year > 2100:
                return Response('Invalid year', status=400)
                
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Calculate date range in local timezone
            local_start = datetime(year, month, 1)
            if month == 12:
                local_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                local_end = datetime(year, month + 1, 1) - timedelta(days=1)
            
            local_start = local_start.replace(hour=0, minute=0, second=0)
            local_end = local_end.replace(hour=23, minute=59, second=59)
            
            start_date = tz.localize(local_start)
            end_date = tz.localize(local_end)
            
            start_date_utc = start_date.astimezone(pytz.UTC)
            end_date_utc = end_date.astimezone(pytz.UTC)

            # Format period for display
            month_names = ['January', 'February', 'March', 'April', 'May', 'June', 
                        'July', 'August', 'September', 'October', 'November', 'December']
            month_display = month_names[month-1]
            period = f"{month_display} {year}"

            # Prepare data for PDF report
            marketing_data = []
            processed_employee_ids = []  # Track which employees we've already processed

            # Get all marketing employees
            marketing_employees = request.env['hr.employee'].sudo().search([
                '|', '|', '|', '|',
                ('job_title', 'ilike', 'Graphic Design'),
                ('job_title', 'ilike', 'Videografer'),
                ('job_title', 'ilike', 'Social Media'),
                ('job_title', 'ilike', 'Digital Marketing'),
                ('job_title', 'ilike', 'Marketing')
            ])
            
            # Process each marketing employee
            for employee in marketing_employees:
                # Get job title
                job_title = employee.job_title or "Marketing"
                department = employee.department_id.name if employee.department_id else "Marketing"
                
                # Get KPI data by calling the KPI endpoint directly
                kpi_response = self.get_marketing_kpi(employee_id=employee.id, month=month, year=year)
                
                if kpi_response.get('status') == 'success' and 'data' in kpi_response:
                    employee_data = kpi_response['data']
                    marketing_data.append(employee_data)
            
            # Debug logging
            _logger.info(f"Total employees in PDF report: {len(marketing_data)}")
            
            # Prepare data for QWeb report
            report_data = {
                'period': period,
                'marketers': marketing_data,
                'current_date': fields.Date.today().strftime('%d-%m-%Y')
            }
            
            # Render PDF using QWeb report
            html = request.env['ir.qweb']._render('pitcar_custom.report_marketing_kpi', report_data)
            pdf_content = request.env['ir.actions.report']._run_wkhtmltopdf(
                [html],
                header=b'', footer=b'',
                landscape=True,
                specific_paperformat_args={
                    'data-report-margin-top': 10,
                    'data-report-margin-bottom': 10,
                    'data-report-margin-left': 5,
                    'data-report-margin-right': 5,
                }
            )

            # Prepare filename
            filename = f"Marketing_KPI_{month}_{year}.pdf"
            
            # Return PDF response
            return Response(
                pdf_content,
                headers={
                    'Content-Type': 'application/pdf',
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Length': len(pdf_content),
                },
                status=200
            )
        
        except Exception as e:
            _logger.error(f"Error exporting marketing KPI to PDF: {str(e)}", exc_info=True)
            return Response(f"Error: {str(e)}", status=500)
            
            # Calculate summary data
            total_weight = sum(kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            total_score = sum(kpi['weighted_score'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            avg_target = sum(kpi['target'] * kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True)) / total_weight if total_weight else 0
            
            # Validate total weight
            if total_weight != 100:
                _logger.warning(f"Total weight ({total_weight}) is not 100% for employee {employee.name}")
            
            # Return response
            return {
                'status': 'success',
                'data': {
                    'employee': {
                        'id': employee.id,
                        'name': employee.name,
                        'position': job_title,
                        'department': department
                    },
                    'period': {
                        'month': month,
                        'year': year
                    },
                    'kpi_scores': kpi_scores,
                    'summary': {
                        'total_weight': total_weight,
                        'target': avg_target,
                        'total_score': total_score,
                        'achievement_status': 'Achieved' if total_score >= avg_target else 'Below Target'
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_marketing_kpi: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kpi/marketing/export_pdf', type='http', auth='user', methods=['POST'], csrf=False)
    def export_marketing_kpi_pdf(self, **kw):
        """Export KPI data for Marketing to PDF format"""
        try:
            # Get and validate month/year
            current_date = datetime.now()
            month = int(kw.get('month', current_date.month))
            year = int(kw.get('year', current_date.year))

            # Validate range
            if not (1 <= month <= 12):
                return Response('Month must be between 1 and 12', status=400)
            if year < 2000 or year > 2100:
                return Response('Invalid year', status=400)
                
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Calculate date range in local timezone
            local_start = datetime(year, month, 1)
            if month == 12:
                local_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                local_end = datetime(year, month + 1, 1) - timedelta(days=1)
            
            local_start = local_start.replace(hour=0, minute=0, second=0)
            local_end = local_end.replace(hour=23, minute=59, second=59)
            
            start_date = tz.localize(local_start)
            end_date = tz.localize(local_end)
            
            start_date_utc = start_date.astimezone(pytz.UTC)
            end_date_utc = end_date.astimezone(pytz.UTC)

            # Format period for display
            month_names = ['January', 'February', 'March', 'April', 'May', 'June', 
                        'July', 'August', 'September', 'October', 'November', 'December']
            month_display = month_names[month-1]
            period = f"{month_display} {year}"

            # Prepare data for PDF report
            marketing_data = []
            processed_employee_ids = []  # Track which employees we've already processed

            # Get all marketing employees
            marketing_employees = request.env['hr.employee'].sudo().search([
                '|', '|', '|', '|',
                ('job_title', 'ilike', 'Graphic Design'),
                ('job_title', 'ilike', 'Videografer'),
                ('job_title', 'ilike', 'Social Media'),
                ('job_title', 'ilike', 'Digital Marketing'),
                ('job_title', 'ilike', 'Marketing')
            ])
            
            # Process each marketing employee
            for employee in marketing_employees:
                # Get job title
                job_title = employee.job_title or "Marketing"
                department = employee.department_id.name if employee.department_id else "Marketing Department"
                
                # Get KPI data by calling the KPI endpoint directly
                kpi_response = self.get_marketing_kpi(employee_id=employee.id, month=month, year=year)
                
                if kpi_response.get('status') == 'success' and 'data' in kpi_response:
                    employee_data = kpi_response['data']
                    marketing_data.append(employee_data)
            
            # Debug logging
            _logger.info(f"Total employees in PDF report: {len(marketing_data)}")
            
            # Prepare data for QWeb report
            report_data = {
                'period': period,
                'marketers': marketing_data,
                'current_date': fields.Date.today().strftime('%d-%m-%Y')
            }
            
            # Render PDF using QWeb report
            html = request.env['ir.qweb']._render('pitcar_custom.report_marketing_kpi', report_data)
            pdf_content = request.env['ir.actions.report']._run_wkhtmltopdf(
                [html],
                header=b'', footer=b'',
                landscape=True,
                specific_paperformat_args={
                    'data-report-margin-top': 10,
                    'data-report-margin-bottom': 10,
                    'data-report-margin-left': 5,
                    'data-report-margin-right': 5,
                }
            )

            # Prepare filename
            filename = f"Marketing_KPI_{month}_{year}.pdf"
            
            # Return PDF response
            return Response(
                pdf_content,
                headers={
                    'Content-Type': 'application/pdf',
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Length': len(pdf_content),
                },
                status=200
            )
        
        except Exception as e:
            _logger.error(f"Error exporting marketing KPI to PDF: {str(e)}", exc_info=True)
            return Response(f"Error: {str(e)}", status=500)