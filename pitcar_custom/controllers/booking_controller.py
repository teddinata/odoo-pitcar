from odoo import http, fields
from odoo.http import request
import logging
from datetime import datetime, timedelta, date, time
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
                
                # Tentukan stall_position berdasarkan stall.name
                stall_position = 'unassigned'
                if stall.name and "Stall " in stall.name:
                    try:
                        stall_number = int(stall.name.replace("Stall ", ""))
                        if 1 <= stall_number <= 10:
                            stall_position = f'stall{stall_number}'
                    except ValueError:
                        pass
                
                # Jika tidak ada konflik, tambahkan ke available stalls
                if not conflicting_bookings:
                    available_stalls.append({
                        'id': stall.id,
                        'name': stall.name,
                        'code': stall.code,
                        'mechanics': [{'id': m.id, 'name': m.name} for m in stall.mechanic_ids],
                        'booked_slots': booked_slots,
                        'is_available': True,
                        'stall_position': stall_position  # Tambahkan informasi ini
                    })
                else:
                    # Optional: Return stall yang sudah terisi juga dengan flag is_available=False
                    available_stalls.append({
                        'id': stall.id,
                        'name': stall.name,
                        'code': stall.code,
                        'mechanics': [{'id': m.id, 'name': m.name} for m in stall.mechanic_ids],
                        'booked_slots': booked_slots,
                        'is_available': False,
                        'stall_position': stall_position  # Tambahkan informasi ini
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
                # Ubah dari 8 menjadi 10 stall
                for i in range(1, 11):  # 1 sampai 10
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
                # Ubah dari 6 menjadi 10 stall
                for i in range(1, 11):  # 1 sampai 10
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
        
    @http.route('/web/v1/booking/add-additional-stalls', type='json', auth="public", methods=['POST'], csrf=False)
    def add_additional_stalls(self, **kw):
        """Tambahkan stall tambahan jika diperlukan"""
        try:
            # Cek stall tertinggi yang sudah ada
            stalls = request.env['pitcar.service.stall'].sudo().search([], order='id desc', limit=1)
            
            highest_stall_number = 0
            if stalls:
                # Coba ekstrak nomor dari nama stall terakhir
                # Asumsi format: "Stall X"
                stall_name = stalls[0].name
                if "Stall " in stall_name:
                    try:
                        highest_stall_number = int(stall_name.replace("Stall ", ""))
                    except ValueError:
                        highest_stall_number = 0
            
            # Tambahkan stall baru hingga mencapai 10
            stalls_added = 0
            for i in range(highest_stall_number + 1, 11):
                request.env['pitcar.service.stall'].sudo().create({
                    'name': f'Stall {i}',
                    'code': f'S{i:02d}',
                    'active': True
                })
                stalls_added += 1
            
            return {
                'status': 'success', 
                'message': f'Added {stalls_added} new stalls', 
                'total_stalls': 10
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/booking/create', type='json', auth="public", methods=['POST'], csrf=False)
    def create_booking(self, **kw):
        """Create booking lengkap dengan registrasi customer/kendaraan jika diperlukan"""
        try:
            with request.env.cr.savepoint():
                # Validasi input wajib
                required_fields = ['plate_number', 'date', 'time', 'stall_id']
                for field in required_fields:
                    if not kw.get(field):
                        return {'status': 'error', 'message': f'Missing required field: {field}'}
                
                # Check if either service_ids or template_id is provided
                if not kw.get('service_ids') and not kw.get('template_id'):
                    return {'status': 'error', 'message': 'Either service_ids or template_id is required'}
                
                # BAGIAN 1: VALIDASI STALL
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
                
                # Tentukan stall_position berdasarkan stall_id
                stall_position = 'unassigned'
                if stall.name and "Stall " in stall.name:
                    try:
                        stall_number = int(stall.name.replace("Stall ", ""))
                        if 1 <= stall_number <= 10:
                            stall_position = f'stall{stall_number}'
                    except ValueError:
                        pass
                
                # BAGIAN 2: VALIDASI KENDARAAN DAN CUSTOMER
                plate_number = kw.get('plate_number').replace(" ", "").upper()

                # Ambil parameter diskon booking online - KONSISTEN MENGGUNAKAN PERSENTASE
                is_online_booking = kw.get('is_online_booking', True)  # Default True untuk API web
                online_discount = kw.get('online_discount', 10.0)  # Default 10% - FORMAT PERSENTASE
                
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
                    
                # BAGIAN 3: PEMBUATAN BOOKING - DISKON HANDLING YANG DIKONSOLIDASI
                # Create booking with appropriate stall_id and stall_position
                booking_vals = {
                    'partner_id': car.partner_id.id,
                    'partner_car_id': car.id,
                    'booking_date': kw.get('date'),
                    'booking_time': float(kw.get('time')),
                    'service_category': kw.get('service_category', 'maintenance'),
                    'service_subcategory': kw.get('service_subcategory', 'periodic_service'),
                    'stall_id': stall_id,
                    'stall_position': stall_position,
                    'notes': kw.get('notes', ''),
                    'state': 'draft',
                    'is_online_booking': is_online_booking,
                    'online_booking_discount': online_discount,  # Simpan persentase diskon
                    'booking_source': 'web',
                }
                
                # Check if a template is provided
                template_id = kw.get('template_id')
                service_ids = kw.get('service_ids', [])
                
                if template_id:
                    template = request.env['sale.order.template'].sudo().browse(int(template_id))
                    if template.exists():
                        booking_vals['sale_order_template_id'] = template.id
                
                # Buat booking tanpa lines dulu
                booking = request.env['pitcar.service.booking'].sudo().create(booking_vals)
                
                # BAGIAN 4: PEMBUATAN BOOKING LINES DENGAN DISKON YANG KONSISTEN
                # Jika ada template, gunakan template untuk mengisi booking_line_ids
                if template_id and booking.sale_order_template_id:
                    # Gunakan fungsi onchange untuk membuat lines dari template
                    booking._onchange_sale_order_template_id()
                    
                    # Terapkan diskon online hanya untuk produk service
                    if is_online_booking:
                        for line in booking.booking_line_ids:
                            if not line.display_type and line.product_id.type == 'service':  # Tambahkan check tipe
                                line.write({
                                    'online_discount': online_discount,
                                    'discount': online_discount
                                })
                        
                elif service_ids:
                    # Add all product lines individually
                    for service_id in service_ids:
                        product = request.env['product.product'].sudo().browse(int(service_id))
                        if product.exists():
                            # PERUBAHAN: Hanya berikan diskon untuk produk bertipe service
                            apply_discount = is_online_booking and product.type == 'service'
                            discount_value = online_discount if apply_discount else 0.0
                            
                            line_vals = {
                                'booking_id': booking.id,
                                'product_id': product.id,
                                'name': product.name,
                                'quantity': 1,
                                'price_unit': product.list_price,
                                'online_discount': discount_value,
                                'discount': discount_value,
                                'service_duration': getattr(product, 'service_duration', 0.0) if product.type == 'service' else 0.0,
                                'tax_ids': [(6, 0, product.taxes_id.ids)],
                            }
                            request.env['pitcar.service.booking.line'].sudo().create(line_vals)
                
                # Force compute all fields to avoid cache issues
                booking.invalidate_recordset()
                
                # Auto confirm booking
                booking.sudo().action_confirm()
                
                # BAGIAN 5: PERHITUNGAN TOTAL UNTUK RESPONSE - GUNAKAN COMPUTED FIELDS
                # Prepare response data - Gunakan computed fields yang sudah ada
                response_data = {
                    'booking_id': booking.id,
                    'booking_reference': booking.name,
                    'unique_code': booking.unique_code,
                    'booking_date': fields.Date.to_string(booking.booking_date),
                    'booking_time': booking.formatted_time,
                    'stall': booking.stall_id.name if booking.stall_id else 'Not Assigned',
                    'total_amount': booking.amount_total,  # Gunakan computed field
                    'original_amount': booking.total_before_discount,  # Gunakan computed field
                    'discount_amount': booking.discount_amount,  # Gunakan computed field
                    'discount_percentage': online_discount if is_online_booking else 0.0,
                    'customer_name': booking.partner_id.name,
                    'car_info': car.name,
                    'plate_number': car.number_plate,
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
        """Mendapatkan daftar layanan yang tersedia dan template paket layanan"""
        try:
            # Get service type parameter with default values
            service_type = kw.get('service_type', 'all')  # Options: 'all', 'individual', 'package'
            
            # Initialize result containers
            services = []
            template_packages = []
            
            # If requesting individual services or all
            if service_type in ['all', 'individual']:
                # Get individual services
                domain = [
                    ('type', '=', 'service'),
                    ('sale_ok', '=', True),
                ]
                    
                products = request.env['product.product'].sudo().search(domain)
                
                for product in products:
                    services.append({
                        'id': product.id,
                        'name': product.name,
                        'price': product.list_price,
                        'duration': product.service_duration if hasattr(product, 'service_duration') else 1.0,
                        'description': product.description_sale or '',
                        'type': 'individual'
                    })
            
            # If requesting package templates or all
            if service_type in ['all', 'package']:
                # Get service templates/packages
                templates = request.env['sale.order.template'].sudo().search([])
                
                for template in templates:
                    # Calculate total duration and price
                    total_duration = 0
                    total_price = 0
                    included_services = []
                    
                    for line in template.sale_order_template_line_ids:
                        if not line.display_type and line.product_id and line.product_id.type == 'service':
                            duration = line.service_duration or 0
                            price = line.product_id.list_price * line.product_uom_qty
                            
                            total_duration += duration
                            total_price += price
                            
                            included_services.append({
                                'id': line.product_id.id,
                                'name': line.name or line.product_id.name,
                                'quantity': line.product_uom_qty,
                                'duration': duration
                            })
                    
                    template_packages.append({
                        'id': template.id,
                        'name': template.name,
                        'price': total_price,
                        'duration': total_duration,
                        'description': template.note or '',
                        'included_services': included_services,
                        'type': 'package'
                    })
            
            # Format response based on what was requested
            result = {}
            if service_type == 'individual':
                result = {'individual_services': services}
            elif service_type == 'package':
                result = {'service_packages': template_packages}
            else:  # 'all'
                result = {
                    'individual_services': services,
                    'service_packages': template_packages
                }
            
            return {
                'status': 'success', 
                'data': result
            }
        except Exception as e:
            _logger.error(f"Error in get_services: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/booking/get-template-details', type='json', auth="public", methods=['POST'], csrf=False)
    def get_template_details(self, **kw):
        """Mendapatkan detail paket layanan dari template"""
        try:
            template_id = kw.get('template_id')
            if not template_id:
                return {'status': 'error', 'message': 'Template ID is required'}
            
            template = request.env['sale.order.template'].sudo().browse(int(template_id))
            if not template.exists():
                return {'status': 'error', 'message': 'Template not found'}
            
            lines = []
            total_duration = 0
            total_price = 0
            
            for line in template.sale_order_template_line_ids:
                if line.display_type:
                    # Untuk section dan note
                    lines.append({
                        'display_type': line.display_type,
                        'name': line.name,
                        'sequence': line.sequence
                    })
                    continue

                if not line.product_id:
                    continue
                
                # PERUBAHAN: Gunakan price_unit dari template jika ada
                unit_price = line.price_unit or line.product_id.list_price
                line_price = unit_price * line.product_uom_qty
                
                # Add service duration if it's a service product
                duration = 0
                if line.product_id.type == 'service':
                    duration = line.service_duration or 0
                    total_duration += duration * line.product_uom_qty
                
                # Tambahkan total price untuk semua produk (termasuk service dan product)
                total_price += line_price
                
                # Buat item line dengan struktur yang sama seperti aslinya
                line_item = {
                    'product_id': line.product_id.id,
                    'name': line.name or line.product_id.name,
                    'quantity': line.product_uom_qty,
                    'price_unit': unit_price,
                    'price_subtotal': line_price,
                    'duration': duration,
                    'sequence': line.sequence,
                    'tax_ids': line.product_id.taxes_id.ids if hasattr(line.product_id, 'taxes_id') else [],
                    'product_type': line.product_id.type
                }
                
                # BARU: Tambahkan field baru tanpa mengubah struktur dasar
                if hasattr(line, 'is_required'):
                    line_item['is_required'] = line.is_required
                    
                lines.append(line_item)
            
            # Buat hasil dengan struktur yang sama dengan API asli
            result = {
                'id': template.id,
                'name': template.name,
                'note': template.note,
                'lines': lines,
                'total_duration': total_duration,
                'total_price': total_price
            }
            
            # BARU: Tambahkan field baru tanpa mengubah struktur dasar
            if hasattr(template, 'booking_description') and template.booking_description:
                result['booking_description'] = template.booking_description
                
            if hasattr(template, 'booking_category') and template.booking_category:
                result['category'] = template.booking_category
                
            if hasattr(template, 'booking_image') and template.booking_image:
                result['thumbnail_url'] = f'/web/image/sale.order.template/{template.id}/booking_image'
                
            return {
                'status': 'success',
                'data': result
            }
        except Exception as e:
            _logger.error(f"Error in get_template_details: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/get-template-categories', type='json', auth="public", methods=['POST'], csrf=False)
    def get_template_categories(self, **kw):
        """Mendapatkan daftar kategori template yang tersedia"""
        try:
            # Ambil kategori unik dari template yang ada
            templates = request.env['sale.order.template'].sudo().search([
                ('is_booking_template', '=', True),
                ('booking_category', '!=', False)
            ])
            
            categories = {}
            for template in templates:
                if template.booking_category not in categories:
                    categories[template.booking_category] = {
                        'code': template.booking_category,
                        'name': dict(template._fields['booking_category'].selection).get(template.booking_category, ''),
                        'count': 1
                    }
                else:
                    categories[template.booking_category]['count'] += 1
            
            return {
                'status': 'success',
                'data': list(categories.values())
            }
        except Exception as e:
            _logger.error(f"Error in get_template_categories: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/booking/get-templates', type='json', auth="public", methods=['POST'], csrf=False)
    def get_templates(self, **kw):
        """Mendapatkan daftar template paket layanan"""
        try:
            # BARU: Tambahkan filter kategori jika diminta, tapi tetap tampilkan semua template secara default
            domain = [('is_booking_template', '=', True)]  # Pastikan hanya template aktif
            
            # BARU: Jika explicitly filter untuk booking templates
            if kw.get('booking_only', False):
                domain.append(('is_booking_template', '=', True))
                
            # BARU: Filter kategori jika diminta
            if kw.get('category'):
                domain.append(('booking_category', '=', kw.get('category')))
                
            templates = request.env['sale.order.template'].sudo().search(domain)
            
            result = []
            for template in templates:
                # Hitung total durasi dan harga
                total_duration = 0
                total_price = 0
                services_count = 0
                products_count = 0  # Counter untuk produk fisik
                services_list = []
                products_list = []  # List untuk produk fisik
                
                # SAMA SEPERTI KODE ASLI: Loop melalui semua line
                for line in template.sale_order_template_line_ids:
                    if not line.display_type and line.product_id:
                        # PERUBAHAN: Prioritaskan price_unit dari template jika ada
                        unit_price = line.price_unit or line.product_id.list_price
                        price = unit_price * line.product_uom_qty
                        
                        if line.product_id.type == 'service':
                            # PERUBAHAN: Gunakan service_duration dari template line
                            duration = line.service_duration or 0
                            total_duration += duration * line.product_uom_qty
                            total_price += price
                            services_count += 1
                            
                            # Tambah service ke list - SAMA STRUKTUR SEPERTI ASLINYA
                            service_item = {
                                'id': line.product_id.id,
                                'name': line.product_id.name,
                                'quantity': line.product_uom_qty,
                                'duration': duration
                            }
                            
                            # BARU: Tambahkan field baru sebagai properti opsional
                            if hasattr(line, 'is_required'):
                                service_item['is_required'] = line.is_required
                                
                            services_list.append(service_item)
                        else:
                            # Produk fisik
                            total_price += price
                            products_count += 1
                            
                            # Tambah product ke list - SAMA STRUKTUR SEPERTI ASLINYA
                            product_item = {
                                'id': line.product_id.id,
                                'name': line.product_id.name,
                                'quantity': line.product_uom_qty
                            }
                            
                            # BARU: Tambahkan field baru sebagai properti opsional
                            if hasattr(line, 'is_required'):
                                product_item['is_required'] = line.is_required
                                
                            products_list.append(product_item)
                
                # Buat hasil dengan struktur yang sama dengan API asli
                template_data = {
                    'id': template.id,
                    'name': template.name,
                    'price': total_price,
                    'duration': total_duration,
                    'services_count': services_count,
                    'products_count': products_count,
                    'description': template.note or '',
                    'services': services_list,
                    'products': products_list
                }
                
                # BARU: Tambahkan field baru tanpa mengubah struktur dasar
                if hasattr(template, 'booking_category') and template.booking_category:
                    template_data['category'] = template.booking_category
                    
                if hasattr(template, 'booking_description') and template.booking_description:
                    template_data['booking_description'] = template.booking_description
                    
                if hasattr(template, 'booking_image') and template.booking_image:
                    template_data['thumbnail_url'] = f'/web/image/sale.order.template/{template.id}/booking_image'
                    
                if hasattr(template, 'is_booking_template'):
                    template_data['is_booking_template'] = template.is_booking_template
                
                result.append(template_data)
                
            return {'status': 'success', 'data': result}
        except Exception as e:
            _logger.error(f"Error in get_templates: {str(e)}")
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
        
    @http.route('/web/v1/booking/metrics', type='json', auth="public", methods=['POST'], csrf=False)
    def get_booking_metrics(self, **kw):
        """Mendapatkan metrik booking untuk dashboard"""
        try:
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            period_type = kw.get('period_type', 'day')
            
            domain = [('period_type', '=', period_type)]
            if date_from:
                domain.append(('date', '>=', date_from))
            if date_to:
                domain.append(('date', '<=', date_to))
                
            metrics = request.env['pitcar.booking.metrics'].sudo().search(domain, order='date')
            
            # Jika tidak ada data, kembalikan response yang sesuai
            if not metrics:
                return {
                    'status': 'success', 
                    'data': {
                        'summary': {
                            'total_bookings': 0,
                            'confirmation_rate': 0,
                            'conversion_rate': 0,
                            'cancellation_rate': 0,
                            'actual_revenue': 0
                        },
                        'trend': []
                    }
                }
            
            # Hitung rata-rata tertimbang untuk persentase
            total_bookings = sum(metrics.mapped('total_bookings'))
            confirmed_bookings = sum(metrics.mapped('confirmed_bookings'))
            
            # Buat summary
            summary = {
                'total_bookings': total_bookings,
                'confirmed_bookings': sum(metrics.mapped('confirmed_bookings')),
                'converted_bookings': sum(metrics.mapped('converted_bookings')),
                'cancelled_bookings': sum(metrics.mapped('cancelled_bookings')),
                'confirmation_rate': sum(m.confirmation_rate * m.total_bookings for m in metrics) / total_bookings if total_bookings else 0,
                'conversion_rate': sum(m.conversion_rate * m.confirmed_bookings for m in metrics) / confirmed_bookings if confirmed_bookings else 0,
                'cancellation_rate': sum(m.cancellation_rate * m.total_bookings for m in metrics) / total_bookings if total_bookings else 0,
                'actual_revenue': sum(metrics.mapped('actual_revenue')),
                'potential_revenue': sum(metrics.mapped('potential_revenue')),
            }
            
            # Buat data trend
            trend = [{
                'date': fields.Date.to_string(m.date),
                'total': m.total_bookings,
                'confirmed': m.confirmed_bookings,
                'converted': m.converted_bookings,
                'cancelled': m.cancelled_bookings,
                'confirmation_rate': m.confirmation_rate,
                'conversion_rate': m.conversion_rate,
                'cancellation_rate': m.cancellation_rate,
                'revenue': m.actual_revenue,
            } for m in metrics]
            
            return {
                'status': 'success',
                'data': {
                    'summary': summary,
                    'trend': trend
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_booking_metrics: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/search', type='json', auth="public", methods=['POST'], csrf=False)
    def search_booking(self, **kw):
        """Mencari booking berdasarkan kode booking atau nomor plat"""
        try:
            booking_code = kw.get('booking_code')
            
            if not booking_code:
                return {'status': 'error', 'message': 'Booking code is required'}
            
            # Bersihkan kode booking (hapus spasi, uppercase)
            booking_code = booking_code.strip().upper()
            
            # Cari booking berdasarkan kode unik atau kode referensi
            booking = request.env['pitcar.service.booking'].sudo().search([
                '|',
                ('unique_code', '=', booking_code),
                ('name', '=', booking_code)
            ], limit=1)
            
            if not booking:
                return {'status': 'not_found', 'message': 'Booking not found'}
            
            # Prepare response data
            response_data = {
                'booking_id': booking.id,
                'booking_reference': booking.name,
                'unique_code': booking.unique_code,  # Tambahkan kode unik ke response
                'booking_date': fields.Date.to_string(booking.booking_date),
                'booking_time': booking.formatted_time,
                'stall': booking.stall_id.name if booking.stall_id else 'Not Assigned',
                'total_amount': booking.amount_total,
                'customer_name': booking.partner_id.name,
                'car_info': booking.partner_car_id.name,
                'state': booking.state,
                'plate_number': booking.partner_car_id.number_plate,
                # Tambahkan QR Code untuk cetak tiket
                'qr_code_data': booking.unique_code  # Gunakan kode unik untuk QR
            }
            
            return {
                'status': 'success',
                'data': response_data
            }
                
        except Exception as e:
            _logger.error(f"Error in search_booking: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/archive', type='json', auth="public", methods=['POST'], csrf=False)
    def archive_booking(self, **kw):
        """Archive booking API endpoint"""
        try:
            booking_id = kw.get('booking_id')
            if not booking_id:
                return {'status': 'error', 'message': 'Booking ID is required'}
            
            booking = request.env['pitcar.service.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'status': 'error', 'message': 'Booking not found'}
            
            # Archive booking
            booking.action_archive_booking()
            
            return {
                'status': 'success',
                'message': 'Booking archived successfully'
            }
        except Exception as e:
            _logger.error(f"Error in archive_booking: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/booking/unarchive', type='json', auth="public", methods=['POST'], csrf=False)
    def unarchive_booking(self, **kw):
        """Unarchive booking API endpoint"""
        try:
            booking_id = kw.get('booking_id')
            if not booking_id:
                return {'status': 'error', 'message': 'Booking ID is required'}
            
            booking = request.env['pitcar.service.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'status': 'error', 'message': 'Booking not found'}
            
            # Unarchive booking
            booking.action_unarchive_booking()
            
            return {
                'status': 'success',
                'message': 'Booking unarchived successfully'
            }
        except Exception as e:
            _logger.error(f"Error in unarchive_booking: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/booking/checkin', type='json', auth="public", methods=['POST'], csrf=False)
    def checkin_booking(self, **kw):
        """Check-in API endpoint for frontend"""
        try:
            unique_code = kw.get('unique_code')
            if not unique_code:
                return {'status': 'error', 'message': 'Booking code is required'}
            
            result = request.env['pitcar.service.booking'].sudo().process_frontend_checkin(unique_code)
            return result
        except Exception as e:
            _logger.error(f"Error in checkin_booking: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/booking/dashboard', type='json', auth="public", methods=['POST'], csrf=False)
    def get_booking_dashboard(self, **kw):
        """Get dashboard data for frontend"""
        try:
            date = kw.get('date', fields.Date.today())
            
            result = request.env['pitcar.service.booking'].sudo().get_dashboard_data(date)
            return {
                'status': 'success',
                'data': result
            }
        except Exception as e:
            _logger.error(f"Error in get_booking_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/stall-utilization', type='json', auth="public", methods=['POST'], csrf=False)
    def get_stall_utilization(self, **kw):
        """Enhanced stall utilization data with deeper metrics"""
        try:
            date_from = kw.get('date_from', fields.Date.today())
            date_to = kw.get('date_to', fields.Date.today())
            
            # Fetch all active stalls
            stalls = request.env['pitcar.service.stall'].sudo().search([('active', '=', True)])
            
            # Define shop working hours
            working_hours_start = 8.0  # 08:00
            working_hours_end = 17.0   # 17:00
            working_hours_per_day = working_hours_end - working_hours_start  # 9 hours
            
            # Calculate date range details
            start_date = fields.Date.from_string(date_from)
            end_date = fields.Date.from_string(date_to)
            days_count = (end_date - start_date).days + 1
            
            # Total available hours for all stalls during period
            total_available_hours = len(stalls) * working_hours_per_day * days_count
            
            # Enhanced stall stats with more metrics
            stall_stats = []
            total_utilized_hours = 0
            total_bookings = 0
            highest_utilization = 0
            most_efficient_stall = None
            
            for stall in stalls:
                # Get ALL bookings for this stall in date range (regardless of state)
                all_bookings = request.env['pitcar.service.booking'].sudo().search([
                    ('stall_id', '=', stall.id),
                    ('booking_date', '>=', date_from),
                    ('booking_date', '<=', date_to),
                ])
                
                # Get confirmed/converted bookings for utilization calculation
                active_bookings = all_bookings.filtered(lambda b: b.state in ['confirmed', 'converted'])
                
                # Get active sale orders using this stall
                active_orders = request.env['sale.order'].sudo().search([
                    ('stall_id', '=', stall.id),
                    ('controller_mulai_servis', '>=', datetime.combine(start_date, time(0, 0))),
                    ('controller_mulai_servis', '<', datetime.combine(end_date + timedelta(days=1), time(0, 0))),
                ])
                
                # Calculate stats
                stall_utilized_hours = 0
                booking_count = len(all_bookings)
                booking_status = {
                    'total': booking_count,
                    'draft': len(all_bookings.filtered(lambda b: b.state == 'draft')),
                    'confirmed': len(all_bookings.filtered(lambda b: b.state == 'confirmed')),
                    'converted': len(all_bookings.filtered(lambda b: b.state == 'converted')),
                    'cancelled': len(all_bookings.filtered(lambda b: b.state == 'cancelled')),
                    'archived': len(all_bookings.filtered(lambda b: b.is_archived)),
                    'not_archived': len(all_bookings.filtered(lambda b: not b.is_archived))
                }
                
                completed_count = len(all_bookings.filtered(lambda b: b.state == 'converted'))
                service_times = []
                peak_hour_usage = {}  # Track usage by hour
                
                # Calculate hours from bookings
                for booking in active_bookings:
                    # Calculate service duration from booking
                    if booking.booking_time and booking.booking_end_time and booking.booking_end_time > booking.booking_time:
                        duration = booking.booking_end_time - booking.booking_time
                        stall_utilized_hours += duration
                        service_times.append(duration)
                        
                        # Track hourly distribution
                        start_hour = int(booking.booking_time)
                        end_hour = int(booking.booking_end_time)
                        
                        # Update peak hour tracking
                        for hour in range(start_hour, end_hour + 1):
                            if 8 <= hour <= 17:  # Only count during working hours
                                if hour not in peak_hour_usage:
                                    peak_hour_usage[hour] = 0
                                
                                # Add partial or full hour
                                if hour == start_hour and hour == end_hour:
                                    peak_hour_usage[hour] += booking.booking_end_time - booking.booking_time
                                elif hour == start_hour:
                                    peak_hour_usage[hour] += (hour + 1) - booking.booking_time
                                elif hour == end_hour:
                                    peak_hour_usage[hour] += booking.booking_end_time - hour
                                else:
                                    peak_hour_usage[hour] += 1.0
                
                # Calculate hours from sale orders
                for order in active_orders:
                    if order.controller_mulai_servis:
                        end_time = order.controller_selesai or fields.Datetime.now()
                        if end_time > order.controller_mulai_servis:
                            # Calculate hours while accounting for job stops
                            if hasattr(order, 'lead_time_servis') and order.lead_time_servis:
                                stall_utilized_hours += order.lead_time_servis
                            else:
                                # Basic calculation if lead_time_servis is not available
                                duration_hours = (end_time - order.controller_mulai_servis).total_seconds() / 3600
                                stall_utilized_hours += duration_hours
                
                # Get current active orders for this stall
                current_orders = request.env['sale.order'].sudo().search([
                    ('stall_id', '=', stall.id),
                    ('controller_mulai_servis', '!=', False),
                    ('controller_selesai', '=', False)
                ])
                
                active_order_details = []
                for order in current_orders:
                    active_order_details.append({
                        'id': order.id,
                        'name': order.name,
                        'customer': order.partner_id.name,
                        'start_time': fields.Datetime.to_string(order.controller_mulai_servis),
                        'elapsed_hours': (fields.Datetime.now() - order.controller_mulai_servis).total_seconds() / 3600,
                        'is_booking': order.is_booking,
                        'origin_booking_id': order.booking_id.id if order.booking_id else False
                    })
                
                # Calculate average service time
                avg_service_time = sum(service_times) / len(service_times) if service_times else 0
                
                # Determine peak hour for this stall
                peak_hour = max(peak_hour_usage.items(), key=lambda x: x[1])[0] if peak_hour_usage else None
                peak_utilization = max(peak_hour_usage.values()) if peak_hour_usage else 0
                
                # Calculate stall-specific available hours
                stall_available_hours = working_hours_per_day * days_count
                
                # Calculate utilization rate
                utilization_rate = (stall_utilized_hours / stall_available_hours) * 100 if stall_available_hours > 0 else 0
                
                # Update totals
                total_utilized_hours += stall_utilized_hours
                total_bookings += booking_count
                
                # Check if this is the most efficient stall
                if utilization_rate > highest_utilization:
                    highest_utilization = utilization_rate
                    most_efficient_stall = {
                        'stall_id': stall.id,
                        'stall_name': stall.name,
                        'utilization_rate': utilization_rate
                    }
                
                # Format for display
                stall_stats.append({
                    'stall_id': stall.id,
                    'stall_name': stall.name,
                    'utilized_hours': stall_utilized_hours,
                    'available_hours': stall_available_hours,
                    'utilization_rate': round(utilization_rate, 2),
                    'booking_count': booking_count,
                    'booking_status': booking_status,
                    'completed_count': completed_count,
                    'completion_rate': round((completed_count / booking_count) * 100, 2) if booking_count > 0 else 0,
                    'avg_service_time': avg_service_time,
                    'peak_hour': peak_hour,
                    'peak_utilization': peak_utilization,
                    'hourly_usage': peak_hour_usage,
                    'current_orders': active_order_details
                })
            
            # Calculate overall utilization rate
            overall_utilization_rate = (total_utilized_hours / total_available_hours) * 100 if total_available_hours > 0 else 0
            
            # Daily utilization trend
            daily_stats = []
            current_date = start_date
            while current_date <= end_date:
                date_str = fields.Date.to_string(current_date)
                
                # Calculate hours used on this date across all stalls
                day_utilized_hours = 0
                day_bookings = 0
                stall_usage = {}  # Track usage by stall for this day
                
                for stall in stalls:
                    stall_usage[stall.id] = 0
                    
                    bookings = request.env['pitcar.service.booking'].sudo().search([
                        ('stall_id', '=', stall.id),
                        ('booking_date', '=', date_str),
                        ('state', 'in', ['confirmed', 'converted']),
                    ])
                    
                    stall_hours = 0
                    for booking in bookings:
                        duration = booking.booking_end_time - booking.booking_time
                        if duration > 0:
                            stall_hours += duration
                            day_utilized_hours += duration
                        day_bookings += 1
                    
                    stall_usage[stall.id] = stall_hours
                
                # Calculate daily utilization rate
                day_available_hours = len(stalls) * working_hours_per_day
                day_utilization_rate = (day_utilized_hours / day_available_hours) * 100 if day_available_hours > 0 else 0
                
                # Find most used stall for this day
                most_used_stall = None
                if stall_usage:
                    stall_id = max(stall_usage.items(), key=lambda x: x[1])[0]
                    stall = request.env['pitcar.service.stall'].sudo().browse(stall_id)
                    if stall.exists():
                        most_used_stall = {
                            'stall_id': stall.id,
                            'stall_name': stall.name,
                            'hours': stall_usage[stall.id]
                        }
                
                daily_stats.append({
                    'date': date_str,
                    'utilized_hours': day_utilized_hours,
                    'available_hours': day_available_hours,
                    'utilization_rate': round(day_utilization_rate, 2),
                    'booking_count': day_bookings,
                    'most_used_stall': most_used_stall,
                    'stall_breakdown': stall_usage
                })
                
                current_date += timedelta(days=1)
            
            # Get mechanic assignment data
            mechanic_stats = []
            mechanics = request.env['pitcar.mechanic.new'].sudo().search([])
            
            for mechanic in mechanics:
                # Count bookings where this mechanic was assigned via stall
                mechanic_stalls = stalls.filtered(lambda s: mechanic.id in s.mechanic_ids.ids)
                mechanic_bookings = request.env['pitcar.service.booking'].sudo().search_count([
                    ('stall_id', 'in', mechanic_stalls.ids),
                    ('booking_date', '>=', date_from),
                    ('booking_date', '<=', date_to),
                    ('state', 'in', ['confirmed', 'converted']),
                ])
                
                if mechanic_bookings > 0:
                    mechanic_stats.append({
                        'mechanic_id': mechanic.id,
                        'name': mechanic.name,
                        'bookings': mechanic_bookings,
                        'assigned_stalls': [{
                            'stall_id': stall.id,
                            'stall_name': stall.name
                        } for stall in mechanic_stalls]
                    })
            
            return {
                'status': 'success',
                'data': {
                    'overall_utilization_rate': round(overall_utilization_rate, 2),
                    'total_utilized_hours': total_utilized_hours,
                    'total_available_hours': total_available_hours,
                    'total_bookings': total_bookings,
                    'most_efficient_stall': most_efficient_stall,
                    'stall_stats': stall_stats,
                    'daily_stats': daily_stats,
                    'mechanic_stats': mechanic_stats
                }
            }
                    
        except Exception as e:
            _logger.error(f"Error in get_stall_utilization: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/booking/statistics', type='json', auth="public", methods=['POST'], csrf=False)
    def get_booking_statistics(self, **kw):
        """Mendapatkan statistik booking lengkap untuk dashboard"""
        try:
            # Handle filter parameter
            start_date = kw.get('start_date', fields.Date.today())
            end_date = kw.get('end_date', fields.Date.today())
            month = kw.get('month', False)
            year = kw.get('year', False)
            
            # Jika menggunakan filter bulan
            if month and year:
                # Convert month/year to date range
                month = int(month)
                year = int(year)
                
                # Get first and last day of month
                start_date = fields.Date.to_string(date(year, month, 1))
                
                # Get last day of month
                if month == 12:
                    last_day = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    last_day = date(year, month + 1, 1) - timedelta(days=1)
                    
                end_date = fields.Date.to_string(last_day)
            
            # Domain untuk filtering booking
            domain = [
                ('booking_date', '>=', start_date),
                ('booking_date', '<=', end_date),
            ]
            
            # Current time
            current_time = fields.Datetime.now()
            
            # 1. Overall Statistics
            # Total bookings
            total_bookings = request.env['pitcar.service.booking'].sudo().search_count(domain)
            
            # Bookings by state
            bookings_by_state = {}
            states = ['draft', 'confirmed', 'converted', 'cancelled']
            for state in states:
                count = request.env['pitcar.service.booking'].sudo().search_count(domain + [('state', '=', state)])
                bookings_by_state[state] = count
            
            # Active bookings (confirmed not yet converted)
            active_bookings = bookings_by_state.get('confirmed', 0)
            
            # Completed bookings (converted)
            completed_bookings = bookings_by_state.get('converted', 0)
            
            # Completion rate
            completion_rate = (completed_bookings / total_bookings * 100) if total_bookings > 0 else 0
            
            # 2. Hourly distribution
            hourly_distribution = {}
            for hour in range(7, 19):  # 7:00 - 18:59
                hourly_distribution[hour] = {
                    'starts': 0,  # Booking starts at this hour
                    'completions': 0  # Booking completions at this hour
                }
            
            # Get all bookings
            bookings = request.env['pitcar.service.booking'].sudo().search(domain)
            
            # Populate hourly distribution
            for booking in bookings:
                # Booking start hour
                start_hour = int(booking.booking_time)
                if 7 <= start_hour <= 18:
                    hourly_distribution[start_hour]['starts'] += 1
                
                # Booking end hour (for completions - assume booking.booking_end_time exists)
                if booking.state in ['confirmed', 'converted'] and hasattr(booking, 'booking_end_time'):
                    end_hour = int(booking.booking_end_time)
                    if 7 <= end_hour <= 18:
                        hourly_distribution[end_hour]['completions'] += 1
            
            # 3. Service Category/Subcategory Statistics
            service_category = {
                'maintenance': 0,
                'repair': 0,
                'uncategorized': 0
            }
            
            service_subcategory = {
                'tune_up': 0,
                'tune_up_addition': 0,
                'periodic_service': 0,
                'periodic_service_addition': 0,
                'general_repair': 0,
                'oil_change': 0,
                'uncategorized': 0
            }
            
            # Count by category/subcategory
            for booking in bookings:
                # Category
                category = booking.service_category or 'uncategorized'
                if category in service_category:
                    service_category[category] += 1
                else:
                    service_category['uncategorized'] += 1
                
                # Subcategory
                subcategory = booking.service_subcategory or 'uncategorized'
                if subcategory in service_subcategory:
                    service_subcategory[subcategory] += 1
                else:
                    service_subcategory['uncategorized'] += 1
            
            # 4. Daily Flat Rate Trend
            # Define date range
            start_date_obj = fields.Date.from_string(start_date)
            end_date_obj = fields.Date.from_string(end_date)
            
            # Prepare daily stats
            daily_flat_rates = []
            
            current_date = start_date_obj
            while current_date <= end_date_obj:
                date_str = fields.Date.to_string(current_date)
                
                # Get bookings for this date
                day_bookings = request.env['pitcar.service.booking'].sudo().search([
                    ('booking_date', '=', date_str),
                    ('state', 'in', ['confirmed', 'converted'])
                ])
                
                # Calculate total flat rate for the day
                total_flat_rate = 0
                for booking in day_bookings:
                    # If flat_rate exists in booking, use it
                    if hasattr(booking, 'flat_rate'):
                        total_flat_rate += booking.flat_rate or 0
                    # Otherwise calculate from booking_end_time - booking_time
                    elif hasattr(booking, 'booking_end_time') and hasattr(booking, 'booking_time'):
                        duration = booking.booking_end_time - booking.booking_time
                        if duration > 0:
                            total_flat_rate += duration
                
                # Function to format duration
                def format_flat_rate(minutes):
                    if not minutes:
                        return '0j 0m'
                    
                    hours = int(minutes)
                    mins = int((minutes - hours) * 60)
                    
                    if mins == 0:
                        return f"{hours}j"
                    return f"{hours}j {mins}m"
                
                # Add to daily stats
                daily_flat_rates.append({
                    'date': date_str,
                    'flat_rate': total_flat_rate,
                    'flat_rate_formatted': format_flat_rate(total_flat_rate),
                    'order_count': len(day_bookings)
                })
                
                current_date += timedelta(days=1)
            
            # 5. Staff Statistics
            # Get active mechanics and advisors
            mechanics_active = request.env['hr.employee'].sudo().search_count([
                ('job_id.name', 'ilike', 'mechanic'),
                ('active', '=', True)
            ])
            
            advisors_active = request.env['hr.employee'].sudo().search_count([
                ('job_id.name', 'ilike', 'advisor'),
                ('active', '=', True)
            ])
            
            # 6. Flat Rate Statistics
            # Get flat rate efficiency if available
            flat_rate_efficiency = 0
            try:
                # Assuming there's a method to calculate flat rate efficiency
                # If not available, use a placeholder or skip
                flat_rate_efficiency = 100.0  # Placeholder
            except:
                flat_rate_efficiency = 0
            
            # Get mechanic flat rates if available
            mechanic_flat_rates = []
            try:
                employees = request.env['hr.employee'].sudo().search([
                    ('job_id.name', 'ilike', 'mechanic'),
                    ('active', '=', True)
                ])
                
                for employee in employees:
                    # Calculate flat rate for this mechanic
                    # This is simplified - implement actual calculation based on your model
                    mechanic_bookings = request.env['pitcar.service.booking'].sudo().search([
                        ('booking_date', '>=', start_date),
                        ('booking_date', '<=', end_date),
                        ('state', 'in', ['confirmed', 'converted']),
                        # Assuming there's a mechanic_id field in booking
                        ('mechanic_id', '=', employee.id)
                    ])
                    
                    mechanic_flat_rate = 0
                    order_count = len(mechanic_bookings)
                    
                    for booking in mechanic_bookings:
                        # If flat_rate exists in booking, use it
                        if hasattr(booking, 'flat_rate'):
                            mechanic_flat_rate += booking.flat_rate or 0
                        # Otherwise calculate from booking_end_time - booking_time
                        elif hasattr(booking, 'booking_end_time') and hasattr(booking, 'booking_time'):
                            duration = booking.booking_end_time - booking.booking_time
                            if duration > 0:
                                mechanic_flat_rate += duration
                    
                    # Only add if the mechanic has bookings
                    if order_count > 0:
                        mechanic_flat_rates.append({
                            'mechanic_id': employee.id,
                            'name': employee.name,
                            'flat_rate': mechanic_flat_rate,
                            'flat_rate_formatted': format_flat_rate(mechanic_flat_rate),
                            'order_count': order_count
                        })
            except Exception as e:
                _logger.error(f"Error calculating mechanic flat rates: {str(e)}")
            
            # Calculate total flat rate
            total_flat_rate = sum(m['flat_rate'] for m in mechanic_flat_rates)
            
            # Calculate average flat rate per mechanic
            avg_flat_rate_per_mechanic = total_flat_rate / len(mechanic_flat_rates) if mechanic_flat_rates else 0
            
            # Create flat rate stats
            flat_rate_stats = {
                'flat_rate_efficiency': flat_rate_efficiency,
                'total_flat_rate': total_flat_rate,
                'formatted': {
                    'total_flat_rate': format_flat_rate(total_flat_rate),
                    'avg_flat_rate_per_mechanic': format_flat_rate(avg_flat_rate_per_mechanic)
                },
                'total_orders': completed_bookings,
                'mechanic_flat_rates': mechanic_flat_rates,
                'daily_flat_rates': daily_flat_rates
            }
            
            # 7. Compile all statistics
            booking_stats = {
                'current_time': fields.Datetime.to_string(current_time),
                'overall': {
                    'total_orders': total_bookings,
                    'active_orders': active_bookings,
                    'completed_orders': completed_bookings,
                    'completion_rate': completion_rate,
                    'status_breakdown': bookings_by_state
                },
                'hourly_distribution': hourly_distribution,
                'service_category': service_category,
                'service_subcategory': service_subcategory,
                'staff': {
                    'mechanics': {'active': mechanics_active},
                    'advisors': {'active': advisors_active}
                },
                'flat_rate': flat_rate_stats
            }
            
            return {
                'status': 'success',
                'data': booking_stats
            }
                
        except Exception as e:
            _logger.error(f"Error in get_booking_statistics: {str(e)}")
            return self._handle_error("Failed to get booking statistics", str(e))