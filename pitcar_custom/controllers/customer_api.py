from odoo import http
from odoo.http import request, Response
import json

class CustomerAPI(http.Controller):

    # API to get all customers
    @http.route('/api/customers', type='http', auth='user', methods=['GET'], csrf=False)
    def get_customers(self, **kwargs):
        customers = request.env['res.partner'].search([])
        customer_data = customers.read(['name', 'email', 'phone'])
        return Response(json.dumps(customer_data), content_type='application/json')

    # API to get customer by ID
    @http.route('/api/customers/<int:id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customer(self, id, **kwargs):
        customer = request.env['res.partner'].browse(id)
        if not customer.exists():
            return Response(json.dumps({'error': 'Customer not found'}), status=404, content_type='application/json')
        customer_data = customer.read(['name', 'email', 'phone', 'customer_rank'])[0]
        return Response(json.dumps(customer_data), content_type='application/json')
