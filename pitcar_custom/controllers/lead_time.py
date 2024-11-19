from odoo import http, fields
from odoo.http import request, Response
import pytz
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError
import json
import math
import logging
from odoo.osv import expression  # Menambahkan import expression

_logger = logging.getLogger(__name__)

class LeadTimeAPIController(http.Controller):
    def _validate_access(self, sale_order_id):
        """Validate user access and return sale order"""
        env = request.env
        sale_order = env['sale.order'].browse(sale_order_id)
        if not sale_order.exists():
            return None
        return sale_order

    def _format_time(self, dt):
        """Format time to HH:MM format"""
        if not dt:
            return None
        tz = pytz.timezone('Asia/Jakarta')
        local_dt = pytz.utc.localize(dt).astimezone(tz)
        return local_dt.strftime('%H:%M')

    def _format_datetime(self, dt):
        """Format datetime to full date time format"""
        if not dt:
            return None
        tz = pytz.timezone('Asia/Jakarta')
        local_dt = pytz.utc.localize(dt).astimezone(tz)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')

    def _parse_time(self, time_str):
        """Parse time string to UTC datetime"""
        try:
            tz = pytz.timezone('Asia/Jakarta')
            today = datetime.now(tz).date()
            local_dt = tz.localize(datetime.combine(today, datetime.strptime(time_str, '%H:%M').time()))
            return local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
        except ValueError:
            raise ValidationError("Invalid time format. Please use HH:MM format")

    def _convert_to_local_time(self, utc_dt):
        """Convert UTC datetime to Asia/Jakarta time"""
        if not utc_dt:
            return None
        tz = pytz.timezone('Asia/Jakarta')
        if not utc_dt.tzinfo:
            utc_dt = pytz.utc.localize(utc_dt)
        return utc_dt.astimezone(tz)

    def _format_local_datetime(self, dt):
        """Format datetime to Asia/Jakarta timezone string"""
        if not dt:
            return None
        local_dt = self._convert_to_local_time(dt)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S WIB')

    def _format_local_time(self, dt):
        """Format time to Asia/Jakarta timezone HH:MM string"""
        if not dt:
            return None
        local_dt = self._convert_to_local_time(dt)
        return local_dt.strftime('%H:%M')
    
    def format_timestamp(dt):
            """Format datetime to simple timestamp string in Jakarta timezone"""
            if not dt:
                return None
            tz = pytz.timezone('Asia/Jakarta')
            if not dt.tzinfo:
                dt = pytz.UTC.localize(dt)
            local_dt = dt.astimezone(tz)
            return local_dt.strftime('%Y-%m-%d %H:%M:%S')

    def _get_order_status(self, order):
        """Get current status including job stops"""
        if order.controller_selesai:
            return {'code': 'selesai', 'text': 'Selesai', 'color': 'gray'}
        elif order.controller_tunggu_part1_mulai and not order.controller_tunggu_part1_selesai:
            return {'code': 'tunggu_part', 'text': 'Menunggu Part', 'color': 'yellow'}
        elif order.controller_tunggu_konfirmasi_mulai and not order.controller_tunggu_konfirmasi_selesai:
            return {'code': 'tunggu_konfirmasi', 'text': 'Tunggu Konfirmasi', 'color': 'orange'}
        elif order.controller_istirahat_shift1_mulai and not order.controller_istirahat_shift1_selesai:
            return {'code': 'istirahat', 'text': 'Istirahat', 'color': 'blue'}
        elif order.controller_mulai_servis:
            return {'code': 'proses', 'text': 'Proses', 'color': 'green'}
        else:
            return {'code': 'belum_mulai', 'text': 'Belum Mulai', 'color': 'gray'}
    def _get_car_details(self, car):
        """Get formatted car details"""
        if not car:
            return {}
        return {
            'id': car.id,
            'brand': car.brand.name if car.brand else None,
            'brand_type': car.brand_type.name if car.brand_type else None,
            'year': car.year,
            'number_plate': car.number_plate,  # Menggunakan number_plate sebagai field yang benar
            'transmission': car.transmission.name if car.transmission else None,
            'engine_type': car.engine_type,
            'engine_number': car.engine_number,
            'frame_number': car.frame_number,
            'color': car.color
        }

    def _get_order_details(self, order):
        """Get detailed order information"""
        return {
            'order_info': {
                'id': order.id,
                'name': order.name,
                'state': order.state,
                'reception_state': order.reception_state,
                'car': self._get_car_details(order.partner_car_id),
                'customer': {
                    'id': order.partner_id.id if order.partner_id else None,
                    'name': order.partner_id.name if order.partner_id else None
                },
                'odometer': order.partner_car_odometer,
                'service_advisor': [{
                    'id': advisor.id,
                    'name': advisor.name
                } for advisor in order.service_advisor_id],
                'mechanic_team': order.generated_mechanic_team
            },
            'status': self._get_order_status(order),
            'timestamps': {
                'servis': {
                    'mulai': self._format_local_time(order.controller_mulai_servis),
                    'selesai': self._format_local_time(order.controller_selesai)
                },
                'tunggu_part': {
                    'mulai': self._format_local_time(order.controller_tunggu_part1_mulai),
                    'selesai': self._format_local_time(order.controller_tunggu_part1_selesai)
                },
                'tunggu_konfirmasi': {
                    'mulai': self._format_local_time(order.controller_tunggu_konfirmasi_mulai),
                    'selesai': self._format_local_time(order.controller_tunggu_konfirmasi_selesai)
                },
                'istirahat': {
                    'mulai': self._format_local_time(order.controller_istirahat_shift1_mulai),
                    'selesai': self._format_local_time(order.controller_istirahat_shift1_selesai)
                }
            },
            'lead_times': {
                'servis': order.lead_time_servis,
                'tunggu_part': order.lead_time_tunggu_part1,
                'tunggu_konfirmasi': order.lead_time_tunggu_konfirmasi,
                'istirahat': order.lead_time_istirahat,
                'total': order.total_lead_time_servis,
                'progress': order.lead_time_progress,
                'stage': order.lead_time_stage
            },
            'notes': order.lead_time_catatan,
            'completion': {
                'date_completed': self._format_local_datetime(order.date_completed)
            }
        }
    
    def _get_active_domain(self):
        """Get base domain for active service orders"""
        return [
            ('sa_cetak_pkb', '!=', False),  # Hanya filter PKB saja sebagai base domain
        ]

    def _validate_pagination_params(self, page, limit):
        """Validate and normalize pagination parameters"""
        try:
            page = int(page)
            if page < 1:
                page = 1
                
            limit = int(limit)
            if limit not in [10, 20, 30, 50]:
                limit = 20
                
            return page, limit
        except (ValueError, TypeError):
            return 1, 20

    @http.route('/web/lead-time/table', type='json', auth='user', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def get_table_data(self, **kw):
        try:
            # Handle OPTIONS request for CORS
            if request.httprequest.method == 'OPTIONS':
                headers = {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                    'Access-Control-Allow-Credentials': 'true'
                }
                return Response(status=200, headers=headers)

            # Extract parameters langsung dari kw (untuk JSON-RPC)
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 20))
            filter_type = kw.get('filter', 'all')
            search_query = kw.get('search_query', '').strip()
            sort_by = kw.get('sort_by', 'id')
            sort_order = kw.get('sort_order', 'desc')

            # Log parameters yang diterima
            _logger.info(f"Received parameters: {kw}")

            # Get base domain
            domain = self._get_active_domain()
            
            # Add filter conditions
            today = fields.Date.today()
            if filter_type and filter_type != 'all':
                if filter_type == 'delay':
                    # Ganti logika delay sesuai kebutuhan
                    # Misalnya: orders yang melewati estimasi selesai
                    domain.extend([
                        ('controller_estimasi_selesai', '!=', False),
                        ('controller_selesai', '=', False),
                        ('controller_estimasi_selesai', '<', fields.Datetime.now())
                    ])
                elif filter_type == 'proses':
                    domain.extend([
                        ('controller_mulai_servis', '!=', False),
                        ('controller_selesai', '=', False)
                    ])
                elif filter_type == 'tunggu_part':
                    domain.extend([
                        ('controller_tunggu_part1_mulai', '!=', False),
                        ('controller_tunggu_part1_selesai', '=', False)
                    ])
                elif filter_type == 'tunggu_konfirmasi':
                    domain.extend([
                        ('controller_tunggu_konfirmasi_mulai', '!=', False),
                        ('controller_tunggu_konfirmasi_selesai', '=', False)
                    ])
                elif filter_type == 'istirahat':
                    domain.extend([
                        ('controller_istirahat_shift1_mulai', '!=', False),
                        ('controller_istirahat_shift1_selesai', '=', False)
                    ])
                elif filter_type == 'selesai':
                    domain.extend([
                        ('controller_selesai', '!=', False),
                        ('controller_selesai', '>=', today),
                        ('controller_selesai', '<', today + timedelta(days=1))
                    ])

            # Add search conditions
            if search_query:
                search_domain = ['|', '|', '|', '|', '|',
                    ('partner_car_id.number_plate', 'ilike', search_query),
                    ('partner_car_brand.name', 'ilike', search_query),
                    ('partner_car_brand_type.name', 'ilike', search_query),
                    ('generated_mechanic_team', 'ilike', search_query),
                    ('service_advisor_id.name', 'ilike', search_query),
                    ('lead_time_catatan', 'ilike', search_query)
                ]
                domain.extend(search_domain)

            # Debug log
            _logger.info(f"Applied domain: {domain}")
            
            # Get records count and calculate pagination
            SaleOrder = request.env['sale.order']
            
            # Validate pagination
            page, limit = self._validate_pagination_params(page, limit)
            
            # Get total count
            total_count = SaleOrder.search_count(domain)
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            
            # Calculate offset
            offset = (page - 1) * limit

            # Prepare sorting
            order_mapping = {
                'id': 'id',
                'date': 'create_date',
                'customer': 'partner_id',
                'status': 'lead_time_stage',
                'plat': 'partner_car_id.number_plate',
                'brand': 'partner_car_brand.name',
                'estimasi': 'controller_estimasi_selesai',
                'progress': 'lead_time_progress'
            }
            sort_field = order_mapping.get(sort_by, 'id')
            order = f'{sort_field} {sort_order}, id DESC'

            # Get paginated records
            orders = SaleOrder.search(domain, limit=limit, offset=offset, order=order)
            _logger.info(f"Found {len(orders)} records")

            # Prepare response
            tz = pytz.timezone('Asia/Jakarta')
            current_time = datetime.now(tz)

            # Update fungsi untuk mendapatkan status yang benar
            def get_order_status(order):
                """Get proper order status based on service state"""
                if order.controller_selesai:
                    return {
                        'code': 'completed',
                        'text': 'Selesai'
                    }
                elif order.controller_mulai_servis:
                    # Cek job stops yang aktif
                    if order.controller_tunggu_part1_mulai and not order.controller_tunggu_part1_selesai:
                        return {
                            'code': 'tunggu_part',
                            'text': 'Menunggu Part'
                        }
                    elif order.controller_tunggu_konfirmasi_mulai and not order.controller_tunggu_konfirmasi_selesai:
                        return {
                            'code': 'tunggu_konfirmasi',
                            'text': 'Tunggu Konfirmasi'
                        }
                    elif order.controller_istirahat_shift1_mulai and not order.controller_istirahat_shift1_selesai:
                        return {
                            'code': 'istirahat',
                            'text': 'Istirahat'
                        }
                    elif order.controller_tunggu_sublet_mulai and not order.controller_tunggu_sublet_selesai:
                        return {
                            'code': 'tunggu_sublet',
                            'text': 'Tunggu Sublet'
                        }
                    elif order.controller_job_stop_lain_mulai and not order.controller_job_stop_lain_selesai:
                        return {
                            'code': 'job_stop_lain',
                            'text': 'Job Stop Lain'
                        }
                    else:
                        return {
                            'code': 'in_progress',
                            'text': 'Sedang Dikerjakan'
                        }
                else:
                    return {
                        'code': 'not_started',
                        'text': 'Belum Dimulai'
                    }
                
            def format_timestamp(dt):
                """Format datetime to simple timestamp string in Jakarta timezone"""
                if not dt:
                    return None
                tz = pytz.timezone('Asia/Jakarta')
                if not dt.tzinfo:
                    dt = pytz.UTC.localize(dt)
                local_dt = dt.astimezone(tz)
                return local_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            rows = []
            start_number = offset + 1
            for order in orders:            
                # Get proper status
                status = get_order_status(order)
                
                rows.append({
                    'id': order.id,
                    'no': start_number + len(rows),
                    'jenis_mobil': f"{order.partner_car_brand.name} {order.partner_car_brand_type.name}".strip() if order.partner_car_brand and order.partner_car_brand_type else '-',
                    'plat_mobil': order.partner_car_id.number_plate if order.partner_car_id else '-',
                    'status': status,
                    'keterangan': status['code'],
                    'catatan': order.lead_time_catatan or '-',
                    'estimasi_selesai': format_timestamp(order.controller_estimasi_selesai),
                    'mekanik': order.generated_mechanic_team or '-',
                    'service_advisor': ', '.join(order.service_advisor_id.mapped('name')) if order.service_advisor_id else '-',
                    'service': {
                        'category': {
                            'code': order.service_category,
                            'text': dict(order._fields['service_category'].selection).get(order.service_category, '-')
                        },
                        'subcategory': {
                            'code': order.service_subcategory,
                            'text': dict(order._fields['service_subcategory'].selection).get(order.service_subcategory, '-')
                        }
                    },
                    'timestamps': {
                        'mulai_servis': format_timestamp(order.controller_mulai_servis),
                        'selesai_servis': format_timestamp(order.controller_selesai),
                        'completion': format_timestamp(order.date_completed)
                    },
                    'progress': {
                        'percentage': order.lead_time_progress or 0,
                        'stage': status['code']
                    },
                    'job_stops': {
                        'istirahat': {
                            'active': bool(order.controller_istirahat_shift1_mulai and not order.controller_istirahat_shift1_selesai),
                            'start': format_timestamp(order.controller_istirahat_shift1_mulai),
                            'end': format_timestamp(order.controller_istirahat_shift1_selesai),
                            'completed': bool(order.controller_istirahat_shift1_selesai)
                        },
                        'job_stop_lain': {
                            'active': bool(order.controller_job_stop_lain_mulai and not order.controller_job_stop_lain_selesai),
                            'start': format_timestamp(order.controller_job_stop_lain_mulai),
                            'end': format_timestamp(order.controller_job_stop_lain_selesai),
                            'completed': bool(order.controller_job_stop_lain_selesai),
                            'note': order.job_stop_lain_keterangan or None
                        },
                        'tunggu_konfirmasi': {
                            'active': bool(order.controller_tunggu_konfirmasi_mulai and not order.controller_tunggu_konfirmasi_selesai),
                            'start': format_timestamp(order.controller_tunggu_konfirmasi_mulai),
                            'end': format_timestamp(order.controller_tunggu_konfirmasi_selesai),
                            'completed': bool(order.controller_tunggu_konfirmasi_selesai)
                        },
                        'tunggu_part': {
                            'active': bool(order.controller_tunggu_part1_mulai and not order.controller_tunggu_part1_selesai),
                            'start': format_timestamp(order.controller_tunggu_part1_mulai),
                            'end': format_timestamp(order.controller_tunggu_part1_selesai),
                            'completed': bool(order.controller_tunggu_part1_selesai)
                        },
                        'tunggu_part_2': {
                            'active': bool(order.controller_tunggu_part2_mulai and not order.controller_tunggu_part2_selesai),
                            'start': format_timestamp(order.controller_tunggu_part2_mulai),
                            'end': format_timestamp(order.controller_tunggu_part2_selesai),
                            'completed': bool(order.controller_tunggu_part2_selesai)
                        },
                        'tunggu_sublet': {
                            'active': bool(order.controller_tunggu_sublet_mulai and not order.controller_tunggu_sublet_selesai),
                            'start': format_timestamp(order.controller_tunggu_sublet_mulai),
                            'end': format_timestamp(order.controller_tunggu_sublet_selesai),
                            'completed': bool(order.controller_tunggu_sublet_selesai)
                        }
                    }
                })

            # Prepare summary
            base_domain = [('sa_cetak_pkb', '!=', False)]
            summary = {
                'total': SaleOrder.search_count(base_domain),
                'proses': SaleOrder.search_count(base_domain + [
                    ('controller_mulai_servis', '!=', False),
                    ('controller_selesai', '=', False)
                ]),
                'tunggu_part': SaleOrder.search_count(base_domain + [
                    ('controller_tunggu_part1_mulai', '!=', False),
                    ('controller_tunggu_part1_selesai', '=', False)
                ]),
                'selesai': SaleOrder.search_count(base_domain + [
                    ('controller_selesai', '!=', False)
                ]),
                'mechanics': {
                    'total': request.env['pitcar.mechanic.new'].search_count([]),
                    'on_duty': 0
                },
                'service_advisors': {
                    'total': request.env['pitcar.service.advisor'].search_count([]),
                    'on_duty': 0
                }
            }

            return {
                'status': 'success',
                'data': {
                    'debug': {
                        'domain': domain,
                        'filter_type': filter_type,
                        'search_query': search_query,
                        'received_params': kw,
                        'total_count': total_count
                    },
                    'current_time': current_time.strftime('%H : %M : %S WIB'),
                    'current_date': current_time.strftime('%A %d %b %Y'),
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': total_pages,
                        'current_page': page,
                        'items_per_page': limit,
                        'has_next': page < total_pages,
                        'has_previous': page > 1,
                        'start_number': start_number,
                        'end_number': min(start_number + limit - 1, total_count)
                    },
                    'rows': rows,
                    'summary': summary
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_table_data: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e),
                'trace': traceback.format_exc(),
                'received_params': kw
            }

    # Job Stop Management Endpoints
    @http.route('/web/lead-time/<int:sale_order_id>/job-stop', type='json', auth='user', methods=['POST'])
    def manage_job_stop(self, sale_order_id, **kwargs):
        """Manage job stop status and times"""
        try:
            sale_order = self._validate_access(sale_order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            status = kwargs.get('status')
            action = kwargs.get('action')
            start_time = kwargs.get('startTime')
            end_time = kwargs.get('endTime')
            notes = kwargs.get('notes')

            # Convert times
            start_dt = self._parse_time(start_time) if start_time else None
            end_dt = self._parse_time(end_time) if end_time else None

            # Handle each status type
            if status == 'proses':
                if action == 'start':
                    sale_order.action_mulai_servis()
                else:
                    sale_order.action_selesai_servis()

            elif status == 'tunggu_part':
                self._handle_part_waiting(sale_order, action, start_dt, end_dt, notes)
            
            elif status == 'tunggu_konfirmasi':
                self._handle_confirmation_waiting(sale_order, action, start_dt, end_dt, notes)
            
            elif status == 'istirahat':
                self._handle_break_time(sale_order, action, start_dt, end_dt, notes)
            
            elif status == 'selesai':
                sale_order.write({
                    'controller_selesai': start_dt,
                    'lead_time_catatan': notes
                })
                sale_order.action_selesai_servis()

            # Recompute lead times
            sale_order.action_recompute_single_order()

            return {
                'status': 'success',
                'message': f'{status} {action} recorded successfully',
                'data': self._get_order_details(sale_order)
            }

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _handle_part_waiting(self, sale_order, action, start_dt, end_dt, notes):
        """Handle part waiting job stop"""
        if action == 'start':
            sale_order.write({
                'controller_tunggu_part1_mulai': start_dt,
                'lead_time_catatan': notes
            })
            sale_order.action_tunggu_part1_mulai()
        else:
            sale_order.write({
                'controller_tunggu_part1_selesai': end_dt,
                'lead_time_catatan': notes
            })
            sale_order.action_tunggu_part1_selesai()
            sale_order.action_mulai_servis()  # Resume service

    def _handle_confirmation_waiting(self, sale_order, action, start_dt, end_dt, notes):
        """Handle confirmation waiting job stop"""
        if action == 'start':
            sale_order.write({
                'controller_tunggu_konfirmasi_mulai': start_dt,
                'lead_time_catatan': notes
            })
            sale_order.action_tunggu_konfirmasi_mulai()
        else:
            sale_order.write({
                'controller_tunggu_konfirmasi_selesai': end_dt,
                'lead_time_catatan': notes
            })
            sale_order.action_tunggu_konfirmasi_selesai()
            sale_order.action_mulai_servis()  # Resume service

    def _handle_break_time(self, sale_order, action, start_dt, end_dt, notes):
        """Handle break time job stop"""
        if action == 'start':
            sale_order.write({
                'controller_istirahat_shift1_mulai': start_dt,
                'need_istirahat': 'yes',
                'lead_time_catatan': notes
            })
            sale_order.action_istirahat_shift1_mulai()
        else:
            sale_order.write({
                'controller_istirahat_shift1_selesai': end_dt,
                'lead_time_catatan': notes
            })
            sale_order.action_istirahat_shift1_selesai()
            sale_order.action_mulai_servis()  # Resume service

    # Additional Endpoints
    @http.route('/web/lead-time/<int:sale_order_id>/estimation', type='json', auth='user', methods=['PUT'])
    def update_estimation(self, sale_order_id, **kwargs):
        """Update service estimation times"""
        try:
            sale_order = self._validate_access(sale_order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            updates = {}
            if 'estimasi_mulai' in kwargs:
                updates['controller_estimasi_mulai'] = self._parse_time(kwargs['estimasi_mulai'])
            if 'estimasi_selesai' in kwargs:
                updates['controller_estimasi_selesai'] = self._parse_time(kwargs['estimasi_selesai'])

            if updates:
                sale_order.write(updates)

            return {
                'status': 'success',
                'message': 'Estimation times updated successfully',
                'data': self._get_order_details(sale_order)
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/lead-time/<int:sale_order_id>/notes', type='json', auth='user', methods=['PUT'])
    def update_notes(self, sale_order_id, notes):
        """Update lead time notes"""
        try:
            sale_order = self._validate_access(sale_order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            sale_order.write({'lead_time_catatan': notes})
            return {
                'status': 'success',
                'message': 'Notes updated successfully',
                'data': self._get_order_details(sale_order)
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _get_summary(self, base_domain):
        """Get summary statistics based on active domain"""
        try:
            orders = request.env['sale.order'].search(base_domain)
            
            # Get active mechanics and service advisors
            active_mechanics = set()
            active_advisors = set()
            
            for order in orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai):
                if order.car_mechanic_id_new:
                    active_mechanics.update(order.car_mechanic_id_new.ids)
                if order.service_advisor_id:
                    active_advisors.update(order.service_advisor_id.ids)

            total_mechanics = len(request.env['pitcar.mechanic.new'].search([]))
            total_advisors = len(request.env['pitcar.service.advisor'].search([]))

            return {
                'total': len(orders),
                'proses': len(orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai)),
                'tunggu_part': len(orders.filtered(lambda o: o.controller_tunggu_part1_mulai and not o.controller_tunggu_part1_selesai)),
                'tunggu_konfirmasi': len(orders.filtered(lambda o: o.controller_tunggu_konfirmasi_mulai and not o.controller_tunggu_konfirmasi_selesai)),
                'istirahat': len(orders.filtered(lambda o: o.controller_istirahat_shift1_mulai and not o.controller_istirahat_shift1_selesai)),
                'selesai': len(orders.filtered(lambda o: o.controller_selesai)),
                'mechanics': {
                    'total': total_mechanics,
                    'on_duty': len(active_mechanics)
                },
                'service_advisors': {
                    'total': total_advisors,
                    'on_duty': len(active_advisors)
                }
            }
        except Exception as e:
            _logger.error(f"Error in _get_summary: {str(e)}")
            return {
                'total': 0,
                'proses': 0,
                'tunggu_part': 0,
                'tunggu_konfirmasi': 0,
                'istirahat': 0,
                'selesai': 0,
                'mechanics': {'total': 0, 'on_duty': 0},
                'service_advisors': {'total': 0, 'on_duty': 0}
            }
    
    @http.route('/web/lead-time/categories', type='json', auth='user', methods=['GET'])
    def get_service_categories(self):
        """Get available service categories and subcategories"""
        try:
            SaleOrder = request.env['sale.order']
            categories = dict(SaleOrder._fields['service_category'].selection)
            subcategories = dict(SaleOrder._fields['service_subcategory'].selection)
            
            # Organize subcategories by category
            categorized_subcategories = {
                'maintenance': {k: v for k, v in subcategories.items() if k in [
                    'tune_up', 'tune_up_addition', 'periodic_service', 'periodic_service_addition'
                ]},
                'repair': {k: v for k, v in subcategories.items() if k in ['general_repair']}
            }
            
            return {
                'status': 'success',
                'data': {
                    'categories': categories,
                    'subcategories': categorized_subcategories
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/lead-time/<int:sale_order_id>/timeline', type='json', auth='user', methods=['GET'])
    def get_order_timeline(self, sale_order_id):
        """Get complete timeline of an order"""
        try:
            sale_order = self._validate_access(sale_order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            timeline = []
            
            # Add all events chronologically
            events = []
            if sale_order.sa_jam_masuk:
                events.append({
                    'time': sale_order.sa_jam_masuk,
                    'type': 'check_in',
                    'description': 'Unit Masuk'
                })
            
            if sale_order.controller_mulai_servis:
                events.append({
                    'time': sale_order.controller_mulai_servis,
                    'type': 'service_start',
                    'description': 'Mulai Servis'
                })

            # Add job stops
            if sale_order.controller_tunggu_part1_mulai:
                events.append({
                    'time': sale_order.controller_tunggu_part1_mulai,
                    'type': 'job_stop_start',
                    'description': 'Mulai Tunggu Part'
                })
            if sale_order.controller_tunggu_part1_selesai:
                events.append({
                    'time': sale_order.controller_tunggu_part1_selesai,
                    'type': 'job_stop_end',
                    'description': 'Selesai Tunggu Part'
                })

            if sale_order.controller_tunggu_konfirmasi_mulai:
                events.append({
                    'time': sale_order.controller_tunggu_konfirmasi_mulai,
                    'type': 'job_stop_start',
                    'description': 'Mulai Tunggu Konfirmasi'
                })
            if sale_order.controller_tunggu_konfirmasi_selesai:
                events.append({
                    'time': sale_order.controller_tunggu_konfirmasi_selesai,
                    'type': 'job_stop_end',
                    'description': 'Selesai Tunggu Konfirmasi'
                })

            if sale_order.controller_istirahat_shift1_mulai:
                events.append({
                    'time': sale_order.controller_istirahat_shift1_mulai,
                    'type': 'job_stop_start',
                    'description': 'Mulai Istirahat'
                })
            if sale_order.controller_istirahat_shift1_selesai:
                events.append({
                    'time': sale_order.controller_istirahat_shift1_selesai,
                    'type': 'job_stop_end',
                    'description': 'Selesai Istirahat'
                })

            if sale_order.controller_selesai:
                events.append({
                    'time': sale_order.controller_selesai,
                    'type': 'service_end',
                    'description': 'Selesai Servis'
                })

            if sale_order.fo_unit_keluar:
                events.append({
                    'time': sale_order.fo_unit_keluar,
                    'type': 'check_out',
                    'description': 'Unit Keluar'
                })

            # Sort events by time
            events.sort(key=lambda x: x['time'])

            # Format times to WIB
            tz = pytz.timezone('Asia/Jakarta')
            for event in events:
                local_dt = pytz.utc.localize(event['time']).astimezone(tz)
                event['formatted_time'] = local_dt.strftime('%H:%M')
                timeline.append({
                    'time': event['formatted_time'],
                    'type': event['type'],
                    'description': event['description']
                })

            return {
                'status': 'success',
                'data': {
                    'timeline': timeline,
                    'total_duration': sale_order.total_lead_time_servis,
                    'active_duration': sale_order.lead_time_servis,
                    'job_stop_duration': sale_order.total_lead_time_servis - sale_order.lead_time_servis
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/lead-time/statistics', type='json', auth='user', methods=['POST'], csrf=False)
    def get_statistics(self, **kw):
        """Get comprehensive lead time statistics for dashboard with date filtering"""
        try:
            # Set Jakarta timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Get date parameters from payload
            data = request.get_json_data()
            params = data.get('params', {})
            
            # Extract parameters
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            month = params.get('month')
            year = params.get('year', now.year)
            
            _logger.info(f"Received parameters: start_date={start_date}, end_date={end_date}, month={month}, year={year}")

            # Initialize variables
            start_utc = None
            end_utc = None
            date_range_start = None
            date_range_end = None
            
            # Base domain
            base_domain = [('sa_cetak_pkb', '!=', False)]

            # Process date filters
            try:
                if start_date and end_date:
                    # Create naive datetime and localize it
                    start = datetime.strptime(f"{start_date} 00:00:00", '%Y-%m-%d %H:%M:%S')
                    end = datetime.strptime(f"{end_date} 23:59:59", '%Y-%m-%d %H:%M:%S')
                    
                    # Set date range
                    date_range_start = start_date
                    date_range_end = end_date
                    
                elif month is not None:
                    month = int(month)
                    if not 1 <= month <= 12:
                        return {'status': 'error', 'message': 'Month must be between 1 and 12'}
                    
                    # Create date range for the specified month
                    start = datetime(year, month, 1)
                    if month == 12:
                        end = datetime(year + 1, 1, 1)
                    else:
                        end = datetime(year, month + 1, 1)
                    
                    # Set date range
                    date_range_start = start.strftime('%Y-%m-%d')
                    date_range_end = (end - timedelta(days=1)).strftime('%Y-%m-%d')
                    
                else:
                    # Default to today
                    today = now.date()
                    start = datetime.combine(today, datetime.min.time())
                    end = start + timedelta(days=1)
                    
                    # Set date range
                    date_range_start = today.strftime('%Y-%m-%d')
                    date_range_end = today.strftime('%Y-%m-%d')

                # Convert to UTC for database comparison
                start_utc = tz.localize(start).astimezone(pytz.UTC).replace(tzinfo=None)
                end_utc = tz.localize(end).astimezone(pytz.UTC).replace(tzinfo=None)
                
                _logger.info(f"Processed date range UTC: {start_utc} to {end_utc}")
                _logger.info(f"Display date range: {date_range_start} to {date_range_end}")

                # Create date domain
                date_domain = [
                    ('sa_jam_masuk', '>=', start_utc),
                    ('sa_jam_masuk', '<', end_utc)
                ]

            except (ValueError, TypeError) as e:
                _logger.error(f"Date processing error: {str(e)}")
                return {'status': 'error', 'message': 'Invalid date format or values'}

            # Get filtered orders
            domain = expression.AND([base_domain, date_domain])
            orders = request.env['sale.order'].search(domain)
            
            _logger.info(f"Found {len(orders)} orders matching criteria")

            def calculate_daily_stats(start_date, end_date, orders):
                """Calculate statistics for each day in range"""
                daily_stats = {}
                current = start_date
                
                while current < end_date:
                    day_end = current + timedelta(days=1)
                    day_orders = orders.filtered(
                        lambda o: current <= o.sa_jam_masuk < day_end
                    )
                    
                    daily_stats[current.strftime('%Y-%m-%d')] = calculate_period_stats(day_orders)
                    current = day_end
                    
                return daily_stats

            def calculate_period_stats(orders):
                """Calculate detailed statistics for a period"""
                if not orders:
                    return {
                        'total_orders': 0,
                        'completed_orders': 0,
                        'active_orders': 0,
                        'completion_rate': 0,
                        'average_lead_time': 0,
                        'average_active_time': 0,
                        'average_completion_time': 0,
                        'job_stops': {
                            'tunggu_part': 0,
                            'tunggu_konfirmasi': 0,
                            'istirahat': 0,
                            'tunggu_sublet': 0,
                            'job_stop_lain': 0
                        },
                        'job_stop_durations': {
                            'tunggu_part': 0,
                            'tunggu_konfirmasi': 0,
                            'istirahat': 0,
                            'tunggu_sublet': 0,
                            'job_stop_lain': 0
                        },
                        'average_job_stop_durations': {
                            'tunggu_part': 0,
                            'tunggu_konfirmasi': 0,
                            'istirahat': 0,
                            'tunggu_sublet': 0,
                            'job_stop_lain': 0
                        },
                        'status_breakdown': {
                            'belum_mulai': 0,
                            'proses': 0,
                            'selesai': 0
                        }
                    }
                    
                completed_orders = orders.filtered(lambda o: o.controller_selesai)
                active_orders = orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai)
                
                # Calculate average times
                avg_lead_time = sum(o.total_lead_time_servis or 0 for o in completed_orders) / len(completed_orders) if completed_orders else 0
                avg_active_time = sum(o.lead_time_servis or 0 for o in completed_orders) / len(completed_orders) if completed_orders else 0
                
                # Calculate avg completion time
                avg_completion_time = 0
                completion_count = 0
                
                for order in completed_orders:
                    if order.controller_mulai_servis and order.controller_selesai:
                        duration = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 60
                        avg_completion_time += duration
                        completion_count += 1
                        
                if completion_count > 0:
                    avg_completion_time /= completion_count
                
                # Job stop statistics
                job_stops = {
                    'tunggu_part': len(orders.filtered(lambda o: o.controller_tunggu_part1_mulai and not o.controller_tunggu_part1_selesai)),
                    'tunggu_konfirmasi': len(orders.filtered(lambda o: o.controller_tunggu_konfirmasi_mulai and not o.controller_tunggu_konfirmasi_selesai)),
                    'istirahat': len(orders.filtered(lambda o: o.controller_istirahat_shift1_mulai and not o.controller_istirahat_shift1_selesai)),
                    'tunggu_sublet': len(orders.filtered(lambda o: o.controller_tunggu_sublet_mulai and not o.controller_tunggu_sublet_selesai)),
                    'job_stop_lain': len(orders.filtered(lambda o: o.controller_job_stop_lain_mulai and not o.controller_job_stop_lain_selesai))
                }

                # Calculate job stop durations
                job_stop_durations = {
                    'tunggu_part': sum((o.controller_tunggu_part1_selesai - o.controller_tunggu_part1_mulai).total_seconds() / 60 
                                    if o.controller_tunggu_part1_selesai and o.controller_tunggu_part1_mulai else 0 
                                    for o in completed_orders),
                    'tunggu_konfirmasi': sum((o.controller_tunggu_konfirmasi_selesai - o.controller_tunggu_konfirmasi_mulai).total_seconds() / 60 
                                        if o.controller_tunggu_konfirmasi_selesai and o.controller_tunggu_konfirmasi_mulai else 0 
                                        for o in completed_orders),
                    'istirahat': sum((o.controller_istirahat_shift1_selesai - o.controller_istirahat_shift1_mulai).total_seconds() / 60 
                                if o.controller_istirahat_shift1_selesai and o.controller_istirahat_shift1_mulai else 0 
                                for o in completed_orders),
                    'tunggu_sublet': sum((o.controller_tunggu_sublet_selesai - o.controller_tunggu_sublet_mulai).total_seconds() / 60 
                                    if o.controller_tunggu_sublet_selesai and o.controller_tunggu_sublet_mulai else 0 
                                    for o in completed_orders),
                    'job_stop_lain': sum((o.controller_job_stop_lain_selesai - o.controller_job_stop_lain_mulai).total_seconds() / 60 
                                    if o.controller_job_stop_lain_selesai and o.controller_job_stop_lain_mulai else 0 
                                    for o in completed_orders)
                }
                
                # Get average job stop durations
                avg_job_stop_durations = {}
                for stop_type, total_duration in job_stop_durations.items():
                    stop_count = len([o for o in completed_orders if getattr(o, f'controller_{stop_type}_selesai', None)])
                    avg_job_stop_durations[stop_type] = total_duration / stop_count if stop_count > 0 else 0
                
                return {
                    'total_orders': len(orders),
                    'completed_orders': len(completed_orders),
                    'active_orders': len(active_orders),
                    'completion_rate': (len(completed_orders) / len(orders) * 100) if orders else 0,
                    'average_lead_time': avg_lead_time,
                    'average_active_time': avg_active_time,
                    'average_completion_time': avg_completion_time,
                    'job_stops': job_stops,
                    'job_stop_durations': job_stop_durations,
                    'average_job_stop_durations': avg_job_stop_durations,
                    'status_breakdown': {
                        'belum_mulai': len(orders.filtered(lambda o: not o.controller_mulai_servis)),
                        'proses': len(active_orders),
                        'selesai': len(completed_orders)
                    }
                }

            def get_hourly_distribution(orders):
                """Calculate hourly distribution for workshop hours (8-17)"""
                hours = {str(i).zfill(2): {'starts': 0, 'completions': 0} for i in range(8, 18)}
                
                for order in orders:
                    if order.controller_mulai_servis:
                        local_time = self._convert_to_local_time(order.controller_mulai_servis)
                        hour = local_time.strftime('%H')
                        if '08' <= hour <= '17':
                            hours[hour]['starts'] += 1
                            
                    if order.controller_selesai:
                        local_time = self._convert_to_local_time(order.controller_selesai)
                        hour = local_time.strftime('%H')
                        if '08' <= hour <= '17':
                            hours[hour]['completions'] += 1
                            
                return hours

            # Get staff stats
            mechanics = request.env['pitcar.mechanic.new'].search([])
            advisors = request.env['pitcar.service.advisor'].search([])
            
            active_mechanics = set()
            active_advisors = set()
            active_orders = orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai)
            
            for order in active_orders:
                if order.car_mechanic_id_new:
                    active_mechanics.update(order.car_mechanic_id_new.ids)
                if order.service_advisor_id:
                    active_advisors.update(order.service_advisor_id.ids)

            # Get service category and subcategory counts
            service_category_counts = {
                'maintenance': len(orders.filtered(lambda o: getattr(o, 'service_category', '') == 'maintenance')),
                'repair': len(orders.filtered(lambda o: getattr(o, 'service_category', '') == 'repair')),
            }
            
            service_subcategory_counts = {
                'tune_up': len(orders.filtered(lambda o: getattr(o, 'service_subcategory', '') == 'tune_up')),
                'tune_up_addition': len(orders.filtered(lambda o: getattr(o, 'service_subcategory', '') == 'tune_up_addition')),
                'periodic_service': len(orders.filtered(lambda o: getattr(o, 'service_subcategory', '') == 'periodic_service')),
                'periodic_service_addition': len(orders.filtered(lambda o: getattr(o, 'service_subcategory', '') == 'periodic_service_addition')),
                'general_repair': len(orders.filtered(lambda o: getattr(o, 'service_subcategory', '') == 'general_repair')),
            }

            # Compile complete statistics
            stats = {
                'current_time': self._format_local_datetime(now),
                'date_range': {
                    'start': date_range_start,
                    'end': date_range_end
                },
                'service_category': service_category_counts,
                'service_subcategory': service_subcategory_counts,
                'overall': calculate_period_stats(orders),
                'daily_breakdown': calculate_daily_stats(start_utc, end_utc, orders),
                'hourly_distribution': get_hourly_distribution(orders),
                'staff': {
                    'mechanics': {
                        'total': len(mechanics),
                        'active': len(active_mechanics),
                        'utilization': (len(active_mechanics) / len(mechanics) * 100) if mechanics else 0
                    },
                    'advisors': {
                        'total': len(advisors),
                        'active': len(active_advisors),
                        'utilization': (len(active_advisors) / len(advisors) * 100) if advisors else 0
                    }
                }
            }

            return {
                'status': 'success',
                'data': stats
            }

        except Exception as e:
            _logger.error(f"Error in get_statistics: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}



    # NEW VERSION API : SIMPLE WAY
    @http.route('/web/lead-time/start-service', type='json', auth='user', methods=['POST'])
    def start_service(self, **kw):
        """Start a new service or resume service"""
        try:
            order_id = kw.get('order_id')
            if not order_id:
                return {'status': 'error', 'message': 'Order ID is required'}

            sale_order = self._validate_access(order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            try:
                sale_order.action_mulai_servis()
                return {
                    'status': 'success',
                    'message': 'Service started successfully',
                    'data': {
                        'order_id': sale_order.id,
                        'status': 'in_progress',
                        'started_at': self._format_datetime(sale_order.controller_mulai_servis)
                    }
                }
            except Exception as e:
                return {'status': 'error', 'message': str(e)}

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/lead-time/pause-service', type='json', auth='user', methods=['POST'])
    def pause_service(self, **kw):
        """Pause service with specific stop type"""
        try:
            order_id = kw.get('order_id')
            stop_type = kw.get('stop_type')
            note = kw.get('note')

            if not order_id or not stop_type:
                return {'status': 'error', 'message': 'Order ID and stop type are required'}

            sale_order = self._validate_access(order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            # Map stop types to corresponding actions
            stop_actions = {
                'tunggu_konfirmasi': 'action_tunggu_konfirmasi_mulai',
                'tunggu_part_1': 'action_tunggu_part1_mulai',
                'tunggu_part_2': 'action_tunggu_part2_mulai',
                'istirahat': 'action_istirahat_shift1_mulai',
                'tunggu_sublet': 'action_tunggu_sublet_mulai',
                'job_stop_lain': 'action_job_stop_lain_mulai'
            }

            try:
                # Execute corresponding action
                if stop_type in stop_actions:
                    action = getattr(sale_order, stop_actions[stop_type])
                    action()

                    # Update note if provided for job_stop_lain
                    if stop_type == 'job_stop_lain' and note:
                        sale_order.write({
                            'job_stop_lain_keterangan': note,
                            'need_other_job_stop': 'yes'
                        })

                    return {
                        'status': 'success',
                        'message': f'Service paused with {stop_type}',
                        'data': {
                            'order_id': sale_order.id,
                            'status': 'paused',
                            'stop_type': stop_type,
                            'paused_at': self._format_datetime(fields.Datetime.now())
                        }
                    }
                else:
                    return {'status': 'error', 'message': 'Invalid stop type'}

            except Exception as e:
                return {'status': 'error', 'message': str(e)}

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/lead-time/resume-service', type='json', auth='user', methods=['POST'])
    def resume_service(self, **kw):
        """Resume service from specific stop type"""
        try:
            order_id = kw.get('order_id')
            stop_type = kw.get('stop_type')

            if not order_id or not stop_type:
                return {'status': 'error', 'message': 'Order ID and stop type are required'}

            sale_order = self._validate_access(order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            # Map stop types to corresponding completion actions
            stop_actions = {
                'tunggu_konfirmasi': 'action_tunggu_konfirmasi_selesai',
                'tunggu_part_1': 'action_tunggu_part1_selesai',
                'tunggu_part_2': 'action_tunggu_part2_selesai',
                'istirahat': 'action_istirahat_shift1_selesai',
                'tunggu_sublet': 'action_tunggu_sublet_selesai',
                'job_stop_lain': 'action_job_stop_lain_selesai'
            }

            try:
                # Execute corresponding completion action
                if stop_type in stop_actions:
                    action = getattr(sale_order, stop_actions[stop_type])
                    action()

                    # Resume service after completing the stop
                    # sale_order.action_mulai_servis()

                    return {
                        'status': 'success',
                        'message': f'Service resumed from {stop_type}',
                        'data': {
                            'order_id': sale_order.id,
                            'status': 'in_progress',
                            'resumed_at': self._format_datetime(fields.Datetime.now())
                        }
                    }
                else:
                    return {'status': 'error', 'message': 'Invalid stop type'}

            except Exception as e:
                return {'status': 'error', 'message': str(e)}

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/lead-time/complete-service', type='json', auth='user', methods=['POST'])
    def complete_service(self, **kw):
        """Complete the service"""
        try:
            order_id = kw.get('order_id')
            if not order_id:
                return {'status': 'error', 'message': 'Order ID is required'}

            sale_order = self._validate_access(order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            try:
                sale_order.action_selesai_servis()
                return {
                    'status': 'success',
                    'message': 'Service completed successfully',
                    'data': {
                        'order_id': sale_order.id,
                        'status': 'completed',
                        'completed_at': self._format_datetime(sale_order.controller_selesai)
                    }
                }
            except Exception as e:
                return {'status': 'error', 'message': str(e)}

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/lead-time/<int:sale_order_id>/status', type='json', auth='user', methods=['GET'])
    def get_service_status(self, sale_order_id):
        """Get current service status including active job stops"""
        try:
            sale_order = self._validate_access(sale_order_id)
            if not sale_order:
                return {'status': 'error', 'message': 'Sale order not found'}

            status_data = {
                'order_id': sale_order.id,
                'current_status': sale_order.lead_time_stage,
                'is_active': bool(sale_order.controller_mulai_servis and not sale_order.controller_selesai),
                'progress': sale_order.lead_time_progress,
                'active_job_stops': []
            }

            # Check for active job stops
            job_stops = []
            if sale_order.controller_tunggu_konfirmasi_mulai and not sale_order.controller_tunggu_konfirmasi_selesai:
                job_stops.append({
                    'type': 'tunggu_konfirmasi',
                    'started_at': self._format_datetime(sale_order.controller_tunggu_konfirmasi_mulai)
                })
            if sale_order.controller_tunggu_part1_mulai and not sale_order.controller_tunggu_part1_selesai:
                job_stops.append({
                    'type': 'tunggu_part_1',
                    'started_at': self._format_datetime(sale_order.controller_tunggu_part1_mulai)
                })
            # ... add other job stop checks ...

            status_data['active_job_stops'] = job_stops

            return {
                'status': 'success',
                'data': status_data
            }

        except Exception as e:
            return {'status': 'error', 'message': str(e)}