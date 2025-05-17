# models/sale_order_template.py
from odoo import models, fields, api

class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    # Tambahkan flag untuk booking system
    is_booking_template = fields.Boolean(
        string='Tersedia di Booking System',
        default=True,  # Default True agar semua template yang ada tetap ditampilkan
        help='Jika dicentang, template ini akan tersedia untuk dipilih di sistem booking'
    )
    
    # Tambahkan kategori/jenis untuk template booking
    booking_category = fields.Selection([
        ('maintenance', 'Perawatan'),
        ('repair', 'Perbaikan'),
        ('service', 'Servis Umum'),
        ('other', 'Lainnya')
    ], string='Kategori Booking', 
       help='Kategori template untuk pemfilteran di sistem booking')
    
    # Tambahkan field untuk deskripsi yang ditampilkan di booking system
    booking_description = fields.Html(
        string='Deskripsi Booking',
        help='Deskripsi yang akan ditampilkan ke pelanggan di aplikasi booking'
    )
    
    # Tambahkan field untuk citra/gambar thumbnail
    booking_image = fields.Binary(
        string='Gambar Template',
        attachment=True,
        help='Gambar yang akan ditampilkan di aplikasi booking'
    )

    def action_update_prices(self):
        """Update semua harga dari produk terkait"""
        for template in self:
            for line in template.sale_order_template_line_ids:
                if line.product_id and not line.display_type:
                    line.price_unit = line.product_id.list_price
        return True

    def _compute_template_line_values(self, line, partner, pricelist, company, fiscal_position_id, date_order):
        # Memanggil fungsi asli dari Odoo
        result = super()._compute_template_line_values(line, partner, pricelist, company, fiscal_position_id, date_order)
        
        # Tambahkan harga kustom dari template line jika ada
        result['price_unit'] = line.price_unit or result.get('price_unit', 0.0)
        
        # Tambahkan service_duration jika ada
        if hasattr(line, 'service_duration'):
            result['service_duration'] = line.service_duration
        
        return result