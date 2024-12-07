from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    mechanic_id = fields.One2many('pitcar.mechanic.new', 'employee_id', string='Mechanic Reference')
    is_mechanic = fields.Boolean(string='Is Mechanic', compute='_compute_is_mechanic', store=True)
    position_id = fields.Many2one(
        related='mechanic_id.position_id',
        string='Mechanic Position',
        readonly=True
    )
    monthly_target = fields.Float(
        related='mechanic_id.monthly_target',
        string='Monthly Target',
        readonly=True
    )
    current_revenue = fields.Float(
        related='mechanic_id.current_revenue',
        string='Current Revenue',
        readonly=True
    )
    attendance_achievement = fields.Float(
        related='mechanic_id.attendance_achievement',
        string='Attendance Achievement',
        readonly=True
    )
    face_descriptor = fields.Text(
        string='Face Descriptor', 
        help='Face encoding data for recognition'
    )
    face_image = fields.Binary('Face Image Reference')

    @api.depends('mechanic_id')
    def _compute_is_mechanic(self):
        for employee in self:
            employee.is_mechanic = bool(employee.mechanic_id)

    def create_mechanic(self):
        self.ensure_one()
        if not self.mechanic_id:
            default_position = self.env.ref('your_module.default_mechanic_position', raise_if_not_found=False)
            mechanic = self.env['pitcar.mechanic.new'].create({
                'name': self.name,
                'employee_id': self.id,
                'position_id': default_position and default_position.id or False,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pitcar.mechanic.new',
                'res_id': mechanic.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return True

    def attendance_manual(self, next_action, entered_pin=None):
        res = super(HrEmployee, self).attendance_manual(next_action, entered_pin)
        if self.is_mechanic:
            # Additional logic for mechanic attendance
            pass
        return res