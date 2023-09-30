from odoo import api, fields, models, _

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _prepare_invoice_values(self, order, so_line):
        print(order)
        print(order.partner_car_id)
        print(order.partner_car_odometer)
        res = super(SaleAdvancePaymentInv, self)._prepare_invoice_values(order, so_line)
        res['partner_car_id'] = order.partner_car_id.id
        res['partner_car_odometer'] = order.partner_car_odometer
        return res
