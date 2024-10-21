from odoo import http
from odoo.http import request

class PitCarQueue(http.Controller):

    @http.route('/api/sale_orders/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_sale_order(self, **kwargs):
        try:
            # Create a new sale order
            sale_order = request.env['sale.order'].with_context(from_api=True).create({})

            # Call the action_record_car_arrival_time method
            sale_order.with_context(from_api=True).action_record_car_arrival_time()

            return {
                'status': 'success',
                'message': 'Sale order created and car arrival time recorded successfully',
                'order_id': sale_order.id,
                'car_arrival_time': sale_order.car_arrival_time,
                'sa_jam_masuk': sale_order.sa_jam_masuk
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/sale_orders/<int:order_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_sale_order(self, order_id, **kwargs):
        try:
            sale_order = request.env['sale.order'].with_context(from_api=True).browse(order_id)
            if not sale_order.exists():
                return {
                    'status': 'error',
                    'message': 'Sale Order not found',
                }

            sale_order_data = sale_order.read(['name', 'sa_jam_masuk', 'car_arrival_time', 'is_arrival_time_set'])[0]
            return {
                'status': 'success',
                'data': sale_order_data
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }