from odoo import http, fields
from odoo.http import request, Response
import pytz
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError
import json
import math
import logging
from odoo.osv import expression  # Menambahkan import 
import traceback

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

    def _format_local_datetime_id(self, dt):
        """Format datetime to Asia/Jakarta timezone string"""
        if not dt:
            return None
        local_dt = self._convert_to_local_time(dt)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S WIB')

    def _format_local_datetime(self, dt):
        """Format datetime to Jakarta timezone"""
        if not dt:
            return None
        
        # Convert to Jakarta timezone
        tz = pytz.timezone('Asia/Jakarta')
        if not dt.tzinfo:
            dt = pytz.UTC.localize(dt)
        local_dt = dt.astimezone(tz)
        
        # Format without timezone info
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')

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

    def _get_service_details(self, order):
        """Get formatted service order details"""
        services = []
        
        # Get order lines that are services
        service_lines = order.order_line.filtered(lambda l: l.product_id.type == 'service')
        
        for line in service_lines:
            services.append({
                'id': line.id,
                'name': line.product_id.name,
                'description': line.name,
                'quantity': line.product_uom_qty,
                'uom': line.product_uom.name,
                'price_unit': line.price_unit,
                'price_subtotal': line.price_subtotal,
                'price_total': line.price_total,
                'discount': line.discount,
            })
        
        return {
            'count': len(services),
            'items': services,
            'total_amount': sum(s['price_total'] for s in services),
        }


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
            MentorRequest = request.env['pitcar.mentor.request'].sudo()
            for order in orders:
                status = get_order_status(order)
                
                # Cek permintaan bantuan terkait
                mentor_request = MentorRequest.search([('sale_order_id', '=', order.id)], limit=1)
                has_mentor_request = bool(mentor_request)
                mentor_request_state = mentor_request.state if mentor_request else None
                
                rows.append({
                    'id': order.id,
                    'no': start_number + len(rows),
                    'jenis_mobil': f"{order.partner_car_brand.name} {order.partner_car_brand_type.name}".strip() if order.partner_car_brand and order.partner_car_brand_type else '-',
                    'plat_mobil': order.partner_car_id.number_plate if order.partner_car_id else '-',
                    'status': status,
                    'keterangan': status['code'],
                    'catatan': order.lead_time_catatan or '-',
                    'estimasi_mulai': format_timestamp(order.controller_estimasi_mulai),
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
                        },
                        'details': self._get_service_details(order)
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
                    },
                    'has_mentor_request': has_mentor_request,
                    'mentor_request_state': mentor_request_state
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

            # Standards for job stops (in minutes)
            JOB_STOP_STANDARDS = {
                'tunggu_penerimaan': 15,
                'penerimaan': 15, 
                'tunggu_servis': 15,
                'tunggu_konfirmasi': 40,
                'tunggu_part1': 45,
                'tunggu_part2': 45
            }

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
                """Calculate detailed statistics for a period with accurate job stop tracking"""
                if not orders:
                    # Initialize standards analysis struktur
                    default_standards = {}
                    for key, standard_time in JOB_STOP_STANDARDS.items():
                        default_standards[key] = {
                            'standard_time': standard_time,
                            'total_count': 0,
                            'exceeded_count': 0,
                            'within_count': 0,
                            'exceeded_percentage': 0,
                            'within_percentage': 0,
                            'avg_exceeded_duration': 0,
                            'avg_within_duration': 0
                        }
                    return {
                        'total_orders': 0,
                        'completed_orders': 0,
                        'active_orders': 0,
                        'completion_rate': 0,
                        'average_lead_time': 0,
                        'average_active_time': 0,
                        'average_completion_time': 0,
                        'job_stops': {
                            'tunggu_part1': 0,
                            'tunggu_part2': 0,
                            'tunggu_konfirmasi': 0,
                            'istirahat': 0,
                            'tunggu_sublet': 0,
                            'job_stop_lain': 0
                        },
                        'job_stop_durations': {
                            'tunggu_part1': 0,
                            'tunggu_part2': 0,
                            'tunggu_konfirmasi': 0,
                            'istirahat': 0,
                            'tunggu_sublet': 0,
                            'job_stop_lain': 0
                        },
                        'average_job_stop_durations': {
                            'tunggu_part1': 0,
                            'tunggu_part2': 0,
                            'tunggu_konfirmasi': 0,
                            'istirahat': 0,
                            'tunggu_sublet': 0,
                            'job_stop_lain': 0
                        },
                        'standards_analysis': default_standards,  # Menggunakan struktur standar yang baru
                        'status_breakdown': {
                            'belum_mulai': 0,
                            'proses': 0,
                            'selesai': 0
                        }
                    }
                    
                completed_orders = orders.filtered(lambda o: o.controller_selesai)
                active_orders = orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai)
                
                # Calculate basic metrics
                avg_lead_time = sum(o.total_lead_time_servis or 0 for o in completed_orders) / len(completed_orders) if completed_orders else 0
                avg_active_time = sum(o.lead_time_servis or 0 for o in completed_orders) / len(completed_orders) if completed_orders else 0
                
                # Calculate avg completion time
                completion_times = []
                for order in completed_orders:
                    if order.controller_mulai_servis and order.controller_selesai:
                        duration = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 60
                        if duration > 0:
                            completion_times.append(duration)
                avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0

                # Initialize job stop tracking
                job_stops = {
                    'tunggu_part1': 0,
                    'tunggu_part2': 0,
                    'tunggu_konfirmasi': 0,
                    'istirahat': 0,
                    'tunggu_sublet': 0,
                    'job_stop_lain': 0
                }

                job_stop_durations = dict.fromkeys(job_stops.keys(), 0)
                completed_job_stops = dict.fromkeys(job_stops.keys(), 0)

                # Initialize standards analysis
                standards_analysis = {}
                for key, standard_time in JOB_STOP_STANDARDS.items():
                    standards_analysis[key] = {
                        'standard_time': standard_time,
                        'total_count': 0,
                        'exceeded_count': 0,
                        'within_count': 0,
                        'exceeded_percentage': 0,
                        'within_percentage': 0,
                        'avg_exceeded_duration': 0,
                        'avg_within_duration': 0
                    }

                 # Lists untuk tracking durasi
                exceeded_durations = {key: [] for key in JOB_STOP_STANDARDS.keys()}
                within_durations = {key: [] for key in JOB_STOP_STANDARDS.keys()}

                 # Initialize overall lead time statistics
                overall_lead_times = []
                min_overall_lead_time = float('inf')
                max_overall_lead_time = 0
                overall_lead_time_distribution = {
                    'under_2_hours': 0,
                    '2_to_4_hours': 0,
                    '4_to_6_hours': 0,
                    '6_to_8_hours': 0,
                    'over_8_hours': 0
                }
                
                # Add specific tracking for each lead time stage
                stage_durations = {
                    'arrival_to_reception': [],  # sa_jam_masuk -> sa_mulai_penerimaan
                    'reception_to_pkb': [],      # sa_mulai_penerimaan -> sa_cetak_pkb
                    'pkb_to_service_start': [],  # sa_cetak_pkb -> controller_mulai_servis
                    'service_duration': []       # controller_mulai_servis -> controller_selesai
                }

                for order in orders:
                    # Count active job stops
                    if order.controller_tunggu_part1_mulai and not order.controller_tunggu_part1_selesai:
                        job_stops['tunggu_part1'] += 1
                    if order.controller_tunggu_part2_mulai and not order.controller_tunggu_part2_selesai:
                        job_stops['tunggu_part2'] += 1
                    if order.controller_tunggu_konfirmasi_mulai and not order.controller_tunggu_konfirmasi_selesai:
                        job_stops['tunggu_konfirmasi'] += 1
                    if order.controller_istirahat_shift1_mulai and not order.controller_istirahat_shift1_selesai:
                        job_stops['istirahat'] += 1
                    if order.controller_tunggu_sublet_mulai and not order.controller_tunggu_sublet_selesai:
                        job_stops['tunggu_sublet'] += 1
                    if order.controller_job_stop_lain_mulai and not order.controller_job_stop_lain_selesai:
                        job_stops['job_stop_lain'] += 1

                    # Process overall lead time (from sa_jam_masuk to controller_selesai)
                    if order.sa_jam_masuk and order.controller_selesai:
                        # Calculate overall lead time in hours
                        overall_lead_time = (order.controller_selesai - order.sa_jam_masuk).total_seconds() / 3600
                        
                        # Add to metrics
                        if overall_lead_time > 0:
                            overall_lead_times.append(overall_lead_time)
                            min_overall_lead_time = min(min_overall_lead_time, overall_lead_time)
                            max_overall_lead_time = max(max_overall_lead_time, overall_lead_time)
                            
                            # Update distribution
                            if overall_lead_time < 2:
                                overall_lead_time_distribution['under_2_hours'] += 1
                            elif overall_lead_time < 4:
                                overall_lead_time_distribution['2_to_4_hours'] += 1
                            elif overall_lead_time < 6:
                                overall_lead_time_distribution['4_to_6_hours'] += 1
                            elif overall_lead_time < 8:
                                overall_lead_time_distribution['6_to_8_hours'] += 1
                            else:
                                overall_lead_time_distribution['over_8_hours'] += 1

                    # Process completed job stops
                    def process_job_stop_standards(start, end, key):
                        """Process job stop and classify according to standards"""
                        if start and end and end > start:
                            duration = (end - start).total_seconds() / 60
                            if duration > 0:
                                if key in standards_analysis:
                                    standards_analysis[key]['total_count'] += 1
                                    if duration > JOB_STOP_STANDARDS[key]:
                                        standards_analysis[key]['exceeded_count'] += 1
                                        exceeded_durations[key].append(duration)
                                    else:
                                        standards_analysis[key]['within_count'] += 1
                                        within_durations[key].append(duration)
                                
                                # Update general job stop statistics
                                if key in job_stop_durations:
                                    job_stop_durations[key] += duration
                                    completed_job_stops[key] += 1

                    # Process all job stops with standards
                    if hasattr(order, 'sa_jam_masuk') and hasattr(order, 'sa_mulai_penerimaan'):
                        process_job_stop_standards(order.sa_jam_masuk, order.sa_mulai_penerimaan, 'tunggu_penerimaan')
                    if hasattr(order, 'sa_mulai_penerimaan') and hasattr(order, 'sa_cetak_pkb'):
                        process_job_stop_standards(order.sa_mulai_penerimaan, order.sa_cetak_pkb, 'penerimaan')
                    if hasattr(order, 'sa_cetak_pkb') and hasattr(order, 'controller_mulai_servis'):
                        process_job_stop_standards(order.sa_cetak_pkb, order.controller_mulai_servis, 'tunggu_servis')
                        
                    process_job_stop_standards(order.controller_tunggu_konfirmasi_mulai, 
                                            order.controller_tunggu_konfirmasi_selesai, 
                                            'tunggu_konfirmasi')
                    process_job_stop_standards(order.controller_tunggu_part1_mulai, 
                                            order.controller_tunggu_part1_selesai, 
                                            'tunggu_part1')
                    process_job_stop_standards(order.controller_tunggu_part2_mulai, 
                                            order.controller_tunggu_part2_selesai, 
                                            'tunggu_part2')

                 # Calculate averages
                average_job_stop_durations = {}
                for key in job_stops.keys():
                    average_job_stop_durations[key] = (
                        job_stop_durations[key] / completed_job_stops[key]
                        if completed_job_stops[key] > 0
                        else 0
                    )
                    
                    # Calculate final standards analysis
                    for key in standards_analysis:
                        stats = standards_analysis[key]
                        total = stats['total_count']

                        if total > 0:
                            stats['exceeded_percentage'] = (stats['exceeded_count'] / total) * 100
                            stats['within_percentage'] = (stats['within_count'] / total) * 100

                        if exceeded_durations[key]:
                            stats['avg_exceeded_duration'] = sum(exceeded_durations[key]) / len(exceeded_durations[key])
                        if within_durations[key]:
                            stats['avg_within_duration'] = sum(within_durations[key]) / len(within_durations[key])

                # Calculate service categories
                service_metrics = {
                    'categories': {
                        'maintenance': len(orders.filtered(lambda o: o.service_category == 'maintenance')),
                        'repair': len(orders.filtered(lambda o: o.service_category == 'repair')),
                        'uncategorized': len(orders.filtered(lambda o: not o.service_category))
                    },
                    'subcategories': {
                        'tune_up': len(orders.filtered(lambda o: o.service_subcategory == 'tune_up')),
                        'tune_up_addition': len(orders.filtered(lambda o: o.service_subcategory == 'tune_up_addition')),
                        'periodic_service': len(orders.filtered(lambda o: o.service_subcategory == 'periodic_service')),
                        'periodic_service_addition': len(orders.filtered(lambda o: o.service_subcategory == 'periodic_service_addition')),
                        'general_repair': len(orders.filtered(lambda o: o.service_subcategory == 'general_repair')),
                        'oil_change': len(orders.filtered(lambda o: o.service_subcategory == 'oil_change')),
                        'uncategorized': len(orders.filtered(lambda o: not o.service_subcategory))
                    }
                }

                # Calculate overall lead time average
                avg_overall_lead_time = sum(overall_lead_times) / len(overall_lead_times) if overall_lead_times else 0
                
                # Set min_overall_lead_time to 0 if no data
                if min_overall_lead_time == float('inf'):
                    min_overall_lead_time = 0

                # Log statistics for verification
                _logger.info(f"""
                Period Statistics:
                Total Orders: {len(orders)}
                Completed Orders: {len(completed_orders)}
                Active Orders: {len(active_orders)}
                Job Stops: {job_stops}
                Job Stop Durations: {job_stop_durations}
                Average Job Stop Durations: {average_job_stop_durations}
                Exceeded Standards: { standards_analysis }
                Service Metrics: {service_metrics}
                """)

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
                    'average_job_stop_durations': average_job_stop_durations,
                    'standards_analysis': standards_analysis,
                    'status_breakdown': {
                        'belum_mulai': len(orders.filtered(lambda o: not o.controller_mulai_servis)),
                        'proses': len(active_orders),
                        'selesai': len(completed_orders)
                    },
                    'service_metrics': service_metrics,
                    # Add overall lead time statistics to the result
                    'overall_lead_time': {
                        'average_hours': avg_overall_lead_time,
                        'min_hours': min_overall_lead_time,
                        'max_hours': max_overall_lead_time,
                        'distribution': overall_lead_time_distribution,
                        'formatted': {
                            'average': format_duration(avg_overall_lead_time),
                            'min': format_duration(min_overall_lead_time),
                            'max': format_duration(max_overall_lead_time)
                        },
                        'count': len(overall_lead_times),
                        'total_hours': sum(overall_lead_times) if overall_lead_times else 0
                    },
                    # Add individual lead time breakdown for key service stages
                    'lead_time_breakdown': {
                        'arrival_to_reception': {
                            'average': sum((o.sa_mulai_penerimaan - o.sa_jam_masuk).total_seconds() / 3600 
                                    for o in orders if o.sa_jam_masuk and o.sa_mulai_penerimaan) / 
                                    len([o for o in orders if o.sa_jam_masuk and o.sa_mulai_penerimaan]) 
                                    if any(o.sa_jam_masuk and o.sa_mulai_penerimaan for o in orders) else 0,
                            'formatted': format_duration(sum((o.sa_mulai_penerimaan - o.sa_jam_masuk).total_seconds() / 3600 
                                        for o in orders if o.sa_jam_masuk and o.sa_mulai_penerimaan) / 
                                        len([o for o in orders if o.sa_jam_masuk and o.sa_mulai_penerimaan]) 
                                        if any(o.sa_jam_masuk and o.sa_mulai_penerimaan for o in orders) else 0)
                        },
                        'reception_to_pkb': {
                            'average': sum((o.sa_cetak_pkb - o.sa_mulai_penerimaan).total_seconds() / 3600 
                                    for o in orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb) / 
                                    len([o for o in orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb]) 
                                    if any(o.sa_mulai_penerimaan and o.sa_cetak_pkb for o in orders) else 0,
                            'formatted': format_duration(sum((o.sa_cetak_pkb - o.sa_mulai_penerimaan).total_seconds() / 3600 
                                        for o in orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb) / 
                                        len([o for o in orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb]) 
                                        if any(o.sa_mulai_penerimaan and o.sa_cetak_pkb for o in orders) else 0)
                        },
                        'pkb_to_service_start': {
                            'average': sum((o.controller_mulai_servis - o.sa_cetak_pkb).total_seconds() / 3600 
                                    for o in orders if o.sa_cetak_pkb and o.controller_mulai_servis) / 
                                    len([o for o in orders if o.sa_cetak_pkb and o.controller_mulai_servis]) 
                                    if any(o.sa_cetak_pkb and o.controller_mulai_servis for o in orders) else 0,
                            'formatted': format_duration(sum((o.controller_mulai_servis - o.sa_cetak_pkb).total_seconds() / 3600 
                                        for o in orders if o.sa_cetak_pkb and o.controller_mulai_servis) / 
                                        len([o for o in orders if o.sa_cetak_pkb and o.controller_mulai_servis]) 
                                        if any(o.sa_cetak_pkb and o.controller_mulai_servis for o in orders) else 0)
                        },
                        'service_duration': {
                            'average': sum((o.controller_selesai - o.controller_mulai_servis).total_seconds() / 3600 
                                    for o in orders if o.controller_mulai_servis and o.controller_selesai) / 
                                    len([o for o in orders if o.controller_mulai_servis and o.controller_selesai]) 
                                    if any(o.controller_mulai_servis and o.controller_selesai for o in orders) else 0,
                            'formatted': format_duration(sum((o.controller_selesai - o.controller_mulai_servis).total_seconds() / 3600 
                                        for o in orders if o.controller_mulai_servis and o.controller_selesai) / 
                                        len([o for o in orders if o.controller_mulai_servis and o.controller_selesai]) 
                                        if any(o.controller_mulai_servis and o.controller_selesai for o in orders) else 0)
                        },
                        'total_service_process': {
                            'average': avg_overall_lead_time,
                            'formatted': format_duration(avg_overall_lead_time),
                            'description': 'Waktu total dari kedatangan sampai selesai servis (sa_jam_masuk hingga controller_selesai)'
                        }
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
            
            # Helper function to format duration
            def format_duration(hours):
                """Format hours to readable string (e.g., "2j 30m")"""
                if not hours:
                    return "0j 0m"
                    
                hours_int = int(hours)
                minutes = int((hours - hours_int) * 60)
                
                return f"{hours_int}j {minutes}m"

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

            # Calculate overall lead time metrics for the summary on top
            completed_with_full_times = orders.filtered(lambda o: o.sa_jam_masuk and o.controller_selesai)
            overall_lead_time_summary = {
                'count': len(completed_with_full_times),
                'average_hours': 0,
                'min_hours': 0,
                'max_hours': 0,
                'distribution': {
                    'under_2_hours': 0,
                    '2_to_4_hours': 0,
                    '4_to_6_hours': 0, 
                    '6_to_8_hours': 0,
                    'over_8_hours': 0
                }
            }
            
            if completed_with_full_times:
                # Calculate lead times
                lead_times = [(o.controller_selesai - o.sa_jam_masuk).total_seconds() / 3600 
                            for o in completed_with_full_times]
                
                # Calculate averages and ranges
                overall_lead_time_summary['average_hours'] = sum(lead_times) / len(lead_times)
                overall_lead_time_summary['min_hours'] = min(lead_times) if lead_times else 0
                overall_lead_time_summary['max_hours'] = max(lead_times) if lead_times else 0
                
                # Calculate distribution
                for lt in lead_times:
                    if lt < 2:
                        overall_lead_time_summary['distribution']['under_2_hours'] += 1
                    elif lt < 4:
                        overall_lead_time_summary['distribution']['2_to_4_hours'] += 1
                    elif lt < 6:
                        overall_lead_time_summary['distribution']['4_to_6_hours'] += 1
                    elif lt < 8:
                        overall_lead_time_summary['distribution']['6_to_8_hours'] += 1
                    else:
                        overall_lead_time_summary['distribution']['over_8_hours'] += 1
                
            # Add formatted values
            overall_lead_time_summary['formatted'] = {
                'average': format_duration(overall_lead_time_summary['average_hours']),
                'min': format_duration(overall_lead_time_summary['min_hours']),
                'max': format_duration(overall_lead_time_summary['max_hours'])
            }

            # Calculate lead time stages distribution
            lead_time_stages = {
                'not_started': 0,
                'check_in': 0, 
                'reception': 0,
                'pkb_printed': 0,
                'waiting_service': 0,
                'in_service': 0,
                'service_done': 0
            }
            
            for order in orders:
                if not order.sa_jam_masuk:
                    lead_time_stages['not_started'] += 1
                elif not order.sa_mulai_penerimaan:
                    lead_time_stages['check_in'] += 1
                elif not order.sa_cetak_pkb:
                    lead_time_stages['reception'] += 1
                elif not order.controller_mulai_servis:
                    lead_time_stages['waiting_service'] += 1
                elif not order.controller_selesai:
                    lead_time_stages['in_service'] += 1
                else:
                    lead_time_stages['service_done'] += 1

            # Get service category and subcategory counts with uncategorized
            service_category_counts = {
                'maintenance': len(orders.filtered(lambda o: o.service_category == 'maintenance')),
                'repair': len(orders.filtered(lambda o: o.service_category == 'repair')),
                'uncategorized': len(orders.filtered(lambda o: not o.service_category))
            }
            
            service_subcategory_counts = {
                'tune_up': len(orders.filtered(lambda o: o.service_subcategory == 'tune_up')),
                'tune_up_addition': len(orders.filtered(lambda o: o.service_subcategory == 'tune_up_addition')),
                'periodic_service': len(orders.filtered(lambda o: o.service_subcategory == 'periodic_service')),
                'periodic_service_addition': len(orders.filtered(lambda o: o.service_subcategory == 'periodic_service_addition')),
                'general_repair': len(orders.filtered(lambda o: o.service_subcategory == 'general_repair')),
                'oil_change': len(orders.filtered(lambda o: o.service_subcategory == 'oil_change')),
                'uncategorized': len(orders.filtered(lambda o: not o.service_subcategory))
            }

            # Compile complete statistics
            stats = {
                'current_time': self._format_local_datetime(now),
                'date_range': {
                    'start': date_range_start,
                    'end': date_range_end
                },
                # Add lead time summary at the top level for easy access
                'lead_time_summary': {
                    'total_service_process': overall_lead_time_summary,
                    'process_breakdown': {
                        'arrival_to_reception': {
                            'average_hours': sum((o.sa_mulai_penerimaan - o.sa_jam_masuk).total_seconds() / 3600 
                                        for o in orders if o.sa_jam_masuk and o.sa_mulai_penerimaan) / 
                                        len([o for o in orders if o.sa_jam_masuk and o.sa_mulai_penerimaan]) 
                                        if any(o.sa_jam_masuk and o.sa_mulai_penerimaan for o in orders) else 0,
                            'formatted': format_duration(sum((o.sa_mulai_penerimaan - o.sa_jam_masuk).total_seconds() / 3600 
                                        for o in orders if o.sa_jam_masuk and o.sa_mulai_penerimaan) / 
                                        len([o for o in orders if o.sa_jam_masuk and o.sa_mulai_penerimaan]) 
                                        if any(o.sa_jam_masuk and o.sa_mulai_penerimaan for o in orders) else 0),
                            'name': 'Kedatangan ke Penerimaan'
                        },
                        'reception_to_pkb': {
                            'average_hours': sum((o.sa_cetak_pkb - o.sa_mulai_penerimaan).total_seconds() / 3600 
                                        for o in orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb) / 
                                        len([o for o in orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb]) 
                                        if any(o.sa_mulai_penerimaan and o.sa_cetak_pkb for o in orders) else 0,
                            'formatted': format_duration(sum((o.sa_cetak_pkb - o.sa_mulai_penerimaan).total_seconds() / 3600 
                                        for o in orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb) / 
                                        len([o for o in orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb]) 
                                        if any(o.sa_mulai_penerimaan and o.sa_cetak_pkb for o in orders) else 0),
                            'name': 'Penerimaan ke Cetak PKB'
                        },
                        'pkb_to_service_start': {
                            'average_hours': sum((o.controller_mulai_servis - o.sa_cetak_pkb).total_seconds() / 3600 
                                        for o in orders if o.sa_cetak_pkb and o.controller_mulai_servis) / 
                                        len([o for o in orders if o.sa_cetak_pkb and o.controller_mulai_servis]) 
                                        if any(o.sa_cetak_pkb and o.controller_mulai_servis for o in orders) else 0,
                            'formatted': format_duration(sum((o.controller_mulai_servis - o.sa_cetak_pkb).total_seconds() / 3600 
                                        for o in orders if o.sa_cetak_pkb and o.controller_mulai_servis) / 
                                        len([o for o in orders if o.sa_cetak_pkb and o.controller_mulai_servis]) 
                                        if any(o.sa_cetak_pkb and o.controller_mulai_servis for o in orders) else 0),
                            'name': 'Cetak PKB ke Mulai Servis'
                        },
                        'service_duration': {
                            'average_hours': sum((o.controller_selesai - o.controller_mulai_servis).total_seconds() / 3600 
                                        for o in orders if o.controller_mulai_servis and o.controller_selesai) / 
                                        len([o for o in orders if o.controller_mulai_servis and o.controller_selesai]) 
                                        if any(o.controller_mulai_servis and o.controller_selesai for o in orders) else 0,
                            'formatted': format_duration(sum((o.controller_selesai - o.controller_mulai_servis).total_seconds() / 3600 
                                        for o in orders if o.controller_mulai_servis and o.controller_selesai) / 
                                        len([o for o in orders if o.controller_mulai_servis and o.controller_selesai]) 
                                        if any(o.controller_mulai_servis and o.controller_selesai for o in orders) else 0),
                            'name': 'Durasi Servis Aktif'
                        }
                    }
                },
                'service_category': service_category_counts,
                'service_subcategory': service_subcategory_counts,
                'overall': calculate_period_stats(orders),
                'daily_breakdown': calculate_daily_stats(start_utc, end_utc, orders),
                'hourly_distribution': get_hourly_distribution(orders),
                'lead_time_stages': lead_time_stages,
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

    def _build_service_timeline(self, order):
        """
        Build comprehensive service timeline from sa_jam_masuk to controller_selesai
        Returns timeline events with durations and status
        """
        timeline = []
        
        # Standards for validating durations (in minutes)
        duration_standards = {
            'tunggu_penerimaan': 15,  # Tunggu dari jam masuk ke mulai penerimaan
            'penerimaan': 15,         # Proses penerimaan sampai cetak PKB
            'tunggu_servis': 15,      # Tunggu dari PKB ke mulai servis
            'tunggu_konfirmasi': 40,  # Waktu tunggu konfirmasi
            'tunggu_part': 45         # Waktu tunggu part
        }

        def calculate_duration(start, end):
            """Calculate duration in minutes between two timestamps"""
            if start and end and end > start:
                return (end - start).total_seconds() / 60
            return 0

        def add_timeline_event(event_type, title, start_time, end_time=None, standard_time=None, notes=None):
            """Add event to timeline with duration analysis"""
            if not start_time:
                return

            duration = calculate_duration(start_time, end_time) if end_time else 0
            exceeded = False
            exceeded_by = 0

            if standard_time and end_time:
                exceeded = duration > standard_time
                exceeded_by = max(0, duration - standard_time)

            event = {
                'type': event_type,
                'title': title,
                'start_time': self._format_local_datetime(start_time),
                'end_time': self._format_local_datetime(end_time) if end_time else None,
                'duration_minutes': duration,
                'duration_text': f"{int(duration)} menit" if duration else None,
                'status': 'completed' if end_time else 'in_progress',
                'notes': notes
            }

            if standard_time:
                event.update({
                    'standard_time': standard_time,
                    'exceeded': exceeded,
                    'exceeded_by': exceeded_by,
                    'exceeded_text': f"{int(exceeded_by)} menit melebihi standar" if exceeded else None
                })

            timeline.append(event)

        # 1. Check In / Jam Masuk
        add_timeline_event(
            'check_in',
            'Customer Check In',
            order.sa_jam_masuk,
            order.sa_mulai_penerimaan,
            duration_standards['tunggu_penerimaan']
        )

        # 2. Penerimaan oleh Service Advisor
        add_timeline_event(
            'reception',
            'Penerimaan oleh Service Advisor',
            order.sa_mulai_penerimaan,
            order.sa_cetak_pkb,
            duration_standards['penerimaan']
        )

        # 3. Cetak PKB
        add_timeline_event(
            'pkb',
            'PKB Dicetak',
            order.sa_cetak_pkb,
            order.controller_mulai_servis,
            duration_standards['tunggu_servis']
        )

        # 4. Mulai Servis
        if order.controller_mulai_servis:
            add_timeline_event(
                'service_start',
                'Mulai Servis',
                order.controller_mulai_servis
            )

            # Track job stops between mulai and selesai servis
            # 4a. Tunggu Konfirmasi
            if order.controller_tunggu_konfirmasi_mulai:
                add_timeline_event(
                    'tunggu_konfirmasi',
                    'Tunggu Konfirmasi Customer',
                    order.controller_tunggu_konfirmasi_mulai,
                    order.controller_tunggu_konfirmasi_selesai,
                    duration_standards['tunggu_konfirmasi']
                )

            # 4b. Tunggu Part 1
            if order.controller_tunggu_part1_mulai:
                add_timeline_event(
                    'tunggu_part1',
                    'Tunggu Part 1',
                    order.controller_tunggu_part1_mulai,
                    order.controller_tunggu_part1_selesai,
                    duration_standards['tunggu_part']
                )

            # 4c. Tunggu Part 2
            if order.controller_tunggu_part2_mulai:
                add_timeline_event(
                    'tunggu_part2',
                    'Tunggu Part 2',
                    order.controller_tunggu_part2_mulai,
                    order.controller_tunggu_part2_selesai,
                    duration_standards['tunggu_part']
                )

            # 4d. Istirahat
            if order.controller_istirahat_shift1_mulai:
                add_timeline_event(
                    'istirahat',
                    'Istirahat',
                    order.controller_istirahat_shift1_mulai,
                    order.controller_istirahat_shift1_selesai
                )

            # 4e. Tunggu Sublet
            if order.controller_tunggu_sublet_mulai:
                add_timeline_event(
                    'tunggu_sublet',
                    'Tunggu Sublet',
                    order.controller_tunggu_sublet_mulai,
                    order.controller_tunggu_sublet_selesai
                )

            # 4f. Job Stop Lain
            if order.controller_job_stop_lain_mulai:
                add_timeline_event(
                    'job_stop_lain',
                    'Job Stop Lain',
                    order.controller_job_stop_lain_mulai,
                    order.controller_job_stop_lain_selesai,
                    notes=order.job_stop_lain_keterangan
                )

        # 5. Selesai Servis
        if order.controller_selesai:
            add_timeline_event(
                'service_complete',
                'Selesai Servis',
                order.controller_selesai
            )

        # Calculate additional metrics
        total_duration = calculate_duration(order.sa_jam_masuk, order.controller_selesai)
        active_duration = total_duration
        delay_duration = 0

        # Calculate total delay time from job stops
        job_stops = ['tunggu_konfirmasi', 'tunggu_part1', 'tunggu_part2', 'istirahat', 'tunggu_sublet', 'job_stop_lain']
        for event in timeline:
            if event['type'] in job_stops and event['duration_minutes']:
                delay_duration += event['duration_minutes']

        # Calculate active service time (excluding delays)
        if total_duration > 0:
            active_duration = max(0, total_duration - delay_duration)

        metrics = {
            'total_duration': total_duration,
            'total_duration_text': f"{int(total_duration)} menit",
            'active_duration': active_duration,
            'active_duration_text': f"{int(active_duration)} menit",
            'delay_duration': delay_duration,
            'delay_duration_text': f"{int(delay_duration)} menit",
            'is_completed': bool(order.controller_selesai),
            'has_delays': delay_duration > 0
        }

        # Sort timeline by start_time
        timeline.sort(key=lambda x: x['start_time'] if x['start_time'] else '')

        return {
            'events': timeline,
            'metrics': metrics
        }

    # Tambahkan fungsi helper untuk endpoint report detail
    def _get_service_progress(self, order):
        """Calculate service progress from sa_jam_masuk to controller_selesai"""
        if not order.sa_jam_masuk:
            return 0

        # Define progress weights for each stage
        stages = [
            ('sa_jam_masuk', 10),             # Check in: 10%
            ('sa_mulai_penerimaan', 15),      # Start reception: 15%
            ('sa_cetak_pkb', 15),             # Print PKB: 15%
            ('controller_mulai_servis', 30),   # Start service: 30%
            ('controller_selesai', 30)         # Complete service: 30%
        ]

        # Calculate completed stages
        progress = 0
        for field, weight in stages:
            if getattr(order, field):
                progress += weight

        # Adjust for active job stops
        active_job_stops = 0
        if order.controller_tunggu_konfirmasi_mulai and not order.controller_tunggu_konfirmasi_selesai:
            active_job_stops += 1
        if order.controller_tunggu_part1_mulai and not order.controller_tunggu_part1_selesai:
            active_job_stops += 1
        if order.controller_tunggu_part2_mulai and not order.controller_tunggu_part2_selesai:
            active_job_stops += 1
        if order.controller_istirahat_shift1_mulai and not order.controller_istirahat_shift1_selesai:
            active_job_stops += 1
        if order.controller_tunggu_sublet_mulai and not order.controller_tunggu_sublet_selesai:
            active_job_stops += 1
        if order.controller_job_stop_lain_mulai and not order.controller_job_stop_lain_selesai:
            active_job_stops += 1

        # Reduce progress by 5% for each active job stop
        progress = max(0, progress - (active_job_stops * 5))

        return min(progress, 100)

    def _calculate_comparison_stats(self, current_orders, date_range='month'):
        """Calculate stats with comparison to previous period"""
        try:
            # Get current period stats
            current_stats = {
                'total_services': len(current_orders),
                'avg_service_time': 0,
                'completion_rate': 0,
                'customer_satisfaction': 0
            }
            
            completed_orders = current_orders.filtered(lambda o: o.controller_selesai)
            
            # Calculate average service time
            if completed_orders:
                total_time = sum((o.controller_selesai - o.controller_mulai_servis).total_seconds() / 3600 
                            for o in completed_orders if o.controller_mulai_servis)
                current_stats['avg_service_time'] = total_time / len(completed_orders)
            
            # Calculate completion rate
            if current_orders:
                current_stats['completion_rate'] = (len(completed_orders) / len(current_orders)) * 100
            
            # Calculate customer satisfaction (assuming there's a rating field)
            satisfied_orders = completed_orders.filtered(lambda o: getattr(o, 'customer_rating', 0) >= 4)
            if completed_orders:
                current_stats['customer_satisfaction'] = (len(satisfied_orders) / len(completed_orders)) * 100

            # Get previous period domain
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            if date_range == 'month':
                # Current month start
                current_start = now.replace(day=1)
                # Previous month
                if now.month == 1:
                    prev_start = now.replace(year=now.year-1, month=12, day=1)
                else:
                    prev_start = now.replace(month=now.month-1, day=1)
            elif date_range == 'week':
                # Current week start
                current_start = now - timedelta(days=now.weekday())
                # Previous week
                prev_start = current_start - timedelta(days=7)
            else:  # day
                current_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                prev_start = current_start - timedelta(days=1)

            # Convert to UTC for database query
            current_start_utc = current_start.astimezone(pytz.UTC)
            prev_start_utc = prev_start.astimezone(pytz.UTC)
            
            # Get previous period orders
            prev_domain = [
                ('sa_cetak_pkb', '!=', False),
                ('sa_jam_masuk', '>=', prev_start_utc),
                ('sa_jam_masuk', '<', current_start_utc)
            ]
            
            previous_orders = request.env['sale.order'].search(prev_domain)
            prev_completed = previous_orders.filtered(lambda o: o.controller_selesai)
            
            # Calculate previous period stats
            prev_stats = {
                'total_services': len(previous_orders),
                'avg_service_time': 0,
                'completion_rate': 0,
                'customer_satisfaction': 0
            }
            
            if prev_completed:
                # Avg service time
                prev_total_time = sum((o.controller_selesai - o.controller_mulai_servis).total_seconds() / 3600 
                                    for o in prev_completed if o.controller_mulai_servis)
                prev_stats['avg_service_time'] = prev_total_time / len(prev_completed)
                
                # Customer satisfaction
                prev_satisfied = prev_completed.filtered(lambda o: getattr(o, 'customer_rating', 0) >= 4)
                prev_stats['customer_satisfaction'] = (len(prev_satisfied) / len(prev_completed)) * 100
            
            if previous_orders:
                prev_stats['completion_rate'] = (len(prev_completed) / len(previous_orders)) * 100

            # Calculate changes
            changes = {
                'total_services': self._calculate_percentage_change(
                    prev_stats['total_services'], 
                    current_stats['total_services']
                ),
                'avg_service_time': self._calculate_percentage_change(
                    prev_stats['avg_service_time'], 
                    current_stats['avg_service_time']
                ),
                'completion_rate': self._calculate_percentage_change(
                    prev_stats['completion_rate'], 
                    current_stats['completion_rate']
                ),
                'customer_satisfaction': self._calculate_percentage_change(
                    prev_stats['customer_satisfaction'], 
                    current_stats['customer_satisfaction']
                )
            }

            # Return formatted stats
            return {
                'total_services': {
                    'value': current_stats['total_services'],
                    'change': changes['total_services'],
                    'trend': 'up' if changes['total_services'] > 0 else 'down',
                    'comparison': 'better' if changes['total_services'] > 0 else 'worse'
                },
                'avg_service_time': {
                    'value': f"{current_stats['avg_service_time']:.1f}h",
                    'change': changes['avg_service_time'],
                    'trend': 'down' if changes['avg_service_time'] < 0 else 'up',
                    'comparison': 'better' if changes['avg_service_time'] < 0 else 'worse'
                },
                'completion_rate': {
                    'value': f"{current_stats['completion_rate']:.1f}%",
                    'change': changes['completion_rate'],
                    'trend': 'up' if changes['completion_rate'] > 0 else 'down',
                    'comparison': 'better' if changes['completion_rate'] > 0 else 'worse'
                },
                'customer_satisfaction': {
                    'value': f"{current_stats['customer_satisfaction']:.1f}%",
                    'change': changes['customer_satisfaction'],
                    'trend': 'up' if changes['customer_satisfaction'] > 0 else 'down',
                    'comparison': 'better' if changes['customer_satisfaction'] > 0 else 'worse'
                }
            }

        except Exception as e:
            _logger.error(f"Error calculating comparison stats: {str(e)}", exc_info=True)
            return {
                'total_services': {'value': 0, 'change': 0, 'trend': 'neutral', 'comparison': 'same'},
                'avg_service_time': {'value': '0h', 'change': 0, 'trend': 'neutral', 'comparison': 'same'},
                'completion_rate': {'value': '0%', 'change': 0, 'trend': 'neutral', 'comparison': 'same'},
                'customer_satisfaction': {'value': '0%', 'change': 0, 'trend': 'neutral', 'comparison': 'same'}
            }

    def _calculate_percentage_change(self, old_value, new_value):
        """Calculate percentage change between two values"""
        if old_value == 0:
            return 100 if new_value > 0 else 0
        return ((new_value - old_value) / old_value) * 100

    def _get_previous_period_stats(self, date_range='month'):
        """Get statistics from previous period for comparison"""
        try:
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Calculate date ranges based on period
            if date_range == 'month':
                if now.month == 1:
                    prev_start = now.replace(year=now.year-1, month=12, day=1)
                    prev_end = now.replace(year=now.year, month=1, day=1)
                else:
                    prev_start = now.replace(month=now.month-1, day=1)
                    prev_end = now.replace(month=now.month, day=1)
            elif date_range == 'week':
                week_start = now - timedelta(days=now.weekday())
                prev_start = week_start - timedelta(days=7)
                prev_end = week_start
            else:  # day
                prev_start = now - timedelta(days=1)
                prev_end = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Convert to UTC for database query
            prev_start_utc = prev_start.astimezone(pytz.UTC).replace(tzinfo=None)
            prev_end_utc = prev_end.astimezone(pytz.UTC).replace(tzinfo=None)

            # Get orders from previous period
            domain = [
                ('sa_cetak_pkb', '!=', False),
                ('sa_jam_masuk', '>=', prev_start_utc),
                ('sa_jam_masuk', '<', prev_end_utc)
            ]
            
            orders = request.env['sale.order'].search(domain)
            completed_orders = orders.filtered(lambda o: o.controller_selesai)
            
            # Calculate basic stats
            total_orders = len(orders)
            completion_rate = (len(completed_orders) / total_orders * 100) if total_orders > 0 else 0
            
            # Calculate average service time
            service_times = []
            wait_times = []
            for order in completed_orders:
                if order.controller_mulai_servis and order.controller_selesai:
                    service_time = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 3600
                    service_times.append(service_time)
                
                if order.sa_jam_masuk and order.controller_mulai_servis:
                    wait_time = (order.controller_mulai_servis - order.sa_jam_masuk).total_seconds() / 3600
                    wait_times.append(wait_time)

            avg_service_time = sum(service_times) / len(service_times) if service_times else 0
            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
            
            # Calculate delay rate
            delayed_orders = completed_orders.filtered(lambda o: 
                o.controller_estimasi_selesai and o.controller_selesai > o.controller_estimasi_selesai
            )
            delay_rate = (len(delayed_orders) / len(completed_orders) * 100) if completed_orders else 0

            return {
                'total_orders': total_orders,
                'completion_rate': completion_rate,
                'avg_service_time': avg_service_time,
                'avg_wait_time': avg_wait_time,
                'delay_rate': delay_rate
            }

        except Exception as e:
            _logger.error(f"Error getting previous period stats: {str(e)}", exc_info=True)
            return {}

    def _calculate_service_statistics(self, orders, date_range='month'):
        """Calculate comprehensive service statistics"""
        try:
            # Basic counts
            total_orders = len(orders)
            completed_orders = orders.filtered(lambda o: o.controller_selesai)
            active_orders = orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai)
            delayed_orders = orders.filtered(lambda o: 
                o.controller_estimasi_selesai and o.controller_selesai and 
                o.controller_selesai > o.controller_estimasi_selesai
            )

            # Service time calculations
            service_times = []
            wait_times = []
            for order in completed_orders:
                if order.controller_mulai_servis and order.controller_selesai:
                    service_time = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 3600
                    service_times.append(service_time)
                
                if order.sa_jam_masuk and order.controller_mulai_servis:
                    wait_time = (order.controller_mulai_servis - order.sa_jam_masuk).total_seconds() / 3600
                    wait_times.append(wait_time)

            # Calculate percentages and averages
            completion_rate = (len(completed_orders) / total_orders * 100) if total_orders > 0 else 0
            avg_service_time = sum(service_times) / len(service_times) if service_times else 0
            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
            delay_rate = (len(delayed_orders) / len(completed_orders) * 100) if completed_orders else 0

            # Get previous period stats for comparison
            prev_stats = self._get_previous_period_stats(date_range)

            # Calculate on time completion
            completed_with_estimate = completed_orders.filtered(lambda o: o.controller_estimasi_selesai)
            on_time_orders = completed_with_estimate.filtered(lambda o: 
                o.controller_selesai and o.controller_estimasi_selesai and 
                o.controller_selesai <= o.controller_estimasi_selesai
            )
            on_time_rate = (len(on_time_orders) / len(completed_with_estimate) * 100) if completed_with_estimate else 0

            # Build main stats with comparison
            main_stats = {
                'service_volume': {
                    'value': total_orders,
                    'change': self._calculate_percentage_change(prev_stats.get('total_orders', 0), total_orders),
                    'label': 'Total Services'
                },
                'completion': {
                    'value': completion_rate,
                    'change': self._calculate_percentage_change(prev_stats.get('completion_rate', 0), completion_rate),
                    'label': 'Completion Rate',
                    'format': 'percentage'
                },
                'service_time': {
                    'value': avg_service_time,
                    'change': self._calculate_percentage_change(prev_stats.get('avg_service_time', 0), avg_service_time),
                    'label': 'Average Service Time',
                    'format': 'hours'
                },
                'wait_time': {
                    'value': avg_wait_time,
                    'change': self._calculate_percentage_change(prev_stats.get('avg_wait_time', 0), avg_wait_time),
                    'label': 'Average Wait Time',
                    'format': 'hours'
                },
                    'on_time_completion': {          # Metrik baru
                    'value': on_time_rate,
                    'change': self._calculate_percentage_change(prev_stats.get('on_time_rate', 0), on_time_rate),
                    'label': 'On Time Completion',
                    'format': 'percentage'
                }
            }

            # Build additional metrics
            additional_metrics = {
                'active_orders': len(active_orders),
                'job_stops': {
                    'tunggu_part': len(orders.filtered(lambda o: 
                        (o.controller_tunggu_part1_mulai and not o.controller_tunggu_part1_selesai) or
                        (o.controller_tunggu_part2_mulai and not o.controller_tunggu_part2_selesai)
                    )),
                    'tunggu_konfirmasi': len(orders.filtered(lambda o: 
                        o.controller_tunggu_konfirmasi_mulai and not o.controller_tunggu_konfirmasi_selesai
                    ))
                },
                'service_types': {
                    'maintenance': len(orders.filtered(lambda o: o.service_category == 'maintenance')),
                    'repair': len(orders.filtered(lambda o: o.service_category == 'repair')),
                    'uncategorized': len(orders.filtered(lambda o: not o.service_category))
                }
            }

             # Tambahkan detail on time completion ke additional metrics
            additional_metrics.update({
                'completion_details': {
                    'total_completed': len(completed_orders),
                    'with_estimate': len(completed_with_estimate),
                    'on_time': len(on_time_orders),
                    'delayed': len(completed_with_estimate) - len(on_time_orders)
                }
            })

            return {
                'main_stats': main_stats,
                'additional_metrics': additional_metrics,
                'date_range': {
                    'start': self._format_local_datetime(orders[0].create_date) if orders else None,
                    'end': self._format_local_datetime(fields.Datetime.now())
                }
            }

        except Exception as e:
            _logger.error(f"Error calculating service statistics: {str(e)}", exc_info=True)
            return {
                'main_stats': {},
                'additional_metrics': {},
                'date_range': {}
            }

    def _build_date_domain(self, date_range, start_date=None, end_date=None):
        """Build domain for date filtering"""
        try:
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            if date_range == 'today':
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
            elif date_range == 'week':
                start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=7)
            elif date_range == 'month':
                start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if now.month == 12:
                    end = now.replace(year=now.year + 1, month=1, day=1)
                else:
                    end = now.replace(month=now.month + 1, day=1)
            elif date_range == 'custom' and start_date and end_date:
                start = datetime.strptime(f"{start_date} 00:00:00", '%Y-%m-%d %H:%M:%S')
                end = datetime.strptime(f"{end_date} 23:59:59", '%Y-%m-%d %H:%M:%S')
                # Convert to timezone aware
                start = tz.localize(start)
                end = tz.localize(end)
            else:
                return []

            # Convert to UTC for database query
            start_utc = start.astimezone(pytz.UTC).replace(tzinfo=None)
            end_utc = end.astimezone(pytz.UTC).replace(tzinfo=None)

            return [
                ('sa_jam_masuk', '>=', start_utc),
                ('sa_jam_masuk', '<', end_utc)
            ]

        except Exception as e:
            _logger.error(f"Error building date domain: {str(e)}", exc_info=True)
            return []
        
    def _calculate_lead_time_summary(self, orders):
        """Calculate summary statistics for various lead time metrics"""
        try:
            if not orders:
                return {}
                
            # Initialize counters and accumulators
            summary = {
                'tunggu_penerimaan': {
                    'total_hours': 0,
                    'count': 0,
                    'avg_hours': 0,
                    'max_hours': 0,
                    'min_hours': float('inf'),
                    'standard_hours': 0.25,  # 15 minutes in hours
                    'exceeded_count': 0,
                    'exceeded_percentage': 0
                },
                'penerimaan': {
                    'total_hours': 0,
                    'count': 0,
                    'avg_hours': 0,
                    'max_hours': 0,
                    'min_hours': float('inf'),
                    'standard_hours': 0.25,  # 15 minutes in hours
                    'exceeded_count': 0,
                    'exceeded_percentage': 0
                },
                'tunggu_servis': {
                    'total_hours': 0,
                    'count': 0,
                    'avg_hours': 0,
                    'max_hours': 0,
                    'min_hours': float('inf'),
                    'standard_hours': 0.25,  # 15 minutes in hours
                    'exceeded_count': 0,
                    'exceeded_percentage': 0
                },
                'tunggu_konfirmasi': {
                    'total_hours': 0,
                    'count': 0,
                    'avg_hours': 0,
                    'max_hours': 0,
                    'min_hours': float('inf'),
                    'standard_hours': 0.67,  # 40 minutes in hours
                    'exceeded_count': 0,
                    'exceeded_percentage': 0
                },
                'tunggu_part': {
                    'total_hours': 0,
                    'count': 0,
                    'avg_hours': 0,
                    'max_hours': 0,
                    'min_hours': float('inf'),
                    'standard_hours': 0.75,  # 45 minutes in hours
                    'exceeded_count': 0,
                    'exceeded_percentage': 0
                },
                'servis_aktif': {
                    'total_hours': 0,
                    'count': 0,
                    'avg_hours': 0,
                    'max_hours': 0,
                    'min_hours': float('inf'),
                    'distribution': {
                        'under_1_hour': 0,
                        '1_to_2_hours': 0,
                        '2_to_3_hours': 0,
                        '3_to_4_hours': 0,
                        'over_4_hours': 0
                    }
                },
                'total_servis': {
                    'total_hours': 0,
                    'count': 0,
                    'avg_hours': 0,
                    'max_hours': 0,
                    'min_hours': float('inf'),
                    'distribution': {
                        'under_2_hours': 0,
                        '2_to_4_hours': 0,
                        '4_to_6_hours': 0,
                        '6_to_8_hours': 0,
                        'over_8_hours': 0
                    }
                }
            }
            
            # Process each order to collect lead time data
            for order in orders:
                # Tunggu penerimaan (from sa_jam_masuk to sa_mulai_penerimaan)
                if order.lead_time_tunggu_penerimaan > 0:
                    lead_time = order.lead_time_tunggu_penerimaan
                    summary['tunggu_penerimaan']['total_hours'] += lead_time
                    summary['tunggu_penerimaan']['count'] += 1
                    summary['tunggu_penerimaan']['max_hours'] = max(summary['tunggu_penerimaan']['max_hours'], lead_time)
                    summary['tunggu_penerimaan']['min_hours'] = min(summary['tunggu_penerimaan']['min_hours'], lead_time)
                    if lead_time > summary['tunggu_penerimaan']['standard_hours']:
                        summary['tunggu_penerimaan']['exceeded_count'] += 1
                
                # Penerimaan (from sa_mulai_penerimaan to sa_cetak_pkb)
                if order.lead_time_penerimaan > 0:
                    lead_time = order.lead_time_penerimaan
                    summary['penerimaan']['total_hours'] += lead_time
                    summary['penerimaan']['count'] += 1
                    summary['penerimaan']['max_hours'] = max(summary['penerimaan']['max_hours'], lead_time)
                    summary['penerimaan']['min_hours'] = min(summary['penerimaan']['min_hours'], lead_time)
                    if lead_time > summary['penerimaan']['standard_hours']:
                        summary['penerimaan']['exceeded_count'] += 1
                
                # Tunggu servis (from sa_cetak_pkb to controller_mulai_servis)
                if order.lead_time_tunggu_servis > 0:
                    lead_time = order.lead_time_tunggu_servis
                    summary['tunggu_servis']['total_hours'] += lead_time
                    summary['tunggu_servis']['count'] += 1
                    summary['tunggu_servis']['max_hours'] = max(summary['tunggu_servis']['max_hours'], lead_time)
                    summary['tunggu_servis']['min_hours'] = min(summary['tunggu_servis']['min_hours'], lead_time)
                    if lead_time > summary['tunggu_servis']['standard_hours']:
                        summary['tunggu_servis']['exceeded_count'] += 1
                
                # Tunggu konfirmasi
                if order.lead_time_tunggu_konfirmasi > 0:
                    lead_time = order.lead_time_tunggu_konfirmasi
                    summary['tunggu_konfirmasi']['total_hours'] += lead_time
                    summary['tunggu_konfirmasi']['count'] += 1
                    summary['tunggu_konfirmasi']['max_hours'] = max(summary['tunggu_konfirmasi']['max_hours'], lead_time)
                    summary['tunggu_konfirmasi']['min_hours'] = min(summary['tunggu_konfirmasi']['min_hours'], lead_time)
                    if lead_time > summary['tunggu_konfirmasi']['standard_hours']:
                        summary['tunggu_konfirmasi']['exceeded_count'] += 1
                
                # Tunggu part (combining part1 and part2)
                part_lead_time = (order.lead_time_tunggu_part1 or 0) + (order.lead_time_tunggu_part2 or 0)
                if part_lead_time > 0:
                    summary['tunggu_part']['total_hours'] += part_lead_time
                    summary['tunggu_part']['count'] += 1
                    summary['tunggu_part']['max_hours'] = max(summary['tunggu_part']['max_hours'], part_lead_time)
                    summary['tunggu_part']['min_hours'] = min(summary['tunggu_part']['min_hours'], part_lead_time)
                    if part_lead_time > summary['tunggu_part']['standard_hours']:
                        summary['tunggu_part']['exceeded_count'] += 1
                
                # Servis aktif (using lead_time_servis)
                if order.lead_time_servis > 0:
                    lead_time = order.lead_time_servis
                    summary['servis_aktif']['total_hours'] += lead_time
                    summary['servis_aktif']['count'] += 1
                    summary['servis_aktif']['max_hours'] = max(summary['servis_aktif']['max_hours'], lead_time)
                    summary['servis_aktif']['min_hours'] = min(summary['servis_aktif']['min_hours'], lead_time)
                    
                    # Update distribution
                    if lead_time < 1:
                        summary['servis_aktif']['distribution']['under_1_hour'] += 1
                    elif lead_time < 2:
                        summary['servis_aktif']['distribution']['1_to_2_hours'] += 1
                    elif lead_time < 3:
                        summary['servis_aktif']['distribution']['2_to_3_hours'] += 1
                    elif lead_time < 4:
                        summary['servis_aktif']['distribution']['3_to_4_hours'] += 1
                    else:
                        summary['servis_aktif']['distribution']['over_4_hours'] += 1
                
                # Total servis (using total_lead_time_servis)
                if order.total_lead_time_servis > 0:
                    lead_time = order.total_lead_time_servis
                    summary['total_servis']['total_hours'] += lead_time
                    summary['total_servis']['count'] += 1
                    summary['total_servis']['max_hours'] = max(summary['total_servis']['max_hours'], lead_time)
                    summary['total_servis']['min_hours'] = min(summary['total_servis']['min_hours'], lead_time)
                    
                    # Update distribution
                    if lead_time < 2:
                        summary['total_servis']['distribution']['under_2_hours'] += 1
                    elif lead_time < 4:
                        summary['total_servis']['distribution']['2_to_4_hours'] += 1
                    elif lead_time < 6:
                        summary['total_servis']['distribution']['4_to_6_hours'] += 1
                    elif lead_time < 8:
                        summary['total_servis']['distribution']['6_to_8_hours'] += 1
                    else:
                        summary['total_servis']['distribution']['over_8_hours'] += 1
            
            # Calculate averages and percentages
            for key in summary:
                if summary[key]['count'] > 0:
                    summary[key]['avg_hours'] = summary[key]['total_hours'] / summary[key]['count']
                    if 'exceeded_count' in summary[key]:
                        summary[key]['exceeded_percentage'] = (summary[key]['exceeded_count'] / summary[key]['count']) * 100
                
                # Set min to 0 if no data was found
                if summary[key]['min_hours'] == float('inf'):
                    summary[key]['min_hours'] = 0
                    
                # Format hours to readable format
                for time_key in ['avg_hours', 'max_hours', 'min_hours', 'standard_hours']:
                    if time_key in summary[key]:
                        hours = summary[key][time_key]
                        hours_int = int(hours)
                        minutes = int((hours - hours_int) * 60)
                        summary[key][f'{time_key}_formatted'] = f"{hours_int}j {minutes}m"
            
            return summary
            
        except Exception as e:
            _logger.error(f"Error calculating lead time summary: {str(e)}", exc_info=True)
            return {}

    def _get_lead_time_status(self, order):
        """Determine lead time status based on standards and actual values"""
        try:
            status = {
                'overall': 'on_time',
                'details': {
                    'tunggu_penerimaan': 'on_time',
                    'penerimaan': 'on_time',
                    'tunggu_servis': 'on_time',
                    'tunggu_konfirmasi': 'on_time',
                    'tunggu_part': 'on_time'
                },
                'has_delays': False,
                'most_significant_delay': None,
                'delay_reasons': []
            }
            
            # Standards in hours (from duration_standards in _build_service_timeline)
            standards = {
                'tunggu_penerimaan': 0.25,  # 15 minutes
                'penerimaan': 0.25,         # 15 minutes
                'tunggu_servis': 0.25,      # 15 minutes
                'tunggu_konfirmasi': 0.67,  # 40 minutes
                'tunggu_part': 0.75         # 45 minutes (for each part wait)
            }
            
            # Check tunggu penerimaan
            if order.lead_time_tunggu_penerimaan > standards['tunggu_penerimaan']:
                status['details']['tunggu_penerimaan'] = 'delayed'
                status['has_delays'] = True
                status['delay_reasons'].append({
                    'reason': 'tunggu_penerimaan',
                    'excess_hours': order.lead_time_tunggu_penerimaan - standards['tunggu_penerimaan'],
                    'name': 'Tunggu Penerimaan'
                })
            
            # Check penerimaan
            if order.lead_time_penerimaan > standards['penerimaan']:
                status['details']['penerimaan'] = 'delayed'
                status['has_delays'] = True
                status['delay_reasons'].append({
                    'reason': 'penerimaan',
                    'excess_hours': order.lead_time_penerimaan - standards['penerimaan'],
                    'name': 'Proses Penerimaan'
                })
            
            # Check tunggu servis
            if order.lead_time_tunggu_servis > standards['tunggu_servis']:
                status['details']['tunggu_servis'] = 'delayed'
                status['has_delays'] = True
                status['delay_reasons'].append({
                    'reason': 'tunggu_servis',
                    'excess_hours': order.lead_time_tunggu_servis - standards['tunggu_servis'],
                    'name': 'Tunggu Servis'
                })
            
            # Check tunggu konfirmasi
            if order.lead_time_tunggu_konfirmasi > standards['tunggu_konfirmasi']:
                status['details']['tunggu_konfirmasi'] = 'delayed'
                status['has_delays'] = True
                status['delay_reasons'].append({
                    'reason': 'tunggu_konfirmasi',
                    'excess_hours': order.lead_time_tunggu_konfirmasi - standards['tunggu_konfirmasi'],
                    'name': 'Tunggu Konfirmasi'
                })
            
            # Check tunggu part (combining part1 and part2)
            part1_delay = max(0, order.lead_time_tunggu_part1 - standards['tunggu_part']) if order.lead_time_tunggu_part1 else 0
            part2_delay = max(0, order.lead_time_tunggu_part2 - standards['tunggu_part']) if order.lead_time_tunggu_part2 else 0
            
            if part1_delay > 0 or part2_delay > 0:
                status['details']['tunggu_part'] = 'delayed'
                status['has_delays'] = True
                
                if part1_delay > 0:
                    status['delay_reasons'].append({
                        'reason': 'tunggu_part1',
                        'excess_hours': part1_delay,
                        'name': 'Tunggu Part 1'
                    })
                
                if part2_delay > 0:
                    status['delay_reasons'].append({
                        'reason': 'tunggu_part2',
                        'excess_hours': part2_delay,
                        'name': 'Tunggu Part 2'
                    })
            
            # Set overall status
            if status['has_delays']:
                status['overall'] = 'delayed'
                # Sort delay reasons by excess hours to find most significant
                if status['delay_reasons']:
                    sorted_delays = sorted(status['delay_reasons'], key=lambda x: x['excess_hours'], reverse=True)
                    status['most_significant_delay'] = sorted_delays[0]['reason']
            
            # Check if service is on time according to estimated completion time
            if (order.controller_estimasi_selesai and order.controller_selesai and 
                order.controller_selesai > order.controller_estimasi_selesai):
                status['completion_on_time'] = False
                status['overall'] = 'delayed'
                estimated_vs_actual = (order.controller_selesai - order.controller_estimasi_selesai).total_seconds() / 3600
                status['delay_reasons'].append({
                    'reason': 'completion_delay',
                    'excess_hours': estimated_vs_actual,
                    'name': 'Melebihi Estimasi Selesai'
                })
            else:
                status['completion_on_time'] = True
            
            return status
            
        except Exception as e:
            _logger.error(f"Error getting lead time status: {str(e)}", exc_info=True)
            return {'overall': 'unknown', 'details': {}, 'has_delays': False}

    @http.route('/web/service-report/table', type='json', auth='user', methods=['POST'], csrf=False)
    def get_report_table(self, **kw):
        """Get paginated service report data with filtering"""
        try:
            # Get parameters
            params = request.get_json_data().get('params', {})
            
            # Extract filter parameters
            date_range = params.get('date_range', 'today')
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            service_type = params.get('service_type', 'all')
            status = params.get('status', 'all')
            search = params.get('search', '')
            page = int(params.get('page', 1))
            limit = int(params.get('limit', 20))
            
            # Build base domain
            base_domain = [('sa_cetak_pkb', '!=', False)]
            
            # Add date domain
            date_domain = self._build_date_domain(date_range, start_date, end_date)
            if date_domain:
                base_domain.extend(date_domain)
            
            # Service type filter
            if service_type != 'all':
                base_domain.append(('service_category', '=', service_type))

            # Status filter
            if status != 'all':
                if status == 'completed':
                    base_domain.append(('controller_selesai', '!=', False))
                elif status == 'in_progress':
                    base_domain.extend([
                        ('controller_mulai_servis', '!=', False),
                        ('controller_selesai', '=', False)
                    ])
                elif status == 'delayed':
                    base_domain.extend([
                        ('controller_estimasi_selesai', '!=', False),
                        ('controller_selesai', '=', False),
                        ('controller_estimasi_selesai', '<', fields.Datetime.now())
                    ])

            # Search domain
            search_domain = []
            if search:
                search_domain = ['|', '|', '|', '|',
                    ('name', 'ilike', search),
                    ('partner_id.name', 'ilike', search),
                    ('partner_car_id.number_plate', 'ilike', search),
                    ('service_advisor_id.name', 'ilike', search),
                    ('generated_mechanic_team', 'ilike', search)
                ]

            # Combine domains
            final_domain = expression.AND([base_domain, search_domain]) if search_domain else base_domain

            # Get all matching orders for statistics
            SaleOrder = request.env['sale.order']
            all_matching_orders = SaleOrder.search(final_domain)
            
            # Calculate statistics
            stats = self._calculate_service_statistics(all_matching_orders, date_range)
            
            # Add additional lead time summary stats
            lead_time_summary = self._calculate_lead_time_summary(all_matching_orders)
            stats['lead_time_summary'] = lead_time_summary
            
            # Get paginated data with selected fields
            total_count = len(all_matching_orders)
            offset = (page - 1) * limit
            
            paginated_orders = SaleOrder.search(
                final_domain,
                limit=limit,
                offset=offset,
                order='sa_jam_masuk desc, id desc'
            )

            # Format paginated data
            rows = []
            for order in paginated_orders:
                # Format lead times with proper handling for None values
                def format_duration(hours):
                    if not hours:
                        return "0j 0m"
                    hours_int = int(hours)
                    minutes = int((hours - hours_int) * 60)
                    return f"{hours_int}j {minutes}m"

                # Format job stops data
                job_stops = {
                    'tunggu_konfirmasi': {
                        'duration': order.lead_time_tunggu_konfirmasi or 0,
                        'formatted': format_duration(order.lead_time_tunggu_konfirmasi)
                    },
                    'tunggu_part1': {
                        'duration': order.lead_time_tunggu_part1 or 0,
                        'formatted': format_duration(order.lead_time_tunggu_part1)
                    },
                    'tunggu_part2': {
                        'duration': order.lead_time_tunggu_part2 or 0,
                        'formatted': format_duration(order.lead_time_tunggu_part2)
                    },
                    'istirahat': {
                        'duration': order.lead_time_istirahat or 0,
                        'formatted': format_duration(order.lead_time_istirahat)
                    },
                    'tunggu_sublet': {
                        'duration': order.lead_time_tunggu_sublet or 0,
                        'formatted': format_duration(order.lead_time_tunggu_sublet)
                    },
                    'job_stop_lain': {
                        'duration': order.lead_time_job_stop_lain or 0,
                        'formatted': format_duration(order.lead_time_job_stop_lain)
                    }
                }

                # Calculate total job stops duration
                total_job_stops_duration = (
                    (order.lead_time_tunggu_konfirmasi or 0) +
                    (order.lead_time_tunggu_part1 or 0) +
                    (order.lead_time_tunggu_part2 or 0) +
                    (order.lead_time_istirahat or 0) +
                    (order.lead_time_tunggu_sublet or 0) +
                    (order.lead_time_job_stop_lain or 0)
                )

                # Add detailed lead time information
                detailed_lead_times = {
                    'tunggu_penerimaan': {
                        'duration': order.lead_time_tunggu_penerimaan or 0,
                        'formatted': format_duration(order.lead_time_tunggu_penerimaan)
                    },
                    'penerimaan': {
                        'duration': order.lead_time_penerimaan or 0,
                        'formatted': format_duration(order.lead_time_penerimaan)
                    },
                    'tunggu_servis': {
                        'duration': order.lead_time_tunggu_servis or 0,
                        'formatted': format_duration(order.lead_time_tunggu_servis)
                    },
                    'estimasi_pengerjaan': {
                        'duration': order.estimasi_durasi_pengerjaan or 0,
                        'formatted': format_duration(order.estimasi_durasi_pengerjaan)
                    },
                    'overall': {
                        'duration': order.overall_lead_time or 0,
                        'formatted': format_duration(order.overall_lead_time)
                    }
                }

                # Get lead time status based on comparison with standards
                lead_time_status = self._get_lead_time_status(order)

                rows.append({
                    'id': order.id,
                    'service_id': order.name,
                    'customer': order.partner_id.name,
                    'vehicle': f"{order.partner_car_brand.name} {order.partner_car_brand_type.name}",
                    'service_type': {
                        'code': order.service_category,
                        'name': dict(order._fields['service_category'].selection).get(order.service_category, 'Uncategorized')
                    },
                    'start_date': self._format_local_datetime(order.sa_jam_masuk),
                    'completion_date': self._format_local_datetime(order.controller_selesai),
                    'status': self._get_order_status(order),
                    'advisor': ', '.join(order.service_advisor_id.mapped('name')),
                    'mechanic': order.generated_mechanic_team,
                    # Tambahan data lead time
                    'lead_times': {
                        'service': order.lead_time_servis or 0,
                        'total': order.total_lead_time_servis or 0,
                        'total_job_stops': total_job_stops_duration,
                        'formatted_service': format_duration(order.lead_time_servis),
                        'formatted_total': format_duration(order.total_lead_time_servis),
                        'formatted_total_job_stops': format_duration(total_job_stops_duration),
                        'detailed': detailed_lead_times,
                        'status': lead_time_status
                    },
                    'job_stops': job_stops,
                    'timestamps': {
                        'start': self._format_local_datetime(order.controller_mulai_servis),
                        'end': self._format_local_datetime(order.controller_selesai),
                        'sa_jam_masuk': self._format_local_datetime(order.sa_jam_masuk),
                        'sa_mulai_penerimaan': self._format_local_datetime(order.sa_mulai_penerimaan),
                        'sa_cetak_pkb': self._format_local_datetime(order.sa_cetak_pkb),
                        'fo_unit_keluar': self._format_local_datetime(order.fo_unit_keluar)
                    },
                    'lead_time_stage': order.lead_time_stage,
                    'lead_time_progress': order.lead_time_progress
                })

            return {
                'status': 'success',
                'data': {
                    'stats': stats,
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit),
                        'current_page': page,
                        'items_per_page': limit,
                        'has_next': page < math.ceil(total_count / limit),
                        'has_previous': page > 1
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_report_table: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    

    # Endpoint untuk export report
    @http.route('/web/service-report/export', type='json', auth='user', methods=['POST'], csrf=False)
    def export_service_report(self, **kw):
        """Generate exportable service report data"""
        try:
            # Implementation for export...
            pass
        except Exception as e:
            _logger.error(f"Error in export_service_report: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    # Endpoint untuk detail report
    @http.route('/web/service-report/detail', type='json', auth='user', methods=['POST'], csrf=False)
    def get_report_detail(self, **kw):
        """Get detailed service report information"""
        try:
            # Get order ID from params
            data = request.get_json_data()
            params = data.get('params', {})
            order_id = params.get('order_id')
            
            if not order_id:
                return {
                    'status': 'error',
                    'message': 'Order ID is required'
                }

            # Get order
            order = self._validate_access(order_id)
            if not order:
                return {
                    'status': 'error',
                    'message': 'Order not found or access denied'
                }

            # Get navigation info
            nav_info = self._get_navigation_info(order)

            # Get timeline and progress
            timeline_data = self._build_service_timeline(order)
            progress = self._get_service_progress(order)

            # Build detailed response
            detail = {
                'navigation': nav_info,
                'basic_info': {
                    'id': order.id,
                    'service_id': order.name,
                    'status': self._get_order_status(order),
                    'create_date': self._format_local_datetime(order.create_date),
                    'progress': progress
                },
                'customer': {
                    'id': order.partner_id.id,
                    'name': order.partner_id.name,
                    'phone': order.partner_id.phone
                },
                'vehicle': {
                    'brand': order.partner_car_brand.name,
                    'type': order.partner_car_brand_type.name,
                    'plate': order.partner_car_id.number_plate,
                    'year': order.partner_car_year,
                    'transmission': order.partner_car_transmission.name,
                    'color': order.partner_car_color
                },
                'service': {
                    'category': {
                        'code': order.service_category,
                        'name': dict(order._fields['service_category'].selection).get(order.service_category, 'Uncategorized')
                    },
                    'subcategory': {
                        'code': order.service_subcategory,
                        'name': dict(order._fields['service_subcategory'].selection).get(order.service_subcategory, 'Uncategorized')
                    }
                },
                'timeline': timeline_data,
                'staff': {
                    'advisors': [{
                        'id': advisor.id,
                        'name': advisor.name
                    } for advisor in order.service_advisor_id],
                    'mechanics': order.generated_mechanic_team
                },
                'completion': {
                    'estimated': self._format_local_datetime(order.controller_estimasi_selesai),
                    'actual': self._format_local_datetime(order.controller_selesai),
                    'is_delayed': order.controller_estimasi_selesai and order.controller_selesai and 
                                order.controller_selesai > order.controller_estimasi_selesai,
                    'notes': order.lead_time_catatan
                }
            }

            return {
                'status': 'success',
                'data': detail
            }

        except Exception as e:
            _logger.error(f"Error in get_report_detail: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
    def _get_navigation_info(self, current_order):
        """Get previous and next order IDs for navigation"""
        try:
            # Get base domain (same as your table endpoint)
            base_domain = [('sa_cetak_pkb', '!=', False)]
            
            # Find orders before current order
            prev_domain = base_domain + [
                ('sa_jam_masuk', '<=', current_order.sa_jam_masuk),
                ('id', '!=', current_order.id)
            ]
            prev_order = request.env['sale.order'].search(
                prev_domain, 
                order='sa_jam_masuk desc, id desc', 
                limit=1
            )

            # Find orders after current order
            next_domain = base_domain + [
                ('sa_jam_masuk', '>=', current_order.sa_jam_masuk),
                ('id', '!=', current_order.id)
            ]
            next_order = request.env['sale.order'].search(
                next_domain, 
                order='sa_jam_masuk asc, id asc', 
                limit=1
            )

            return {
                'previous': {
                    'id': prev_order.id if prev_order else None,
                    'service_id': prev_order.name if prev_order else None,
                    'customer': prev_order.partner_id.name if prev_order else None
                } if prev_order else None,
                'next': {
                    'id': next_order.id if next_order else None,
                    'service_id': next_order.name if next_order else None,
                    'customer': next_order.partner_id.name if next_order else None
                } if next_order else None,
                'current_position': {
                    'id': current_order.id,
                    'service_id': current_order.name,
                    'customer': current_order.partner_id.name
                }
            }

        except Exception as e:
            _logger.error(f"Error getting navigation info: {str(e)}", exc_info=True)
            return {
                'previous': None,
                'next': None,
                'current_position': None
            }


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
        
    

    @http.route('/web/lead-time/detail', type='json', auth='user', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def get_lead_time_detail(self, **kw):
        """Get comprehensive lead time details for a specific order"""
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

             # Get request data
            # # data = request.jsonrequest
            # params = data.get('params', {})
            order_id = kw.get('order_id')
            
            if not order_id:
                return {
                    'status': 'error',
                    'message': 'Order ID is required'
                }

            # Validate access and get order
            order = self._validate_access(order_id)
            if not order:
                return {
                    'status': 'error',
                    'message': 'Order not found or access denied'
                }

            # Standards for job stops (in minutes)
            JOB_STOP_STANDARDS = {
                'tunggu_penerimaan': 15,
                'penerimaan': 15,
                'tunggu_servis': 15,
                'tunggu_konfirmasi': 40,
                'tunggu_part1': 45,
                'tunggu_part2': 45
            }

            def calculate_duration_minutes(start, end):
                """Calculate duration in minutes between two timestamps"""
                if start and end and end > start:
                    return (end - start).total_seconds() / 60
                return 0

            def format_duration(minutes):
                """Format duration minutes to human readable string"""
                if minutes == 0:
                    return "0 menit"
                hours = int(minutes // 60)
                mins = int(minutes % 60)
                parts = []
                if hours > 0:
                    parts.append(f"{hours} jam")
                if mins > 0:
                    parts.append(f"{mins} menit")
                return " ".join(parts)

            def analyze_job_stop(start, end, standard_time=None):
                """Analyze a job stop duration and status"""
                duration = calculate_duration_minutes(start, end)
                result = {
                    'start_time': self._format_local_datetime(start),
                    'end_time': self._format_local_datetime(end) if end else None,
                    'duration_minutes': duration,
                    'duration_text': format_duration(duration),
                    'status': 'completed' if end else ('in_progress' if start else 'not_started')
                }
                
                if standard_time is not None:
                    result.update({
                        'standard_time': standard_time,
                        'standard_time_text': format_duration(standard_time),
                        'exceeded': duration > standard_time if end else False,
                        'exceeded_by': max(0, duration - standard_time) if end else 0,
                        'exceeded_by_text': format_duration(max(0, duration - standard_time)) if end else None
                    })
                
                return 
            
            def calculate_service_progress(order):
                """
                Calculate comprehensive service progress from sa_jam_masuk to controller_selesai
                Returns dictionary containing progress information and timeline
                """
                try:
                    if not order.sa_jam_masuk:
                        return {
                            'percentage': 0,
                            'current_stage': 'not_started',
                            'timeline': [],
                            'active_job_stops': []
                        }

                    # Define all stages and their weights
                    stages = [
                        {
                            'name': 'check_in',
                            'description': 'Check In',
                            'field': 'sa_jam_masuk',
                            'weight': 10,
                            'value': order.sa_jam_masuk
                        },
                        {
                            'name': 'reception',
                            'description': 'Penerimaan Customer',
                            'field': 'sa_mulai_penerimaan',
                            'weight': 15,
                            'value': order.sa_mulai_penerimaan
                        },
                        {
                            'name': 'pkb',
                            'description': 'Cetak PKB',
                            'field': 'sa_cetak_pkb',
                            'weight': 15,
                            'value': order.sa_cetak_pkb
                        },
                        {
                            'name': 'service_start',
                            'description': 'Mulai Servis',
                            'field': 'controller_mulai_servis',
                            'weight': 30,
                            'value': order.controller_mulai_servis
                        },
                        {
                            'name': 'service_complete',
                            'description': 'Selesai Servis',
                            'field': 'controller_selesai',
                            'weight': 30,
                            'value': order.controller_selesai
                        }
                    ]

                    # Define job stops
                    job_stops = [
                        {
                            'name': 'tunggu_konfirmasi',
                            'description': 'Tunggu Konfirmasi',
                            'start_field': 'controller_tunggu_konfirmasi_mulai',
                            'end_field': 'controller_tunggu_konfirmasi_selesai',
                            'start_value': order.controller_tunggu_konfirmasi_mulai,
                            'end_value': order.controller_tunggu_konfirmasi_selesai
                        },
                        {
                            'name': 'tunggu_part1',
                            'description': 'Tunggu Part 1',
                            'start_field': 'controller_tunggu_part1_mulai',
                            'end_field': 'controller_tunggu_part1_selesai',
                            'start_value': order.controller_tunggu_part1_mulai,
                            'end_value': order.controller_tunggu_part1_selesai
                        },
                        {
                            'name': 'tunggu_part2',
                            'description': 'Tunggu Part 2',
                            'start_field': 'controller_tunggu_part2_mulai',
                            'end_field': 'controller_tunggu_part2_selesai',
                            'start_value': order.controller_tunggu_part2_mulai,
                            'end_value': order.controller_tunggu_part2_selesai
                        },
                        {
                            'name': 'istirahat',
                            'description': 'Istirahat',
                            'start_field': 'controller_istirahat_shift1_mulai',
                            'end_field': 'controller_istirahat_shift1_selesai',
                            'start_value': order.controller_istirahat_shift1_mulai,
                            'end_value': order.controller_istirahat_shift1_selesai
                        },
                        {
                            'name': 'tunggu_sublet',
                            'description': 'Tunggu Sublet',
                            'start_field': 'controller_tunggu_sublet_mulai',
                            'end_field': 'controller_tunggu_sublet_selesai',
                            'start_value': order.controller_tunggu_sublet_mulai,
                            'end_value': order.controller_tunggu_sublet_selesai
                        },
                        {
                            'name': 'job_stop_lain',
                            'description': 'Job Stop Lain',
                            'start_field': 'controller_job_stop_lain_mulai',
                            'end_field': 'controller_job_stop_lain_selesai',
                            'start_value': order.controller_job_stop_lain_mulai,
                            'end_value': order.controller_job_stop_lain_selesai,
                            'note': order.job_stop_lain_keterangan
                        }
                    ]

                    # Build timeline
                    timeline = []
                    total_weight = sum(stage['weight'] for stage in stages)
                    completed_weight = 0
                    current_stage = None

                    # Add stages to timeline
                    for stage in stages:
                        if stage['value']:
                            timeline.append({
                                'type': 'stage',
                                'name': stage['name'],
                                'description': stage['description'],
                                'timestamp': stage['value'],
                                'completed': True
                            })
                            completed_weight += stage['weight']
                        else:
                            if not current_stage:
                                current_stage = stage['name']
                            timeline.append({
                                'type': 'stage',
                                'name': stage['name'],
                                'description': stage['description'],
                                'timestamp': None,
                                'completed': False
                            })

                    # Track active job stops
                    active_job_stops = []
                    
                    # Add job stops to timeline
                    for job_stop in job_stops:
                        if job_stop['start_value']:
                            timeline.append({
                                'type': 'job_stop_start',
                                'name': job_stop['name'],
                                'description': job_stop['description'],
                                'timestamp': job_stop['start_value'],
                                'completed': bool(job_stop['end_value'])
                            })

                            if job_stop['end_value']:
                                timeline.append({
                                    'type': 'job_stop_end',
                                    'name': job_stop['name'],
                                    'description': job_stop['description'],
                                    'timestamp': job_stop['end_value'],
                                    'completed': True
                                })
                            else:
                                active_job_stops.append({
                                    'name': job_stop['name'],
                                    'description': job_stop['description'],
                                    'start_time': job_stop['start_value']
                                })

                    # Sort timeline by timestamp
                    timeline = [event for event in timeline if event['timestamp'] is not None]
                    timeline.sort(key=lambda x: x['timestamp'])

                    # Calculate base progress percentage
                    base_progress = (completed_weight / total_weight * 100) if total_weight > 0 else 0

                    # Adjust progress for active job stops
                    if active_job_stops:
                        # Reduce 5% for each active job stop
                        progress_reduction = len(active_job_stops) * 5
                        adjusted_progress = max(0, base_progress - progress_reduction)
                    else:
                        adjusted_progress = base_progress

                    # Cap progress at 100%
                    final_progress = min(100, adjusted_progress)

                    return {
                        'percentage': final_progress,
                        'current_stage': current_stage,
                        'timeline': timeline,
                        'active_job_stops': active_job_stops,
                        'completion': {
                            'total_stages': len(stages),
                            'completed_stages': sum(1 for stage in stages if stage['value']),
                            'active_job_stops': len(active_job_stops)
                        }
                    }

                except Exception as e:
                    _logger.error(f"Error calculating service progress: {str(e)}", exc_info=True)
                    return {
                        'percentage': 0,
                        'current_stage': 'error',
                        'timeline': [],
                        'active_job_stops': [],
                        'error': str(e)
                    }

            # Calculate progress and get timeline
            progress_info = calculate_service_progress(order)

            # Build comprehensive response
            response = {
                'order_info': {
                    'id': order.id,
                    'name': order.name,
                    'state': order.state,
                    'reception_state': order.reception_state,
                    'create_date': self._format_local_datetime(order.create_date),
                    'date_completed': self._format_local_datetime(order.date_completed)
                },

                'customer': {
                    'id': order.partner_id.id,
                    'name': order.partner_id.name,
                    'phone': order.partner_id.phone
                },

                'car': {
                    'id': order.partner_car_id.id,
                    'brand': order.partner_car_brand.name if order.partner_car_brand else None,
                    'brand_type': order.partner_car_brand_type.name if order.partner_car_brand_type else None,
                    'year': order.partner_car_year,
                    'number_plate': order.partner_car_id.number_plate,
                    'transmission': order.partner_car_transmission.name if order.partner_car_transmission else None,
                    'engine_type': order.partner_car_engine_type,
                    'engine_number': order.partner_car_engine_number,
                    'frame_number': order.partner_car_frame_number,
                    'color': order.partner_car_color,
                    'odometer': order.partner_car_odometer
                },

                'service': {
                    'category': {
                        'code': order.service_category,
                        'name': dict(order._fields['service_category'].selection).get(order.service_category, 'Uncategorized')
                    },
                    'subcategory': {
                        'code': order.service_subcategory,
                        'name': dict(order._fields['service_subcategory'].selection).get(order.service_subcategory, 'Uncategorized')
                    }
                },

                'staff': {
                    'service_advisors': [{
                        'id': advisor.id,
                        'name': advisor.name
                    } for advisor in order.service_advisor_id],
                    'mechanics': order.generated_mechanic_team
                },

                'timeline': {
                    'reception': {
                        'check_in': {
                            'time': self._format_local_datetime(order.sa_jam_masuk),
                            'status': 'completed' if order.sa_jam_masuk else 'pending'
                        },
                        'tunggu_penerimaan': analyze_job_stop(
                            order.sa_jam_masuk,
                            order.sa_mulai_penerimaan,
                            JOB_STOP_STANDARDS['tunggu_penerimaan']
                        ),
                        'penerimaan': analyze_job_stop(
                            order.sa_mulai_penerimaan,
                            order.sa_cetak_pkb,
                            JOB_STOP_STANDARDS['penerimaan']
                        ),
                        'pkb_printed': {
                            'time': self._format_local_datetime(order.sa_cetak_pkb),
                            'status': 'completed' if order.sa_cetak_pkb else 'pending'
                        }
                    },

                    'service': {
                        'tunggu_servis': analyze_job_stop(
                            order.sa_cetak_pkb,
                            order.controller_mulai_servis,
                            JOB_STOP_STANDARDS['tunggu_servis']
                        ),
                        'mulai': {
                            'time': self._format_local_datetime(order.controller_mulai_servis),
                            'status': 'completed' if order.controller_mulai_servis else 'pending'
                        },
                        'selesai': {
                            'time': self._format_local_datetime(order.controller_selesai),
                            'status': 'completed' if order.controller_selesai else (
                                'in_progress' if order.controller_mulai_servis else 'pending'
                            )
                        }
                    },

                    'job_stops': {
                        'tunggu_konfirmasi': analyze_job_stop(
                            order.controller_tunggu_konfirmasi_mulai,
                            order.controller_tunggu_konfirmasi_selesai,
                            JOB_STOP_STANDARDS['tunggu_konfirmasi']
                        ),
                        'tunggu_part1': analyze_job_stop(
                            order.controller_tunggu_part1_mulai,
                            order.controller_tunggu_part1_selesai,
                            JOB_STOP_STANDARDS['tunggu_part1']
                        ),
                        'tunggu_part2': analyze_job_stop(
                            order.controller_tunggu_part2_mulai,
                            order.controller_tunggu_part2_selesai,
                            JOB_STOP_STANDARDS['tunggu_part2']
                        ),
                        'istirahat': analyze_job_stop(
                            order.controller_istirahat_shift1_mulai,
                            order.controller_istirahat_shift1_selesai
                        ),
                        'tunggu_sublet': analyze_job_stop(
                            order.controller_tunggu_sublet_mulai,
                            order.controller_tunggu_sublet_selesai
                        ),
                        'job_stop_lain': analyze_job_stop(
                            order.controller_job_stop_lain_mulai,
                            order.controller_job_stop_lain_selesai
                        )
                    }
                },

                'lead_times': {
                    'total': {
                        'minutes': order.total_lead_time_servis * 60,
                        'text': format_duration(order.total_lead_time_servis * 60)
                    },
                    'active_service': {
                        'minutes': order.lead_time_servis * 60,
                        'text': format_duration(order.lead_time_servis * 60)
                    },
                    'components': {
                        'tunggu_penerimaan': {
                            'minutes': order.lead_time_tunggu_penerimaan * 60,
                            'text': format_duration(order.lead_time_tunggu_penerimaan * 60)
                        },
                        'penerimaan': {
                            'minutes': order.lead_time_penerimaan * 60,
                            'text': format_duration(order.lead_time_penerimaan * 60)
                        },
                        'tunggu_servis': {
                            'minutes': order.lead_time_tunggu_servis * 60,
                            'text': format_duration(order.lead_time_tunggu_servis * 60)
                        },
                        'tunggu_konfirmasi': {
                            'minutes': order.lead_time_tunggu_konfirmasi * 60,
                            'text': format_duration(order.lead_time_tunggu_konfirmasi * 60)
                        },
                        'tunggu_part1': {
                            'minutes': order.lead_time_tunggu_part1 * 60,
                            'text': format_duration(order.lead_time_tunggu_part1 * 60)
                        },
                        'tunggu_part2': {
                            'minutes': order.lead_time_tunggu_part2 * 60,
                            'text': format_duration(order.lead_time_tunggu_part2 * 60)
                        },
                        'istirahat': {
                            'minutes': order.lead_time_istirahat * 60,
                            'text': format_duration(order.lead_time_istirahat * 60)
                        },
                        'tunggu_sublet': {
                            'minutes': order.lead_time_tunggu_sublet * 60,
                            'text': format_duration(order.lead_time_tunggu_sublet * 60)
                        },
                        'job_stop_lain': {
                            'minutes': order.lead_time_job_stop_lain * 60,
                            'text': format_duration(order.lead_time_job_stop_lain * 60)
                        }
                    }
                },

                'progress': progress_info,

                'completion': {
                    'is_completed': bool(order.controller_selesai),
                    'completion_time': self._format_local_datetime(order.controller_selesai),
                    'unit_keluar': self._format_local_datetime(order.fo_unit_keluar),
                    'is_overnight': order.is_overnight,
                    'estimated_completion': self._format_local_datetime(order.controller_estimasi_selesai)
                },

                'notes': {
                    'lead_time': order.lead_time_catatan,
                    'job_stop_lain': order.job_stop_lain_keterangan
                }
            }

            return {
                'status': 'success',
                'data': response
            }

        except Exception as e:
            _logger.error(f"Error in get_lead_time_detail: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
        
    def _calculate_duration_minutes(self, start, end):
        """Calculate duration in minutes between two timestamps"""
        if start and end and end > start:
            return (end - start).total_seconds() / 60
        return 0

    def _get_job_stop_status(self, start, end):
        """Get status of a job stop"""
        if not start:
            return 'pending'
        if not end:
            return 'in_progress'
        return 'completed'

