from odoo import models, fields, api, _, exceptions
from random import randint

class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    partner_count = fields.Integer(string="Partner Count", compute='_compute_partner_count')

    @api.depends('partner_ids')
    def _compute_partner_count(self):
        for category in self:
            category.partner_count = len(category.partner_ids)


class ResPartnerSource(models.Model):
    _name = 'res.partner.source'
    _description = 'Source of partner'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

class ResPartner(models.Model):
    _inherit = ['res.partner']

    gender = fields.Selection(
        [('male', 'Male'), 
         ('female', 'Female'),
        ], string="Gender"
    )
    source = fields.Many2one('res.partner.source', string="Source")
    dob = fields.Date(string="Date of Birth")
    car_ids = fields.One2many('res.partner.car', 'partner_id', string="Cars")
    category_id = fields.Many2many('res.partner.category', column1='partner_id',
                                    column2='category_id', string='Tags', required=True)
    phone = fields.Char(unaccent=False, required=True)

class PitcarMechanic(models.Model):
    _name = 'pitcar.mechanic'
    _description = 'Mechanic'
    _order = 'name'

    name = fields.Char(string="Name", required=True)
    
class PitcarMechanicNew(models.Model):
    _name = 'pitcar.mechanic.new'
    _description = 'Mechanic New'
    _order = 'name'
    
    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string="Name", required=True, tracking=True)
    color = fields.Integer('Color', default=_get_default_color)
    
    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Mechanic name already exists !"),
    ]

