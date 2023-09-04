from datetime import date
from odoo import models, fields, api, _, exceptions

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
    number_plate = fields.Char(string="Number Plate", required=True)
    frame_number = fields.Char(string="Frame Number")
    engine_number = fields.Char(string="Engine Number")
    brand = fields.Many2one('res.partner.car.brand', string="Brand", required=True)
    brand_type = fields.Many2one('res.partner.car.type', string="Type", required=True, domain="[('brand','=',brand)]")
    color = fields.Char(string="Color")
    year = fields.Char(string="Year", default=date.today().year, required=True)
    transmission = fields.Many2one('res.partner.car.transmission', string="Transmission", required=True)
    image = fields.Binary(string="Image")
    comment = fields.Html(string='Notes')
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)

    # if brand changed, type will be reset
    @api.onchange('brand')
    def _onchange_brand(self):
        self.brand_type = False
        return {'domain': {'brand_type': [('brand','=',self.brand.id)]}}

    # Name Computation from Brand and Type
    @api.depends('brand','brand_type')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.brand.name + ' ' + rec.brand_type.name

    # Number Plate Validation for Unique
    @api.constrains('number_plate')
    def _check_number_plate(self):
        for rec in self:
            if rec.number_plate:
                if self.env['res.partner.car'].search_count([('number_plate','=',rec.number_plate)]) > 1:
                    raise exceptions.ValidationError(_("Number Plate must be unique!"))
                
    # Year Validation
    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year:
                if rec.year.isdigit() == False:
                    raise exceptions.ValidationError(_("Year must be a number between 1900 and {year}".format(year = date.today().year)))
                if int(rec.year) > date.today().year:
                    raise exceptions.ValidationError(_("Year must be less than or equal to {year}".format(year = date.today().year)))
                if int(rec.year) < 1900:
                    raise exceptions.ValidationError(_("Year must be greater than or equal to 1900!"))
