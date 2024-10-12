from odoo import http
from odoo.http import request

class LeadTimeController(http.Controller):
    @http.route('/lead_time/summary', type='json', auth='user')
    def get_lead_time_summary(self, order_id):
        order = request.env['sale.order'].browse(int(order_id))
        return {
            'total_lead_time': order.total_lead_time,
            'lead_time_progress': order.lead_time_progress,
            'lead_time_stage': order.lead_time_stage,
        }