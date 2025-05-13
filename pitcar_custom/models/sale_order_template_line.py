# models/sale_order_template_line.py
from odoo import models, fields, api

class SaleOrderTemplateLine(models.Model):
    _inherit = "sale.order.template.line"

    service_duration = fields.Float(
        string='Durasi (Jam)',
        help='Durasi estimasi layanan',
        digits=(16, 2)
    )
    
    # Tambahkan field price_unit
    price_unit = fields.Float(
        string='Harga Satuan',
        digits='Product Price',
        help='Harga satuan untuk produk dalam template quotation'
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if self.product_id.type == 'service':
                self.service_duration = self.product_id.service_duration
            
            # Tambahkan logika untuk mengisi harga otomatis dari produk
            self.price_unit = self.product_id.list_price