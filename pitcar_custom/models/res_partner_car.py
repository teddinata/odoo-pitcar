from datetime import date
from odoo import models, fields, api, _

class ResPartnerCarTransmission(models.Model):
    _name='res.partner.car.transmission'
    _description = 'Transmission of car'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

class ResPartnerCarBrand(models.Model):
    _name='res.partner.car.brand'
    _description = 'Brand of car'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

class ResPartnerCarType(models.Model):
    _name='res.partner.car.type'
    _description = 'Type of car'
    _order = 'name'

    name = fields.Char(string="Name", required=True)
    brand = fields.Many2one('res.partner.car.brand', string="Brand", required=True)

class ResPartnerCar(models.Model):
    _name='res.partner.car'
    _description = 'Cars of partner'
    _order = 'name'

    name = fields.Char(string="Name", required=True, compute='_compute_name')
    number_plate = fields.Char(string="Number Plat", required=True)
    frame_number = fields.Char(string="Frame Number", required=True)
    engine_number = fields.Char(string="Engine Number", required=True)
    brand = fields.Many2one('res.partner.car.brand', string="Brand", required=True)
    brand_type = fields.Many2one('res.partner.car.type', string="Type", required=True, domain="[('brand','=',brand)]")
    color = fields.Char(string="Color")
    year = fields.Integer(string="Year", default=date.today().year, required=True)
    transmission = fields.Many2one('res.partner.car.transmission', string="Transmission", required=True)
    comment = fields.Html(string='Notes')
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)

    @api.onchange('brand')
    def _onchange_brand(self):
        self.brand_type = False
        return {'domain': {'brand_type': [('brand','=',self.brand.id)]}}

    @api.depends('brand','brand_type')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.brand.name + ' ' + rec.brand_type.name
