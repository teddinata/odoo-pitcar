# models/hr_employee_public.py

from odoo import models, fields, api

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'
    
    mechanic_id = fields.One2many('pitcar.mechanic.new', 'employee_id', string='Mechanic Reference', readonly=True)
    is_mechanic = fields.Boolean(string='Is Mechanic', readonly=True)  # Ubah jadi readonly=True
    # mechanic_id = fields.One2many('pitcar.mechanic.new', 'employee_id', string='Mechanic Reference', readonly=True)
    # is_mechanic = fields.Boolean(string='Is Mechanic', compute='_compute_is_mechanic', store=True)
    
    # @api.depends('mechanic_id')
    # def _compute_is_mechanic(self):
    #     for employee in self:
    #         employee.is_mechanic = bool(employee.mechanic_id)