from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta

class MechanicHandTool(models.Model):
    _name = 'pitcar.mechanic.hand.tool'
    _description = 'Mechanic Hand Tool Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Tool Name', required=True, tracking=True)
    code = fields.Char('Tool Code', tracking=True)
    category_id = fields.Many2one('pitcar.tool.category', 'Tool Category')
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)
    qty_expected = fields.Integer('Expected Quantity', default=1, help="Expected quantity in the system")
    mechanic_id = fields.Many2one('hr.employee', 'Assigned Mechanic', 
                                  domain="[('job_id.name', 'ilike', 'mechanic')]", tracking=True)
    date_assigned = fields.Date('Date Assigned')
    image = fields.Binary('Tool Image')
    location = fields.Char('Storage Location')
    serial_number = fields.Char('Serial Number')
    purchase_date = fields.Date('Purchase Date')
    warranty_end_date = fields.Date('Warranty End Date')
    maintenance_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ], string='Maintenance Frequency')
    last_maintenance_date = fields.Date('Last Maintenance Date')
    next_maintenance_date = fields.Date('Next Maintenance Date', compute='_compute_next_maintenance', store=True)
    state = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Under Maintenance'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged')
    ], string='Status', default='available', tracking=True)
    notes = fields.Text('Notes')
    
    @api.depends('last_maintenance_date', 'maintenance_frequency')
    def _compute_next_maintenance(self):
        for tool in self:
            if not tool.last_maintenance_date or not tool.maintenance_frequency:
                tool.next_maintenance_date = False
                continue
                
            if tool.maintenance_frequency == 'daily':
                tool.next_maintenance_date = tool.last_maintenance_date + timedelta(days=1)
            elif tool.maintenance_frequency == 'weekly':
                tool.next_maintenance_date = tool.last_maintenance_date + timedelta(days=7)
            elif tool.maintenance_frequency == 'monthly':
                tool.next_maintenance_date = tool.last_maintenance_date + timedelta(days=30)
            elif tool.maintenance_frequency == 'quarterly':
                tool.next_maintenance_date = tool.last_maintenance_date + timedelta(days=91)
            elif tool.maintenance_frequency == 'yearly':
                tool.next_maintenance_date = tool.last_maintenance_date + timedelta(days=365)
    
    def action_assign(self, mechanic_id):
        self.write({
            'mechanic_id': mechanic_id,
            'date_assigned': fields.Date.today(),
            'state': 'assigned'
        })
    
    def action_return(self):
        self.write({
            'mechanic_id': False,
            'date_assigned': False,
            'state': 'available'
        })
    
    def action_maintenance(self):
        self.write({
            'state': 'maintenance'
        })
    
    def action_mark_lost(self):
        self.write({
            'state': 'lost'
        })
    
    def action_mark_damaged(self):
        self.write({
            'state': 'damaged'
        })

class ToolCategory(models.Model):
    _name = 'pitcar.tool.category'
    _description = 'Tool Category'
    
    name = fields.Char('Category Name', required=True)
    description = fields.Text('Description')
    parent_id = fields.Many2one('pitcar.tool.category', 'Parent Category')

class MechanicToolCheck(models.Model):
    _name = 'pitcar.mechanic.tool.check'
    _description = 'Mechanic Hand Tools Daily Check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char('Reference', compute='_compute_name', store=True)
    date = fields.Date('Check Date', required=True, default=fields.Date.context_today, tracking=True)
    month = fields.Char('Month', compute='_compute_month', store=True)
    
    mechanic_id = fields.Many2one('hr.employee', 'Mechanic', 
        domain="[('job_id.name', 'ilike', 'mechanic')]", required=True, tracking=True)
    supervisor_id = fields.Many2one('hr.employee', 'Checked By', tracking=True)
    
    check_line_ids = fields.One2many('pitcar.mechanic.tool.check.line', 'check_id', 'Tool Checks')
    total_items = fields.Integer('Total Tools', compute='_compute_metrics', store=True)
    matched_items = fields.Integer('Matched Tools', compute='_compute_metrics', store=True)
    accuracy_rate = fields.Float('Accuracy Rate (%)', compute='_compute_metrics', store=True)
    
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
    
    @api.depends('mechanic_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.mechanic_id and record.date:
                record.name = f"TOOLS-CHECK/{record.date.strftime('%Y%m%d')}/{record.mechanic_id.name}"
    
    @api.depends('check_line_ids.qty_matched')
    def _compute_metrics(self):
        for record in self:
            record.total_items = len(record.check_line_ids)
            record.matched_items = len(record.check_line_ids.filtered('qty_matched'))
            record.accuracy_rate = (record.matched_items / record.total_items * 100) if record.total_items else 0
    
    def action_done(self):
        self.write({
            'state': 'done',
            'supervisor_id': self.env.user.employee_id.id
        })
    
    @api.model
    def create(self, vals):
        # Auto-create check lines for all tools assigned to the mechanic
        record = super().create(vals)
        
        # Get all tools assigned to this mechanic
        mechanic_id = vals.get('mechanic_id')
        if not mechanic_id:
            return record
            
        tools = self.env['pitcar.mechanic.hand.tool'].search([
            ('mechanic_id', '=', mechanic_id),
            ('active', '=', True)
        ])
        
        for tool in tools:
            self.env['pitcar.mechanic.tool.check.line'].create({
                'check_id': record.id,
                'tool_id': tool.id,
                'qty_expected': tool.qty_expected,
                'qty_actual': 0  # To be filled during check
            })
        return record

class MechanicToolCheckLine(models.Model):
    _name = 'pitcar.mechanic.tool.check.line'
    _description = 'Mechanic Tool Check Line'
    
    check_id = fields.Many2one('pitcar.mechanic.tool.check', 'Check Reference', required=True, ondelete='cascade')
    tool_id = fields.Many2one('pitcar.mechanic.hand.tool', 'Tool', required=True)
    qty_expected = fields.Integer('Expected Quantity', default=1)
    qty_actual = fields.Integer('Actual Quantity', default=0)
    qty_matched = fields.Boolean('Quantity Matched', compute='_compute_qty_matched', store=True)
    physical_condition = fields.Selection([
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
        ('missing', 'Missing')
    ], string='Physical Condition', default='good')
    notes = fields.Text('Notes')
    
    @api.depends('qty_expected', 'qty_actual')
    def _compute_qty_matched(self):
        for record in self:
            record.qty_matched = record.qty_expected == record.qty_actual

    @api.constrains('qty_actual')
    def _check_qty_actual(self):
        for record in self:
            if record.qty_actual < 0:
                raise ValidationError("Actual quantity cannot be negative.")