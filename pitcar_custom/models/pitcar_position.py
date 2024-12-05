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

class ServiceAdvisorPosition(models.Model):
    _name = 'pitcar.service.advisor.position'
    _description = 'Service Advisor Position'

    name = fields.Char('Name', required=True)
    code = fields.Selection([
        ('leader', 'Team Leader'),
        ('advisor', 'Service Advisor')
    ], string='Position Code', required=True)
    monthly_target = fields.Float('Monthly Target', default=225000000)  # 225jt default untuk advisor
