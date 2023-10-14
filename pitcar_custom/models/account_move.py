from odoo import models, fields, api, _, exceptions

class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_car_id = fields.Many2one(
        'res.partner.car',
        string="Serviced Car",
        domain="[('partner_id','=',partner_id)]",
        tracking=True,
        index=True,
    )
    partner_car_odometer = fields.Float(
        string="Odometer",
    )