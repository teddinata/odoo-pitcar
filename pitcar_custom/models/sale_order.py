from odoo import models, fields, api, _, exceptions

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_car_id = fields.Many2one(
        'res.partner.car', 
        string="Serviced Car",
        domain="[('partner_id','=',partner_id)]",
        tracking=True,
    )
    partner_car_odometer = fields.Float(string="Odometer", tracking=True)

    # if confirmed, partner_car_id and partner_car_odometer should be copied to stock.picking
    def _action_confirm(self):
        res = super(SaleOrder, self)._action_confirm()
        for order in self:
            for picking in order.picking_ids:
                picking.partner_car_id = order.partner_car_id
        return res