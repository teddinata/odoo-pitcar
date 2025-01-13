import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import http
from odoo.http import request

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

        # Default nilai dari kw langsung
        month = int(kw.get('month', datetime.now().month))
        year = int(kw.get('year', datetime.now().year))

        # Validasi range
        if not (1 <= month <= 12):
            return {'status': 'error', 'message': 'Month must be between 1 and 12'}
            
        if year < 2000 or year > 2100:
            return {'status': 'error', 'message': 'Invalid year'}

        # Get employee
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            return {'status': 'error', 'message': 'Employee not found'}

        # Set period range
        start_date = datetime(year, month, 1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)

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

         # Inisialisasi kpi_scores
        kpi_scores = []

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

            # 1. Mengontrol Kinerja Tim
            domain = [
                ('date_completed', '>=', start_date),
                ('date_completed', '<=', end_date),
                ('state', 'in', ['sale', 'done'])
            ]

            all_orders = request.env['sale.order'].sudo().search(domain)
            non_compliant_orders = all_orders.filtered(
                lambda o: not o.sa_mulai_penerimaan or 
                         not o.sa_cetak_pkb or
                         not o.controller_mulai_servis or
                         not o.controller_selesai
            )
            total_non_compliant = len(non_compliant_orders)
            
            # 2. Penyelesaian Komplain
            total_complaints = len(all_orders.filtered(
                lambda o: o.customer_rating in ['1', '2']
            ))
            resolved_complaints = len(all_orders.filtered(
                lambda o: o.customer_rating in ['1', '2'] and 
                         o.complaint_status == 'solved'
            ))

            # 3. Target Revenue
            team_revenue = sum(all_orders.mapped('amount_total'))
            team_target = sum(team_sa.mapped('monthly_target'))

            # 4. Pengembangan Kualitas Tim
            trainings_domain = [
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('type', '=', 'training'),
                ('employee_id', 'in', team_members.ids)
            ]
            completed_trainings = request.env['hr.training'].sudo().search_count(trainings_domain)
            training_target = 80  # Target per bulan

            # 5. Kedisiplinan
            attendance_domain = [
                ('check_in', '>=', start_date),
                ('check_in', '<=', end_date),
                ('employee_id', 'in', team_members.ids)
            ]
            team_attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
            late_count = sum(1 for att in team_attendances if att.is_late)

            kpi_scores = [
            {
                'name': 'Bertanggung Jawab Mengontrol Kinerja Tim',
                'type': 'team_control',
                'weight': kpi_values.get('team_control', {}).get('weight', 30),
                'target': kpi_values.get('team_control', {}).get('target', 90),
                'measurement': kpi_values.get('team_control', {}).get('measurement', 
                    'Dari total temuan SA, terdapat temuan yang tidak sesuai'),
                'actual': kpi_values.get('team_control', {}).get('actual', 0),
                'description': kpi_values.get('team_control', {}).get('description', 
                    'Mengontrol kinerja tim sesuai dengan SOP'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Penyelesaian Komplain',
                'type': 'complaint_handling',
                'weight': kpi_values.get('complaint_handling', {}).get('weight', 20),
                'target': kpi_values.get('complaint_handling', {}).get('target', 90),
                'measurement': kpi_values.get('complaint_handling', {}).get('measurement',
                    'Jumlah komplain yang diselesaikan'),
                'actual': kpi_values.get('complaint_handling', {}).get('actual', 0),
                'description': kpi_values.get('complaint_handling', {}).get('description',
                    'Menyelesaikan komplain customer dengan baik'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Meningkatkan Omset Penjualan',
                'type': 'revenue_target',
                'weight': kpi_values.get('revenue_target', {}).get('weight', 20),
                'target': kpi_values.get('revenue_target', {}).get('target', 100),
                'measurement': kpi_values.get('revenue_target', {}).get('measurement',
                    'Target revenue tim yang tercapai'),
                'actual': kpi_values.get('revenue_target', {}).get('actual', 0),
                'description': kpi_values.get('revenue_target', {}).get('description',
                    'Pencapaian target revenue tim'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Memimpin dan Mengembangkan Kualitas Tim',
                'type': 'team_development',
                'weight': kpi_values.get('team_development', {}).get('weight', 10),
                'target': kpi_values.get('team_development', {}).get('target', 95),
                'measurement': kpi_values.get('team_development', {}).get('measurement',
                    'Jumlah pelatihan tim yang terlaksana'),
                'actual': kpi_values.get('team_development', {}).get('actual', 0),
                'description': kpi_values.get('team_development', {}).get('description',
                    'Pengembangan kualitas tim melalui pelatihan'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Menjalankan Kegiatan Operasional',
                'type': 'operational',
                'weight': kpi_values.get('operational', {}).get('weight', 20),
                'target': kpi_values.get('operational', {}).get('target', 90),
                'measurement': kpi_values.get('operational', {}).get('measurement',
                    'Jumlah keterlambatan tim'),
                'actual': kpi_values.get('operational', {}).get('actual', 0),
                'description': kpi_values.get('operational', {}).get('description',
                    'Kedisiplinan dan kepatuhan operasional tim'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            }
        ]
            
        # ... lanjutkan dengan logic untuk SA dan CS seperti sebelumnya
        # Handle Service Advisor KPI
        elif 'Service Advisor' in job_title:
            # Get SA record
            service_advisor = request.env['pitcar.service.advisor'].sudo().search([
                ('user_id', '=', employee.user_id.id)
            ], limit=1)

            if not service_advisor:
                return {'status': 'error', 'message': 'Service Advisor record not found'}

            # Get orders dalam periode
            domain = [
                ('service_advisor_id', 'in', [service_advisor.id]),
                ('date_completed', '>=', start_date),
                ('date_completed', '<=', end_date),
                ('state', 'in', ['sale', 'done'])
            ]
            orders = request.env['sale.order'].sudo().search(domain)

            # 1. Melayani Kebutuhan Customer Secara Offline
            total_complaints = len(orders.filtered(lambda o: o.customer_rating in ['1', '2']))
            resolved_complaints = len(orders.filtered(
                lambda o: o.customer_rating in ['1', '2'] and o.complaint_status == 'solved'
            ))

            # 2. Analisa Jasa
            total_services = len(orders)
            incorrect_analysis = len(orders.filtered(lambda o: o.recommendation_ids))

            # 3. Efisiensi Pelayanan
            completed_orders = orders.filtered(lambda o: o.sa_mulai_penerimaan and o.sa_cetak_pkb)
            on_time_services = sum(1 for order in completed_orders 
                if (order.sa_cetak_pkb - order.sa_mulai_penerimaan).total_seconds() / 60 <= 15)

            # 4. Target Revenue
            current_revenue = sum(orders.mapped('amount_total'))

            # 5. SOP dan Kedisiplinan
            sop_domain = [
                ('sa_id', 'in', [service_advisor.id]),
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ]
            total_sop = request.env['pitcar.sop.sampling'].sudo().search_count(sop_domain)
            passed_sop = request.env['pitcar.sop.sampling'].sudo().search_count([
                *sop_domain,
                ('result', '=', 'pass')
            ])

            attendance_domain = [
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_date),
                ('check_in', '<=', end_date)
            ]
            attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
            late_count = sum(1 for att in attendances if att.is_late)

            kpi_scores = [
            {
                'name': 'Melayani Kebutuhan Customer Secara Offline',
                'type': 'customer_service',
                'weight': kpi_values.get('customer_service', {}).get('weight', 10),
                'target': kpi_values.get('customer_service', {}).get('target', 90),
                'measurement': kpi_values.get('customer_service', {}).get('measurement',
                    'Jumlah komplain yang diselesaikan'),
                'actual': kpi_values.get('customer_service', {}).get('actual', 0),
                'description': kpi_values.get('customer_service', {}).get('description',
                    'Pelayanan customer offline dan penanganan komplain'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Tidak ada kesalahan analisa jasa',
                'type': 'service_analysis',
                'weight': kpi_values.get('service_analysis', {}).get('weight', 15),
                'target': kpi_values.get('service_analysis', {}).get('target', 90),
                'measurement': kpi_values.get('service_analysis', {}).get('measurement',
                    'Jumlah kesalahan analisa'),
                'actual': kpi_values.get('service_analysis', {}).get('actual', 0),
                'description': kpi_values.get('service_analysis', {}).get('description',
                    'Ketepatan analisa jasa service'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Efisiensi Pelayanan Customer',
                'type': 'service_efficiency',
                'weight': kpi_values.get('service_efficiency', {}).get('weight', 15),
                'target': kpi_values.get('service_efficiency', {}).get('target', 90),
                'measurement': kpi_values.get('service_efficiency', {}).get('measurement',
                    'Jumlah pelayanan tepat waktu'),
                'actual': kpi_values.get('service_efficiency', {}).get('actual', 0),
                'description': kpi_values.get('service_efficiency', {}).get('description',
                    'Kecepatan dan ketepatan pelayanan'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Target Revenue',
                'type': 'sa_revenue',
                'weight': kpi_values.get('sa_revenue', {}).get('weight', 15),
                'target': kpi_values.get('sa_revenue', {}).get('target', 0),
                'measurement': kpi_values.get('sa_revenue', {}).get('measurement',
                    'Target revenue individu'),
                'actual': kpi_values.get('sa_revenue', {}).get('actual', 0),
                'description': kpi_values.get('sa_revenue', {}).get('description',
                    'Pencapaian target revenue individu'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'SOP Compliance',
                'type': 'sop_compliance',
                'weight': kpi_values.get('sop_compliance', {}).get('weight', 25),
                'target': kpi_values.get('sop_compliance', {}).get('target', 90),
                'measurement': kpi_values.get('sop_compliance', {}).get('measurement',
                    'Jumlah kepatuhan SOP'),
                'actual': kpi_values.get('sop_compliance', {}).get('actual', 0),
                'description': kpi_values.get('sop_compliance', {}).get('description',
                    'Kepatuhan terhadap SOP'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Kedisiplinan',
                'type': 'discipline',
                'weight': kpi_values.get('discipline', {}).get('weight', 20),
                'target': kpi_values.get('discipline', {}).get('target', 90),
                'measurement': kpi_values.get('discipline', {}).get('measurement',
                    'Jumlah keterlambatan'),
                'actual': kpi_values.get('discipline', {}).get('actual', 0),
                'description': kpi_values.get('discipline', {}).get('description',
                    'Kedisiplinan kehadiran'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            }
        ]

        # Handle Customer Service KPI
        elif 'Customer Service' in job_title:
            domain = [
                ('create_date', '>=', start_date),
                ('create_date', '<=', end_date),
                ('campaign', '!=', False),  # CS menangani online leads
                ('state', 'in', ['draft', 'sent', 'sale', 'done'])
            ]
            orders = request.env['sale.order'].sudo().search(domain)

            # 1. Online Response Time
            total_responses = len(orders)
            on_time_responses = len(orders.filtered(
                lambda o: o.response_duration and o.response_duration <= 30  # 30 menit target
            ))

            # 2. Leads Report
            total_leads = len(orders)
            converted_leads = len(orders.filtered(lambda o: o.state in ['sale', 'done']))

            # 3. Customer Contact Management
            broadcast_domain = [
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('cs_id', '=', employee.id)
            ]
            total_broadcasts = request.env['customer.broadcast'].sudo().search_count(broadcast_domain)
            target_broadcasts = 30  # Target per bulan

            # 4. Service Reminder
            reminder_domain = [
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('cs_id', '=', employee.id)
            ]
            total_reminders = request.env['service.reminder'].sudo().search_count(reminder_domain)
            completed_reminders = request.env['service.reminder'].sudo().search_count([
                *reminder_domain,
                ('state', '=', 'completed')
            ])

            # 5. Documentation & Reports
            reports_complete = True  # Assuming all reports are complete, modify as needed

            # 6. Kedisiplinan
            attendance_domain = [
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_date),
                ('check_in', '<=', end_date)
            ]
            attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
            late_count = sum(1 for att in attendances if att.is_late)

            kpi_scores = [
            {
                'name': 'Response Time Online Customer',
                'type': 'online_response',
                'weight': kpi_values.get('online_response', {}).get('weight', 20),
                'target': kpi_values.get('online_response', {}).get('target', 100),
                'measurement': kpi_values.get('online_response', {}).get('measurement',
                    'Jumlah respon tepat waktu'),
                'actual': kpi_values.get('online_response', {}).get('actual', 0),
                'description': kpi_values.get('online_response', {}).get('description',
                    'Kecepatan respon customer online'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Leads Report',
                'type': 'leads_report',
                'weight': kpi_values.get('leads_report', {}).get('weight', 15),
                'target': kpi_values.get('leads_report', {}).get('target', 100),
                'measurement': kpi_values.get('leads_report', {}).get('measurement',
                    'Jumlah leads yang dikonversi'),
                'actual': kpi_values.get('leads_report', {}).get('actual', 0),
                'description': kpi_values.get('leads_report', {}).get('description',
                    'Konversi dan pelaporan leads'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Customer Contact Management',
                'type': 'customer_contact',
                'weight': kpi_values.get('customer_contact', {}).get('weight', 10),
                'target': kpi_values.get('customer_contact', {}).get('target', 100),
                'measurement': kpi_values.get('customer_contact', {}).get('measurement',
                    'Jumlah broadcast yang dilakukan'),
                'actual': kpi_values.get('customer_contact', {}).get('actual', 0),
                'description': kpi_values.get('customer_contact', {}).get('description',
                    'Pengelolaan komunikasi customer'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Service Reminder',
                'type': 'service_reminder',
                'weight': kpi_values.get('service_reminder', {}).get('weight', 10),
                'target': kpi_values.get('service_reminder', {}).get('target', 100),
                'measurement': kpi_values.get('service_reminder', {}).get('measurement',
                    'Jumlah reminder yang selesai'),
                'actual': kpi_values.get('service_reminder', {}).get('actual', 0),
                'description': kpi_values.get('service_reminder', {}).get('description',
                    'Pelaksanaan reminder service'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Documentation',
                'type': 'documentation',
                'weight': kpi_values.get('documentation', {}).get('weight', 25),
                'target': kpi_values.get('documentation', {}).get('target', 100),
                'measurement': kpi_values.get('documentation', {}).get('measurement',
                    'Kelengkapan dokumentasi'),
                'actual': kpi_values.get('documentation', {}).get('actual', 0),
                'description': kpi_values.get('documentation', {}).get('description',
                    'Kelengkapan dokumentasi dan laporan'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            },
            {
                'name': 'Kedisiplinan',
                'type': 'discipline',
                'weight': kpi_values.get('discipline', {}).get('weight', 20),
                'target': kpi_values.get('discipline', {}).get('target', 90),
                'measurement': kpi_values.get('discipline', {}).get('measurement',
                    'Jumlah keterlambatan'),
                'actual': kpi_values.get('discipline', {}).get('actual', 0),
                'description': kpi_values.get('discipline', {}).get('description',
                    'Kedisiplinan kehadiran'),
                'editable': ['weight', 'target', 'measurement', 'actual']
            }
        ]

        else:
          return {'status': 'error', 'message': f'Invalid position: {job_title}'}

        # Hanya lanjutkan kalkulasi jika ada KPI scores
        if not kpi_scores:
            return {'status': 'error', 'message': 'No KPI configuration found for this position'}

        # Calculate achievement and total score
        for kpi in kpi_scores:
            if kpi['actual'] and kpi['target']:
                kpi['achievement'] = (kpi['actual'] / kpi['target']) * 100
            else:
                kpi['achievement'] = 0

        total_score = sum(
            kpi['achievement'] * (kpi['weight']/100)
            for kpi in kpi_scores
        )

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