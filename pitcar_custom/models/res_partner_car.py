from datetime import date
from odoo import models, fields, api, _, exceptions
import re

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
    
    car_ids = fields.One2many('res.partner.car', 'brand', string="Cars")
    car_count = fields.Integer(string="Car Count", compute='_compute_count')
    car_count_string = fields.Char(string="Total Car", compute='_compute_count_string')
    
    brand_type_ids = fields.One2many('res.partner.car.type', 'brand', string="Types")
    brand_type_count = fields.Integer(string="Type Count", compute='_compute_brand_type_count')
    brand_type_count_string = fields.Char(string="Total Type", compute='_compute_brand_type_count_string')

    @api.depends('car_ids')
    def _compute_count(self):
        for rec in self:
            rec.car_count = len(rec.car_ids)

    @api.depends('car_count')
    def _compute_count_string(self):
        for rec in self:
            rec.car_count_string = f"{rec.car_count} Car{'s' if rec.car_count != 1 else ''}"

    @api.depends('brand_type_ids')
    def _compute_brand_type_count(self):
        for rec in self:
            rec.brand_type_count = len(rec.brand_type_ids)

    @api.depends('brand_type_count')
    def _compute_brand_type_count_string(self):
        for rec in self:
            rec.brand_type_count_string = f"{rec.brand_type_count} Type{'s' if rec.brand_type_count != 1 else ''}"

            


class ResPartnerCarType(models.Model):
    _name='res.partner.car.type'
    _description = 'Type of car'
    _order = 'name'

    name = fields.Char(string="Name", required=True)
    formatted_name = fields.Char(string="Combined Brand and Type Name", compute='_compute_formatted_name', store=True, index="trigram")
    brand = fields.Many2one('res.partner.car.brand', string="Brand", required=True)
    
    car_ids = fields.One2many('res.partner.car', 'brand_type', string="Cars")
    car_count = fields.Integer(string="Car Count", compute='_compute_count', store=True)
    car_count_string = fields.Char(string="Total Car", compute='_compute_count_string')
    
    @api.depends('car_ids')
    def _compute_count(self):
        for rec in self:
            rec.car_count = len(rec.car_ids)
    
    @api.depends('car_count')
    def _compute_count_string(self):
        for rec in self:
            rec.car_count_string = f"{rec.car_count} Car{'s' if rec.car_count != 1 else ''}"
            
    @api.depends('name', 'brand')
    def _compute_formatted_name(self):
        for rec in self:
            rec.formatted_name = '{brand} {name}'.format(brand=rec.brand.name, name=rec.name)


class ResPartnerCar(models.Model):
    _name='res.partner.car'
    _description = 'Cars of partner'
    _order = 'name asc'

    name = fields.Char(string="Name", compute='_compute_name', store=True)
    number_plate = fields.Char(string="Number Plate", required=True, copy=False, index="trigram")
    frame_number = fields.Char(string="Frame Number")
    engine_number = fields.Char(string="Engine Number")
    brand = fields.Many2one('res.partner.car.brand', string="Brand", required=True, index="btree_not_null")
    brand_type = fields.Many2one('res.partner.car.type', string="Type", required=True, domain="[('brand','=',brand)]", index="btree_not_null",)
    color = fields.Char(string="Color")
    year = fields.Char(string="Year", default=date.today().year, required=True)
    transmission = fields.Many2one('res.partner.car.transmission', string="Transmission", required=True)
    image = fields.Binary(string="Image")
    comment = fields.Html(string='Notes')
    partner_id = fields.Many2one('res.partner', string="Customer", required=True, index=True)
    engine_type = fields.Selection([
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
        ('gas', 'Gas'),
        ('other', 'Other'),
    ], string='Engine Type')

    # if brand changed, type will be reset
    @api.onchange('brand')
    def _onchange_brand(self):
        self.brand_type = False
        return {'domain': {'brand_type': [('brand','=',self.brand.id)]}}

    # Name Computation from Brand and Type
    @api.depends('brand','brand_type','number_plate')
    def _compute_name(self):
        for rec in self:
            rec.name = '{number_plate} {brand} {brand_type}'.format(
                brand=rec.brand.name, 
                brand_type=rec.brand_type.name, 
                number_plate=rec.number_plate
            ) 

    # Number Plate Validation for Unique
    @api.constrains('number_plate')
    def _check_number_plate(self):
        for rec in self:
            if rec.number_plate:
                if self.env['res.partner.car'].search_count([('number_plate','=',rec.number_plate)]) > 1:
                    raise exceptions.ValidationError(_("Number Plate must be unique!"))

    # Number Plate Remove space in create and update
    @api.onchange('number_plate')
    def _onchange_number_plate(self):
        if self.number_plate:
            self.number_plate = self.number_plate.replace(" ", "").upper()

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
