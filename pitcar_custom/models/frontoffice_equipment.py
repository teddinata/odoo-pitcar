from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FrontOfficeEquipment(models.Model):
    _name = 'pitcar.front.office.equipment'
    _description = 'Front Office Equipment Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Equipment Name', required=True, tracking=True)
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)

class FrontOfficeCheck(models.Model):
    _name = 'pitcar.front.office.check'
    _description = 'Front Office Equipment Daily Check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char('Reference', compute='_compute_name', store=True)
    date = fields.Date('Check Date', required=True, default=fields.Date.context_today, tracking=True)
    month = fields.Char('Month', compute='_compute_month', store=True)
    
    valet_id = fields.Many2one('hr.employee', 'Valet Staff', 
        domain="[('job_id.name', 'ilike', 'valet')]", required=True, tracking=True)
    controller_id = fields.Many2one('hr.employee', 'Checked By', tracking=True)
    
    check_line_ids = fields.One2many('pitcar.front.office.check.line', 'check_id', 'Equipment Checks')
    total_items = fields.Integer('Total Items', compute='_compute_metrics', store=True)
    complete_items = fields.Integer('Complete Items', compute='_compute_metrics', store=True)
    completeness_rate = fields.Float('Completeness Rate (%)', compute='_compute_metrics', store=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ], default='draft', tracking=True)
    
    notes = fields.Text('Notes')
    
    @api.depends('date')
    def _compute_month(self):
        for record in self:
            if record.date:
                record.month = record.date.strftime('%Y-%m')
    
    @api.depends('valet_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.valet_id and record.date:
                record.name = f"CHECK/{record.date.strftime('%Y%m%d')}/{record.valet_id.name}"
    
    @api.depends('check_line_ids.is_complete')
    def _compute_metrics(self):
        for record in self:
            record.total_items = len(record.check_line_ids)
            record.complete_items = len(record.check_line_ids.filtered('is_complete'))
            record.completeness_rate = (record.complete_items / record.total_items * 100) if record.total_items else 0
    
    def action_done(self):
        self.write({
            'state': 'done',
            'controller_id': self.env.user.employee_id.id
        })
    
    @api.model
    def create(self, vals):
        # Auto-create check lines for all active equipment
        record = super().create(vals)
        equipments = self.env['pitcar.front.office.equipment'].search([('active', '=', True)])
        for equipment in equipments:
            self.env['pitcar.front.office.check.line'].create({
                'check_id': record.id,
                'equipment_id': equipment.id
            })
        return record

class FrontOfficeCheckLine(models.Model):
    _name = 'pitcar.front.office.check.line'
    _description = 'Front Office Equipment Check Line'
    
    check_id = fields.Many2one('pitcar.front.office.check', 'Check Reference', required=True, ondelete='cascade')
    equipment_id = fields.Many2one('pitcar.front.office.equipment', 'Equipment', required=True)
    is_complete = fields.Boolean('Complete & Organized', default=False)
    notes = fields.Text('Notes')