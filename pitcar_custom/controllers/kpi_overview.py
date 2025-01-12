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
        
        # Get job position
        job_title = employee.job_id.name

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
                    'weight': 30,
                    'target': 90,
                    'achievement': ((32 - total_non_compliant) / 32 * 100) if total_non_compliant <= 32 else 0,
                    'details': {
                        'total_orders': len(all_orders),
                        'non_compliant': total_non_compliant,
                        'target': 32
                    }
                },
                {
                    'name': 'Menganalisis dan Menyelesaikan Complain',
                    'weight': 20,
                    'target': 90,
                    'achievement': (resolved_complaints / total_complaints * 100) if total_complaints else 100,
                    'details': {
                        'total_complaints': total_complaints,
                        'resolved': resolved_complaints,
                        'target_resolution': 562
                    }
                },
                {
                    'name': 'Meningkatkan Omset Penjualan',
                    'weight': 20,
                    'target': 100,
                    'achievement': (team_revenue / team_target * 100) if team_target else 0,
                    'details': {
                        'current_revenue': team_revenue,
                        'target_revenue': team_target
                    }
                },
                {
                    'name': 'Memimpin dan Mengembangkan Kualitas Tim',
                    'weight': 10,
                    'target': 95,
                    'achievement': (completed_trainings / training_target * 100) if training_target else 0,
                    'details': {
                        'completed_trainings': completed_trainings,
                        'target_trainings': training_target
                    }
                },
                {
                    'name': 'Menjalankan Kegiatan Operasional',
                    'weight': 20,
                    'target': 90,
                    'achievement': ((26 - late_count) / 26 * 100) if late_count <= 26 else 0,
                    'details': {
                        'total_late': late_count,
                        'target_attendance': 26
                    }
                }
            ]

            # Calculate total score
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
                        'position': 'CS Lead',
                        'department': employee.department_id.name
                    },
                    'period': {
                        'month': month,
                        'year': year
                    },
                    'kpi_scores': kpi_scores,
                    'total_score': total_score,
                    'team_overview': {
                        'total_members': len(team_members),
                        'total_orders': len(all_orders),
                        'total_revenue': team_revenue,
                        'complaint_rate': (total_complaints / len(all_orders) * 100) if all_orders else 0
                    }
                }
            }
            
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
                    'weight': 10,
                    'target': 90,
                    'achievement': (resolved_complaints / total_complaints * 100) if total_complaints else 100,
                    'details': {
                        'total_complaints': total_complaints,
                        'resolved_complaints': resolved_complaints
                    }
                },
                {
                    'name': 'Tidak ada kesalahan analisa jasa',
                    'weight': 15,
                    'target': 90,
                    'achievement': ((total_services - incorrect_analysis) / total_services * 100) if total_services else 100,
                    'details': {
                        'total_services': total_services,
                        'incorrect_analysis': incorrect_analysis
                    }
                },
                {
                    'name': 'Efisiensi Pelayanan Customer',
                    'weight': 15,
                    'target': 90,
                    'achievement': (on_time_services / len(completed_orders) * 100) if completed_orders else 0,
                    'details': {
                        'total_services': len(completed_orders),
                        'on_time_services': on_time_services
                    }
                },
                {
                    'name': 'Target Revenue',
                    'weight': 15,
                    'target': service_advisor.monthly_target,
                    'achievement': (current_revenue / service_advisor.monthly_target * 100) if service_advisor.monthly_target else 0,
                    'details': {
                        'current_revenue': current_revenue,
                        'target_revenue': service_advisor.monthly_target
                    }
                },
                {
                    'name': 'SOP Compliance',
                    'weight': 25,
                    'target': 90,
                    'achievement': (passed_sop / total_sop * 100) if total_sop else 100,
                    'details': {
                        'total_sop': total_sop,
                        'passed_sop': passed_sop
                    }
                },
                {
                    'name': 'Kedisiplinan',
                    'weight': 20,
                    'target': 90,
                    'achievement': ((26 - late_count) / 26 * 100) if late_count <= 26 else 0,
                    'details': {
                        'late_count': late_count,
                        'target_attendance': 26
                    }
                }
            ]

            # Calculate total score
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
                    'weight': 20,
                    'target': 100,
                    'achievement': (on_time_responses / total_responses * 100) if total_responses else 100,
                    'details': {
                        'total_responses': total_responses,
                        'on_time_responses': on_time_responses
                    }
                },
                {
                    'name': 'Leads Report',
                    'weight': 15,
                    'target': 100,
                    'achievement': (converted_leads / total_leads * 100) if total_leads else 0,
                    'details': {
                        'total_leads': total_leads,
                        'converted_leads': converted_leads
                    }
                },
                {
                    'name': 'Customer Contact Management',
                    'weight': 10,
                    'target': 100,
                    'achievement': (total_broadcasts / target_broadcasts * 100) if target_broadcasts else 0,
                    'details': {
                        'total_broadcasts': total_broadcasts,
                        'target_broadcasts': target_broadcasts
                    }
                },
                {
                    'name': 'Service Reminder',
                    'weight': 10,
                    'target': 100,
                    'achievement': (completed_reminders / total_reminders * 100) if total_reminders else 100,
                    'details': {
                        'total_reminders': total_reminders,
                        'completed_reminders': completed_reminders
                    }
                },
                {
                    'name': 'Documentation',
                    'weight': 25,
                    'target': 100,
                    'achievement': 100 if reports_complete else 0,
                    'details': {
                        'reports_complete': reports_complete
                    }
                },
                {
                    'name': 'Kedisiplinan',
                    'weight': 20,
                    'target': 90,
                    'achievement': ((26 - late_count) / 26 * 100) if late_count <= 26 else 0,
                    'details': {
                        'late_count': late_count,
                        'target_attendance': 26
                    }
                }
            ]

         # Calculate total score
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
    
    # Jika tidak masuk kondisi manapun        
        # return {'status': 'error', 'message': 'Invalid employee position'}

    except Exception as e:
        _logger.error(f"Error in get_customer_support_kpi: {str(e)}")
        return {'status': 'error', 'message': str(e)}