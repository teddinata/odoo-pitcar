from odoo import http, fields
from odoo.http import request
import pytz
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError
import json
import math
import logging

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
                    'mulai': self._format_time(order.controller_mulai_servis),
                    'selesai': self._format_time(order.controller_selesai)
                },
                'tunggu_part': {
                    'mulai': self._format_time(order.controller_tunggu_part1_mulai),
                    'selesai': self._format_time(order.controller_tunggu_part1_selesai)
                },
                'tunggu_konfirmasi': {
                    'mulai': self._format_time(order.controller_tunggu_konfirmasi_mulai),
                    'selesai': self._format_time(order.controller_tunggu_konfirmasi_selesai)
                },
                'istirahat': {
                    'mulai': self._format_time(order.controller_istirahat_shift1_mulai),
                    'selesai': self._format_time(order.controller_istirahat_shift1_selesai)
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
                'date_completed': self._format_datetime(order.date_completed) if order.date_completed else None
            }
        }
    
    def _validate_pagination_params(self, page, limit):
        """Validate and normalize pagination parameters"""
        try:
            # Convert and validate page
            page = int(page)
            if page < 1:
                page = 1
                
            # Convert and validate limit
            limit = int(limit)
            if limit not in [10, 20, 30, 50]:
                limit = 20  # Default to 20 if invalid
                
            return page, limit
        except (ValueError, TypeError):
            return 1, 20  # Default values if conversion fails

    # Main Table Endpoints
    def _get_active_domain(self):
        """Get base domain for active service orders"""
        today = fields.Date.today()
        # today_start = datetime.combine(today, datetime.min.time())
        # today_end = datetime.combine(today, datetime.max.time())
        
        return [
            # Filter orders yang sudah di-PKB dan belum selesai atau selesai hari ini
            ('sa_cetak_pkb', '!=', False),
            '|',
                ('controller_selesai', '=', False),
                '&',
                    ('controller_selesai', '>=', today),
                    ('controller_selesai', '<=', today + timedelta(days=1))
        ]

    @http.route('/web/lead-time/table', type='json', auth='user', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def get_table_data(self, **kw):
        """Get lead time table data with filtering and pagination"""
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

            # Log received parameters
            _logger.info(f"Received parameters: {kw}")
            
            # Extract parameters from JSON-RPC format
            params = kw.get('params', {})
            page = int(params.get('page', 1))
            limit = int(params.get('limit', 20))
            filter_type = params.get('filter', 'all')
            search_query = params.get('search', '')
            sort_by = params.get('sort_by', 'id')
            sort_order = params.get('sort_order', 'desc')

            # Validate pagination params
            page, limit = self._validate_pagination_params(page, limit)
            offset = (page - 1) * limit

            # Start with base domain for active orders
            domain = self._get_active_domain()

            # Add additional filters
            if filter_type == 'delay':
                domain.append(('is_delayed', '=', True))
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
                today = fields.Date.today()
                domain.extend([
                    ('controller_selesai', '!=', False),
                    ('controller_selesai', '>=', today),
                    ('controller_selesai', '<=', today + timedelta(days=1))
                ])

            # Add search filters
            if search_query:
                domain += ['|', '|', '|', '|', '|',
                    ('partner_car_id.number_plate', 'ilike', search_query),
                    ('partner_car_id.brand.name', 'ilike', search_query),
                    ('partner_car_id.brand_type.name', 'ilike', search_query),
                    ('lead_time_catatan', 'ilike', search_query),
                    ('service_advisor_id.name', 'ilike', search_query),
                    ('generated_mechanic_team', 'ilike', search_query)
                ]

            _logger.info(f"Applied domain: {domain}")

            # Get total count for pagination
            total_count = request.env['sale.order'].search_count(domain)
            total_pages = math.ceil(total_count / limit)

            # Validate page number
            if page > total_pages and total_pages > 0:
                page = total_pages
                offset = (page - 1) * limit

            # Prepare sorting
            order_mapping = {
                'id': 'id',
                'date': 'create_date',
                'customer': 'partner_id',
                'status': 'lead_time_stage',
                'plat': 'partner_car_id.number_plate',
                'brand': 'partner_car_id.brand.name',
                'estimasi': 'controller_estimasi_selesai',
                'progress': 'lead_time_progress'
            }
            sort_field = order_mapping.get(sort_by, 'id')
            order = f'{sort_field} {sort_order}'

            # Get paginated records
            orders = request.env['sale.order'].search(
                domain,
                limit=limit,
                offset=offset,
                order=order
            )

            _logger.info(f"Found {len(orders)} records")

            # Prepare response data
            tz = pytz.timezone('Asia/Jakarta')
            current_time = datetime.now(tz)
            
            rows = []
            start_number = offset + 1
            for order in orders:
                number_plate = order.partner_car_id.number_plate if order.partner_car_id else '-'
                brand_name = order.partner_car_brand.name if order.partner_car_brand else ''
                brand_type_name = order.partner_car_brand_type.name if order.partner_car_brand_type else ''
                
                rows.append({
                    'id': order.id,
                    'no': start_number + len(rows),
                    'jenis_mobil': f"{brand_name} {brand_type_name}".strip() or '-',
                    'plat_mobil': number_plate,
                    'status': self._get_order_status(order),
                    'keterangan': order.lead_time_stage or '-',
                    'catatan': order.lead_time_catatan or '-',
                    'estimasi_selesai': self._format_time(order.controller_estimasi_selesai),
                    'mekanik': order.generated_mechanic_team or '-',
                    'service_advisor': ', '.join(order.service_advisor_id.mapped('name')) if order.service_advisor_id else '-',
                    'timestamps': {
                        'mulai_servis': self._format_time(order.controller_mulai_servis),
                        'selesai_servis': self._format_time(order.controller_selesai),
                        'completion': self._format_datetime(order.date_completed)
                    },
                    'progress': {
                        'percentage': order.lead_time_progress or 0,
                        'stage': order.lead_time_stage or 'not_started'
                    }
                })

            # Update summary data
            summary = self._get_summary(domain)

            return {
            'jsonrpc': '2.0',
            'id': None,
            'result': {
                'status': 'success',
                'data': {
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
        }

        except Exception as e:
            _logger.error(f"Error in get_table_data: {str(e)}", exc_info=True)
            return {
                'jsonrpc': '2.0',
                'id': None,
                'error': {
                    'code': 500,
                    'message': str(e),
                    'data': {
                        'name': 'Internal Server Error',
                        'debug': str(e),
                        'arguments': [],
                        'exception_type': type(e).__name__
                    }
                }
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

    @http.route('/web/lead-time/statistics', type='json', auth='user', methods=['GET'])
    def get_statistics(self):
        """Get overall lead time statistics"""
        try:
            today = fields.Date.today()
            orders = request.env['sale.order'].search([
                ('sa_jam_masuk', '>=', today),
                ('sa_jam_masuk', '<', today + timedelta(days=1))
            ])

            stats = {
                'today': {
                    'total_orders': len(orders),
                    'completed_orders': len(orders.filtered(lambda o: o.controller_selesai)),
                    'average_lead_time': sum(o.lead_time_servis or 0 for o in orders) / len(orders) if orders else 0,
                    'total_job_stops': sum(1 for o in orders if o.controller_tunggu_part1_mulai or 
                                         o.controller_tunggu_konfirmasi_mulai or 
                                         o.controller_istirahat_shift1_mulai),
                    'status_breakdown': {
                        'proses': len(orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai)),
                        'tunggu_part': len(orders.filtered(lambda o: o.controller_tunggu_part1_mulai and not o.controller_tunggu_part1_selesai)),
                        'tunggu_konfirmasi': len(orders.filtered(lambda o: o.controller_tunggu_konfirmasi_mulai and not o.controller_tunggu_konfirmasi_selesai)),
                        'istirahat': len(orders.filtered(lambda o: o.controller_istirahat_shift1_mulai and not o.controller_istirahat_shift1_selesai)),
                        'selesai': len(orders.filtered(lambda o: o.controller_selesai))
                    }
                }
            }

            return {
                'status': 'success',
                'data': stats
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}