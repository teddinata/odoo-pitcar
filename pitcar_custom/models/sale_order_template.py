# models/sale_order_template.py
from odoo import models, fields, api

class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    def _compute_template_line_values(self, line, partner, pricelist, company, fiscal_position_id, date_order):
        # Memanggil fungsi asli dari Odoo
        result = super()._compute_template_line_values(line, partner, pricelist, company, fiscal_position_id, date_order)
        
        # Tambahkan harga kustom dari template line jika ada
        result['price_unit'] = line.price_unit or result.get('price_unit', 0.0)
        
        # Tambahkan service_duration jika ada
        if hasattr(line, 'service_duration'):
            result['service_duration'] = line.service_duration
        
        return result