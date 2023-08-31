from odoo import models, fields, api, _

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



