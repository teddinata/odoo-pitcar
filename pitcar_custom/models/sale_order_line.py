# models/sale_order_line.py

from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    service_duration = fields.Float(
        string='Durasi (Jam)',
        help='Durasi estimasi layanan',
        digits=(16, 2)
    )

    @api.onchange('product_id')
    def _onchange_product_duration(self):
        """New onchange method specifically for duration"""
        for line in self:
            if line.product_id and line.product_id.type == 'service':
                line.service_duration = line.product_id.service_duration
            else:
                line.service_duration = 0.0