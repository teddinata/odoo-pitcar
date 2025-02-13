from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CSFinanceCheckItem(models.Model):
    _name = 'cs.finance.check.item'
    _description = 'CS Finance Check Item Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Item Name', required=True, tracking=True)
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)

class CSFinanceCheck(models.Model):
    _name = 'cs.finance.check'
    _description = 'CS Finance Daily Check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char('Reference', compute='_compute_name', store=True)
    date = fields.Date('Check Date', required=True, default=fields.Date.context_today, tracking=True)
    cs_id = fields.Many2one('hr.employee', 'Customer Service', 
        domain="[('job_id.name', 'ilike', 'customer service')]", required=True, tracking=True)
    controller_id = fields.Many2one('hr.employee', 'Checked By', tracking=True)
    
    check_line_ids = fields.One2many('cs.finance.check.line', 'check_id', 'Finance Checks')
    total_items = fields.Integer('Total Items', compute='_compute_metrics', store=True)
    complete_items = fields.Integer('Complete Items', compute='_compute_metrics', store=True)
    completeness_rate = fields.Float('Completeness Rate (%)', compute='_compute_metrics', store=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ], default='draft', tracking=True)
    
    notes = fields.Text('Notes')
    
    @api.depends('cs_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.cs_id and record.date:
                record.name = f"FIN-CHECK/{record.date.strftime('%Y%m%d')}/{record.cs_id.name}"
    
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
        # Auto-create check lines for all active items
        record = super().create(vals)
        check_items = self.env['cs.finance.check.item'].search([('active', '=', True)])
        for item in check_items:
            self.env['cs.finance.check.line'].create({
                'check_id': record.id,
                'item_id': item.id
            })
        return record

class CSFinanceCheckLine(models.Model):
    _name = 'cs.finance.check.line'
    _description = 'CS Finance Check Line'
    
    check_id = fields.Many2one('cs.finance.check', 'Check Reference', required=True, ondelete='cascade')
    item_id = fields.Many2one('cs.finance.check.item', 'Check Item', required=True)
    is_complete = fields.Boolean('Complete & Verified', default=False)
    notes = fields.Text('Notes')