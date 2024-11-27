# models/pitcar_position.py
from odoo import models, fields, api

class PitcarPosition(models.Model):
    _name = 'pitcar.position'
    _description = 'PitCar Position'

    name = fields.Char('Name', required=True)
    code = fields.Selection([
        ('leader', 'Team Leader'),
        ('mechanic', 'Mechanic')
    ], string='Position Code', required=True)
    monthly_target = fields.Float('Monthly Target', default=64000000)  # 64jt default untuk mekanik