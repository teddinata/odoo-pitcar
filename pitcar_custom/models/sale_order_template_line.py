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

    # Tambahkan field discount
    discount = fields.Float(
        string='Diskon (%)',
        digits='Discount',
        default=0.0,
        help='Diskon dalam persentase'
    )
    
    # Tambahkan flag untuk menandai apakah line ini penting/wajib
    is_required = fields.Boolean(
        string='Wajib',
        default=True,
        help='Jika dicentang, line ini tidak dapat dihapus saat membuat booking'
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if self.product_id.type == 'service':
                # Ambil durasi dari produk jika service
                self.service_duration = getattr(self.product_id, 'service_duration', 1.0)
            else:
                self.service_duration = 0.0
            
            # Tambahkan logika untuk mengisi harga otomatis dari produk
            self.price_unit = self.product_id.list_price