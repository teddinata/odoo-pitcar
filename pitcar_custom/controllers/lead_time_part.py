from odoo import http, fields
from odoo.http import request, Response
import json
import pytz
from datetime import datetime, timedelta
import logging
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError
import math

_logger = logging.getLogger(__name__)

class LeadTimePartController(http.Controller):
    def _validate_access(self, sale_order_id):
        """Validate user access and return sale order"""
        env = request.env
        sale_order = env['sale.order'].browse(sale_order_id)
        if not sale_order.exists():
            return None
        return sale_order

    def _format_datetime(self, dt):
        """Format datetime to Asia/Jakarta timezone"""
        if not dt:
            return None
        tz = pytz.timezone('Asia/Jakarta')
        local_dt = pytz.utc.localize(dt).astimezone(tz)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')

    def _format_time(self, dt):
        """Format time to HH:MM format"""
        if not dt:
            return None
        tz = pytz.timezone('Asia/Jakarta')
        local_dt = pytz.utc.localize(dt).astimezone(tz)
        return local_dt.strftime('%H:%M')

    def _parse_time(self, time_str):
        """Parse time string to UTC datetime"""
        try:
            tz = pytz.timezone('Asia/Jakarta')
            today = datetime.now(tz).date()
            local_dt = tz.localize(datetime.combine(today, datetime.strptime(time_str, '%H:%M').time()))
            return local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
        except ValueError:
            raise ValidationError("Invalid time format. Please use HH:MM format")

    def _get_purchase_details(self, purchase):
      """Get formatted purchase details"""
      if not purchase:
          return {}

      return {
          'id': purchase.id,
          'name': f'PP{str(purchase.id).zfill(5)}',
          'sale_order': {
              'id': purchase.sale_order_id.id,
              'name': purchase.sale_order_id.name
          },
          'customer': {
              'id': purchase.partner_id.id,
              'name': purchase.partner_id.name
          },
          'car': {
              'id': purchase.partner_car_id.id,
              'brand': purchase.partner_car_id.brand.name if purchase.partner_car_id.brand else None,
              'type': purchase.partner_car_id.brand_type.name if purchase.partner_car_id.brand_type else None,
              'plate': purchase.partner_car_id.number_plate
          },
          'timestamps': {
              'departure': self._format_datetime(purchase.departure_time),
              'return': self._format_datetime(purchase.return_time),
              'estimated_departure': self._format_datetime(purchase.estimated_departure),
              'estimated_return': self._format_datetime(purchase.estimated_return)
          },
          'duration': {
              'hours': purchase.duration,
              'display': purchase.duration_display,
              'estimated_hours': purchase.estimated_duration,
              'estimated_display': self._format_duration(purchase.estimated_duration)
          },
          'partman': {
              'id': purchase.partman_id.id,
              'name': purchase.partman_id.name
          } if purchase.partman_id else None,
          'review_type': purchase.review_type,
          'notes': purchase.notes,
          'state': purchase.state
      }
    
    @http.route('/web/part-purchase/available-orders', type='json', auth='user', methods=['POST'])
    def get_available_orders(self, **kw):
        """Get available sale orders for part purchase"""
        try:
            # Extract parameters
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 20))
            search_query = kw.get('search', '').strip()
            filter_type = kw.get('filter', 'all')  # all, need_part, active, completed
            
            # Base domain - ambil order yang sudah ada PKB
            domain = [
                ('sa_cetak_pkb', '!=', False),  # Harus sudah cetak PKB
                # ('controller_mulai_servis', '!=', False),  # Harus sudah mulai servis
                ('controller_selesai', '=', False)  # Belum selesai servis
            ]
            
            # Add search
            if search_query:
                domain = ['&'] + domain + ['|', '|', '|', '|',
                    ('name', 'ilike', search_query),
                    ('partner_id.name', 'ilike', search_query),
                    ('partner_car_id.number_plate', 'ilike', search_query),
                    ('generated_mechanic_team', 'ilike', search_query),
                    ('service_advisor_id.name', 'ilike', search_query)
                ]

            # Add filter
            if filter_type == 'need_part':
                domain.append(('need_part_purchase', '=', 'yes'))
            elif filter_type == 'active':
                domain.append(('part_purchase_ids.state', 'in', ['draft', 'departed']))
            elif filter_type == 'completed':
                domain.extend([
                    ('need_part_purchase', '=', 'yes'),
                    ('part_purchase_status', '=', 'completed')
                ])

            # Get total count for pagination
            SaleOrder = request.env['sale.order']
            total_count = SaleOrder.search_count(domain)
            total_pages = math.ceil(total_count / limit)
            
            # Get paginated records
            offset = (page - 1) * limit
            orders = SaleOrder.search(domain, limit=limit, offset=offset, 
                                    order='create_date desc')

            # Format response
            result = []
            for order in orders:
                result.append({
                    'id': order.id,
                    'name': order.name,
                    'customer': {
                        'id': order.partner_id.id,
                        'name': order.partner_id.name
                    },
                    'car': {
                        'brand': order.partner_car_brand.name,
                        'type': order.partner_car_brand_type.name,
                        'plate': order.partner_car_id.number_plate
                    },
                    'need_part': order.need_part_purchase == 'yes',
                    'part_purchase_status': {
                        'code': order.part_purchase_status,
                        'text': dict(order._fields['part_purchase_status'].selection).get(
                            order.part_purchase_status
                        )
                    },
                    'mechanic': order.generated_mechanic_team,
                    'service_advisor': ', '.join(order.service_advisor_id.mapped('name')),
                    'part_purchases': [{
                        'id': pp.id,
                        'name': pp.name,
                        'departure': self._format_datetime(pp.departure_time),
                        'return': self._format_datetime(pp.return_time),
                        'duration': pp.duration_display,
                        'state': pp.state,
                        'partman': pp.partman_id.name if pp.partman_id else None
                    } for pp in order.part_purchase_ids],
                    'timestamps': {
                        'reception': self._format_datetime(order.sa_jam_masuk),
                        'service_start': self._format_datetime(order.controller_mulai_servis),
                        'pkb_printed': self._format_datetime(order.sa_cetak_pkb)
                    }
                })

            return {
                'status': 'success',
                'data': {
                    'rows': result,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': total_pages,
                        'current_page': page,
                        'items_per_page': limit,
                        'has_next': page < total_pages,
                        'has_previous': page > 1
                    },
                    'summary': {
                        'total_orders': total_count,
                        'need_part': SaleOrder.search_count([
                            ('need_part_purchase', '=', 'yes')
                        ]),
                        'active_purchases': SaleOrder.search_count([
                            ('part_purchase_ids.state', 'in', ['draft', 'departed'])
                        ])
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_available_orders: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/part-purchase/order/<int:order_id>/toggle-need-part', type='json', auth='user', methods=['POST'])
    def toggle_need_part(self, order_id, **kw):
        """Toggle need part purchase flag for sale order"""
        try:
            order = request.env['sale.order'].browse(order_id)
            if not order.exists():
                return {
                    'status': 'error',
                    'message': 'Sale order not found'
                }

            # Toggle flag
            new_value = 'no' if order.need_part_purchase == 'yes' else 'yes'
            order.write({'need_part_purchase': new_value})

            return {
                'status': 'success',
                'data': {
                    'id': order.id,
                    'need_part_purchase': new_value,
                    'status': order.part_purchase_status
                }
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }


    @http.route('/web/part-purchase/table', type='json', auth='user', methods=['POST'])
    def get_table_data(self, **kw):
        """Get paginated part purchase data with filtering"""
        try:
            # Extract parameters
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 20))
            search_query = kw.get('search', '').strip()
            filter_type = kw.get('filter', 'all')
            sort_by = kw.get('sort_by', 'id')
            sort_order = kw.get('sort_order', 'desc')

            domain = []
            
            # Add search conditions
            if search_query:
                search_domain = ['|', '|', '|', '|',
                    ('name', 'ilike', search_query),
                    ('sale_order_id.name', 'ilike', search_query),
                    ('partner_id.name', 'ilike', search_query),
                    ('partner_car_id.number_plate', 'ilike', search_query),
                    ('partman_id.name', 'ilike', search_query)
                ]
                domain.extend(search_domain)

            # Add filter conditions
            if filter_type != 'all':
                domain.append(('state', '=', filter_type))

            # Prepare sorting
            order_mapping = {
                'id': 'id',
                'date': 'departure_time',
                'customer': 'partner_id',
                'status': 'state',
                'duration': 'duration'
            }
            sort_field = order_mapping.get(sort_by, 'id')
            order = f'{sort_field} {sort_order}'

            # Get records count
            PartPurchase = request.env['part.purchase.leadtime']
            total_count = PartPurchase.search_count(domain)
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

            # Get paginated records
            offset = (page - 1) * limit
            purchases = PartPurchase.search(domain, limit=limit, offset=offset, order=order)

            # Format response data
            rows = []
            for purchase in purchases:
                rows.append(self._get_purchase_details(purchase))

            # Get summary statistics
            summary = {
                'total': PartPurchase.search_count([]),
                'departed': PartPurchase.search_count([('state', '=', 'departed')]),
                'returned': PartPurchase.search_count([('state', '=', 'returned')]),
                'cancelled': PartPurchase.search_count([('state', '=', 'cancel')]),
                'avg_duration': PartPurchase.search_read([
                    ('state', '=', 'returned'),
                    ('duration', '>', 0)
                ], ['duration'])
            }

            if summary['avg_duration']:
                total_duration = sum(record['duration'] for record in summary['avg_duration'])
                summary['avg_duration'] = total_duration / len(summary['avg_duration'])
            else:
                summary['avg_duration'] = 0

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': total_pages,
                        'current_page': page,
                        'items_per_page': limit
                    },
                    'summary': summary
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_table_data: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    # Ubah method ini di class LeadTimePartController
    # Di LeadTimePartController
    @http.route('/web/part-purchase/detail', type='json', auth='user', methods=['POST'])
    def get_purchase_detail(self, **kw):
        """Get detailed part purchase information"""
        try:
            _logger.info(f"Received kw: {kw}")  # Debug log untuk melihat isi kw
            
            # Cek langsung dari kw
            purchase_id = kw.get('purchase_id')
            
            # Jika tidak ada di kw langsung, cek di params
            if not purchase_id:
                params = kw.get('params', {})
                purchase_id = params.get('purchase_id')
                
            _logger.info(f"Found purchase_id: {purchase_id}")  # Debug log purchase_id

            if not purchase_id:
                return {
                    'status': 'error',
                    'message': 'Purchase ID is required'
                }

            purchase = request.env['part.purchase.leadtime'].browse(int(purchase_id))
            if not purchase.exists():
                return {
                    'status': 'error',
                    'message': 'Purchase record not found'
                }

            details = self._get_purchase_details(purchase)
            _logger.info(f"Purchase details: {details}")  # Debug log hasil

            return {
                'status': 'success',
                'data': details
            }

        except Exception as e:
            _logger.error(f"Error in get_purchase_detail: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/part-purchase/create', type='json', auth='user', methods=['POST'])
    def create_purchase(self, **kw):
        """Create new part purchase record"""
        try:
            # Ambil params langsung dari kw karena kita pakai type='json'
            sale_order_id = kw.get('sale_order_id')
            partman_id = kw.get('partman_id')
            
            # Validasi required fields
            if not sale_order_id or not partman_id:
                return {
                    'status': 'error',
                    'message': 'sale_order_id and partman_id are required'
                }

            # Parse time inputs
            est_departure_str = kw.get('estimated_departure')
            est_return_str = kw.get('estimated_return')
            
            if not est_departure_str or not est_return_str:
                return {
                    'status': 'error',
                    'message': 'Estimated departure and return times are required'
                }

            try:
                est_departure = self._parse_time(est_departure_str)
                est_return = self._parse_time(est_return_str)
            except ValueError as e:
                return {
                    'status': 'error',
                    'message': f'Invalid time format: {str(e)}. Please use HH:mm format.'
                }
            
            # Calculate estimated duration
            estimated_duration = 0
            if est_departure and est_return:
                if est_return < est_departure:
                    est_return += timedelta(days=1)  # Asumsi kembali di hari berikutnya
                time_diff = est_return - est_departure
                estimated_duration = time_diff.total_seconds() / 3600  # Convert to hours

            # Prepare values for creation
            values = {
                'sale_order_id': int(sale_order_id),
                'partman_id': int(partman_id),
                'review_type': kw.get('review_type'),
                'notes': kw.get('notes'),
                'estimated_departure': est_departure,
                'estimated_return': est_return,
                'estimated_duration': estimated_duration
            }

            purchase = request.env['part.purchase.leadtime'].create(values)
            
            return {
                'status': 'success',
                'data': self._get_purchase_details(purchase),
                'message': 'Part purchase record created successfully'
            }

        except Exception as e:
            _logger.error(f"Error in create_purchase: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def _parse_time(self, time_str):
      """Parse time string to datetime with correct timezone
      Args:
          time_str (str): Time string in HH:mm format
      Returns:
          datetime: Datetime object in UTC
      """
      if not time_str:
          raise ValueError("Time string cannot be empty")
          
      try:
          # Parse input time
          hours, minutes = map(int, time_str.split(':'))
          if not (0 <= hours <= 23 and 0 <= minutes <= 59):
              raise ValueError("Hours must be 0-23 and minutes must be 0-59")
              
          # Get current date in Asia/Jakarta timezone
          tz = pytz.timezone('Asia/Jakarta')
          local_now = fields.Datetime.now().astimezone(tz)
          
          # Create local datetime
          local_dt = local_now.replace(
              hour=hours,
              minute=minutes,
              second=0,
              microsecond=0
          )
          
          # Convert to UTC for storage
          utc_dt = local_dt.astimezone(pytz.UTC)
          
          return utc_dt.replace(tzinfo=None)  # Remove tzinfo for Odoo compatibility
          
      except ValueError:
          raise ValueError("Invalid time format. Please use HH:mm format")

    @http.route('/web/part-purchase/<int:purchase_id>/depart', type='json', auth='user', methods=['POST'])
    def record_departure(self, purchase_id, **kw):
        """Record part purchase departure"""
        try:
            # Get parameters from kw
            start_time = kw.get('startTime')  # Format HH:MM
            notes = kw.get('notes')

            purchase = request.env['part.purchase.leadtime'].browse(purchase_id)
            if not purchase.exists():
                return {
                    'status': 'error',
                    'message': 'Purchase record not found'
                }

            if purchase.state != 'draft':
                return {
                    'status': 'error', 
                    'message': 'Invalid state for departure'
                }

            values = {}
            if start_time:
                values['departure_time'] = self._parse_time(start_time)
            else:
                values['departure_time'] = fields.Datetime.now()

            if notes:
                values['notes'] = notes

            values['state'] = 'departed'
            purchase.write(values)

            # Log activity
            msg = f"""
                <p><strong>Partman berangkat</strong></p>
                <ul>
                    <li>Waktu: {self._format_datetime(values['departure_time'])}</li>
                    {f'<li>Catatan: {notes}</li>' if notes else ''}
                </ul>
            """
            purchase.message_post(body=msg)
            
            return {
                'status': 'success',
                'data': self._get_purchase_details(purchase),
                'message': 'Departure recorded successfully'
            }

        except Exception as e:
            _logger.error(f"Error recording departure: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/part-purchase/<int:purchase_id>/return', type='json', auth='user', methods=['POST'])
    def record_return(self, purchase_id, **kw):
        """Record part purchase return"""
        try:
            # Get parameters from kw
            end_time = kw.get('endTime')  # Format HH:MM
            notes = kw.get('notes')

            purchase = request.env['part.purchase.leadtime'].browse(purchase_id)
            if not purchase.exists():
                return {
                    'status': 'error',
                    'message': 'Purchase record not found'
                }

            if purchase.state != 'departed':
                return {
                    'status': 'error',
                    'message': 'Invalid state for return'
                }

            values = {}
            if end_time:
                values['return_time'] = self._parse_time(end_time)
            else:
                values['return_time'] = fields.Datetime.now()

            if notes:
                values['notes'] = notes

            values['state'] = 'returned'
            purchase.write(values)

            # Log activity
            msg = f"""
                <p><strong>Partman kembali</strong></p>
                <ul>
                    <li>Waktu: {self._format_datetime(values['return_time'])}</li>
                    {f'<li>Catatan: {notes}</li>' if notes else ''}
                    <li>Durasi: {purchase.duration_display}</li>
                </ul>
            """
            purchase.message_post(body=msg)

            return {
                'status': 'success',
                'data': self._get_purchase_details(purchase),
                'message': 'Return recorded successfully'
            }

        except Exception as e:
            _logger.error(f"Error recording return: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/part-purchase/<int:purchase_id>/cancel', type='json', auth='user', methods=['POST'])
    def cancel_purchase(self, purchase_id, **kw):
        """Cancel part purchase"""
        try:
            notes = kw.get('notes')

            purchase = request.env['part.purchase.leadtime'].browse(purchase_id)
            if not purchase.exists():
                return {
                    'status': 'error',
                    'message': 'Purchase record not found'
                }

            if purchase.state in ['returned', 'cancel']:
                return {
                    'status': 'error',
                    'message': 'Cannot cancel completed or already cancelled purchase'
                }

            values = {
                'state': 'cancel'
            }
            if notes:
                values['notes'] = notes

            purchase.write(values)

            # Log activity
            msg = f"""
                <p><strong>Pembelian dibatalkan</strong></p>
                <ul>
                    <li>Waktu: {self._format_datetime(fields.Datetime.now())}</li>
                    {f'<li>Alasan: {notes}</li>' if notes else ''}
                </ul>
            """
            purchase.message_post(body=msg)

            return {
                'status': 'success',
                'data': self._get_purchase_details(purchase),
                'message': 'Purchase cancelled successfully'
            }

        except Exception as e:
            _logger.error(f"Error cancelling purchase: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/part-purchase/statistics', type='json', auth='user', methods=['POST'])
    def get_statistics(self, **kw):
        """Get comprehensive statistics for part purchases"""
        try:
            # Extract parameters
            params = kw.get('params', {})
            date_range = params.get('date_range', 'today')  # today, week, month, year
            start_date = params.get('start_date')
            end_date = params.get('end_date')

            PartPurchase = request.env['part.purchase.leadtime']
            
            # Build date domain
            domain = []
            if date_range == 'today':
                today = fields.Date.today()
                domain = [('create_date', '>=', today)]
            elif date_range == 'week':
                week_start = fields.Date.today() - timedelta(days=fields.Date.today().weekday())
                domain = [('create_date', '>=', week_start)]
            elif date_range == 'month':
                month_start = fields.Date.today().replace(day=1)
                domain = [('create_date', '>=', month_start)]
            elif date_range == 'custom' and start_date and end_date:
                domain = [
                    ('create_date', '>=', start_date),
                    ('create_date', '<=', end_date)
                ]

            # Basic stats with date filter
            total_purchases = PartPurchase.search_count(domain)
            departed_purchases = PartPurchase.search_count(domain + [('state', '=', 'departed')])
            completed_purchases = PartPurchase.search_count(domain + [('state', '=', 'returned')])
            cancelled_purchases = PartPurchase.search_count(domain + [('state', '=', 'cancel')])
            
            # Duration stats
            completed_records = PartPurchase.search_read(
                domain + [
                    ('state', '=', 'returned'),
                    ('duration', '>', 0)
                ], 
                ['duration']
            )
            
            avg_duration = 0
            if completed_records:
                total_duration = sum(record['duration'] for record in completed_records)
                avg_duration = total_duration / len(completed_records)

            # Partman performance
            partman_stats = PartPurchase.read_group(
                domain + [('state', '=', 'returned')],
                ['partman_id', 'duration:avg'],
                ['partman_id']
            )

            # Format time periods for display
            period_info = {
                'start': self._format_datetime(fields.Datetime.from_string(start_date)) if start_date else None,
                'end': self._format_datetime(fields.Datetime.from_string(end_date)) if end_date else None,
                'range': date_range
            }

            return {
                'status': 'success',
                'data': {
                    'period': period_info,
                    'summary': {
                        'total_purchases': total_purchases,
                        'departed_purchases': departed_purchases,
                        'completed_purchases': completed_purchases,
                        'cancelled_purchases': cancelled_purchases,
                        'completion_rate': (completed_purchases / total_purchases * 100) if total_purchases else 0,
                        'average_duration': avg_duration,
                        'average_duration_display': self._format_duration(avg_duration)
                    },
                    'partman_performance': [{
                        'partman_id': stat['partman_id'][0],
                        'partman_name': stat['partman_id'][1],
                        'avg_duration': stat['duration'],
                        'avg_duration_display': self._format_duration(stat['duration'])
                    } for stat in partman_stats if stat['partman_id']]
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_statistics: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def _format_duration(self, duration_hours):
        """Format duration from hours to readable string"""
        if not duration_hours:
            return "0j 0m"
        hours = int(duration_hours)
        minutes = int((duration_hours - hours) * 60)
        return f"{hours}j {minutes}m"