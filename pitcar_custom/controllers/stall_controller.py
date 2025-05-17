from odoo import http, fields
from odoo.http import request
import logging
from datetime import datetime, timedelta, time
import psycopg2  # Tambahkan import ini
import math
import pytz

_logger = logging.getLogger(__name__)

class StallDashboardController(http.Controller):
    @http.route('/web/v1/stall/dashboard', type='json', auth="public", methods=['POST'], csrf=False)
    def get_stall_dashboard(self, **kw):
        """Get data for stall utilization dashboard"""
        try:
            date = kw.get('date', fields.Date.today())
            
            # Get all stalls
            stalls = request.env['pitcar.service.stall'].sudo().search([('active', '=', True)])
            
            # Get all orders for the day
            orders = request.env['sale.order'].sudo().search([
                '|',
                '&', 
                    ('controller_mulai_servis', '>=', datetime.combine(date, time(0, 0))),
                    ('controller_mulai_servis', '<', datetime.combine(date + timedelta(days=1), time(0, 0))),
                '&',
                    ('controller_selesai', '>=', datetime.combine(date, time(0, 0))),
                    ('controller_selesai', '<', datetime.combine(date + timedelta(days=1), time(0, 0)))
            ])
            
            # Get all bookings for the day
            bookings = request.env['pitcar.service.booking'].sudo().search([
                ('booking_date', '=', date),
                ('state', 'not in', ['cancelled'])
            ])
            
            # Prepare stall data
            stall_data = []
            for stall in stalls:
                # Get stall's orders for the day
                stall_orders = orders.filtered(lambda o: o.stall_id.id == stall.id)
                active_orders = stall_orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai)
                completed_orders = stall_orders.filtered(lambda o: o.controller_selesai)
                
                # Get stall's bookings for the day
                stall_bookings = bookings.filtered(lambda b: b.stall_id.id == stall.id)
                
                # Prepare timeline
                timeline = []
                
                # Add bookings to timeline
                for booking in stall_bookings:
                    start_hour = int(booking.booking_time)
                    start_minute = int((booking.booking_time - start_hour) * 60)
                    
                    # Calculate end time
                    duration = booking.estimated_duration or 1.0  # Default 1 hour
                    end_hour = int(booking.booking_time + duration)
                    end_minute = int(((booking.booking_time + duration) % 1) * 60)
                    
                    timeline.append({
                        'id': booking.id,
                        'type': 'booking',
                        'title': f"{booking.partner_id.name} - {booking.partner_car_id.number_plate if booking.partner_car_id else ''}",
                        'start': f"{start_hour:02d}:{start_minute:02d}",
                        'end': f"{end_hour:02d}:{end_minute:02d}",
                        'state': booking.state,
                        'is_converted': booking.state == 'converted',
                        'sale_order_id': booking.sale_order_id.id if booking.sale_order_id else None
                    })
                
                # Add orders to timeline
                for order in stall_orders:
                    if order.controller_mulai_servis:
                        # Format times
                        start_local = pytz.utc.localize(order.controller_mulai_servis).astimezone(pytz.timezone('Asia/Jakarta'))
                        start_time = start_local.strftime('%H:%M')
                        
                        # For end time, use either actual completion or estimated
                        if order.controller_selesai:
                            end_local = pytz.utc.localize(order.controller_selesai).astimezone(pytz.timezone('Asia/Jakarta'))
                            end_time = end_local.strftime('%H:%M')
                        elif order.controller_estimasi_selesai:
                            end_local = pytz.utc.localize(order.controller_estimasi_selesai).astimezone(pytz.timezone('Asia/Jakarta'))
                            end_time = end_local.strftime('%H:%M')
                        else:
                            # Default to +2 hours if no estimation
                            end_local = start_local + timedelta(hours=2)
                            end_time = end_local.strftime('%H:%M')
                        
                        # Determine status
                        status = 'in_progress'
                        if order.controller_selesai:
                            status = 'completed'
                        elif order.controller_tunggu_part1_mulai and not order.controller_tunggu_part1_selesai:
                            status = 'tunggu_part'
                        elif order.controller_tunggu_konfirmasi_mulai and not order.controller_tunggu_konfirmasi_selesai:
                            status = 'tunggu_konfirmasi'
                        elif order.controller_istirahat_shift1_mulai and not order.controller_istirahat_shift1_selesai:
                            status = 'istirahat'
                        
                        timeline.append({
                            'id': order.id,
                            'type': 'service',
                            'title': f"{order.partner_id.name} - {order.partner_car_id.number_plate if order.partner_car_id else ''}",
                            'start': start_time,
                            'end': end_time,
                            'status': status,
                            'is_complete': bool(order.controller_selesai),
                            'is_booking': bool(order.booking_id),
                            'progress': order.lead_time_progress or 0
                        })
                
                # Sort timeline by start time
                timeline.sort(key=lambda x: x['start'])
                
                # Calculate utilization
                total_minutes = 9 * 60  # 9 hours workday (8AM - 5PM)
                used_minutes = 0
                
                # Calculate from orders
                for order in completed_orders:
                    if order.controller_mulai_servis and order.controller_selesai:
                        duration = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 60
                        used_minutes += min(duration, total_minutes)
                
                # For active orders, count time until now
                now = fields.Datetime.now()
                for order in active_orders:
                    if order.controller_mulai_servis:
                        duration = (now - order.controller_mulai_servis).total_seconds() / 60
                        used_minutes += min(duration, total_minutes - used_minutes)
                
                utilization = min(100, (used_minutes / total_minutes) * 100) if total_minutes > 0 else 0
                
                # Add current order info
                current_order = None
                if active_orders:
                    order = active_orders[0]
                    # Determine job stop status
                    job_stop = None
                    if order.controller_tunggu_part1_mulai and not order.controller_tunggu_part1_selesai:
                        job_stop = 'tunggu_part'
                    elif order.controller_tunggu_konfirmasi_mulai and not order.controller_tunggu_konfirmasi_selesai:
                        job_stop = 'tunggu_konfirmasi'
                    elif order.controller_istirahat_shift1_mulai and not order.controller_istirahat_shift1_selesai:
                        job_stop = 'istirahat'
                    
                    current_order = {
                        'id': order.id,
                        'name': order.name,
                        'customer': order.partner_id.name if order.partner_id else '',
                        'vehicle': f"{order.partner_car_brand.name} {order.partner_car_brand_type.name}" if order.partner_car_brand and order.partner_car_brand_type else '',
                        'plate': order.partner_car_id.number_plate if order.partner_car_id else '',
                        'start_time': self._format_datetime(order.controller_mulai_servis),
                        'job_stop': job_stop,
                        'progress': order.lead_time_progress or 0,
                        'mechanic': order.generated_mechanic_team,
                        'service_category': order.service_category,
                        'service_subcategory': order.service_subcategory
                    }
                
                # Compile stall data
                stall_data.append({
                    'id': stall.id,
                    'name': stall.name,
                    'code': stall.code,
                    'status': stall.status,
                    'is_occupied': bool(current_order),
                    'current_order': current_order,
                    'timeline': timeline,
                    'utilization': utilization,
                    'orders_count': len(stall_orders),
                    'active_orders_count': len(active_orders),
                    'completed_orders_count': len(completed_orders),
                    'bookings_count': len(stall_bookings),
                    'mechanics': [{
                        'id': m.id,
                        'name': m.name
                    } for m in stall.mechanic_ids] if hasattr(stall, 'mechanic_ids') else []
                })
            
            # Calculate overall statistics
            total_stalls = len(stalls)
            occupied_stalls = sum(1 for stall in stall_data if stall['is_occupied'])
            total_orders = len(orders)
            active_orders = len(orders.filtered(lambda o: o.controller_mulai_servis and not o.controller_selesai))
            completed_orders = len(orders.filtered(lambda o: o.controller_selesai))
            total_bookings = len(bookings)
            
            # Overall utilization
            overall_utilization = sum(stall['utilization'] for stall in stall_data) / total_stalls if total_stalls > 0 else 0
            
            return {
                'status': 'success',
                'data': {
                    'stalls': stall_data,
                    'stats': {
                        'total_stalls': total_stalls,
                        'occupied_stalls': occupied_stalls,
                        'occupancy_rate': (occupied_stalls / total_stalls) * 100 if total_stalls > 0 else 0,
                        'overall_utilization': overall_utilization,
                        'total_orders': total_orders,
                        'active_orders': active_orders,
                        'completed_orders': completed_orders,
                        'total_bookings': total_bookings,
                        'date': date
                    }
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_stall_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v1/stall/assign', type='json', auth="public", methods=['POST'], csrf=False)
    def assign_stall(self, **kw):
        """Assign stall to a service order"""
        try:
            order_id = kw.get('order_id')
            stall_id = kw.get('stall_id')
            notes = kw.get('notes', '')
            
            if not order_id or not stall_id:
                return {'status': 'error', 'message': 'Order ID and Stall ID are required'}
            
            # Check if stall already assigned to another active order
            conflicting_order = request.env['sale.order'].sudo().search([
                ('stall_id', '=', int(stall_id)),
                ('controller_mulai_servis', '!=', False),
                ('controller_selesai', '=', False),
                ('id', '!=', int(order_id))
            ], limit=1)
            
            if conflicting_order and not kw.get('force'):
                return {
                    'status': 'warning',
                    'message': f'Stall already assigned to Order {conflicting_order.name}',
                    'data': {
                        'conflicting_order': {
                            'id': conflicting_order.id,
                            'name': conflicting_order.name
                        }
                    }
                }
            
            # Get the order
            order = request.env['sale.order'].sudo().browse(int(order_id))
            
            # End previous stall history if any
            if order.stall_id:
                history = request.env['pitcar.stall.history'].sudo().search([
                    ('sale_order_id', '=', order.id),
                    ('stall_id', '=', order.stall_id.id),
                    ('end_time', '=', False)
                ], limit=1)
                
                if history:
                    history.write({'end_time': fields.Datetime.now()})
            
            # Assign new stall
            stall = request.env['pitcar.service.stall'].sudo().browse(int(stall_id))
            order.write({'stall_id': stall.id})
            
            # Create history entry
            history_vals = {
                'sale_order_id': order.id,
                'stall_id': stall.id,
                'start_time': fields.Datetime.now(),
                'notes': notes
            }
            request.env['pitcar.stall.history'].sudo().create(history_vals)
            
            # Log to chatter
            user = request.env.user
            body = f"""
            <p><strong>Stall Assigned</strong></p>
            <ul>
                <li>Stall: {stall.name}</li>
                <li>Assigned by: {user.name}</li>
                <li>Notes: {notes}</li>
            </ul>
            """
            order.message_post(body=body, message_type='notification')
            
            return {
                'status': 'success',
                'message': f'Stall {stall.name} assigned to Order {order.name}',
                'data': {
                    'order_id': order.id,
                    'stall_id': stall.id,
                    'stall_name': stall.name
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in assign_stall: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _format_datetime(self, dt):
        if not dt:
            return None
        tz = pytz.timezone('Asia/Jakarta')
        local_dt = pytz.utc.localize(dt).astimezone(tz)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')