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
    sequence = fields.Integer(string='Sequence', default=10)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'sequence')
    def _compute_amount(self):
        super(SaleOrderLine, self)._compute_amount()
        for line in self:
            if line.display_type != 'line_section':  # Hanya untuk product lines
                sections = line.order_id.order_line.filtered(
                    lambda l: l.display_type == 'line_section' and 
                            l.sequence < line.sequence
                ).sorted('sequence', reverse=True)
                
                if sections and sections[0].name == 'RECOMMENDATION':
                    line.price_unit = 0
                    line.price_subtotal = 0
                    line.price_tax = 0
                    line.price_total = 0

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

    # models/sale_order_line.py
class SaleOrderRecommendation(models.Model):
    _name = 'sale.order.recommendation'
    _description = 'Sale Order Recommendation'
    _order = 'estimated_date'
    
    order_id = fields.Many2one('sale.order', string='Order Reference')
    product_id = fields.Many2one('product.product', string='Product')
    name = fields.Text(string='Description')
    estimated_date = fields.Date(string='Estimated Service Date')
    service_duration = fields.Float(string='Durasi (Jam)', digits=(16, 2))
    formatted_duration = fields.Char(string='Durasi', compute='_compute_formatted_duration')
    price_unit = fields.Float(string='Unit Price', digits='Product Price')  # Perhatikan nama field ini
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id')

    @api.depends('service_duration')
    def _compute_formatted_duration(self):
        for rec in self:
            rec.formatted_duration = format_duration(rec.service_duration)
            
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.get_product_multiline_description_sale()
            self.service_duration = self.product_id.service_duration 
            self.price_unit = self.product_id.list_price  # Sesuaikan dengan nama field yang benar
    
    @api.model_create_multi
    def create(self, vals_list):
        recommendations = super().create(vals_list)
        for rec in recommendations:
            message = f"""
                <b>New Service Recommendation Added</b>
                <ul>
                    <li>Service: {rec.product_id.name}</li>
                    <li>Price: {rec.currency_id.symbol} {rec.price_unit:,.2f}</li>
                </ul>
            """
            rec.order_id.message_post(body=message, message_type='notification')
        return recommendations

    def write(self, vals):
        for rec in self:
            changes = []
            if 'product_id' in vals and vals['product_id'] != rec.product_id.id:
                new_product = self.env['product.product'].browse(vals['product_id'])
                changes.append(f'Service changed from {rec.product_id.name} to {new_product.name}')
            
            if 'estimated_date' in vals and vals['estimated_date'] != rec.estimated_date:
                changes.append(f'Estimated date changed from {rec.estimated_date} to {vals["estimated_date"]}')
            
            if 'service_duration' in vals:
                old_duration = format_duration(rec.service_duration)
                new_duration = format_duration(vals['service_duration'])
                changes.append(f'Duration changed from {old_duration} to {new_duration}')
            
            if 'price_unit' in vals and vals['price_unit'] != rec.price_unit:
                changes.append(f'Price changed from {rec.currency_id.symbol} {rec.price_unit:,.2f} to {rec.currency_id.symbol} {vals["price_unit"]:,.2f}')

            if changes:
                message = f"""
                    <b>Service Recommendation Updated</b>
                    <ul>
                        {''.join(f'<li>{change}</li>' for change in changes)}
                    </ul>
                """
                rec.order_id.message_post(body=message, message_type='notification')

        return super().write(vals)

    def unlink(self):
        for rec in self:
            message = f"""
                <b>Service Recommendation Removed</b>
                <ul>
                    <li>Service: {rec.product_id.name}</li>
                    <li>Estimated Date: {rec.estimated_date}</li>
                </ul>
            """
            rec.order_id.message_post(body=message, message_type='notification')
        return super().unlink()

