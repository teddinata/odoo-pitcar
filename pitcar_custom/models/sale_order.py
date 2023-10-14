from odoo import models, fields, api, _, exceptions

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_car_id = fields.Many2one(
        'res.partner.car',
        string="Serviced Car",
        domain="[('partner_id','=',partner_id)]",
        index=True,
    )
    partner_car_odometer = fields.Float(
        string="Odometer",
    )
    car_mechanic_id = fields.Many2one(
        'pitcar.mechanic',
        string="Mechanic",
        tracking=True,
        index=True,
    )


    # Copying car information from sales order to delivery data when sales confirmed
    # model : stock.picking
    def _action_confirm(self):
        res = super(SaleOrder, self)._action_confirm()
        for order in self:
            for picking in order.picking_ids:
                picking.partner_car_id = order.partner_car_id
                picking.partner_car_odometer = order.partner_car_odometer
                picking.car_mechanic_id = order.car_mechanic_id
        return res

    # Copying car information from sales order to invoice data when invoice created
    # model : account.move
    def _create_invoices(self, grouped=False, final=False):
        res = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
        for order in self:
            for invoice in order.invoice_ids:
                invoice.partner_car_id = order.partner_car_id
                invoice.partner_car_odometer = order.partner_car_odometer
                invoice.car_mechanic_id = order.car_mechanic_id
        return res