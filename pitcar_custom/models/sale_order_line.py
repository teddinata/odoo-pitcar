# models/sale_order_line.py

from odoo import models, fields, api

def format_duration(duration_in_hours):
    """
    Convert decimal hours to a human-readable format
    Example: 
    1.5 -> "1 jam 30 menit"
    0.75 -> "45 menit"
    2.25 -> "2 jam 15 menit"
    """
    if not duration_in_hours:
        return "0 menit"
        
    hours = int(duration_in_hours)
    minutes = int((duration_in_hours - hours) * 60)
    
    if hours == 0:
        return f"{minutes} menit"
    elif minutes == 0:
        return f"{hours} jam"
    else:
        return f"{hours} jam {minutes} menit"

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    service_duration = fields.Float(
        string='Durasi (Jam)',
        help='Durasi estimasi layanan',
        digits=(16, 2)
    )

    formatted_duration = fields.Char(
        string='Durasi',
        compute='_compute_formatted_duration',
        store=False
    )

    @api.onchange('product_id')
    def _onchange_product_duration(self):
        """New onchange method specifically for duration"""
        for line in self:
            if line.product_id and line.product_id.type == 'service':
                line.service_duration = line.product_id.service_duration
            else:
                line.service_duration = 0.0

    @api.depends('service_duration')
    def _compute_formatted_duration(self):
        for line in self:
            line.formatted_duration = format_duration(line.service_duration)