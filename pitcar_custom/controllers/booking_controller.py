from odoo import http, fields
from odoo.http import request
import logging
from datetime import datetime, timedelta
import psycopg2  # Tambahkan import ini
import math

_logger = logging.getLogger(__name__)

class BookingController(http.Controller):
    
    def _handle_error(self, error_message, details=None):
      """Centralized error handling"""
      _logger.error(f"Booking API Error: {error_message}")
      if details:
          _logger.error(f"Error details: {details}")
      return {
          'status': 'error',
          'message': error_message,
          'details': details if details else None
      }
    
    @http.route('/web/v1/booking/verify-vehicle', type='json', auth="public", methods=['POST'], csrf=False)
    def verify_vehicle(self, **kw):
        """Verifikasi kendaraan berdasarkan plat nomor"""
        try:
            plate_number = kw.get('plate_number')
            if not plate_number:
                return {'status': 'error', 'message': 'Plate number is required'}
            
            # Standardisasi plat nomor (hapus spasi, uppercase)
            plate_number = plate_number.replace(" ", "").upper()
            
            car = request.env['res.partner.car'].sudo().search([
                ('number_plate', '=', plate_number)
            ], limit=1)
            
            if car:
                return {
                    'status': 'found',
                    'data': {
                        'car_id': car.id,
                        'customer_name': car.partner_id.name,
                        'customer_id': car.partner_id.id,
                        'car_brand': car.brand.name,
                        'car_type': car.brand_type.name,
                        'car_year': car.year,
                        'car_color': car.color,
                        'engine_type': car.engine_type,
                        'transmission': car.transmission.name
                    }
                }
            else:
                return {'status': 'not_found', 'message': 'Vehicle not registered'}
                
        except Exception as e:
            _logger.error(f"Error in verify_vehicle: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/booking/check-availability', type='json', auth="public", methods=['POST'], csrf=False)
    def check_availability(self, **kw):
        """Cek ketersediaan stall berdasarkan tanggal, waktu, dan durasi layanan"""
        try:
            date = kw.get('date')
            time = kw.get('time')
            duration = kw.get('duration')
            
            if not all([date, time is not None, duration]):
                return {'status': 'error', 'message': 'Missing required parameters'}
            
            time = float(time)
            duration = float(duration)
            
            # Validasi waktu operasional bengkel
            working_hours_start = 8.0  # 08:00
            working_hours_end = 17.0   # 17:00
            
            if time < working_hours_start or (time + duration) > working_hours_end:
                return {
                    'status': 'error', 
                    'message': f'Booking hours must be between {working_hours_start}:00 and {working_hours_end}:00'
                }
            
            # Hitung end_time
            end_time = time + duration
            
            # Ambil semua stall aktif
            stalls = request.env['pitcar.service.stall'].sudo().search([('active', '=', True)])
            
            available_stalls = []
            for stall in stalls:
                # Cek konflik booking
                conflicting_bookings = request.env['pitcar.service.booking'].sudo().search([
                    ('stall_id', '=', stall.id),
                    ('booking_date', '=', date),
                    ('state', 'not in', ['cancelled']),
                    '|',
                    '&', ('booking_time', '<', time), ('booking_end_time', '>', time),
                    '&', ('booking_time', '<', end_time), ('booking_end_time', '>', end_time),
                    '&', ('booking_time', '>=', time), ('booking_time', '<', end_time)
                ])
                
                # Dapatkan semua booking yang ada untuk stall ini pada tanggal tersebut
                existing_bookings = request.env['pitcar.service.booking'].sudo().search([
                    ('stall_id', '=', stall.id),
                    ('booking_date', '=', date),
                    ('state', 'not in', ['cancelled']),
                ], order='booking_time')
                
                booked_slots = []
                for booking in existing_bookings:
                    booked_slots.append({
                        'start_time': booking.booking_time,
                        'end_time': booking.booking_end_time,
                        'customer': booking.partner_id.name,
                        'service': booking.service_subcategory
                    })
                
                # Jika tidak ada konflik, tambahkan ke available stalls
                if not conflicting_bookings:
                    available_stalls.append({
                        'id': stall.id,
                        'name': stall.name,
                        'code': stall.code,
                        'mechanics': [{'id': m.id, 'name': m.name} for m in stall.mechanic_ids],
                        'booked_slots': booked_slots,
                        'is_available': True
                    })
                else:
                    # Optional: Return stall yang sudah terisi juga dengan flag is_available=False
                    available_stalls.append({
                        'id': stall.id,
                        'name': stall.name,
                        'code': stall.code,
                        'mechanics': [{'id': m.id, 'name': m.name} for m in stall.mechanic_ids],
                        'booked_slots': booked_slots,
                        'is_available': False
                    })
            
            return {
                'status': 'success',
                'available_stalls': available_stalls,
                'requested_time': {
                    'date': date,
                    'start_time': time,
                    'end_time': end_time,
                    'duration': duration
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in check_availability: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/booking/init-stalls', type='json', auth="public", methods=['POST'], csrf=False)
    def init_stalls(self, **kw):
        """Initialize stalls if not exist"""
        try:
            stalls = request.env['pitcar.service.stall'].sudo().search([])
            
            if not stalls:
                for i in range(1, 7):
                    request.env['pitcar.service.stall'].sudo().create({
                        'name': f'Stall {i}',
                        'code': f'S{i:02d}',
                        'active': True
                    })
                return {'status': 'success', 'message': 'Stalls initialized successfully'}
            
            return {'status': 'success', 'message': 'Stalls already exist'}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/get-stalls', type='json', auth="public", methods=['POST'], csrf=False)
    def get_stalls(self, **kw):
        """Mendapatkan daftar stall yang tersedia"""
        try:
            stalls = request.env['pitcar.service.stall'].sudo().search([('active', '=', True)])
            
            if not stalls:
                # Create default stalls
                for i in range(1, 7):
                    request.env['pitcar.service.stall'].sudo().create({
                        'name': f'Stall {i}',
                        'code': f'S{i:02d}',
                        'active': True
                    })
                stalls = request.env['pitcar.service.stall'].sudo().search([('active', '=', True)])
            
            result = []
            for stall in stalls:
                result.append({
                    'id': stall.id,
                    'name': stall.name,
                    'code': stall.code
                })
            
            return {'status': 'success', 'data': result}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/booking/create', type='json', auth="public", methods=['POST'], csrf=False)
    def create_booking(self, **kw):
        """Create booking lengkap dengan registrasi customer/kendaraan jika diperlukan"""
        try:
            with request.env.cr.savepoint():
                # Validasi input wajib
                required_fields = ['plate_number', 'date', 'time', 'service_ids', 'stall_id']
                for field in required_fields:
                    if not kw.get(field):
                        return {'status': 'error', 'message': f'Missing required field: {field}'}
                
                # Validasi stall exists
                stall_id = int(kw.get('stall_id'))
                stall = request.env['pitcar.service.stall'].sudo().browse(stall_id)
                if not stall.exists():
                    # Coba cari stall yang tersedia
                    available_stalls = request.env['pitcar.service.stall'].sudo().search([('active', '=', True)], limit=1)
                    if not available_stalls:
                        return {'status': 'error', 'message': 'No stalls available'}
                    stall = available_stalls[0]
                    stall_id = stall.id
                
                plate_number = kw.get('plate_number').replace(" ", "").upper()
                
                # Cek kendaraan
                car = request.env['res.partner.car'].sudo().search([
                    ('number_plate', '=', plate_number)
                ], limit=1)
                
                # Jika kendaraan belum ada, buat baru
                if not car:
                    if not all([kw.get('customer_name'), kw.get('customer_phone'), 
                              kw.get('brand_id'), kw.get('brand_type_id')]):
                        return {'status': 'error', 'message': 'Missing required customer/car data'}
                    
                    # Format phone number (hapus format phone validation)
                    phone = kw.get('customer_phone', '')
                    
                    # Buat customer baru dengan context yang disable phone validation
                    customer_vals = {
                        'name': kw.get('customer_name'),
                        'phone': phone,
                        'email': kw.get('customer_email'),
                        'customer_rank': 1,  # Set as customer
                    }
                    
                    # Create customer dengan context khusus
                    ctx = {
                        'tracking_disable': True,
                        'mail_create_nosubscribe': True,
                        'mail_create_nolog': True,
                        'phone_validation_skip': True,  # Skip phone validation
                    }
                    customer = request.env['res.partner'].with_context(ctx).sudo().create(customer_vals)
                    
                    # Cek apakah customer tag ada, jika ada tambahkan
                    customer_tag = request.env.ref('pitcar_custom.customer_tag', raise_if_not_found=False)
                    if customer_tag:
                        customer.write({'category_id': [(4, customer_tag.id)]})
                    
                    # Buat kendaraan baru
                    car_vals = {
                        'number_plate': plate_number,
                        'partner_id': customer.id,
                        'brand': int(kw.get('brand_id')),
                        'brand_type': int(kw.get('brand_type_id')),
                        'color': kw.get('car_color', 'Unknown'),
                        'year': kw.get('car_year', str(datetime.now().year)),
                        'transmission': int(kw.get('transmission_id')) if kw.get('transmission_id') else False,
                        'engine_type': kw.get('engine_type', 'petrol'),
                    }
                    car = request.env['res.partner.car'].sudo().create(car_vals)
                
                # Create booking
                booking_vals = {
                    'partner_id': car.partner_id.id,
                    'partner_car_id': car.id,
                    'booking_date': kw.get('date'),
                    'booking_time': float(kw.get('time')),
                    'service_category': kw.get('service_category', 'maintenance'),
                    'service_subcategory': kw.get('service_subcategory', 'periodic_service'),
                    'stall_id': stall_id,
                    'notes': kw.get('notes', ''),
                    'state': 'draft',
                    'booking_source': 'web',
                }
                
                booking = request.env['pitcar.service.booking'].sudo().create(booking_vals)
                
                # Add service lines
                for service_id in kw.get('service_ids', []):
                    product = request.env['product.product'].sudo().browse(int(service_id))
                    if product.exists():
                        line_vals = {
                            'booking_id': booking.id,
                            'product_id': product.id,
                            'name': product.name,
                            'quantity': 1,
                            'price_unit': product.list_price,
                            'service_duration': getattr(product, 'service_duration', 1.0),
                            'tax_ids': [(6, 0, product.taxes_id.ids)],
                        }
                        request.env['pitcar.service.booking.line'].sudo().create(line_vals)
                
                # Force compute all fields to avoid cache issues
                booking.invalidate_recordset()
                
                # Auto confirm booking
                booking.sudo().action_confirm()
                
                # Prepare response data
                response_data = {
                    'booking_id': booking.id,
                    'booking_reference': booking.name,
                    'booking_date': fields.Date.to_string(booking.booking_date),
                    'booking_time': booking.formatted_time,
                    'stall': booking.stall_id.name if booking.stall_id else 'Not Assigned',
                    'total_amount': booking.amount_total,
                    'customer_name': booking.partner_id.name,
                    'car_info': car.name,
                }
                
                return {
                    'status': 'success',
                    'data': response_data
                }
            
        except Exception as e:
            _logger.error(f"Error in create_booking: {str(e)}")
            request.env.cr.rollback()
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/booking/stall-status', type='json', auth="public", methods=['POST'], csrf=False)
    def get_stall_status(self, **kw):
        """Mendapatkan status real-time semua stall"""
        try:
            date = kw.get('date', fields.Date.today())
            
            stalls = request.env['pitcar.service.stall'].sudo().search([('active', '=', True)])
            
            stall_status = []
            for stall in stalls:
                bookings = request.env['pitcar.service.booking'].sudo().search([
                    ('stall_id', '=', stall.id),
                    ('booking_date', '=', date),
                    ('state', 'not in', ['cancelled']),
                ], order='booking_time')
                
                timeline = []
                for booking in bookings:
                    timeline.append({
                        'booking_id': booking.id,
                        'customer': booking.partner_id.name,
                        'car': booking.partner_car_id.name,
                        'service': booking.service_subcategory,
                        'start_time': booking.booking_time,
                        'end_time': booking.booking_end_time,
                        'status': booking.state,
                    })
                
                stall_status.append({
                    'stall_id': stall.id,
                    'stall_name': stall.name,
                    'timeline': timeline,
                    'next_available': fields.Datetime.to_string(stall.next_available_time) if stall.next_available_time else None,
                })
            
            return {
                'status': 'success',
                'data': stall_status
            }
            
        except Exception as e:
            _logger.error(f"Error in get_stall_status: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/booking/get-brands', type='json', auth="public", methods=['POST'], csrf=False)
    def get_brands(self, **kw):
        """Mendapatkan daftar brand mobil"""
        try:
            brands = request.env['res.partner.car.brand'].sudo().search([], order='name')
            result = []
            for brand in brands:
                result.append({
                    'id': brand.id,
                    'name': brand.name
                })
            return {'status': 'success', 'data': result}
        except Exception as e:
            _logger.error(f"Error in get_brands: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/booking/get-brand-types', type='json', auth="public", methods=['POST'], csrf=False)
    def get_brand_types(self, **kw):
        """Mendapatkan daftar tipe mobil berdasarkan brand"""
        try:
            brand_id = kw.get('brand_id')
            if not brand_id:
                return {'status': 'error', 'message': 'Brand ID is required'}
            
            types = request.env['res.partner.car.type'].sudo().search([
                ('brand', '=', int(brand_id))
            ], order='name')
            
            result = []
            for type_ in types:
                result.append({
                    'id': type_.id,
                    'name': type_.name
                })
            return {'status': 'success', 'data': result}
        except Exception as e:
            _logger.error(f"Error in get_brand_types: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/booking/get-services', type='json', auth="public", methods=['POST'], csrf=False)
    def get_services(self, **kw):
        """Mendapatkan daftar layanan yang tersedia"""
        try:
            service_category = kw.get('service_category', 'maintenance')
            
            # Ganti query karena service_category tidak ada di product.product
            # Gunakan product type service dan filter berdasarkan nama atau kategori produk
            domain = [
                ('type', '=', 'service'),
                ('sale_ok', '=', True),
            ]
            
            # Jika ada kategori tertentu, bisa ditambahkan filter custom
            # Misalnya menggunakan kategori produk atau custom field
            products = request.env['product.product'].sudo().search(domain)
            
            result = []
            for product in products:
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'price': product.list_price,
                    'duration': product.service_duration if hasattr(product, 'service_duration') else 1.0,
                    'description': product.description_sale or ''
                })
            
            return {'status': 'success', 'data': result}
        except Exception as e:
            _logger.error(f"Error in get_services: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/get-transmissions', type='json', auth="public", methods=['POST'], csrf=False)
    def get_transmissions(self, **kw):
        """Mendapatkan daftar jenis transmisi"""
        try:
            transmissions = request.env['res.partner.car.transmission'].sudo().search([], order='name')
            result = []
            for transmission in transmissions:
                result.append({
                    'id': transmission.id,
                    'name': transmission.name
                })
            return {'status': 'success', 'data': result}
        except Exception as e:
            _logger.error(f"Error in get_transmissions: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/booking/status', type='json', auth="public", methods=['POST'], csrf=False)
    def get_booking_status(self, **kw):
        """Mendapatkan status booking"""
        try:
            booking_id = kw.get('booking_id')
            if not booking_id:
                return {'status': 'error', 'message': 'Booking ID is required'}
            
            booking = request.env['pitcar.service.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'status': 'error', 'message': 'Booking not found'}
            
            return {
                'status': 'success',
                'data': {
                    'booking_id': booking.id,
                    'booking_reference': booking.name,
                    'state': booking.state,
                    'customer': booking.partner_id.name,
                    'car': booking.partner_car_id.name,
                    'booking_date': fields.Date.to_string(booking.booking_date),
                    'booking_time': booking.formatted_time,
                    'stall': booking.stall_id.name,
                    'total_amount': booking.amount_total,
                    'services': [{
                        'name': line.name,
                        'quantity': line.quantity,
                        'price': line.price_unit,
                        'subtotal': line.price_subtotal
                    } for line in booking.booking_line_ids if not line.display_type]
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_booking_status: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/list', type='json', auth="public", methods=['POST'], csrf=False)
    def get_booking_list(self, **kw):
        """Mendapatkan daftar booking dengan filter"""
        try:
            # Parameter filter
            date_from = kw.get('date_from', fields.Date.today())
            date_to = kw.get('date_to', fields.Date.today())
            state = kw.get('state', False)
            customer_name = kw.get('customer_name', False)
            plate_number = kw.get('plate_number', False)
            
            domain = [
                ('booking_date', '>=', date_from),
                ('booking_date', '<=', date_to),
            ]
            
            if state:
                domain.append(('state', '=', state))
            if customer_name:
                domain.append(('partner_id.name', 'ilike', customer_name))
            if plate_number:
                domain.append(('partner_car_id.number_plate', 'ilike', plate_number))
                
            # Pagination
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 10))
            offset = (page - 1) * limit
            
            # Sorting
            order = kw.get('sort', 'booking_date desc, booking_time')
            
            # Fetch bookings
            bookings = request.env['pitcar.service.booking'].sudo().search(
                domain, limit=limit, offset=offset, order=order
            )
            
            total_count = request.env['pitcar.service.booking'].sudo().search_count(domain)
            
            result = []
            for booking in bookings:
                result.append({
                    'id': booking.id,
                    'name': booking.name,
                    'customer': booking.partner_id.name,
                    'car': booking.partner_car_id.name,
                    'plate_number': booking.partner_car_id.number_plate,
                    'booking_date': fields.Date.to_string(booking.booking_date),
                    'booking_time': booking.formatted_time,
                    'service_type': booking.service_subcategory,
                    'stall': booking.stall_id.name if booking.stall_id else 'Unassigned',
                    'state': booking.state,
                    'total_amount': booking.amount_total,
                    'created_at': fields.Datetime.to_string(booking.create_date),
                })
            
            return {
                'status': 'success',
                'data': result,
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'limit': limit,
                    'total_pages': math.ceil(total_count / limit)
                }
            }
                
        except Exception as e:
            _logger.error(f"Error in get_booking_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/stats', type='json', auth="public", methods=['POST'], csrf=False)
    def get_booking_stats(self, **kw):
        """Mendapatkan statistik booking untuk dashboard"""
        try:
            date_from = kw.get('date_from', fields.Date.today())
            date_to = kw.get('date_to', fields.Date.today())
            
            domain_base = [
                ('booking_date', '>=', date_from),
                ('booking_date', '<=', date_to),
            ]
            
            # Total booking per status
            stats_by_state = {}
            states = ['draft', 'confirmed', 'converted', 'cancelled']
            for state in states:
                domain = domain_base + [('state', '=', state)]
                count = request.env['pitcar.service.booking'].sudo().search_count(domain)
                stats_by_state[state] = count
            
            # Total booking per stall
            stats_by_stall = {}
            stalls = request.env['pitcar.service.stall'].sudo().search([])
            for stall in stalls:
                domain = domain_base + [('stall_id', '=', stall.id)]
                count = request.env['pitcar.service.booking'].sudo().search_count(domain)
                stats_by_stall[stall.name] = count
            
            # Total booking per service type
            stats_by_service = {}
            service_types = request.env['pitcar.service.booking'].sudo()._fields['service_subcategory'].selection
            for service_code, service_name in service_types:
                domain = domain_base + [('service_subcategory', '=', service_code)]
                count = request.env['pitcar.service.booking'].sudo().search_count(domain)
                stats_by_service[service_name] = count
            
            # Booking per hari (untuk grafik)
            stats_by_day = []
            current_date = fields.Date.from_string(date_from)
            end_date = fields.Date.from_string(date_to)
            while current_date <= end_date:
                domain = [('booking_date', '=', current_date)]
                count = request.env['pitcar.service.booking'].sudo().search_count(domain)
                stats_by_day.append({
                    'date': fields.Date.to_string(current_date),
                    'count': count
                })
                current_date += timedelta(days=1)
            
            return {
                'status': 'success',
                'data': {
                    'total_bookings': sum(stats_by_state.values()),
                    'by_state': stats_by_state,
                    'by_stall': stats_by_stall,
                    'by_service': stats_by_service,
                    'by_day': stats_by_day
                }
            }
                
        except Exception as e:
            _logger.error(f"Error in get_booking_stats: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/update-status', type='json', auth="public", methods=['POST'], csrf=False)
    def update_booking_status(self, **kw):
        """Update status booking"""
        try:
            booking_id = kw.get('booking_id')
            new_state = kw.get('state')
            stall_id = kw.get('stall_id', False)
            
            if not all([booking_id, new_state]):
                return {'status': 'error', 'message': 'Missing required parameters'}
                
            booking = request.env['pitcar.service.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'status': 'error', 'message': 'Booking not found'}
                
            # Validasi perubahan state
            valid_transitions = {
                'draft': ['confirmed', 'cancelled'],
                'confirmed': ['converted', 'cancelled'],
                'converted': [],  # Tidak bisa diubah lagi
                'cancelled': ['draft']  # Optional: allow reactivation
            }
            
            if new_state not in valid_transitions.get(booking.state, []):
                return {
                    'status': 'error', 
                    'message': f'Cannot change status from {booking.state} to {new_state}'
                }
            
            values = {'state': new_state}
            if stall_id:
                values['stall_id'] = int(stall_id)
                
            booking.write(values)
            
            # Jalankan action khusus sesuai state baru
            if new_state == 'confirmed':
                booking.action_confirm()
            elif new_state == 'cancelled':
                booking.action_cancel()
            
            return {
                'status': 'success',
                'message': 'Booking status updated successfully',
                'data': {
                    'id': booking.id,
                    'state': booking.state,
                    'stall': booking.stall_id.name if booking.stall_id else 'Unassigned'
                }
            }
                
        except Exception as e:
            _logger.error(f"Error in update_booking_status: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/daily-schedule', type='json', auth="public", methods=['POST'], csrf=False)
    def get_daily_schedule(self, **kw):
        """Mendapatkan jadwal booking harian untuk tampilan kalender"""
        try:
            date = kw.get('date', fields.Date.today())
            
            bookings = request.env['pitcar.service.booking'].sudo().search([
                ('booking_date', '=', date),
                ('state', 'not in', ['cancelled'])
            ], order='booking_time')
            
            events = []
            for booking in bookings:
                start_hour = int(booking.booking_time)
                start_minute = int((booking.booking_time - start_hour) * 60)
                
                end_hour = int(booking.booking_end_time)
                end_minute = int((booking.booking_end_time - end_hour) * 60)
                
                start_time = f"{start_hour:02d}:{start_minute:02d}"
                end_time = f"{end_hour:02d}:{end_minute:02d}"
                
                events.append({
                    'id': booking.id,
                    'title': f"{booking.partner_id.name} - {booking.partner_car_id.number_plate}",
                    'start': f"{date}T{start_time}",
                    'end': f"{date}T{end_time}",
                    'resource': booking.stall_id.id if booking.stall_id else 'unassigned',
                    'allDay': False,
                    'extendedProps': {
                        'customer': booking.partner_id.name,
                        'car': booking.partner_car_id.name,
                        'plate': booking.partner_car_id.number_plate,
                        'service': booking.service_subcategory,
                        'status': booking.state,
                        'booking_ref': booking.name
                    }
                })
            
            # Get stall data for resources
            stalls = request.env['pitcar.service.stall'].sudo().search([('active', '=', True)])
            resources = []
            for stall in stalls:
                resources.append({
                    'id': stall.id,
                    'title': stall.name,
                    'stall_code': stall.code
                })
            
            return {
                'status': 'success',
                'data': {
                    'events': events,
                    'resources': resources
                }
            }
                
        except Exception as e:
            _logger.error(f"Error in get_daily_schedule: {str(e)}")
            return {'status': 'error', 'message': str(e)}