from odoo import models, fields, api

class MechanicCredentialWizard(models.TransientModel):
    _name = 'mechanic.credential.wizard'
    _description = 'Mechanic Credential Wizard'

    mechanic_id = fields.Many2one('pitcar.mechanic.new', string='Mechanic')
    login = fields.Char(related='mechanic_id.user_id.login', readonly=True)
    temp_password = fields.Char(related='mechanic_id.temp_password', readonly=True)