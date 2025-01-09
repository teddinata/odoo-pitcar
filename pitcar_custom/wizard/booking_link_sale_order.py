# wizards/booking_link_sale_order.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
from dateutil.relativedelta import relativedelta

class BookingLinkSaleOrderWizard(models.TransientModel):
    _name = 'booking.link.sale.order.wizard'
    _description = 'Link Booking to Sale Order Wizard'

    booking_id = fields.Many2one('pitcar.service.booking', required=True)
    sale_order_id = fields.Many2one(
        'sale.order', 
        string='Select Sale Order',
        required=True,
        domain="[('state', '!=', 'cancel')]"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Get booking record
        booking_id = self.env.context.get('default_booking_id')
        if not booking_id:
            return res
            
        booking = self.env['pitcar.service.booking'].browse(booking_id)
        if not booking:
            return res

        # Get today's sale orders
        today = fields.Date.today()
        domain = [
            ('create_date', '>=', f"{today} 00:00:00"),
            ('create_date', '<', f"{(today + relativedelta(days=1)).strftime('%Y-%m-%d')} 00:00:00"),
            ('state', '!=', 'cancel')
        ]
        
        sale_orders = self.env['sale.order'].search(domain)
        if sale_orders:
            res['sale_order_id'] = sale_orders[0].id
            
        return res

    def action_link_sale_order(self):
        self.ensure_one()
        booking = self.booking_id
        sale_order = self.sale_order_id

        if not booking or not sale_order:
            raise ValidationError(_('Booking and Sale Order are required'))

        try:
            # Clear existing lines first if any
            sale_order.order_line.unlink()
            
            # Prepare sale order values
            sale_order_vals = {
                'partner_id': booking.partner_id.id,
                'partner_car_id': booking.partner_car_id.id,
                'partner_car_odometer': booking.partner_car_odometer,
                'is_booking': True,
                'booking_id': booking.id,
                'service_category': booking.service_category,
                'service_subcategory': booking.service_subcategory,
                'service_advisor_id': [(6, 0, booking.service_advisor_id.ids)],
                'origin': booking.name,
                'sale_order_template_id': booking.sale_order_template_id.id
            }

            # Update sale order with all booking data
            sale_order.write(sale_order_vals)
            
            # Update addresses
            sale_order._onchange_partner_id()

            # Copy booking lines
            existing_products = set()  # Track products untuk mencegah duplikasi
            
            for line in booking.booking_line_ids:
                if line.display_type:
                    # Handle sections and notes
                    vals = {
                        'order_id': sale_order.id,
                        'display_type': line.display_type,
                        'name': line.name,
                        'sequence': line.sequence,
                    }
                    self.env['sale.order.line'].create(vals)
                else:
                    # Handle product lines - cek duplikasi
                    if line.product_id.id not in existing_products:
                        vals = {
                            'order_id': sale_order.id,
                            'product_id': line.product_id.id,
                            'product_uom_qty': line.quantity,
                            'service_duration': line.service_duration,
                            'name': line.name,
                            'price_unit': line.price_unit,
                            'discount': line.discount,
                            'tax_id': [(6, 0, line.tax_ids.ids)],
                            'sequence': line.sequence,
                        }
                        self.env['sale.order.line'].create(vals)
                        existing_products.add(line.product_id.id)

            # Mark booking as converted
            booking.write({
                'state': 'converted',
                'sale_order_id': sale_order.id
            })

            # Post message
            msg_body = f"""
            <p><strong>Linked to Sale Order</strong></p>
            <ul>
                <li>Sale Order: {sale_order.name}</li>
                <li>Customer: {booking.partner_id.name}</li>
                <li>Car: {booking.partner_car_id.display_name}</li>
                <li>Queue Number: {sale_order.display_queue_number or 'Not assigned'}</li>
                <li>Linked by: {self.env.user.name}</li>
                <li>Link Time: {fields.Datetime.now()}</li>
            </ul>
            """
            booking.message_post(body=msg_body, message_type='notification')
            sale_order.message_post(body=msg_body, message_type='notification')

            return {
                'type': 'ir.actions.act_window',
                'name': 'Sale Order',
                'res_model': 'sale.order',
                'res_id': sale_order.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            raise ValidationError(_(f"Error linking booking to sale order: {str(e)}"))
