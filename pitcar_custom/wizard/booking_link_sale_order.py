# wizards/booking_link_sale_order.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime

class BookingLinkSaleOrderWizard(models.TransientModel):
    _name = 'booking.link.sale.order.wizard'
    _description = 'Link Booking to Sale Order Wizard'

    booking_id = fields.Many2one('pitcar.service.booking', required=True)
    sale_order_id = fields.Many2one(
        'sale.order', 
        string='Select Sale Order',
        required=True,
        domain="[('state', '!=', 'cancel')]"  # Simplify domain
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        # Set domain untuk sale orders hari ini
        domain = [
            ('create_date', '>=', f"{today} 00:00:00"),
            ('create_date', '<', f"{tomorrow} 00:00:00"),
            ('state', '!=', 'cancel')
        ]
        
        sale_orders = self.env['sale.order'].search(domain)
        
        if 'sale_order_id' in fields_list:
            if sale_orders:
                res['sale_order_id'] = sale_orders[0].id
        
        return res

    def action_link_sale_order(self):
        self.ensure_one()
        booking = self.booking_id
        sale_order = self.sale_order_id

        try:
            # Update sale order dengan data booking
            sale_order.write({
                'is_booking': True,
                'booking_id': booking.id,
                'service_category': booking.service_category,
                'service_subcategory': booking.service_subcategory,
                'service_advisor_id': [(6, 0, booking.service_advisor_id.ids)]
            })

            # Copy booking lines ke sale order
            for line in booking.booking_line_ids:
                self.env['sale.order.line'].create({
                    'order_id': sale_order.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'service_duration': line.service_duration,
                    'name': line.name,
                })

            # Update booking status
            booking.write({
                'state': 'converted',
                'sale_order_id': sale_order.id
            })

            # Post message di booking
            booking.message_post(
                body=f"""
                <p><strong>Linked to Sale Order</strong></p>
                <ul>
                    <li>Sale Order: {sale_order.name}</li>
                    <li>Queue Number: {sale_order.display_queue_number}</li>
                    <li>Linked by: {self.env.user.name}</li>
                </ul>
                """,
                message_type='notification'
            )

            return {
                'type': 'ir.actions.act_window',
                'name': 'Sale Order',
                'res_model': 'sale.order',
                'res_id': sale_order.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            raise ValidationError(f"Error linking booking to sale order: {str(e)}")