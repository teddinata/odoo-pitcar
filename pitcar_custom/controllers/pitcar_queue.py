from odoo import http, fields, api, SUPERUSER_ID
from odoo.http import request, Response
from datetime import datetime, timedelta
import pytz
import odoo
import logging
from .cors import cors_handler

_logger = logging.getLogger(__name__)
class PitCarQueue(http.Controller):
    @http.route('/web/sale_orders/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_sale_order(self, **kwargs):
        try:
            # Create environment using authenticated user's environment
            env = request.env
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Create sale order with timezone context
            sale_order = env['sale.order'].with_context(
                from_api=True,
                tz='Asia/Jakarta'
            ).create({
                'is_booking': kwargs.get('is_booking', False),
            })
            
            # Record arrival and get queue
            sale_order.with_context(from_api=True, tz='Asia/Jakarta').action_record_car_arrival_time()
            
            # Get queue info
            queue_line = sale_order.queue_line_id
            if not queue_line:
                return {
                    'status': 'error',
                    'message': 'Failed to create queue number'
                }

            queue_info = queue_line.get_queue_info()
            
            # Get current local time
            local_time = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
            
            body = f"""
            <p><strong>Antrean API</strong></p>
            <ul>
                <li>Nomor Antrean: {queue_info['queue_number']}</li>
                <li>Tipe Antrean: {'Prioritas' if queue_info['is_priority'] else 'Regular'}</li>
                <li>Antrean Saat Ini: {queue_info['current_number']}</li>
                <li>Antrean Di Depan: {queue_info['numbers_ahead']}</li>
                <li>Estimasi Waktu Tunggu: {queue_info['estimated_wait_minutes']} menit</li>
                <li>Estimasi Waktu Pelayanan: {queue_info['estimated_service_time']}</li>
                <li>Waktu Pengambilan Antrean: {local_time.strftime('%Y-%m-%d %H:%M:%S')}</li>
            </ul>
            """
            sale_order.message_post(body=body, message_type='notification')

            # Format response times to local timezone
            car_arrival = pytz.utc.localize(fields.Datetime.from_string(sale_order.car_arrival_time)).astimezone(tz)
            sa_jam_masuk = pytz.utc.localize(fields.Datetime.from_string(sale_order.sa_jam_masuk)).astimezone(tz)
            
            # Update queue_info estimated service time to local timezone
            if queue_info.get('estimated_service_time'):
                est_time = fields.Datetime.from_string(queue_info['estimated_service_time'])
                if est_time:
                    est_time_local = pytz.utc.localize(est_time).astimezone(tz)
                    queue_info['estimated_service_time'] = fields.Datetime.to_string(est_time_local.replace(tzinfo=None))
            
            # Trigger refresh after successful creation
            env['queue.management'].browse(queue_line.queue_id.id)._broadcast_queue_update()

            return {
                'status': 'success',
                'message': 'Sale order created successfully and queue number generated',
                'data': {
                    'order_id': sale_order.id,
                    'car_arrival_time': fields.Datetime.to_string(car_arrival.replace(tzinfo=None)),
                    'sa_jam_masuk': fields.Datetime.to_string(sa_jam_masuk.replace(tzinfo=None)),
                    'queue_info': queue_info,
                    'queue_number': queue_info['queue_number'],
                    'is_priority': queue_info['is_priority'],
                    'current_number': queue_info['current_number'],
                    'numbers_ahead': queue_info['numbers_ahead'],
                    'estimated_wait_minutes': queue_info['estimated_wait_minutes'],
                    'estimated_service_time': queue_info['estimated_service_time'],
                    'timestamp': local_time.strftime('%Y-%m-%d %H:%M:%S')
                },
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    @http.route('/web/queue/status/<int:order_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_queue_status(self, order_id, **kwargs):
        """Get current queue status for an order"""
        try:
            sale_order = request.env['sale.order'].browse(order_id)
            if not sale_order.exists():
                return {
                    'status': 'error',
                    'message': 'Order tidak ditemukan'
                }

            queue_line = sale_order.queue_line_id
            # if not queue_line:
            #     return {
            #         'status': 'error',
            #         'message': 'Order tidak memiliki nomor antrian'
            #     }

            return {
                'status': 'success',
                'data': {
                    'order_id': sale_order.id,
                    'queue_number': queue_line.display_number,
                    'queue_type': 'Priority' if sale_order.is_booking else 'Regular',
                    'queue_status': queue_line.status,
                    'current_number': queue_line.queue_id.current_number,
                    'numbers_ahead': sale_order.numbers_ahead,
                    'estimated_wait_minutes': sale_order.estimated_wait_minutes,
                    'estimated_service_time': queue_line.estimated_service_time,
                    'actual_service_start': sale_order.sa_mulai_penerimaan,
                    'actual_service_end': sale_order.sa_cetak_pkb,
                    'service_duration': queue_line.service_duration if queue_line.service_duration else 0
                }
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/queue/stats/today', type='json', auth='user', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def get_today_queue_stats(self, **kwargs):
        """Get queue statistics for today"""
        try:
            if request.httprequest.method == 'OPTIONS':
                headers = {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                    'Access-Control-Allow-Credentials': 'true'
                }
                return Response(status=200, headers=headers)

            queue_record = request.env['queue.management'].search([
                ('date', '=', fields.Date.today())
            ], limit=1)
            
            if not queue_record:
                return {
                    'status': 'error',
                    'message': 'No queue data for today'
                }

            # Get queue statistics
            waiting_lines = queue_record.queue_line_ids.filtered(lambda l: l.status == 'waiting')
            completed_lines = queue_record.queue_line_ids.filtered(lambda l: l.status == 'completed')
            
            # Format current number
            current_number_display = None
            if queue_record.current_number:
                if queue_record.queue_line_ids.filtered(
                    lambda l: l.queue_number == queue_record.current_number and l.is_priority
                ):
                    current_number_display = f"P{queue_record.current_number:03d}"
                else:
                    current_number_display = f"{queue_record.current_number:03d}"
            
            stats = {
                'current_number': current_number_display or '-',
                'total_numbers': queue_record.last_number + queue_record.last_priority_number,
                'total_waiting': len(waiting_lines),
                'total_completed': len(completed_lines),
                'average_service_time': round(queue_record.average_service_time, 1),
                'priority_stats': {
                    'total_priority': len(queue_record.queue_line_ids.filtered(lambda l: l.is_priority)),
                    'waiting_priority': len(waiting_lines.filtered(lambda l: l.is_priority)),
                    'completed_priority': len(completed_lines.filtered(lambda l: l.is_priority)),
                    'last_number': f"P{queue_record.last_priority_number:03d}" if queue_record.last_priority_number else 'P000'
                },
                'regular_stats': {
                    'total_regular': len(queue_record.queue_line_ids.filtered(lambda l: not l.is_priority)),
                    'waiting_regular': len(waiting_lines.filtered(lambda l: not l.is_priority)),
                    'completed_regular': len(completed_lines.filtered(lambda l: not l.is_priority)),
                    'last_number': f"{queue_record.last_number:03d}" if queue_record.last_number else '000'
                }
            }

            next_queue = queue_record.get_next_queue()
            current_number = None

            # Get next waiting number if any
            next_queue = queue_record.get_next_queue()
            if next_queue:
                current_number = f"P{next_queue.queue_number:03d}" if next_queue.is_priority else f"{next_queue.queue_number:03d}"
                stats['next_number'] = f"P{next_queue.queue_number:03d}" if next_queue.is_priority else f"{next_queue.queue_number:03d}"

                stats['next_number'] = current_number or '-'
            else:
                stats['next_number'] = '-'

            return {
                'status': 'success',
                'data': stats
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
        
    @http.route('/web/queue/dashboard', type='json', auth='user', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def get_queue_dashboard(self, **kwargs):
        """Get comprehensive queue dashboard data"""
        try:
            if request.httprequest.method == 'OPTIONS':
                headers = {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                    'Access-Control-Allow-Credentials': 'true'
                }
                return Response(status=200, headers=headers)

            queue_mgmt = request.env['queue.management'].search([
                ('date', '=', fields.Date.today())
            ], limit=1)
            
            if not queue_mgmt:
                return {
                    'status': 'error',
                    'message': 'No queue data for today'
                }

            # Get next queue
            next_queue = queue_mgmt.get_next_queue()
            next_number = next_queue.display_number if next_queue else '-'
            
            # Get current active queue
            current_queue = queue_mgmt.queue_line_ids.filtered(
                lambda l: l.status == 'in_progress'
            )
            current_display = current_queue.display_number if current_queue else '-'

            # Get service performance metrics
            completed_queues = queue_mgmt.queue_line_ids.filtered(
                lambda l: l.status == 'completed'
            )
            avg_service_time = 0
            if completed_queues:
                avg_service_time = sum(completed_queues.mapped('service_duration')) / len(completed_queues)

            # Prepare queue statistics
            waiting_lines = queue_mgmt.queue_line_ids.filtered(lambda l: l.status == 'waiting')
            priority_waiting = waiting_lines.filtered(lambda l: l.is_priority)
            regular_waiting = waiting_lines.filtered(lambda l: not l.is_priority)

            dashboard_data = {
                'summary': {
                    'title': 'Dashboard Summary',
                    'date': fields.Date.today().strftime('%d %B %Y'),
                    'avg_service_time': round(avg_service_time, 1),
                    'total_served_today': len(completed_queues),
                    'last_update': fields.Datetime.now().strftime('%H:%M:%S')
                },
                'current_service': {
                    'number': current_display,
                    'start_time': current_queue.start_time.strftime('%H:%M:%S') if current_queue and current_queue.start_time else '-',
                    'type': 'Priority' if current_queue and current_queue.is_priority else 'Regular',
                    'service_duration': round(current_queue.service_duration, 1) if current_queue else 0
                },
                'next_queue': {
                    'number': next_number,
                    'type': 'Priority' if next_queue and next_queue.is_priority else 'Regular',
                    'estimated_time': next_queue.estimated_service_time.strftime('%H:%M:%S') if next_queue else '-'
                },
                'waiting_status': {
                    'total_waiting': len(waiting_lines),
                    'priority_waiting': len(priority_waiting),
                    'regular_waiting': len(regular_waiting),
                    'estimated_completion': fields.Datetime.now() + timedelta(minutes=len(waiting_lines) * queue_mgmt.average_service_time)
                },
                'queue_distribution': {
                    'priority': {
                        'total': queue_mgmt.last_priority_number,
                        'waiting': len(priority_waiting),
                        'in_service': len(current_queue.filtered(lambda l: l.is_priority)),
                        'completed': len(completed_queues.filtered(lambda l: l.is_priority)),
                        'last_number': f"P{queue_mgmt.last_priority_number:03d}"
                    },
                    'regular': {
                        'total': queue_mgmt.last_number,
                        'waiting': len(regular_waiting),
                        'in_service': len(current_queue.filtered(lambda l: not l.is_priority)),
                        'completed': len(completed_queues.filtered(lambda l: not l.is_priority)),
                        'last_number': f"{queue_mgmt.last_number:03d}"
                    }
                },
                'service_metrics': {
                    'avg_service_time': round(avg_service_time, 1),
                    'min_service_time': round(min(completed_queues.mapped('service_duration') or [0]), 1),
                    'max_service_time': round(max(completed_queues.mapped('service_duration') or [0]), 1),
                    'total_service_time': round(sum(completed_queues.mapped('service_duration') or [0]), 1)
                }
            }

            return {
                'status': 'success',
                'data': dashboard_data
            }

        except Exception as e:
            _logger.error("Dashboard error: %s", str(e))
            return {
                'status': 'error',
                'message': str(e)
            }