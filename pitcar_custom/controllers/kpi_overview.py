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
                    'name': 'Persentase seluruh interaksi calon customer direspon sesuai waktu yang ditentukan setiap harinya',
                    'type': 'online_response',
                    'weight': 25,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah chat yang direspon sesuai target waktu',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': 'Persentase rekap leads tepat sesuai sampel',
                    'type': 'leads_report',
                    'weight': 15,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah Leads di Rekap Leads Sesuai Dengan Aktual',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Persentase seluruh customer ditambahkan grup siaran & melakukan story WA setiap hari serta broadcast',
                    'type': 'customer_contact',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Diukur dari kelengkapan kontak, story dan broadcast WA',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Persentase customer loyal direminder servis',
                    'type': 'service_reminder',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah reminder customer loyal sesuai target',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': 'Jumlah transaksi keuangan harian selalu balance',
                    'type': 'finance_check',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Diukur dari kelengkapan verifikasi laporan keuangan harian',
                    'include_in_calculation': True
                },
                {
                    'no': 6,
                    'name': 'Rating survey kepuasan customer memberikan nilai minimal 4,8 dari 5',
                    'type': 'customer_satisfaction',
                    'weight': 15,
                    'target': 95,
                    'measurement': 'Diukur dari survey rating kepuasan customer',
                    'include_in_calculation': True
                },
                {
                    'no': 7,
                    'name': 'Persentase sampel tim CS bekerja sesuai alur SOP',
                    'type': 'sop_compliance',
                    'weight': 15,
                    'target': 95,
                    'measurement': 'Diukur dari temuan pekerjaan tidak sesuai alur',
                    'include_in_calculation': True
                },
                {
                    'no': 8,  # Tambahkan sebagai KPI terakhir
                    'name': 'Kedisiplinan (Informasi)',
                    'type': 'discipline',
                    'weight': 0,  # Weight 0 karena tidak dihitung
                    'target': 0,
                    'measurement': 'Diukur dari jumlah keterlambatan dan ketidakhadiran',
                    'include_in_calculation': False  # Set False untuk tidak masuk perhitungan
                }
            ]

            lead_cs_kpi_template = [
                {
                    'no': 1,
                    'name': 'Jumlah omzet pitcar service sesuai target',
                    'type': 'productivity',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah omzet yang dihasilkan dari PKB yang ditangani',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': 'Persentase rata-rata waktu penanganan customer yang sesuai target waktu',
                    'type': 'service_efficiency',
                    'weight': 10,
                    'target': 80,
                    'measurement': 'Diukur dari kesesuaian waktu penanganan customer berdasarkan target waktu',
                    'include_in_calculation': True
                },
                # {
                #     'no': 3,
                #     'name': 'Distribusi pekerjaan servis secara optimal',
                #     'type': 'customer_satisfaction',
                #     'weight': 15,
                #     'target': 95,
                #     'measurement': 'Diukur dari rata-rata waktu pengerjaan per PKB setiap mekanik',
                #     'include_in_calculation': True
                # },
                {
                    'no': 3,
                    'name': 'Rating survey kepuasan customer memberikan nilai minimal 4,8 dari 5',
                    'type': 'customer_satisfaction',
                    'weight': 20,
                    'target': 95,
                    'measurement': 'Diukur dari survey rating kepuasan customer',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Jumlah customer merasa puas terhadap pelayanan & solusi diberikan maksimal 3 hari setelah komplain dilayangkan',
                    'type': 'complaint_handling',
                    'weight': 20,
                    'target': 95,
                    'measurement': 'Diukur dari customer merasa puas terhadap pelayanan & solusi yang diberikan dalam kurun waktu 3 hari setelah complaint',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': 'Persentase waktu pengerjaan mekanik yang sesuai waktu rata-rata pengerjaan seluruh mekanik',
                    'type': 'mechanic_efficiency',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Diukur dari rata-rata waktu pengerjaan per PKB setiap mekanik',
                    'include_in_calculation': True
                },
                {
                    'no': 6,
                    'name': 'Persentase sampel tim support bekerja sesuai alur SOP',
                    'type': 'team_control',
                    'weight': 15,
                    'target': 95,
                    'measurement': 'Diukur dari jumlah temuan pekerjaan tim support yang dilakukan tidak sesuai dengan alur/SOP',
                    'include_in_calculation': True
                },
                {
                    'no': 7,  # Tambahkan sebagai KPI terakhir
                    'name': 'Kedisiplinan Tim (Informasi)',  
                    'type': 'team_discipline',
                    'weight': 0,
                    'target': 0,
                    'measurement': 'Diukur dari jumlah keterlambatan dan ketidakhadiran tim',
                    'include_in_calculation': False
                }
            ]

            # Template untuk Service Advisor
            sa_kpi_template = [
                {
                    'no': 1,
                    'name': 'Jumlah omzet pitcar service sesuai target',
                    'type': 'productivity',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah omzet yang dihasilkan dari PKB yang ditangani',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': 'Persentase rata-rata penanganan customer yang sesuai target waktu',
                    'type': 'service_efficiency',
                    'weight': 20,
                    'target': 80,
                    'measurement': 'Diukur dari kesesuaian waktu penanganan customer berdasarkan target waktu',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Rating survey kepuasan customer memberikan nilai minimal 4,8 dari 5',
                    'type': 'customer_satisfaction',
                    'weight': 20,
                    'target': 95,
                    'measurement': 'Diukur dari survey rating kepuasan customer',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Jumlah customer merasa puas terhadap pelayanan & solusi diberikan maksimal 3 hari setelah komplain dilayangkan',
                    'type': 'complaint_handling',
                    'weight': 15,
                    'target': 95,
                    'measurement': 'Diukur dari customer merasa puas terhadap pelayanan & solusi yang diberikan dalam kurun waktu 3 hari setelah complaint',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': 'Follow up H+3 untuk setiap customer setelah servis',
                    'type': 'follow_up_h3',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah follow up yang dilakukan setelah servis',
                },
                {
                    'no': 6,
                    'name': 'Pekerjaan operasional dilakukan sesuai alur dan SOP yang ditetapkan',
                    'type': 'sop_compliance',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Persentase kepatuhan terhadap SOP'
                },
                {
                    'no': 7,  # Tambahkan sebagai KPI terakhir
                    'name': 'Kedisiplinan (Informasi)',  
                    'type': 'discipline',
                    'weight': 0,
                    'target': 0,
                    'measurement': 'Diukur dari jumlah keterlambatan dan ketidakhadiran tim',
                    'include_in_calculation': False
                }
            ]

            # Template KPI untuk Valet Parking
            valet_kpi_template = [
                {
                    'no': 1,
                    'name': '% sampel tim valet parking bekerja sesuai alur SOP',
                    'type': 'valet_sop',
                    'weight': 50,
                    'target': 95,
                    'measurement': 'Diukur dari jumlah temuan pekerjaan sesuai SOP',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': '% peralatan front office lengkap dan sesuai pada tempatnya',
                    'type': 'front_office',
                    'weight': 30,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah temuan peralatan lengkap & sesuai',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Rating survey kepuasan customer memberikan nilai minimal 4.8 dari 5',
                    'type': 'customer_satisfaction',
                    'weight': 20,
                    'target': 95,
                    'measurement': 'Diukur dari survey rating kepuasan customer',
                    'include_in_calculation': True
                }
            ]

                        # Template KPI Admin Part
            admin_part_template = [
                {
                    'no': 1,
                    'name': '% kebutuhan part & tools terpenuhi',
                    'type': 'part_fulfillment',
                    'weight': 20,
                    'target': 95,
                    'measurement': 'Diukur dari jumlah part & tools terpenuhi / jumlah sampel',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': 'Response time estimasi part < 15 menit',
                    'type': 'part_response',
                    'weight': 20,
                    'target': 95,
                    'measurement': 'Diukur dari kecepatan response part request',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Jumlah hari stok part tersedia',
                    'type': 'part_availability',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah hari stok part wajib ready tersedia',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Selisih nilai part sistem vs aktual',
                    'type': 'part_audit',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Diukur dari selisih nilai part < Rp 200.000',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': 'Selisih nilai tools sistem vs aktual',
                    'type': 'tools_audit',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Diukur dari selisih nilai tools < Rp 200.000',
                    'include_in_calculation': True
                },
                {
                    'no': 6,
                    'name': '% sampel admin part bekerja sesuai SOP',
                    'type': 'sop_compliance',
                    'weight': 20,
                    'target': 95,
                    'measurement': 'Diukur dari jumlah sampel sesuai SOP / total sampel',
                    'include_in_calculation': True
                }
            ]

            # Template KPI untuk Toolkeeper
            toolkeeper_template = [
                {
                    'no': 1,
                    'name': '% hari belanja part sesuai target & kecocokan',
                    'type': 'part_purchase',
                    'weight': 25,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah belanja part yang sesuai target dan cocok',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': '% hari belanja tools sesuai target & kecocokan',
                    'type': 'tool_purchase',
                    'weight': 20,
                    'target': 95,
                    'measurement': 'Diukur dari jumlah belanja tools yang sesuai target dan cocok',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Selisih nilai part sistem vs aktual',
                    'type': 'part_audit',
                    'weight': 10,
                    'target': 100,
                    'measurement': 'Diukur dari selisih nilai part < Rp 200.000',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Selisih nilai tools sistem vs aktual',
                    'type': 'tools_audit',
                    'weight': 25,
                    'target': 100,
                    'measurement': 'Diukur dari selisih nilai tools < Rp 200.000',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': '% sampel toolkeeper bekerja sesuai SOP',
                    'type': 'sop_compliance',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah sampel sesuai SOP / total sampel',
                    'include_in_calculation': True
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
            # Update perhitungan di dalam handler
            if 'Customer Service' in job_title:
                for kpi in cs_kpi_template:
                    actual = 0
                    
                    if kpi['type'] == 'online_response':
                        # Ambil data dari cs.chat.sampling
                        chat_sampling = request.env['cs.chat.sampling'].sudo().search([
                            ('cs_id', '=', employee.id),
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('state', '=', 'done')
                        ])
                        if chat_sampling:
                            responses = sum(chat_sampling.mapped('responded_ontime'))
                            total_chats = sum(chat_sampling.mapped('total_chats'))
                            actual = (responses / total_chats * 100) if total_chats else 0
                            kpi['measurement'] = f"Chat direspon tepat waktu: {responses} dari {total_chats} chat"
                        
                    elif kpi['type'] == 'leads_report':
                        # Ambil data dari cs.leads.verification
                        leads_checks = request.env['cs.leads.verification'].sudo().search([
                            ('cs_id', '=', employee.id),
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('state', '=', 'done')
                        ])
                        if leads_checks:
                            actual = sum(leads_checks.mapped('accuracy_rate')) / len(leads_checks)
                            kpi['measurement'] = f"Rata-rata akurasi rekap leads: {actual:.1f}%"
                        
                    elif kpi['type'] == 'customer_contact':
                        # Ambil data dari cs.contact.monitoring
                        contact_checks = request.env['cs.contact.monitoring'].sudo().search([
                            ('cs_id', '=', employee.id),
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('state', '=', 'done')
                        ])
                        if contact_checks:
                            actual = sum(contact_checks.mapped('compliance_rate')) / len(contact_checks)
                            kpi['measurement'] = f"Rata-rata kepatuhan kontak & broadcast: {actual:.1f}%"
                        
                    elif kpi['type'] == 'service_reminder':
                        # Existing code untuk reminder service
                        reminder_domain = [
                            ('next_follow_up_3_months', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('next_follow_up_3_months', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('state', 'in', ['sale', 'done'])
                        ]
                        due_reminders = request.env['sale.order'].sudo().search(reminder_domain)
                        completed_reminders = due_reminders.filtered(lambda o: o.reminder_3_months == 'yes')
                        total_due = len(due_reminders)
                        actual = (len(completed_reminders) / total_due * 100) if total_due else 0
                        kpi['measurement'] = f"Reminder terkirim: {len(completed_reminders)} dari {total_due}"
                        
                    elif kpi['type'] == 'finance_check':
                        # Ambil data dari cs.finance.check
                        finance_checks = request.env['cs.finance.check'].sudo().search([
                            ('cs_id', '=', employee.id),
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('state', '=', 'done')
                        ])
                        if finance_checks:
                            actual = sum(finance_checks.mapped('completeness_rate')) / len(finance_checks)
                            kpi['measurement'] = f"Rata-rata kelengkapan verifikasi: {actual:.1f}%"
                        
                    elif kpi['type'] == 'customer_satisfaction':
                        # Define period_orders first
                        period_orders = request.env['sale.order'].sudo().search([
                            ('date_completed', '>=', start_date.strftime('%Y-%m-%d')),
                            ('date_completed', '<=', end_date.strftime('%Y-%m-%d')),
                            ('state', 'in', ['sale', 'done'])
                        ])
                        
                        # Then process the ratings
                        rated_orders = period_orders.filtered(lambda o: o.customer_rating)
                        total_rated_orders = len(rated_orders)
                        
                        if total_rated_orders > 0:
                            total_rating = sum(float(order.customer_rating) for order in rated_orders)
                            avg_rating = total_rating / total_rated_orders
                            
                            if avg_rating > 4.8:
                                actual = 120
                            elif avg_rating == 4.8:
                                actual = 100
                            elif 4.6 <= avg_rating <= 4.7:
                                actual = 50
                            else:
                                actual = 0
                                
                            kpi['measurement'] = f"Rating rata-rata: {avg_rating:.1f} dari {total_rated_orders} order"
                        else:
                            actual = 0
                            kpi['measurement'] = f"Belum ada rating pada periode {month}/{year}"
                        
                    elif kpi['type'] == 'sop_compliance':
                        # Existing code untuk SOP compliance
                        samplings = request.env['pitcar.sop.sampling'].sudo().search([
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('cs_id', '=', employee.id),
                            ('state', '=', 'done')
                        ])
                        total_samples = len(samplings)
                        passed_samples = len(samplings.filtered(lambda s: s.result == 'pass'))
                        actual = (passed_samples / total_samples * 100) if total_samples else 0
                        kpi['measurement'] = f"Sesuai SOP: {passed_samples} dari {total_samples} sampel"

                    elif kpi['type'] == 'discipline':
                        attendances = request.env['hr.attendance'].sudo().search([
                            ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('employee_id', '=', employee.id)
                        ])
                        late_count = sum(1 for att in attendances if att.is_late)
                        actual = ((len(attendances) - late_count) / len(attendances) * 100) if attendances else 0
                        kpi['measurement'] = f"Total kehadiran: {len(attendances)}, Terlambat: {late_count}, Tepat waktu: {len(attendances) - late_count}"

                    # Update rumus achievement - langsung actual × weight/100
                    # weighted_score = actual * (kpi['weight'] / 100)
                    # Perhitungan baru: weighted_score langsung dari actual × weight/100
                    weighted_score = actual * (kpi['weight'] / 100)
                    
                    # Set achievement sama dengan weighted_score untuk kompatibilitas frontend
                    achievement = weighted_score

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

                # Calculate total score
                total_weight = sum(kpi['weight'] for kpi in kpi_scores)
                total_score = sum(kpi['weighted_score'] for kpi in kpi_scores)

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
                    measurement = ""
                    
                    if kpi['type'] == 'productivity':
                        # Otomatis ambil data produktivitas dari sistem
                        if team_target == 0:
                            actual = 0
                        else:
                            actual = (team_revenue / team_target * 100)  # Persentase pencapaian target revenue
                        measurement = f"Revenue tim: Rp {team_revenue:,.0f} dari target Rp {team_target:,.0f}/bulan"

                    elif kpi['type'] == 'service_efficiency':
                        # Otomatis ambil data efisiensi waktu dari sistem
                        orders_with_duration = all_orders.filtered(lambda o: o.duration_deviation is not False)
                        if orders_with_duration:
                            avg_deviation = abs(sum(orders_with_duration.mapped('duration_deviation'))) / len(orders_with_duration)
                            actual = max(0, 100 - avg_deviation)  # Convert deviation to efficiency
                        measurement = f"Rata-rata deviasi waktu: {avg_deviation:.1f}%, Efisiensi: {actual:.1f}%"

                    elif kpi['type'] == 'customer_satisfaction':
                        # Filter orders berdasarkan periode yang dipilih
                        period_orders = request.env['sale.order'].sudo().search([
                            ('date_completed', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('date_completed', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('state', 'in', ['sale', 'done']),
                            ('service_advisor_id', 'in', team_sa.ids)  # Untuk memastikan hanya order dari tim SA yang dihitung
                        ])
                        
                        # Ambil order yang memiliki rating dari periode yang dipilih
                        rated_orders = period_orders.filtered(lambda o: o.customer_rating)
                        total_rated_orders = len(rated_orders)
                        
                        if total_rated_orders > 0:
                            # Hitung rata-rata rating
                            total_rating = sum(float(order.customer_rating) for order in rated_orders)
                            avg_rating = total_rating / total_rated_orders
                            
                            # Implementasi formula khusus
                            if avg_rating > 4.8:
                                actual = 120
                            elif avg_rating == 4.8:
                                actual = 100
                            elif 4.6 <= avg_rating <= 4.7:
                                actual = 50
                            else:  # < 4.6
                                actual = 0
                                
                            measurement = (
                                f"Rating rata-rata: {avg_rating:.1f} dari {total_rated_orders} order "
                                f"pada periode {month}/{year}."
                            )
                        else:
                            actual = 0
                            measurement = f"Belum ada rating customer pada periode {month}/{year}"

                    elif kpi['type'] == 'complaint_handling':
                        # Otomatis ambil data penanganan komplain dari sistem
                        actual = (len(resolved_complaints) / len(complaints) * 100) if complaints else 100
                        measurement = f"Komplain terselesaikan: {len(resolved_complaints)} dari {len(complaints)}"

                    # Perbaikan perhitungan mechanic efficiency
                    elif kpi['type'] == 'mechanic_efficiency':
                        # Ambil mekanik yang aktif berdasarkan orders di periode tersebut
                        active_mechanics = request.env['sale.order'].sudo().search([
                            *base_domain,
                            ('state', 'in', ['sale', 'done'])
                        ]).mapped('car_mechanic_id_new')
                        
                        _logger.info(f"Found {len(active_mechanics)} active mechanics in period {month}/{year}")

                        if not active_mechanics:
                            actual = 0
                            measurement = f"Tidak ada mekanik aktif pada periode {month}/{year}"
                        else:
                            # Get orders untuk mekanik yang aktif
                            all_orders = request.env['sale.order'].sudo().search([
                                *base_domain,
                                ('car_mechanic_id_new', 'in', active_mechanics.ids),
                                ('state', 'in', ['sale', 'done'])
                            ])
                            
                            _logger.info(f"Found {len(all_orders)} orders for active mechanics")

                            # Hitung rata-rata waktu pengerjaan per mekanik
                            mechanic_times = {}
                            for order in all_orders:
                                if order.controller_mulai_servis and order.controller_selesai and order.lead_time_servis:
                                    for mech in order.car_mechanic_id_new:
                                        if mech not in mechanic_times:
                                            mechanic_times[mech] = []
                                        mechanic_times[mech].append(order.lead_time_servis)

                            # Hitung rata-rata untuk setiap mekanik
                            mechanic_averages = {}
                            mechanic_names = {}
                            for mech, times in mechanic_times.items():
                                if times:
                                    avg_time = sum(times) / len(times)
                                    mechanic_averages[mech.id] = avg_time
                                    mechanic_names[mech.id] = mech.name
                                    _logger.info(f"Mechanic {mech.name}: avg time = {avg_time:.2f} hours, orders = {len(times)}")

                            # Di bagian perhitungan measurement, ganti format teks dengan HTML
                            if mechanic_averages:
                                # Hitung rata-rata keseluruhan dan toleransi tetap sama
                                team_average = sum(mechanic_averages.values()) / len(mechanic_averages)
                                upper_limit = team_average * 1.05
                                lower_limit = team_average * 0.95
                                
                                # Persiapkan data untuk tabel
                                in_range_rows = []
                                out_range_rows = []
                                
                                for mech_id, avg_time in mechanic_averages.items():
                                    row_data = {
                                        'name': mechanic_names[mech_id],
                                        'avg_time': avg_time,
                                        'status': 'within' if lower_limit <= avg_time <= upper_limit else 'outside'
                                    }
                                    if row_data['status'] == 'within':
                                        in_range_rows.append(row_data)
                                    else:
                                        out_range_rows.append(row_data)

                                mechanics_in_range = len(in_range_rows)
                                total_mechanics = len(mechanic_averages)
                                actual = (mechanics_in_range / total_mechanics * 100)
                                
                                # Format measurement sebagai HTML
                                measurement = f"""
                            <div class="kpi-measurement">
                                <div class="period-info">
                                    <strong>Periode:</strong> {month}/{year}
                                </div>
                                
                                <div class="summary-stats">
                                    <div class="stat-item">
                                        <span class="label">Rata-rata bengkel:</span>
                                        <span class="value">{team_average:.1f} jam</span>
                                    </div>
                                    <div class="stat-item">
                                        <span class="label">Rentang target:</span>
                                        <span class="value">{lower_limit:.1f} - {upper_limit:.1f} jam</span>
                                    </div>
                                </div>

                                <div class="mechanics-within-range">
                                    <h4>Dalam rentang ({mechanics_in_range}/{total_mechanics}):</h4>
                                    <div class="mechanics-list">
                                        {', '.join(f'<span class="mechanic within">{data["name"]}: {data["avg_time"]:.1f} jam ✓</span>' for data in in_range_rows)}
                                    </div>
                                </div>

                                <div class="mechanics-outside-range">
                                    <h4>Luar rentang ({total_mechanics - mechanics_in_range}/{total_mechanics}):</h4>
                                    <div class="mechanics-list">
                                        {', '.join(f'<span class="mechanic outside">{data["name"]}: {data["avg_time"]:.1f} jam ✗</span>' for data in out_range_rows)}
                                    </div>
                                </div>

                                <div class="data-table">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Mekanik</th>
                                                <th>Rata-rata Waktu (jam)</th>
                                                <th>Status</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {''.join(f"""
                                                <tr class="{data['status']}">
                                                    <td>{data['name']}</td>
                                                    <td>{data['avg_time']:.1f}</td>
                                                    <td>{{'✓' if data['status'] == 'within' else '✗'}}</td>
                                                </tr>
                                            """ for data in sorted(in_range_rows + out_range_rows, key=lambda x: x['name']))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            """
                            else:
                                measurement = f"""
                            <div class="kpi-measurement">
                                <div class="no-data-message">
                                    Belum ada data pengerjaan yang cukup pada periode {month}/{year}
                                </div>
                            </div>
                            """

                        kpi_scores.append({
                            'no': kpi['no'],
                            'name': kpi['name'],
                            'type': kpi['type'],
                            'weight': kpi['weight'],
                            'target': kpi['target'],
                            'measurement': measurement,
                            'actual': actual,
                            'achievement': actual,
                            'weighted_score': (actual * kpi['weight'] / 100),
                            'editable': ['weight', 'target']
                        })

                    elif kpi['type'] == 'stock_management':
                        # Manual input untuk stok management (bisa diotomatisasi jika ada data stok)
                        actual = kpi_values.get(kpi['type'], {}).get('actual', 0)
                        measurement = kpi_values.get(kpi['type'], {}).get('measurement', '') or "Menunggu input: Jumlah temuan stok part habis"

                    elif kpi['type'] == 'team_control':
                        # Get service advisors for team members
                        team_sa = request.env['pitcar.service.advisor'].sudo().search([
                            ('user_id', 'in', team_members.mapped('user_id').ids)
                        ])
                        
                        # Get all SOP samplings for the team's service advisors
                        sa_samplings = request.env['pitcar.sop.sampling'].sudo().search([
                            ('sale_order_id', 'in', all_orders.ids),
                            ('sop_id.is_sa', '=', True),  # Only SA-related SOPs
                            ('sa_id', 'in', team_sa.ids),  # Using service advisor IDs instead of user IDs
                            ('state', '=', 'done')  # Only count completed samplings
                        ])
                        
                        # Count total SA samplings and violations
                        total_samplings = len(sa_samplings)
                        sop_violations = len(sa_samplings.filtered(lambda s: s.result == 'fail'))
                        
                        # Calculate actual score
                        actual = ((total_samplings - sop_violations) / total_samplings * 100) if total_samplings else 0
                        
                        # Format measurement message
                        if total_samplings > 0:
                            measurement = f"Sampling SA sesuai SOP: {total_samplings - sop_violations} dari {total_samplings} sampling ({actual:.1f}%)"
                        else:
                            measurement = "Belum ada sampling SOP untuk tim SA pada periode ini"

                    elif kpi['type'] == 'team_discipline':
                        # Otomatis ambil data kedisiplinan tim dari sistem
                        team_attendances = request.env['hr.attendance'].sudo().search([
                            ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('employee_id', 'in', team_members.ids + [employee.id])
                        ])
                        late_count = sum(1 for att in team_attendances if att.is_late)
                        actual = ((len(team_attendances) - late_count) / len(team_attendances) * 100) if team_attendances else 0
                        measurement = f"Total kehadiran tim: {len(team_attendances)}, Terlambat: {late_count}, Tepat waktu: {len(team_attendances) - late_count}"

                    # achievement = (actual / kpi['target'] * 100) if kpi['target'] else 0
                    # weighted_score = achievement * (kpi['weight'] / 100) if kpi.get('include_in_calculation', True) else 0
                    # Perhitungan baru: weighted_score langsung dari actual × weight/100
                    weighted_score = actual * (kpi['weight'] / 100)
                    
                    # Set achievement sama dengan weighted_score untuk kompatibilitas frontend
                    achievement = weighted_score

                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': measurement,
                        'actual': actual,
                        'achievement': achievement,
                        'weighted_score': weighted_score,
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
                    if kpi['type'] == 'productivity':
                        monthly_target = service_advisor.monthly_target or 64000000
                        current_revenue = sum(orders.mapped('amount_total'))
                        
                        if monthly_target == 0:
                            actual = 0
                        else:
                            actual = (current_revenue / monthly_target * 100)
                            
                        formatted_revenue = "{:,.0f}".format(current_revenue)
                        formatted_target = "{:,.0f}".format(monthly_target)
                        kpi['measurement'] = f"Revenue: Rp {formatted_revenue} dari target Rp {formatted_target}/bulan"

                    elif kpi['type'] == 'service_efficiency':
                        # Ambil data efisiensi waktu dari sistem
                        orders_with_duration = orders.filtered(lambda o: o.duration_deviation is not False)
                        if orders_with_duration:
                            avg_deviation = abs(sum(orders_with_duration.mapped('duration_deviation'))) / len(orders_with_duration)
                            actual = max(0, 100 - avg_deviation)  # Convert deviation to efficiency
                            kpi['measurement'] = f"Rata-rata deviasi waktu: {avg_deviation:.1f}%, Efisiensi: {actual:.1f}%"
                        else:
                            actual = 0
                            kpi['measurement'] = "Belum ada data deviasi waktu pengerjaan"
                    
                    # elif kpi['type'] == 'follow_up_h3':
                    #     # Filter order yang memiliki next_follow_up_3_days dalam bulan KPI yang dipilih
                    #     follow_up_domain = [
                    #         ('next_follow_up_3_days', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                    #         ('next_follow_up_3_days', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                    #         ('state', 'in', ['sale', 'done'])  # Pastikan hanya order yang sudah selesai
                    #     ]

                    #     # Ambil semua order yang masuk dalam kriteria follow-up
                    #     due_follow_ups = request.env['sale.order'].sudo().search(follow_up_domain)

                    #     # Filter order yang sudah benar-benar melakukan follow-up dalam bulan tersebut
                    #     completed_follow_ups = due_follow_ups.filtered(lambda o: o.is_follow_up == 'yes')

                    #     # Menghitung persentase follow-up yang telah dilakukan
                    #     total_due = len(due_follow_ups)
                    #     actual = (len(completed_follow_ups) / total_due * 100) if total_due else 0

                    #     # Memformat output KPI agar lebih jelas
                    #     kpi['measurement'] = (
                    #         f"Follow up H+3: {len(completed_follow_ups)} dari {total_due} "
                    #         f"({actual:.1f}%) pada bulan {start_date_utc.strftime('%B %Y')}."
                    #     )

                    elif kpi['type'] == 'customer_satisfaction':
                        # Filter orders berdasarkan periode yang dipilih
                        period_orders = request.env['sale.order'].sudo().search([
                            ('date_completed', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('date_completed', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('state', 'in', ['sale', 'done']),
                            ('service_advisor_id', '=', service_advisor.id)  # Hanya order dari SA yang bersangkutan
                        ])
                        
                        # Ambil order yang memiliki rating dari periode yang dipilih
                        rated_orders = period_orders.filtered(lambda o: o.customer_rating)
                        total_rated_orders = len(rated_orders)
                        
                        if total_rated_orders > 0:
                            # Hitung rata-rata rating
                            total_rating = sum(float(order.customer_rating) for order in rated_orders)
                            avg_rating = total_rating / total_rated_orders
                            
                            # Implementasi formula khusus
                            if avg_rating > 4.8:
                                actual = 120
                            elif avg_rating == 4.8:
                                actual = 100
                            elif 4.6 <= avg_rating <= 4.7:
                                actual = 50
                            else:  # < 4.6
                                actual = 0
                                
                            kpi['measurement'] = (
                                f"Rating rata-rata: {avg_rating:.1f} dari {total_rated_orders} order "
                                f"pada periode {month}/{year}."
                            )
                        else:
                            actual = 0
                            kpi['measurement'] = f"Belum ada rating customer pada periode {month}/{year}"

                    elif kpi['type'] == 'complaint_handling':
                        # Data komplain
                        complaints = orders.filtered(lambda o: o.customer_rating in ['1', '2'])
                        resolved_complaints = complaints.filtered(lambda o: o.complaint_status == 'solved')
                        actual = (len(resolved_complaints) / len(complaints) * 100) if complaints else 100
                        kpi['measurement'] = f"Komplain terselesaikan: {len(resolved_complaints)} dari {len(complaints)}"

                    elif kpi['type'] == 'follow_up_h3':
                        # Dari data follow up H+3
                        due_follow_ups = orders.filtered(lambda o: o.next_follow_up_3_days)
                        completed_follow_ups = due_follow_ups.filtered(lambda o: o.reminder_sent == True)
                        actual = (len(completed_follow_ups) / len(due_follow_ups) * 100) if due_follow_ups else 0
                        kpi['measurement'] = f"Follow up H+3: {len(completed_follow_ups)} dari {len(due_follow_ups)} order pada periode {month}/{year}"

                    elif kpi['type'] == 'sop_compliance':
                        # Ambil samplings untuk SA dari periode yang dipilih
                        sa_samplings = request.env['pitcar.sop.sampling'].sudo().search([
                            ('date', '>=', start_date.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date.strftime('%Y-%m-%d')),
                            ('sop_id.is_sa', '=', True),  # Hanya SOP untuk SA
                            ('sa_id', 'in', [service_advisor.id]),  # Hanya untuk SA yang bersangkutan
                            ('state', '=', 'done')  # Hanya sampling yang sudah selesai
                        ])
                        
                        # Hitung total sampling dan pelanggaran
                        total_samplings = len(sa_samplings)
                        sop_violations = len(sa_samplings.filtered(lambda s: s.result == 'fail'))
                        
                        # Hitung actual score
                        actual = ((total_samplings - sop_violations) / total_samplings * 100) if total_samplings else 0
                        
                        # Format measurement message
                        if total_samplings > 0:
                            kpi['measurement'] = f"Sampling sesuai SOP: {total_samplings - sop_violations} dari {total_samplings} sampling ({actual:.1f}%)"
                        else:
                            kpi['measurement'] = f"Belum ada sampling SOP pada periode {month}/{year}"

                    elif kpi['type'] == 'discipline':
                        # Data kedisiplinan
                        attendances = request.env['hr.attendance'].sudo().search([
                            ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('employee_id', '=', employee.id)
                        ])
                        late_count = sum(1 for att in attendances if att.is_late)
                        actual = ((len(attendances) - late_count) / len(attendances) * 100) if attendances else 0
                        kpi['measurement'] = f"Total kehadiran: {len(attendances)}, Terlambat: {late_count}, Tepat waktu: {len(attendances) - late_count}"

                    # achievement = (actual / kpi['target'] * 100) if kpi['target'] else 0
                    # weighted_score = achievement * (kpi['weight'] / 100) if kpi.get('include_in_calculation', True) else 0
                    # Perhitungan baru: weighted_score langsung dari actual × weight/100
                    weighted_score = actual * (kpi['weight'] / 100)
                    
                    # Set achievement sama dengan weighted_score untuk kompatibilitas frontend
                    achievement = weighted_score

                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,
                        'weighted_score': weighted_score,
                        'editable': ['weight', 'target']
                    })

            # Handle Valet
            # Di bagian handle different roles, tambahkan kondisi untuk Valet:
            elif 'Valet Parking' in job_title:
                kpi_scores = []
                for kpi in valet_kpi_template:
                    actual = 0
                    if kpi['type'] == 'front_office':
                        # Get daily checks data
                        front_office_checks = request.env['pitcar.front.office.check'].sudo().search([
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('valet_id', '=', employee.id),
                            ('state', '=', 'done')
                        ])

                        total_checks = len(front_office_checks)
                        if total_checks > 0:
                            total_rate = sum(check.completeness_rate for check in front_office_checks)
                            actual = total_rate / total_checks
                            total_complete = sum(1 for check in front_office_checks if check.completeness_rate >= 100)
                            kpi['measurement'] = (
                                f"Pengecekan lengkap: {total_complete} dari {total_checks} kali pengecekan. "
                                f"Rata-rata kelengkapan: {actual:.1f}%"
                            )
                        else:
                            actual = 0
                            kpi['measurement'] = f"Belum ada pengecekan pada periode {month}/{year}"

                    elif kpi['type'] == 'valet_sop':
                        samplings = request.env['pitcar.sop.sampling'].sudo().search([
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('valet_id', 'in', [employee.id]),
                            ('state', '=', 'done')
                        ])
                        
                        total_samplings = len(samplings)
                        if total_samplings > 0:
                            passed_samplings = len(samplings.filtered(lambda s: s.result == 'pass'))
                            actual = (passed_samplings / total_samplings * 100)
                            kpi['measurement'] = f"Sampel sesuai SOP: {passed_samplings} dari {total_samplings} sampling"
                        else:
                            actual = 0
                            kpi['measurement'] = f"Belum ada sampling SOP pada periode {month}/{year}"
                            
                    elif kpi['type'] == 'customer_satisfaction':
                        period_orders = request.env['sale.order'].sudo().search([
                            ('date_completed', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('date_completed', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('state', 'in', ['sale', 'done'])
                        ])
                        
                        rated_orders = period_orders.filtered(lambda o: o.customer_rating)
                        total_rated_orders = len(rated_orders)
                        
                        if total_rated_orders > 0:
                            total_rating = sum(float(order.customer_rating) for order in rated_orders)
                            avg_rating = total_rating / total_rated_orders
                            
                            if avg_rating > 4.8:
                                actual = 120
                            elif avg_rating == 4.8:
                                actual = 100
                            elif 4.6 <= avg_rating <= 4.7:
                                actual = 50
                            else:
                                actual = 0
                                
                            kpi['measurement'] = (
                                f"Rating rata-rata: {avg_rating:.1f} dari {total_rated_orders} order "
                                f"pada periode {month}/{year}"
                            )
                        else:
                            actual = 0
                            kpi['measurement'] = f"Belum ada rating customer pada periode {month}/{year}"

                    # Perhitungan baru: weighted_score langsung dari actual × weight/100
                    weighted_score = actual * (kpi['weight'] / 100)
                    
                    # Set achievement sama dengan weighted_score untuk kompatibilitas frontend
                    achievement = weighted_score

                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,  # Sama dengan weighted_score
                        'weighted_score': weighted_score
                    })

            # Handle Admin Part
            elif 'Admin Part' in job_title:
                kpi_scores = []
                for kpi in admin_part_template:
                    actual = 0
                    if kpi['type'] == 'part_fulfillment':
                        part_items = request.env['sale.order.part.item'].sudo().search([
                            ('create_date', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('create_date', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S'))
                        ])
                        total_items = len(part_items)
                        fulfilled_items = len(part_items.filtered(lambda x: x.is_fulfilled))
                        actual = (fulfilled_items / total_items * 100) if total_items else 0
                        kpi['measurement'] = f'Total request: {total_items}, Terpenuhi: {fulfilled_items}'

                    elif kpi['type'] == 'part_response':
                        part_items = request.env['sale.order.part.item'].sudo().search([
                            ('create_date', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('create_date', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('response_time', '!=', False)
                        ])
                        total_responses = len(part_items)
                        on_time_responses = len(part_items.filtered(
                            lambda x: (x.response_time - x.create_date).total_seconds() / 60 <= 15
                        ))
                        actual = (on_time_responses / total_responses * 100) if total_responses else 0
                        kpi['measurement'] = f'Total response: {total_responses}, Tepat waktu: {on_time_responses}'

                    elif kpi['type'] == 'part_availability':
                        stockouts = request.env['stock.mandatory.stockout'].sudo().search([
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d'))
                        ])
                        total_days = (end_date - start_date).days + 1
                        stockout_days = len(set(stockouts.mapped('date')))
                        actual = ((total_days - stockout_days) / total_days * 100)
                        kpi['measurement'] = f'Hari tanpa stockout: {total_days - stockout_days} dari {total_days} hari'

                    elif kpi['type'] in ['part_audit', 'tools_audit']:
                        audit_type = 'part' if kpi['type'] == 'part_audit' else 'tool'
                        audit_entries = request.env['account.move'].sudo().search([
                            ('is_stock_audit', '=', True),
                            ('audit_type', '=', audit_type),
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('state', '=', 'posted')
                        ])
                        total_audits = len(audit_entries)
                        within_tolerance = len(audit_entries.filtered(
                            lambda x: abs(x.audit_difference) < 200000
                        ))
                        actual = (within_tolerance / total_audits * 100) if total_audits else 0
                        kpi['measurement'] = f'Audit dalam toleransi: {within_tolerance} dari {total_audits}'

                    elif kpi['type'] == 'sop_compliance':
                        samplings = request.env['pitcar.sop.sampling'].sudo().search([
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('sop_id.role', '=', 'admin_part'),
                            ('state', '=', 'done')
                        ])
                        total_samples = len(samplings)
                        passed_samples = len(samplings.filtered(lambda s: s.result == 'pass'))
                        actual = (passed_samples / total_samples * 100) if total_samples else 0
                        kpi['measurement'] = f'Sesuai SOP: {passed_samples} dari {total_samples} sampel'

                    # Perhitungan baru: weighted_score langsung dari actual × weight/100
                    weighted_score = actual * (kpi['weight'] / 100)
                    
                    # Set achievement sama dengan weighted_score untuk kompatibilitas frontend
                    achievement = weighted_score

                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,  # Sama dengan weighted_score
                        'weighted_score': weighted_score,
                        'editable': ['weight', 'target']
                    })
            
            # Handler untuk Toolkeeper
            elif 'Partman' in job_title:
                kpi_scores = []
                for kpi in toolkeeper_template:
                    actual = 0
                    if kpi['type'] == 'part_purchase':
                        purchases = request.env['part.purchase.leadtime'].sudo().search([
                            ('partman_id', '=', employee.id),
                            ('purchase_type', '=', 'part'),
                            ('state', '=', 'returned'),
                            ('return_time', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('return_time', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S'))
                        ])
                        total_purchases = len(purchases)
                        success_purchases = len(purchases.filtered(lambda p: p.actual_completeness >= 90))
                        actual = (success_purchases / total_purchases * 100) if total_purchases else 0
                        kpi['measurement'] = f"Belanja part sesuai: {success_purchases} dari {total_purchases} kali belanja"

                    elif kpi['type'] == 'tool_purchase':
                        tool_purchases = request.env['part.purchase.leadtime'].sudo().search([
                            ('partman_id', '=', employee.id),
                            ('purchase_type', '=', 'tool'),
                            ('state', '=', 'returned'),
                            ('return_time', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                            ('return_time', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S'))
                        ])
                        total_tools = len(tool_purchases)
                        success_tools = len(tool_purchases.filtered(lambda p: p.actual_completeness >= 90))
                        actual = (success_tools / total_tools * 100) if total_tools else 0
                        kpi['measurement'] = f"Belanja tools sesuai: {success_tools} dari {total_tools} kali belanja"

                    elif kpi['type'] in ['part_audit', 'tools_audit']:
                        audit_type = 'part' if kpi['type'] == 'part_audit' else 'tool'
                        audit_entries = request.env['account.move'].sudo().search([
                            ('is_stock_audit', '=', True),
                            ('audit_type', '=', audit_type),
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('state', '=', 'posted')
                        ])
                        total_audits = len(audit_entries)
                        within_tolerance = len(audit_entries.filtered(
                            lambda x: abs(x.audit_difference) < 200000
                        ))
                        actual = (within_tolerance / total_audits * 100) if total_audits else 0
                        kpi['measurement'] = f'Audit dalam toleransi: {within_tolerance} dari {total_audits}'

                    elif kpi['type'] == 'sop_compliance':
                        samplings = request.env['pitcar.sop.sampling'].sudo().search([
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('sop_id.role', '=', 'toolkeeper'),
                            ('state', '=', 'done')
                        ])
                        total_samples = len(samplings)
                        passed_samples = len(samplings.filtered(lambda s: s.result == 'pass'))
                        actual = (passed_samples / total_samples * 100) if total_samples else 0
                        kpi['measurement'] = f'Sesuai SOP: {passed_samples} dari {total_samples} sampel'

                    # Perhitungan baru: weighted_score langsung dari actual × weight/100
                    weighted_score = actual * (kpi['weight'] / 100)
                    
                    # Set achievement sama dengan weighted_score untuk kompatibilitas frontend
                    achievement = weighted_score

                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,  # Sama dengan weighted_score
                        'weighted_score': weighted_score,
                        'editable': ['weight', 'target']
                    })

                # Calculate total score
                total_weight = sum(kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
                total_score = sum(kpi['weighted_score'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
                avg_target = sum(kpi['target'] * kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True)) / total_weight if total_weight else 0

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

            # Get orders for the mechanic
            orders = request.env['sale.order'].sudo().search([
                *base_domain,
                ('car_mechanic_id_new', 'in', [mechanic.id])
            ])

            kpi_scores = []

            # Definisi KPI template sesuai posisi
            mechanic_kpi_template = [
                {
                    'no': 1,
                    'name': 'Jumlah flat rate sesuai target',
                    'type': 'flat_rate',
                    'weight': 30,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah omset yang dihasilkan dari PKB yang ditangani'
                },
                {
                    'no': 2,
                    'name': 'Jumlah PKB yang diberikan rekomendasi tambahan servis',
                    'type': 'service_recommendation',
                    'weight': 20,
                    'target': 80,
                    'measurement': 'Diukur dari persentase rekomendasi yang diberikan',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Persentase customer puas dari hasil pengerjaan / tidak komplain karena mis-analisa atau mis-pengerjaan',
                    'type': 'service_quality',
                    'weight': 30,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah customer yang puas dari hasil pengerjaan (tidak komplain)'
                },
                {
                    'no': 4,
                    'name': 'Persentase sampel tim mekanik bekerja sesuai alur SOP',
                    'type': 'sop_compliance',
                    'weight': 15,
                    'target': 95,
                    'measurement': 'Diukur dari jumlah temuan pekerjaan sesuai SOP',
                    'include_in_calculation': True
                },
                {
                    'no': 5,  # Tambahkan sebagai KPI terakhir
                    'name': 'Kedisiplinan (Informasi)',
                    'type': 'discipline',
                    'weight': 0,  # Weight 0 karena tidak dihitung
                    'target': 0,
                    'measurement': 'Diukur dari jumlah keterlambatan dan ketidakhadiran',
                    'include_in_calculation': False  # Set False untuk tidak masuk perhitungan
                }
            ]

            leader_kpi_template = [
                {
                    'no': 1,
                    'name': 'Jumlah flat rate sesuai target',
                    'type': 'flat_rate',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Diukur dari jumlah PKB yang berhasil dikerjakan',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': 'Persentase waktu pengerjaan mekanik yang sesuai waktu rata-rata pengerjaan seluruh mekanik',
                    'type': 'mechanic_efficiency',
                    'weight': 20,
                    'target': 80,
                    'measurement': 'Diukur dari kesesuaian waktu pengerjaan berdasarkan target waktu',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Jumlah PKB yang diberikan rekomendasi tambahan servis',
                    'type': 'service_recommendation',
                    'weight': 15,
                    'target': 80,
                    'measurement': 'Diukur dari jumlah PKB yang diberikan rekomendasi tambahan servis',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Persentase customer puas dari hasil pengerjaan / tidak komplain karena mis-analisa atau mis-pengerjaan',
                    'type': 'service_quality',
                    'weight': 15,
                    'target': 80,
                    'measurement': 'Diukur dari jumlah customer yang puas dari hasil pengerjaan (tidak komplain)',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': 'Jumlah customer merasa puas terhadap pelayanan & solusi diberikan maksimal 3 hari setelah komplain dilayangkan',
                    'type': 'complaint_handling',
                    'weight': 15,
                    'target': 90,
                    'measurement': 'Diukur dari jumlah customer yang puas dari hasil pengerjaan (tidak komplain)',
                    'include_in_calculation': True
                },
                {
                    'no': 6,
                    'name': 'Analisis dan penyelesaian komplain dari customer',
                    'type': 'complaint_handling',
                    'weight': 15,
                    'target': 100,
                    'measurement': 'Diukur dari customer merasa puas terhadap pelayanan & solusi yang diberikan dalam kurun waktu 3 hari setelah complaint dilayangkan',
                    'include_in_calculation': True
                },
                # {
                #     'no': 7,
                #     'name': 'Kontrol kinerja tim mekanik',
                #     'type': 'sop_compliance',
                #     'weight': 15,
                #     'target': 95,
                #     'measurement': 'Diukur dari jumlah temuan pekerjaan tim mekanik yang dilakukan tidak sesuai dengan alur / SOP yang ditetapkan',
                #     'include_in_calculation': True
                # },
                {
                    'no': 7,
                    'name': 'Menjalankan kegiatan operasional secara disiplin',
                    'type': 'team_discipline',
                    'weight': 0,
                    'target': 0,
                    'measurement': 'Diukur dari jumlah keterlambatan dan ketidakhadiran',
                    'include_in_calculation': False
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
                        else:
                            revenue = total_revenue
                            actual = (revenue / monthly_target * 100)  # Actual jadi persentase
                        
                        formatted_revenue = "{:,.0f}".format(total_revenue)
                        formatted_target = "{:,.0f}".format(monthly_target)
                        kpi['measurement'] = f"Revenue: Rp {formatted_revenue} dari target Rp {formatted_target}/bulan"

                    elif kpi['type'] == 'flat_rate':
                        # Hitung productive hours dari absensi
                        attendances = request.env['hr.attendance'].sudo().search([
                            ('employee_id', '=', employee.id),
                            ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
                        ])
                        
                        productive_hours = 0
                        for attendance in attendances:
                            if attendance.check_out:
                                worked_hours = (attendance.check_out - attendance.check_in).total_seconds() / 3600
                                # Kurangi waktu istirahat (1 jam) jika bekerja lebih dari 6 jam
                                if worked_hours > 6:
                                    worked_hours -= 1
                                productive_hours += worked_hours

                        # Hitung jam terjual dari order yang selesai
                        completed_orders = orders.filtered(lambda o: o.controller_selesai)
                        sold_hours = sum(order.lead_time_servis for order in completed_orders)
                        
                        # Hitung flat rate (dalam persentase)
                        actual = (sold_hours / productive_hours * 100) if productive_hours > 0 else 0
                        
                        formatted_sold = f"{sold_hours:.1f}"
                        formatted_productive = f"{productive_hours:.1f}"
                        kpi['measurement'] = f"Jam terjual: {formatted_sold} jam dari {formatted_productive} jam produktif"

                    elif kpi['type'] == 'service_efficiency':
                        orders_with_duration = orders.filtered(lambda o: o.duration_deviation is not False)
                        if orders_with_duration:
                            avg_deviation = abs(sum(orders_with_duration.mapped('duration_deviation'))) / len(orders_with_duration)
                            actual = max(0, 100 - avg_deviation)  # Convert deviation to efficiency
                            kpi['measurement'] = f"Rata-rata deviasi waktu: {avg_deviation:.1f}%, Efisiensi: {actual:.1f}%"
                        else:
                            actual = 0
                            kpi['measurement'] = "Belum ada data deviasi waktu pengerjaan"
                        
                    elif kpi['type'] == 'service_recommendation':
                        if orders:
                            total_orders = len(orders)
                            orders_with_recs = len(orders.filtered(lambda o: o.total_recommendations > 0))
                            avg_realization = sum(orders.mapped('recommendation_realization_rate')) / total_orders if total_orders else 0
                            
                            kpi['measurement'] = (
                                f"Orders dengan rekomendasi: {orders_with_recs}/{total_orders}, "
                                f"Rata-rata realisasi: {avg_realization:.1f}%"
                            )
                            actual = avg_realization
                        
                    elif kpi['type'] == 'sop_compliance':
                        mechanic_samplings = request.env['pitcar.sop.sampling'].sudo().search([
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('mechanic_id', 'in', [mechanic.id]),
                            ('sop_id.role', '=', 'mechanic'),
                            ('state', '=', 'done')
                        ])
                        
                        total_samplings = len(mechanic_samplings)
                        failed_samplings = len(mechanic_samplings.filtered(lambda s: s.result == 'fail'))
                        
                        if total_samplings > 0:
                            actual = ((total_samplings - failed_samplings) / total_samplings * 100)
                            kpi['measurement'] = f"Sampling sesuai SOP: {total_samplings - failed_samplings} dari {total_samplings} sampling ({actual:.1f}%)"
                        else:
                            actual = 0
                            kpi['measurement'] = f"Belum ada sampling SOP pada periode {month}/{year}"
                        
                    elif kpi['type'] == 'discipline':
                        attendances = request.env['hr.attendance'].sudo().search([
                            ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('employee_id', '=', employee.id)
                        ])
                        late_count = sum(1 for att in attendances if att.is_late)
                        actual = ((len(attendances) - late_count) / len(attendances) * 100) if attendances else 0
                        kpi['measurement'] = f"Total kehadiran: {len(attendances)}, Terlambat: {late_count}, Tepat waktu: {len(attendances) - late_count}"

                    # Perhitungan baru: weighted_score langsung dari actual × weight/100
                    weighted_score = actual * (kpi['weight'] / 100)
                    
                    # Set achievement sama dengan weighted_score untuk kompatibilitas frontend
                    achievement = weighted_score
                    
                    kpi_scores.append({
                        'no': kpi['no'],
                        'name': kpi['name'],
                        'type': kpi['type'],
                        'weight': kpi['weight'],
                        'target': kpi['target'],
                        'measurement': kpi['measurement'],
                        'actual': actual,
                        'achievement': achievement,  # Sama dengan weighted_score
                        'weighted_score': weighted_score
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
                team_target = (len(team_members)) * 64000000  # +1 untuk leader
                
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

                    if kpi['type'] == 'productivity':
                        total_units = len(team_orders)
                        target_units = 145  # Target PKB per bulan
                        actual = (total_units / target_units * 100) if target_units else 0
                        kpi['measurement'] = f"Berhasil handle {total_units} PKB dari target {target_units} PKB/bulan"
                    
                    elif kpi['type'] == 'flat_rate':
                        # Hitung jam terjual dari order yang selesai
                        completed_orders = team_orders.filtered(lambda o: o.controller_selesai)  # Gunakan team_orders bukan orders
                        sold_hours = sum(order.lead_time_servis for order in completed_orders)
                        # Get orders for the mechanic team first
                        team_orders = request.env['sale.order'].sudo().search([
                            *base_domain,
                            ('car_mechanic_id_new', 'in', team_members.ids + [mechanic.id])  # Include leader
                        ])

                        # Hitung productive hours dari absensi
                        attendances = request.env['hr.attendance'].sudo().search([
                            ('employee_id', '=', employee.id),
                            ('check_in', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                            ('check_in', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
                        ])
                        
                        productive_hours = 0
                        for attendance in attendances:
                            if attendance.check_out:
                                worked_hours = (attendance.check_out - attendance.check_in).total_seconds() / 3600
                                # Kurangi waktu istirahat (1 jam) jika bekerja lebih dari 6 jam
                                if worked_hours > 6:
                                    worked_hours -= 1
                                productive_hours += worked_hours

                        # Hitung jam terjual dari order yang selesai
                        completed_orders = orders.filtered(lambda o: o.controller_selesai)
                        sold_hours = sum(order.lead_time_servis for order in completed_orders)
                        
                        # Hitung flat rate (dalam persentase)
                        actual = (sold_hours / productive_hours * 100) if productive_hours > 0 else 0
                        
                        formatted_sold = f"{sold_hours:.1f}"
                        formatted_productive = f"{productive_hours:.1f}"
                        kpi['measurement'] = f"Jam terjual: {formatted_sold} jam dari {formatted_productive} jam produktif"

                    # Perbaikan perhitungan mechanic efficiency
                    elif kpi['type'] == 'mechanic_efficiency':
                        # Debug log
                        _logger.info(f"Calculating mechanic efficiency for team members: {team_members.ids}")
                        
                        # Get orders untuk tim
                        team_orders = request.env['sale.order'].sudo().search([
                            *base_domain,
                            ('car_mechanic_id_new', 'in', team_members.ids)
                        ])
                        
                        _logger.info(f"Found {len(team_orders)} orders for team")

                        # Hitung rata-rata waktu pengerjaan per mekanik
                        mechanic_times = {}
                        for order in team_orders:
                            # Pastikan order memiliki waktu mulai dan selesai
                            if order.controller_mulai_servis and order.controller_selesai:
                                # Hitung waktu pengerjaan bersih (lead_time_servis)
                                for mech in order.car_mechanic_id_new:
                                    if mech not in mechanic_times:
                                        mechanic_times[mech] = []
                                    if order.lead_time_servis:  # Pastikan ada lead time
                                        mechanic_times[mech].append(order.lead_time_servis)
                                        
                        _logger.info(f"Mechanic times collected: {mechanic_times}")

                        # Hitung rata-rata untuk setiap mekanik
                        mechanic_averages = {}
                        mechanic_names = {}  # Untuk menyimpan nama mekanik
                        for mech, times in mechanic_times.items():
                            if times:  # Pastikan ada data waktu
                                avg_time = sum(times) / len(times)
                                mechanic_averages[mech.id] = avg_time
                                mechanic_names[mech.id] = mech.name
                                _logger.info(f"Mechanic {mech.name}: avg time = {avg_time:.2f} hours")

                        if mechanic_averages:
                            # Hitung rata-rata tim
                            team_average = sum(mechanic_averages.values()) / len(mechanic_averages)
                            
                            # Hitung batas toleransi (±5%)
                            upper_limit = team_average * 1.05
                            lower_limit = team_average * 0.95
                            
                            # Hitung mekanik dalam dan luar rentang
                            in_range_mechanics = []
                            out_range_mechanics = []
                            
                            for mech_id, avg_time in mechanic_averages.items():
                                if lower_limit <= avg_time <= upper_limit:
                                    in_range_mechanics.append(f"{mechanic_names[mech_id]}: {avg_time:.1f} jam ✓")
                                else:
                                    out_range_mechanics.append(f"{mechanic_names[mech_id]}: {avg_time:.1f} jam ✗")
                            
                            # Hitung persentase dalam rentang
                            mechanics_in_range = len(in_range_mechanics)
                            total_mechanics = len(mechanic_averages)
                            actual = (mechanics_in_range / total_mechanics * 100)
                            
                            # Detailed measurement message
                            measurement = (
                                f"Rata-rata tim: {team_average:.1f} jam\n"
                                f"Rentang target: {lower_limit:.1f} - {upper_limit:.1f} jam\n"
                                f"Dalam rentang ({mechanics_in_range}/{total_mechanics}): {', '.join(in_range_mechanics)}\n"
                                f"Luar rentang ({total_mechanics - mechanics_in_range}/{total_mechanics}): {', '.join(out_range_mechanics)}"
                            )
                            
                            _logger.info(f"""
                                KPI Calculation Results:
                                - Team Average: {team_average:.1f} hours
                                - Tolerance Range: {lower_limit:.1f} - {upper_limit:.1f} hours
                                - Mechanics in range: {mechanics_in_range}/{total_mechanics}
                                - Actual score: {actual:.1f}%
                            """)
                        else:
                            _logger.warning("No valid mechanic averages found. Checking conditions:")
                            _logger.warning(f"- Team orders found: {len(team_orders)}")
                            _logger.warning(f"- Mechanics with times: {len(mechanic_times)}")
                            _logger.warning(f"- Orders with lead times: {len([o for o in team_orders if o.lead_time_servis])}")
                            
                            actual = 0
                            measurement = "Belum ada data pengerjaan mekanik yang cukup"

                        kpi_scores.append({
                            'no': kpi['no'],
                            'name': kpi['name'],
                            'type': kpi['type'],
                            'weight': kpi['weight'],
                            'target': kpi['target'],
                            'measurement': measurement,
                            'actual': actual,
                            'achievement': actual,  # Langsung gunakan actual sebagai achievement
                            'weighted_score': (actual * kpi['weight'] / 100),
                            'editable': ['weight', 'target']
                        })
                        
                    elif kpi['type'] == 'service_efficiency':
                        # Hitung rata-rata deviasi waktu servis tim
                        orders_with_duration = team_orders.filtered(lambda o: o.duration_deviation is not False)
                        if orders_with_duration:
                            avg_deviation = abs(sum(orders_with_duration.mapped('duration_deviation'))) / len(orders_with_duration)
                            actual = max(0, 100 - avg_deviation)  # Convert deviation to efficiency
                            kpi['measurement'] = f"Rata-rata deviasi waktu: {avg_deviation:.1f}%, Efisiensi: {actual:.1f}%"
                    # elif kpi['type'] == 'work_distribution':
                    #     target_units = 145  # Sesuai target yang ditetapkan
                    #     actual = (total_units / target_units * 100) if target_units else 0
                    #     kpi['measurement'] = f"Berhasil handle {total_units} unit dari target {target_units} unit/bulan"
                    elif kpi['type'] == 'work_distribution':
                        # Hitung distribusi pekerjaan berdasarkan waktu per PKB
                        mechanic_workloads = {}
                        for order in team_orders:
                            for mech in order.car_mechanic_id_new:
                                if mech not in mechanic_workloads:
                                    mechanic_workloads[mech] = []
                                if order.lead_time_servis:
                                    mechanic_workloads[mech].append(order.lead_time_servis)
                        
                        # Hitung rata-rata waktu per mekanik
                        avg_times = []
                        for workload in mechanic_workloads.values():
                            if workload:
                                avg_times.append(sum(workload) / len(workload))
                        
                        if avg_times:
                            variance = max(avg_times) - min(avg_times)  # Variance antar mekanik
                            actual = max(0, 100 - (variance * 10))  # Convert variance to score
                            kpi['measurement'] = f"Variance waktu antar mekanik: {variance:.1f} jam"
    
                    elif kpi['type'] == 'service_quality':
                        actual = (satisfied_customers / total_units * 100) if total_units else 0
                        kpi['measurement'] = f"Total order: {total_units}, Customer puas: {satisfied_customers}, Komplain: {complaints}"
                        
                    elif kpi['type'] == 'complaint_handling':
                        complaints = team_orders.filtered(lambda o: o.customer_rating in ['1', '2'])
                        total_complaints = len(complaints)
                        resolved_complaints = len(complaints.filtered(lambda o: o.complaint_status == 'solved'))
                        actual = (resolved_complaints / total_complaints * 100) if total_complaints else 100
                        kpi['measurement'] = f"Komplain terselesaikan: {resolved_complaints} dari {total_complaints} komplain"

                    
                    elif kpi['type'] == 'service_recommendation':
                        total_orders = len(team_orders)
                        orders_with_recs = len(team_orders.filtered(lambda o: o.recommendation_ids))
                        actual = (orders_with_recs / total_orders * 100) if total_orders else 0
                        kpi['measurement'] = f"PKB dengan rekomendasi: {orders_with_recs} dari {total_orders} PKB"

                    elif kpi['type'] == 'team_recommendation':
                        filtered_orders = team_orders.filtered(lambda o: o.car_mechanic_id_new in team_members)
                        total_team_orders = len(filtered_orders)
                        team_orders_with_recs = len(filtered_orders.filtered(lambda o: o.recommendation_ids))
                        # team_orders_with_recs = len(team_orders.filtered(lambda o: o.recommendation_ids))
                        actual = (team_orders_with_recs / total_team_orders * 100) if total_team_orders else 0
                        kpi['measurement'] = f"Orders tim dengan rekomendasi: {team_orders_with_recs} dari {total_team_orders}"
                        
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
                        # Get SOP samplings for all team members
                        team_samplings = request.env['pitcar.sop.sampling'].sudo().search([
                            ('date', '>=', start_date_utc.strftime('%Y-%m-%d')),
                            ('date', '<=', end_date_utc.strftime('%Y-%m-%d')),
                            ('mechanic_id', 'in', team_members.ids),
                            ('sop_id.role', '=', 'mechanic'),
                            ('state', '=', 'done')
                        ])
                        
                        total_samplings = len(team_samplings)
                        failed_samplings = len(team_samplings.filtered(lambda s: s.result == 'fail'))
                        
                        if total_samplings > 0:
                            actual = ((total_samplings - failed_samplings) / total_samplings * 100)
                            kpi['measurement'] = (
                                f"Total sampling tim: {total_samplings}, "
                                f"Sesuai SOP: {total_samplings - failed_samplings}, "
                                f"Pelanggaran: {failed_samplings} ({actual:.1f}%)"
                            )
                        else:
                            actual = 0
                            kpi['measurement'] = f"Belum ada sampling SOP tim pada periode {month}/{year}"

                        
                    elif kpi['type'] == 'team_discipline':
                        actual = ((len(team_attendances) - late_count) / len(team_attendances) * 100) if team_attendances else 0
                        kpi['measurement'] = f"Total kehadiran tim: {len(team_attendances)}, Terlambat: {late_count}, Tepat waktu: {len(team_attendances) - late_count}"

                    achievement = (actual / kpi['target'] * 100) if kpi['target'] else 0
                    weighted_score = achievement * (kpi['weight'] / 100)
                    
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


            # Calculate total score
            # total_weight = sum(kpi['weight'] for kpi in kpi_scores)
            # total_score = sum(kpi['weighted_score'] for kpi in kpi_scores)
            # if total_weight != 100:
            #     _logger.warning(f"Total weight ({total_weight}) is not 100%")
            # avg_target = sum(kpi['target'] * kpi['weight'] for kpi in kpi_scores) / total_weight if total_weight else 0
            # Di bagian perhitungan total score untuk Team Leader
            total_weight = sum(kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            total_score = sum(kpi['weighted_score'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            avg_target = sum(kpi['target'] * kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True)) / total_weight if total_weight else 0

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
