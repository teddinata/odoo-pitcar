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
    # position_id = fields.Many2one('pitcar.mechanic.position', string='Mechanic Position', readonly=True)
    # monthly_target = fields.Float(string='Monthly Target', readonly=True)
    # current_revenue = fields.Float(string='Current Revenue', readonly=True)
    # attendance_achievement = fields.Float(string='Attendance Achievement', readonly=True)
    face_descriptor = fields.Text(string='Face Descriptor', readonly=True)
    # face_image = fields.Binary('Face Image', readonly=True)