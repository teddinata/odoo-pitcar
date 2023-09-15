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