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

            # === TEMPLATE DEFINITIONS ===
            # Template untuk CS Regular
            cs_kpi_template = [
                {
                    'no': 1,
                    'name': 'Sigap Melayani Customer Secara Online',
                    'type': 'online_response',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Response time untuk chat/komentar/telfon customer'
                },
                {
                    'no': 2,
                    'name': 'Membuat Laporan Rekap Leads Harian',
                    'type': 'leads_report',
                    'weight': 15,
                    'target': 100,
                    'measurement': 'Akurasi laporan leads harian'
                },
                {
                    'no': 3,
                    'name': 'Menambahkan Kontak Semua Customer',
                    'type': 'customer_contact',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Penambahan customer ke grup'
                },
                {
                    'no': 4,
                    'name': 'Melakukan Reminder Service 3 Bulan',
                    'type': 'service_reminder',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Reminder service untuk customer'
                },
                {
                    'no': 5,
                    'name': 'Membuat Laporan Keuangan Harian Kasir',
                    'type': 'documentation',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Akurasi laporan keuangan'
                },
                {
                    'no': 6,
                    'name': 'Melakukan Pekerjaan CS Sesuai Alur',
                    'type': 'operational',
                    'weight': 15,
                    'target': 100,
                    'measurement': 'Kepatuhan terhadap alur kerja'
                },
                {
                    'no': 7,
                    'name': 'Menjalankan kegiatan operasional secara disiplin',
                    'type': 'discipline',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Ketepatan waktu kehadiran'
                }
            ]

            # Template untuk Lead CS
            lead_cs_kpi_template = [
                {
                    'no': 1,
                    'name': 'Bertanggung Jawab Mengontrol Kinerja Tim',
                    'type': 'team_control',
                    'weight': 30,
                    'target': 90,
                    'measurement': 'Kontrol kinerja tim sesuai SOP'
                },
                {
                    'no': 2,
                    'name': 'Penyelesaian Komplain',
                    'type': 'complaint_handling',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Penyelesaian komplain customer'
                },
                {
                    'no': 3,
                    'name': 'Pencapaian Target Revenue Tim',
                    'type': 'revenue_target',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Pencapaian target revenue tim'
                },
                {
                    'no': 4,
                    'name': 'Pengembangan Tim',
                    'type': 'team_development',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Program pengembangan tim'
                },
                {
                    'no': 5,
                    'name': 'Kegiatan Operasional',
                    'type': 'operational',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Kedisiplinan operasional tim'
                }
            ]

            # Template untuk Service Advisor
            sa_kpi_template = [
                {
                    'no': 1,
                    'name': 'Melayani Customer',
                    'type': 'customer_service',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Persentase kepuasan customer dan minimnya komplain'
                },
                {
                    'no': 2,
                    'name': 'Analisa Jasa',
                    'type': 'service_analysis',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Persentase ketepatan analisa kebutuhan service'
                },
                {
                    'no': 3,
                    'name': 'Efisiensi Pelayanan',
                    'type': 'service_efficiency',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Persentase pelayanan yang selesai tepat waktu'
                },
                {
                    'no': 4,
                    'name': 'Target Revenue SA',
                    'type': 'sa_revenue',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Persentase pencapaian target revenue individu'
                },
                {
                    'no': 5,
                    'name': 'Kepatuhan SOP',
                    'type': 'sop_compliance',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Persentase kepatuhan terhadap SOP'
                },
                {
                    'no': 6,
                    'name': 'Kedisiplinan',
                    'type': 'discipline',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Persentase kehadiran tepat waktu'
                }
            ]


                # Kemudian gunakan start_date_utc dan end_date_utc untuk semua query database
            # Contoh:
            base_domain = [
                ('date_completed', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', 'in', ['sale', 'done'])
            ]

            # === HANDLE DIFFERENT ROLES ===
            # Handle Customer Service
            if 'Customer Service' in job_title:
                online_orders = request.env['sale.order'].sudo().search([
                    *base_domain,
                    ('campaign', '!=', False)
                ])

                # Calculate metrics
                total_responses = len(online_orders)
                on_time_responses = len(online_orders.filtered(
                    lambda o: o.response_duration and o.response_duration <= 30
                ))
                converted_leads = len(online_orders.filtered(lambda o: o.state in ['sale', 'done']))

                attendance_domain = [
                    ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                    ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                    ('employee_id', 'in', team_members.ids)
                ]

                # Calculate attendance
                attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
                late_count = sum(1 for att in attendances if att.is_late)

                kpi_scores = []
                for kpi in cs_kpi_template:
                    actual = 0
                    if kpi['type'] == 'online_response':
                        actual = (on_time_responses / total_responses * 100) if total_responses else 0
                        kpi['measurement'] = f"Respon tepat waktu: {on_time_responses} dari {total_responses} leads"

                    elif kpi['type'] == 'leads_report':
                        actual = (converted_leads / total_responses * 100) if total_responses else 0
                        kpi['measurement'] = f"Leads terkonversi: {converted_leads} dari {total_responses} leads"

                    elif kpi['type'] == 'discipline':
                        actual = ((len(attendances) - late_count) / len(attendances) * 100) if attendances else 0
                        kpi['measurement'] = f"Total kehadiran: {len(attendances)}, Terlambat: {late_count}, Tepat waktu: {len(attendances) - late_count}"

                    else:
                        actual = kpi_values.get(kpi['type'], {}).get('actual', 0)
                        stored_measurement = kpi_values.get(kpi['type'], {}).get('measurement', '')
                        if stored_measurement:
                            kpi['measurement'] = stored_measurement

                    achievement = (actual / kpi['target'] * 100) if kpi['target'] else 0

                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,
                        'weighted_score': achievement * (kpi['weight'] / 100),
                        'editable': ['weight', 'target', 'actual', 'measurement']
                    })

            # Handle Lead Customer Support
            elif 'Lead Customer Support' in job_title:
                team_members = request.env['hr.employee'].sudo().search([
                    ('parent_id', '=', employee.id)
                ])
                
                team_sa = request.env['pitcar.service.advisor'].sudo().search([
                    ('user_id', 'in', team_members.mapped('user_id').ids)
                ])

                all_orders = request.env['sale.order'].sudo().search(base_domain)
                
                # Calculate team metrics
                non_compliant_orders = all_orders.filtered(
                    lambda o: not o.sa_mulai_penerimaan or 
                            not o.sa_cetak_pkb or
                            not o.controller_mulai_servis or
                            not o.controller_selesai
                )
                complaints = all_orders.filtered(lambda o: o.customer_rating in ['1', '2'])
                resolved_complaints = complaints.filtered(lambda o: o.complaint_status == 'solved')
                
                team_revenue = sum(all_orders.mapped('amount_total'))
                team_target = sum(team_sa.mapped('monthly_target'))

                kpi_scores = []
                for kpi in lead_cs_kpi_template:
                    actual = 0
                    if kpi['type'] == 'team_control':
                        total_orders = len(all_orders)
                        non_compliant = len(non_compliant_orders)
                        actual = 100 - ((non_compliant / total_orders * 100) if total_orders else 0)
                        kpi['measurement'] = f"Order sesuai SOP: {total_orders - non_compliant} dari {total_orders} order"

                    elif kpi['type'] == 'complaint_handling':
                        total_complaints = len(complaints)
                        actual = (len(resolved_complaints) / total_complaints * 100) if total_complaints else 100
                        kpi['measurement'] = f"Komplain terselesaikan: {len(resolved_complaints)} dari {total_complaints}"

                    elif kpi['type'] == 'revenue_target':
                        if team_target == 0:
                            actual = 0
                            achievement = 0
                        else:
                            actual = team_revenue
                            achievement = (team_revenue / team_target * 100)
                        
                        formatted_revenue = "{:,.0f}".format(team_revenue)
                        formatted_target = "{:,.0f}".format(team_target)
                        kpi['measurement'] = f"Revenue tim: Rp {formatted_revenue} dari target Rp {formatted_target}/bulan"

                    else:
                        actual = kpi_values.get(kpi['type'], {}).get('actual', 0)
                        stored_measurement = kpi_values.get(kpi['type'], {}).get('measurement', '')
                        if stored_measurement:
                            kpi['measurement'] = stored_measurement

                    achievement = (actual / kpi['target'] * 100) if kpi['target'] else 0

                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,
                        'weighted_score': achievement * (kpi['weight'] / 100),
                        'editable': ['weight', 'target']
                    })

            # Handle Service Advisor
            elif 'Service Advisor' in job_title:
                service_advisor = request.env['pitcar.service.advisor'].sudo().search([
                    ('user_id', '=', employee.user_id.id)
                ], limit=1)

                if not service_advisor:
                    return {'status': 'error', 'message': 'Service Advisor record not found'}

                orders = request.env['sale.order'].sudo().search([
                    *base_domain,
                    ('service_advisor_id', 'in', [service_advisor.id])
                ])

                total_orders = len(orders)
                complaints = len(orders.filtered(lambda o: o.customer_rating in ['1', '2']))
                completed_orders = orders.filtered(lambda o: o.sa_mulai_penerimaan and o.sa_cetak_pkb)
                current_revenue = sum(orders.mapped('amount_total'))

                kpi_scores = []
                for kpi in sa_kpi_template:
                    actual = 0
                    if kpi['type'] == 'customer_service':
                        actual = 100 - ((complaints / total_orders * 100) if total_orders else 0)
                        kpi['measurement'] = f"Total order: {total_orders}, Komplain: {complaints}"

                    elif kpi['type'] == 'service_efficiency':
                        on_time = sum(1 for order in completed_orders 
                            if (order.sa_cetak_pkb - order.sa_mulai_penerimaan).total_seconds() / 60 <= 15)
                        actual = (on_time / len(completed_orders) * 100) if completed_orders else 0
                        kpi['measurement'] = f"Pengerjaan tepat waktu: {on_time} dari {len(completed_orders)}"

                    elif kpi['type'] == 'sa_revenue':
                        monthly_target = service_advisor.monthly_target or 64000000
                        if monthly_target == 0:
                            actual = 0
                            achievement = 0
                        else:
                            actual = (current_revenue / monthly_target * 100)  # Actual jadi persentase
                            achievement = actual  # Achievement sama dengan actual
                        
                        formatted_revenue = "{:,.0f}".format(current_revenue)
                        formatted_target = "{:,.0f}".format(monthly_target)
                        kpi['measurement'] = f"Revenue: Rp {formatted_revenue} dari target Rp {formatted_target}/bulan"

                    else:
                        actual = kpi_values.get(kpi['type'], {}).get('actual', 0)
                        stored_measurement = kpi_values.get(kpi['type'], {}).get('measurement', '')
                        if stored_measurement:
                            kpi['measurement'] = stored_measurement

                    achievement = (actual / kpi['target'] * 100) if kpi['target'] else 0

                    kpi_scores.append({
                    'no': kpi['no'],
                    'name': kpi['name'],
                    'type': kpi['type'],
                    'weight': kpi['weight'],
                    'target': kpi['target'],
                    'measurement': kpi['measurement'],
                    'actual': actual,
                    'achievement': achievement,
                    'weighted_score': achievement * (kpi['weight'] / 100),
                    'editable': ['weight', 'target']
                })

            else:
                return {'status': 'error', 'message': f'Invalid position: {job_title}'}

            # Calculate total score and summary
            total_weight = sum(kpi['weight'] for kpi in kpi_scores)
            total_score = sum(kpi['weighted_score'] for kpi in kpi_scores)
            avg_target = sum(kpi['target'] * kpi['weight'] for kpi in kpi_scores) / total_weight if total_weight else 0

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
                        'department': employee.department_id.name
                    },
                    'period': {
                        'month': month,
                        'year': year
                    },
                    'kpi_scores': kpi_scores,
                    'summary': {
                        'total_weight': total_weight,
                        'average_target': avg_target,
                        'total_score': total_score,
                        'achievement_status': 'Achieved' if total_score >= avg_target else 'Below Target'
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_customer_support_kpi: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kpi/mechanic', type='json', auth='user', methods=['POST'], csrf=False)
    def get_mechanic_kpi(self, **kw):
        """Get KPI data for Mechanic Department"""
        try:
            # Debug log input parameters
            _logger.info(f"Received kw: {kw}")

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
            
            # Get job position
            mechanic = request.env['pitcar.mechanic.new'].sudo().search([
                ('employee_id', '=', employee.id)
            ], limit=1)
            
            if not mechanic:
                return {'status': 'error', 'message': 'Mechanic record not found'}
                
            job_title = mechanic.position_id.name

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

            # Base domain for order queries
            base_domain = [
                ('date_completed', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', 'in', ['sale', 'done'])
            ]

            kpi_scores = []

            # Definisi KPI template sesuai posisi
            mechanic_kpi_template = [
                {
                    'no': 1,
                    'name': 'Menjamin hasil pekerjaan servis terlaksana dengan baik',
                    'type': 'service_quality',
                    'weight': 25,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah customer yang puas dari hasil pengerjaan (tidak komplain)'
                },
                {
                    'no': 2,
                    'name': 'Produktivitas Mekanik Optimal',
                    'type': 'productivity',
                    'weight': 25,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah omset yang dihasilkan dari PKB yang ditangani'
                },
                {
                    'no': 3,
                    'name': 'Melakukan Pekerjaan Operasional Sesuai Alur dan SOP yang ditetapkan',
                    'type': 'sop_compliance',
                    'weight': 30,
                    'target': 95,
                    'measurement': 'Diukur dari jumlah temuan pekerjaan yang dilakukan tidak sesuai dengan alur / SOP yang ditetapkan'
                },
                {
                    'no': 4,
                    'name': 'Menjalankan kegiatan operasional secara disiplin',
                    'type': 'discipline',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah keterlambatan dan ketidakhadiran'
                }
            ]

            leader_kpi_template = [
                {
                    'no': 1,
                    'name': 'Melakukan distribusi pekerjaan secara efisien',
                    'type': 'work_distribution',
                    'weight': 15,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah unit yang dapat terhandle selama satu bulan'
                },
                {
                    'no': 2,
                    'name': 'Menjamin analisa dan hasil pekerjaan servis terlaksana dengan baik',
                    'type': 'service_quality',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah customer yang puas dari hasil pengerjaan'
                },
                {
                    'no': 3,
                    'name': 'Menganalisis dan Menyelesaikan Komplain Dari Customer',
                    'type': 'complaint_handling',
                    'weight': 15,
                    'target': 100,
                    'measurement': 'Customer Puas Terhadap Pengerjaan & Solusi yang Diberikan'
                },
                {
                    'no': 4,
                    'name': 'Produktivitas Mekanik Optimal',
                    'type': 'team_productivity',
                    'weight': 15,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah omset yang dihasilkan dari PKB yang ditangani'
                },
                {
                    'no': 5,
                    'name': 'Melakukan Pekerjaan Operasional Sesuai Alur dan SOP yang ditetapkan',
                    'type': 'sop_compliance',
                    'weight': 15,
                    'target': 95,
                    'measurement': 'Diukur dari jumlah temuan pekerjaan yang dilakukan tidak sesuai dengan alur / SOP'
                },
                {
                    'no': 6,
                    'name': 'Menjalankan kegiatan operasional secara disiplin',
                    'type': 'team_discipline',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah keterlambatan dan ketidakhadiran'
                }
            ]
            
            # Handle regular mechanic KPI
            if 'Mechanic' in job_title:
                orders = request.env['sale.order'].sudo().search([
                    *base_domain,
                    ('car_mechanic_id_new', 'in', [mechanic.id])
                ])

                # Calculate attendance metrics
                attendance_domain = [
                    ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                    ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                    ('employee_id', '=', employee.id)
                ]

                # Prepare data untuk perhitungan
                total_orders = len(orders)
                total_revenue = sum(order.amount_total / len(order.car_mechanic_id_new) for order in orders)
                satisfied_orders = len(orders.filtered(lambda o: o.customer_rating not in ['1', '2']))
                sop_violations = len(orders.filtered(lambda o: o.sop_sampling_ids.filtered(lambda s: s.result == 'fail')))
                
                # Get attendance data
                attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
                late_count = sum(1 for att in attendances if att.is_late)

                # Calculate KPI scores
                kpi_scores = []
                for kpi in mechanic_kpi_template:
                    actual = 0
                    if kpi['type'] == 'service_quality':
                        actual = (satisfied_orders / total_orders * 100) if total_orders else 0
                        complaints = len(orders.filtered(lambda o: o.customer_rating in ['1', '2']))
                        kpi['measurement'] = f"Total order: {total_orders}, Customer puas: {satisfied_orders}, Komplain: {complaints}"
                        
                    elif kpi['type'] == 'productivity':
                        monthly_target = mechanic.monthly_target or 64000000
                        if monthly_target == 0:
                            actual = 0
                            achievement = 0
                        else:
                            revenue = total_revenue
                            actual = (revenue / monthly_target * 100)  # Actual jadi persentase
                            achievement = actual  # Achievement sama dengan actual
                        
                        formatted_revenue = "{:,.0f}".format(total_revenue)
                        formatted_target = "{:,.0f}".format(monthly_target)
                        kpi['measurement'] = f"Revenue: Rp {formatted_revenue} dari target Rp {formatted_target}/bulan"



                        
                    elif kpi['type'] == 'sop_compliance':
                        actual = ((total_orders - sop_violations) / total_orders * 100) if total_orders else 0
                        kpi['measurement'] = f"Total order: {total_orders}, Sesuai SOP: {total_orders - sop_violations}, Pelanggaran: {sop_violations}"
                        
                    elif kpi['type'] == 'discipline':
                        actual = ((len(attendances) - late_count) / len(attendances) * 100) if attendances else 0
                        kpi['measurement'] = f"Total kehadiran: {len(attendances)}, Terlambat: {late_count}, Tepat waktu: {len(attendances) - late_count}"

                    achievement = (actual / kpi['target'] * 100) if kpi['target'] else 0
                    
                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,
                        'weighted_score': achievement * (kpi['weight'] / 100)
                    })



            # Handle Lead Mechanic KPI
            elif 'Team Leader' in job_title:
                # Get team members
                team_members = request.env['pitcar.mechanic.new'].sudo().search([
                    ('leader_id', '=', mechanic.id)
                ])
                
                # Get all orders for the team including leader's orders
                team_orders = request.env['sale.order'].sudo().search([
                    *base_domain,
                    ('car_mechanic_id_new', 'in', team_members.ids + [mechanic.id])  # Include leader
                ])

                # Unit handling efficiency
                total_units = len(team_orders)
                
                # Service quality
                satisfied_customers = len(team_orders.filtered(lambda o: o.customer_rating not in ['1', '2']))
                
                # Customer complaints
                complaints = len(team_orders.filtered(lambda o: o.customer_rating in ['1', '2']))
                resolved_complaints = len(team_orders.filtered(lambda o: 
                    o.customer_rating in ['1', '2'] and o.complaint_status == 'solved'
                ))

                # Team productivity
                team_revenue = sum(team_orders.mapped('amount_total'))
                team_target = (len(team_members) + 1) * 64000000  # +1 untuk leader
                
                # SOP compliance
                sop_violations = len(team_orders.filtered(lambda o: 
                    o.sop_sampling_ids.filtered(lambda s: s.result == 'fail')
                ))
                
                # Attendance metrics for team
                attendance_domain = [
                    ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                    ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                    ('employee_id', 'in', team_members.mapped('employee_id').ids + [employee.id])
                ]
                team_attendances = request.env['hr.attendance'].sudo().search(attendance_domain)
                late_count = sum(1 for att in team_attendances if att.is_late)

                kpi_scores = []
                for kpi in leader_kpi_template:
                    actual = 0
                    if kpi['type'] == 'work_distribution':
                        target_units = 145  # Sesuai target yang ditetapkan
                        actual = (total_units / target_units * 100) if target_units else 0
                        kpi['measurement'] = f"Berhasil handle {total_units} unit dari target {target_units} unit/bulan"
                        
                    elif kpi['type'] == 'service_quality':
                        actual = (satisfied_customers / total_units * 100) if total_units else 0
                        kpi['measurement'] = f"Total order: {total_units}, Customer puas: {satisfied_customers}, Komplain: {complaints}"
                        
                    elif kpi['type'] == 'complaint_handling':
                        actual = (resolved_complaints / complaints * 100) if complaints else 100
                        kpi['measurement'] = f"Total komplain: {complaints}, Berhasil diselesaikan: {resolved_complaints}"
                        
                    elif kpi['type'] == 'team_productivity':
                        if team_target == 0:
                            actual = 0
                            achievement = 0
                        else:
                            actual = (team_revenue / team_target * 100)  # Actual sebagai persentase
                            achievement = actual
                        
                        formatted_revenue = "{:,.0f}".format(team_revenue)
                        formatted_target = "{:,.0f}".format(team_target)
                        kpi['measurement'] = f"Revenue tim: Rp {formatted_revenue} dari target Rp {formatted_target}/bulan"
                        
                    elif kpi['type'] == 'sop_compliance':
                        actual = ((total_units - sop_violations) / total_units * 100) if total_units else 0
                        kpi['measurement'] = f"Total order: {total_units}, Sesuai SOP: {total_units - sop_violations}, Pelanggaran: {sop_violations}"
                        
                    elif kpi['type'] == 'team_discipline':
                        actual = ((len(team_attendances) - late_count) / len(team_attendances) * 100) if team_attendances else 0
                        kpi['measurement'] = f"Total kehadiran tim: {len(team_attendances)}, Terlambat: {late_count}, Tepat waktu: {len(team_attendances) - late_count}"

                    achievement = (actual / kpi['target'] * 100) if kpi['target'] else 0
                    
                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,
                        'weighted_score': achievement * (kpi['weight'] / 100),
                        'editable': ['weight', 'target']
                    })


            # Calculate total score
            total_weight = sum(kpi['weight'] for kpi in kpi_scores)
            total_score = sum(kpi['weighted_score'] for kpi in kpi_scores)
            if total_weight != 100:
                _logger.warning(f"Total weight ({total_weight}) is not 100%")
            avg_target = sum(kpi['target'] * kpi['weight'] for kpi in kpi_scores) / total_weight if total_weight else 0

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
                    'summary': {
                        'total_weight': total_weight,
                        'average_target': avg_target,
                        'total_score': total_score,
                        'achievement_status': 'Achieved' if total_score >= avg_target else 'Below Target'
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_mechanic_kpi: {str(e)}")
            return {'status': 'error', 'message': str(e)}
