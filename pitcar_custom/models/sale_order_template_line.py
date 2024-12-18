# models/sale_order_template_line.py
from odoo import models, fields, api

class SaleOrderTemplateLine(models.Model):
    _inherit = "sale.order.template.line"

    service_duration = fields.Float(
        string='Durasi (Jam)',
        help='Durasi estimasi layanan',
        digits=(16, 2)
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and self.product_id.type == 'service':
            self.service_duration = self.product_id.service_duration