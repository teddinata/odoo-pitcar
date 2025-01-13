import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import http
from odoo.http import request
import pytz

_logger = logging.getLogger(__name__)

class KPIOverview(http.Controller):
  @http.route('/web/v2/hr/departments', type='json', auth='user', methods=['POST'], csrf=False)
  def get_departments(self, **kw):
      """Get list of departments"""
      try:
          departments = request.env['hr.department'].sudo().search([])
          return {
              'status': 'success',
              'data': [{
                  'id': dept.id,
                  'name': dept.name,
              } for dept in departments]
          }
      except Exception as e:
          _logger.error(f"Error in get_departments: {str(e)}")
          return {'status': 'error', 'message': str(e)}

  @http.route('/web/v2/hr/employees', type='json', auth='user', methods=['POST'], csrf=False)
  def get_employees(self, **kw):
      """Get list of employees with optional department filter"""
      try:
          domain = []
          if kw.get('department_id'):
              domain.append(('department_id', '=', int(kw['department_id'])))

          employees = request.env['hr.employee'].sudo().search(domain)
          return {
              'status': 'success',
              'data': [{
                  'id': emp.id,
                  'name': emp.name,
                  'department_id': emp.department_id.id,
                  'department_name': emp.department_id.name,
                  'job_title': emp.job_id.name,
              } for emp in employees]
          }
      except Exception as e:
          _logger.error(f"Error in get_employees: {str(e)}")
          return {'status': 'error', 'message': str(e)}
      
  @http.route('/web/v2/kpi/update', type='json', auth='user', methods=['POST'], csrf=False)
  def update_kpi_value(self, **kw):
      """Update specific KPI value"""
      try:
          required_fields = ['employee_id', 'period_month', 'period_year', 
                            'kpi_type', 'field_name', 'value']
          if not all(kw.get(field) for field in required_fields):
              return {'status': 'error', 'message': 'Missing required fields'}

          employee_id = int(kw['employee_id'])
          month = int(kw['period_month'])
          year = int(kw['period_year'])
          kpi_type = kw['kpi_type']
          field_name = kw['field_name']  # 'weight', 'target', 'measurement', 'actual'
          value = kw['value']

          # Find or create KPI detail record
          kpi_detail = request.env['cs.kpi.detail'].sudo().search([
              ('employee_id', '=', employee_id),
              ('period_month', '=', month),
              ('period_year', '=', year),
              ('kpi_type', '=', kpi_type)
          ], limit=1)

          if not kpi_detail:
              kpi_detail = request.env['cs.kpi.detail'].sudo().create({
                  'employee_id': employee_id,
                  'period_month': month,
                  'period_year': year,
                  'kpi_type': kpi_type,
                  field_name: value
              })
          else:
              kpi_detail.write({field_name: value})

          return {
              'status': 'success',
              'data': {
                  'id': kpi_detail.id,
                  'kpi_type': kpi_type,
                  field_name: value
              }
          }

      except Exception as e:
          _logger.error(f"Error in update_kpi_value: {str(e)}")
          return {'status': 'error', 'message': str(e)}
      
  @http.route('/web/v2/kpi/customer-support', type='json', auth='user', methods=['POST'], csrf=False)
  def get_customer_support_kpi(self, **kw):
    """Get KPI data for Customer Support Department"""
    try:
        # Debug log input parameters
        _logger.info(f"Received kw: {kw}")

        # Extract dan validasi parameter 
        employee_id = kw.get('employee_id')
        if not employee_id:
            return {'status': 'error', 'message': 'Employee ID is required'}

        # Get and validate month/year
        current_date = datetime.now()
        month = int(kw.get('month', current_date.month))
        year = int(kw.get('year', current_date.year))

        # Validasi range
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
        kpi_details = request.env['cs.kpi.detail'].sudo().search([
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
        job_title = employee.job_id.name
        
        kpi_scores = []

         # Kemudian gunakan start_date_utc dan end_date_utc untuk semua query database
        # Contoh:
        base_domain = [
            ('date_completed', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
            ('date_completed', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
            ('state', 'in', ['sale', 'done'])
        ]

         # Handle CS Lead KPI
        if 'Lead Customer Support' in job_title:
            # Get team members
            team_members = request.env['hr.employee'].sudo().search([
                ('parent_id', '=', employee.id)
            ])
            
            # Get all SA in team 
            team_sa = request.env['pitcar.service.advisor'].sudo().search([
                ('user_id', 'in', team_members.mapped('user_id').ids)
            ])

            # Get all team orders
            all_orders = request.env['sale.order'].sudo().search(base_domain)
            
            # 1. Team Performance Control
            non_compliant_orders = all_orders.filtered(
                lambda o: not o.sa_mulai_penerimaan or 
                         not o.sa_cetak_pkb or
                         not o.controller_mulai_servis or
                         not o.controller_selesai
            )
            non_compliant_rate = (len(non_compliant_orders) / len(all_orders) * 100) if all_orders else 0
            team_performance_score = 100 - non_compliant_rate

            # 2. Complaint Resolution
            complaints = all_orders.filtered(lambda o: o.customer_rating in ['1', '2'])
            resolved_complaints = complaints.filtered(lambda o: o.complaint_status == 'solved')
            complaint_resolution_rate = (len(resolved_complaints) / len(complaints) * 100) if complaints else 100

            # 3. Team Revenue Achievement
            team_revenue = sum(all_orders.mapped('amount_total'))
            team_target = sum(team_sa.mapped('monthly_target'))
            revenue_achievement = (team_revenue / team_target * 100) if team_target else 0

            # 4. Team Operational Discipline
            attendance_domain = [
                ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('employee_id', 'in', team_members.ids)
            ]
            team_attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
            late_count = sum(1 for att in team_attendances if att.is_late)
            discipline_rate = 100 - ((late_count / len(team_attendances) * 100) if team_attendances else 0)

            # 5. Team SOP Compliance
            sop_domain = [
                ('date', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('date', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('sa_id', 'in', team_sa.ids)
            ]
            total_sop = request.env['pitcar.sop.sampling'].sudo().search_count(sop_domain)
            passed_sop = request.env['pitcar.sop.sampling'].sudo().search_count([
                *sop_domain,
                ('result', '=', 'pass')
            ])
            sop_compliance_rate = (passed_sop / total_sop * 100) if total_sop else 0

            kpi_scores = [
              {
                  'name': 'Bertanggung Jawab Mengontrol Kinerja Tim',
                  'type': 'team_control',  # Sesuai dengan selection field
                  'weight': kpi_values.get('team_control', {}).get('weight', 30),
                  'target': kpi_values.get('team_control', {}).get('target', 90),
                  'measurement': 'Persentase order yang sesuai SOP dari total order',
                  'actual': team_performance_score,
                  'description': 'Mengontrol kinerja tim sesuai dengan SOP yang ditetapkan',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Penyelesaian Komplain',
                  'type': 'complaint_handling',  # Sesuai dengan selection field
                  'weight': kpi_values.get('complaint_handling', {}).get('weight', 20),
                  'target': kpi_values.get('complaint_handling', {}).get('target', 90),
                  'measurement': 'Persentase komplain yang berhasil diselesaikan',
                  'actual': complaint_resolution_rate,
                  'description': 'Efektivitas penyelesaian komplain customer',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Pencapaian Target Revenue Tim',
                  'type': 'revenue_target',  # Sesuai dengan selection field
                  'weight': kpi_values.get('revenue_target', {}).get('weight', 20),
                  'target': kpi_values.get('revenue_target', {}).get('target', 100),
                  'measurement': 'Persentase pencapaian target revenue tim',
                  'actual': revenue_achievement,
                  'description': 'Pencapaian target revenue tim secara keseluruhan',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Pengembangan Tim',
                  'type': 'team_development',  # Sesuai dengan selection field
                  'weight': kpi_values.get('team_development', {}).get('weight', 15),
                  'target': kpi_values.get('team_development', {}).get('target', 90),
                  'measurement': 'Persentase pencapaian program pengembangan tim',
                  'actual': sop_compliance_rate,  # Bisa disesuaikan dengan metrik lain
                  'description': 'Pengembangan kualitas dan kapabilitas tim',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Kegiatan Operasional',
                  'type': 'operational',  # Sesuai dengan selection field
                  'weight': kpi_values.get('operational', {}).get('weight', 15),
                  'target': kpi_values.get('operational', {}).get('target', 90),
                  'measurement': 'Persentase kehadiran tepat waktu tim',
                  'actual': discipline_rate,
                  'description': 'Kedisiplinan operasional tim',
                  'editable': ['weight', 'target']
              }
          ]

            
         # Handle Service Advisor KPI
        elif 'Service Advisor' in job_title:
            # Get SA record
            service_advisor = request.env['pitcar.service.advisor'].sudo().search([
                ('user_id', '=', employee.user_id.id)
            ], limit=1)

            if not service_advisor:
                return {'status': 'error', 'message': 'Service Advisor record not found'}

            # Get orders for this SA
            sa_domain = [*base_domain, ('service_advisor_id', 'in', [service_advisor.id])]
            orders = request.env['sale.order'].sudo().search(sa_domain)

            # 1. Customer Service Quality
            total_orders = len(orders)
            complaints = len(orders.filtered(lambda o: o.customer_rating in ['1', '2']))
            resolved_complaints = len(orders.filtered(
                lambda o: o.customer_rating in ['1', '2'] and o.complaint_status == 'solved'
            ))
            service_quality = 100 - ((complaints / total_orders * 100) if total_orders else 0)

            # 2. Service Analysis Accuracy
            incorrect_analysis = len(orders.filtered(lambda o: o.recommendation_ids))
            analysis_accuracy = 100 - ((incorrect_analysis / total_orders * 100) if total_orders else 0)

            # 3. Service Efficiency
            completed_orders = orders.filtered(lambda o: o.sa_mulai_penerimaan and o.sa_cetak_pkb)
            on_time_services = sum(1 for order in completed_orders 
                if (order.sa_cetak_pkb - order.sa_mulai_penerimaan).total_seconds() / 60 <= 15)
            efficiency_rate = (on_time_services / len(completed_orders) * 100) if completed_orders else 0

            # 4. Revenue Achievement
            current_revenue = sum(orders.mapped('amount_total'))
            revenue_achievement = (current_revenue / service_advisor.monthly_target * 100) if service_advisor.monthly_target else 0

            # 5. SOP Compliance
            sop_domain = [
                ('sa_id', '=', service_advisor.id),
                ('date', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('date', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            total_sop = request.env['pitcar.sop.sampling'].sudo().search_count(sop_domain)
            passed_sop = request.env['pitcar.sop.sampling'].sudo().search_count([
                *sop_domain,
                ('result', '=', 'pass')
            ])
            sop_compliance = (passed_sop / total_sop * 100) if total_sop else 0

            # 6. Discipline
            attendance_domain = [
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
            late_count = sum(1 for att in attendances if att.is_late)
            discipline_rate = 100 - ((late_count / len(attendances) * 100) if attendances else 0)

            kpi_scores = [
              {
                  'name': 'Melayani Customer',
                  'type': 'customer_service',  # Sesuai dengan selection field
                  'weight': kpi_values.get('customer_service', {}).get('weight', 20),
                  'target': kpi_values.get('customer_service', {}).get('target', 90),
                  'measurement': 'Persentase kepuasan customer dan minimnya komplain',
                  'actual': service_quality,
                  'description': 'Kualitas pelayanan terhadap customer',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Analisa Jasa',
                  'type': 'service_analysis',  # Sesuai dengan selection field
                  'weight': kpi_values.get('service_analysis', {}).get('weight', 15),
                  'target': kpi_values.get('service_analysis', {}).get('target', 90),
                  'measurement': 'Persentase ketepatan analisa kebutuhan service',
                  'actual': analysis_accuracy,
                  'description': 'Akurasi dalam menganalisa kebutuhan service customer',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Efisiensi Pelayanan',
                  'type': 'service_efficiency',  # Sesuai dengan selection field
                  'weight': kpi_values.get('service_efficiency', {}).get('weight', 15),
                  'target': kpi_values.get('service_efficiency', {}).get('target', 90),
                  'measurement': 'Persentase pelayanan yang selesai tepat waktu',
                  'actual': efficiency_rate,
                  'description': 'Efisiensi waktu dalam melayani customer',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Target Revenue SA',
                  'type': 'sa_revenue',  # Sesuai dengan selection field
                  'weight': kpi_values.get('sa_revenue', {}).get('weight', 20),
                  'target': kpi_values.get('sa_revenue', {}).get('target', 100),
                  'measurement': 'Persentase pencapaian target revenue individu',
                  'actual': revenue_achievement,
                  'description': 'Pencapaian target revenue yang ditetapkan',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Kepatuhan SOP',
                  'type': 'sop_compliance',  # Sesuai dengan selection field
                  'weight': kpi_values.get('sop_compliance', {}).get('weight', 15),
                  'target': kpi_values.get('sop_compliance', {}).get('target', 90),
                  'measurement': 'Persentase kepatuhan terhadap SOP',
                  'actual': sop_compliance,
                  'description': 'Tingkat kepatuhan terhadap SOP yang berlaku',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Kedisiplinan',
                  'type': 'discipline',  # Sesuai dengan selection field
                  'weight': kpi_values.get('discipline', {}).get('weight', 15),
                  'target': kpi_values.get('discipline', {}).get('target', 90),
                  'measurement': 'Persentase kehadiran tepat waktu',
                  'actual': discipline_rate,
                  'description': 'Tingkat kedisiplinan dalam kehadiran',
                  'editable': ['weight', 'target']
              }
          ]

        # Handle Customer Service KPI
        elif 'Customer Service' in job_title:
            # Get orders for online campaigns
            online_domain = [
                *base_domain,
                ('campaign', '!=', False)  # Filter untuk online leads
            ]
            online_orders = request.env['sale.order'].sudo().search(online_domain)

            # 1. Online Response Time
            total_responses = len(online_orders)
            on_time_responses = len(online_orders.filtered(
                lambda o: o.response_duration and o.response_duration <= 30  # 30 menit target
            ))
            response_rate = (on_time_responses / total_responses * 100) if total_responses else 0

            # 2. Leads Conversion
            converted_leads = len(online_orders.filtered(lambda o: o.state in ['sale', 'done']))
            conversion_rate = (converted_leads / total_responses * 100) if total_responses else 0

            # 3. Customer Contact Management
            broadcast_domain = [
                ('date', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('date', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('cs_id', '=', employee.id)
            ]
            total_broadcasts = request.env['customer.broadcast'].sudo().search_count(broadcast_domain)
            broadcast_target = kpi_values.get('customer_contact', {}).get('target', 30)
            broadcast_achievement = (total_broadcasts / broadcast_target * 100) if broadcast_target else 0

            # 4. Service Reminder Performance
            reminder_domain = [
                ('date', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('date', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('cs_id', '=', employee.id)
            ]
            total_reminders = request.env['service.reminder'].sudo().search_count(reminder_domain)
            completed_reminders = request.env['service.reminder'].sudo().search_count([
                *reminder_domain,
                ('state', '=', 'completed')
            ])
            reminder_completion_rate = (completed_reminders / total_reminders * 100) if total_reminders else 0

            # 5. Documentation & Reports
            # Assuming you have a reporting checklist or system
            # Here we'll use a placeholder calculation - modify as needed
            documentation_rate = 100  # Placeholder - implement actual calculation based on your system

            # 6. Discipline
            attendance_domain = [
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
            late_count = sum(1 for att in attendances if att.is_late)
            discipline_rate = 100 - ((late_count / len(attendances) * 100) if attendances else 0)

            kpi_scores = [
              {
                  'name': 'Response Time Online',
                  'type': 'online_response',  # Sesuai dengan selection field
                  'weight': kpi_values.get('online_response', {}).get('weight', 20),
                  'target': kpi_values.get('online_response', {}).get('target', 90),
                  'measurement': 'Persentase respon tepat waktu untuk online leads',
                  'actual': response_rate,
                  'description': 'Kecepatan respon terhadap inquiry online customer',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Laporan Leads',
                  'type': 'leads_report',  # Sesuai dengan selection field
                  'weight': kpi_values.get('leads_report', {}).get('weight', 20),
                  'target': kpi_values.get('leads_report', {}).get('target', 90),
                  'measurement': 'Persentase leads yang berhasil dikonversi',
                  'actual': conversion_rate,
                  'description': 'Tingkat keberhasilan konversi leads menjadi penjualan',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Manajemen Kontak Customer',
                  'type': 'customer_contact',  # Sesuai dengan selection field
                  'weight': kpi_values.get('customer_contact', {}).get('weight', 15),
                  'target': kpi_values.get('customer_contact', {}).get('target', 90),
                  'measurement': 'Persentase pencapaian target broadcast',
                  'actual': broadcast_achievement,
                  'description': 'Efektivitas pengelolaan komunikasi dengan customer',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Reminder Service',
                  'type': 'service_reminder',  # Sesuai dengan selection field
                  'weight': kpi_values.get('service_reminder', {}).get('weight', 15),
                  'target': kpi_values.get('service_reminder', {}).get('target', 90),
                  'measurement': 'Persentase reminder yang berhasil ditindaklanjuti',
                  'actual': reminder_completion_rate,
                  'description': 'Efektivitas follow up reminder service',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Dokumentasi',
                  'type': 'documentation',  # Sesuai dengan selection field
                  'weight': kpi_values.get('documentation', {}).get('weight', 15),
                  'target': kpi_values.get('documentation', {}).get('target', 100),
                  'measurement': 'Persentase kelengkapan dokumentasi dan laporan',
                  'actual': documentation_rate,
                  'description': 'Kelengkapan dan ketepatan dokumentasi serta pelaporan',
                  'editable': ['weight', 'target']
              },
              {
                  'name': 'Kedisiplinan',
                  'type': 'discipline',  # Sesuai dengan selection field
                  'weight': kpi_values.get('discipline', {}).get('weight', 15),
                  'target': kpi_values.get('discipline', {}).get('target', 90),
                  'measurement': 'Persentase kehadiran tepat waktu',
                  'actual': discipline_rate,
                  'description': 'Tingkat kedisiplinan dalam kehadiran',
                  'editable': ['weight', 'target']
              }
          ]

        else:
            return {'status': 'error', 'message': f'Invalid position: {job_title}'}

        # Calculate total score
        total_score = 0
        total_weight = 0

        for kpi in kpi_scores:
            kpi['achievement'] = (kpi['actual'] / kpi['target'] * 100) if kpi['target'] else 0
            # Cap achievement at maximum 100%
            kpi['achievement'] = min(kpi['achievement'], 100)
            total_score += kpi['achievement'] * (kpi['weight'] / 100)
            total_weight += kpi['weight']

        # Normalize total score if weights don't sum to 100
        if total_weight != 100:
            total_score = (total_score / total_weight) * 100 if total_weight else 0

        return {
            'status': 'success',
            'data': {
                'employee': {
                    'id': employee.id,
                    'name': employee.name,
                    'position': job_title,
                    'department': employee.department_id.name
                },
                'period': {
                    'month': month,
                    'year': year
                },
                'kpi_scores': kpi_scores,
                'total_score': total_score
            }
        }

    except Exception as e:
        _logger.error(f"Error in get_customer_support_kpi: {str(e)}")
        return {'status': 'error', 'message': str(e)}
