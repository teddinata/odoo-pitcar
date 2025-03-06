# models/pitcar_tools.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta

class PitcarTools(models.Model):
    _name = 'pitcar.tools'
    _description = 'Pitcar Tools Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc'
    
    name = fields.Char('Tool Name', required=True, tracking=True)
    reference = fields.Char('Reference', compute='_compute_reference', store=True)
    request_date = fields.Date('Request Date', default=fields.Date.context_today, required=True, tracking=True)
    
    requester_id = fields.Many2one('hr.employee', 'Requested By', required=True, tracking=True)
    approver_id = fields.Many2one('hr.employee', 'Approved By', tracking=True)
    
    tool_type = fields.Selection([
        ('mechanical', 'Mechanical'),
        ('electrical', 'Electrical'),
        ('diagnostic', 'Diagnostic'),
        ('other', 'Other')
    ], string='Tool Type', required=True)
    
    expected_lifetime = fields.Integer('Expected Lifetime (months)', required=True)
    depreciation_end_date = fields.Date('Depreciation End Date', compute='_compute_depreciation_end', store=True)
    
    purchase_date = fields.Date('Purchase Date')
    purchase_price = fields.Float('Purchase Price')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('purchased', 'Purchased'),
        ('in_use', 'In Use'),
        ('broken', 'Broken'),
        ('deprecated', 'Deprecated')
    ], default='draft', tracking=True)
    
    broken_date = fields.Date('Broken Date')
    is_premature_broken = fields.Boolean('Premature Breakage', compute='_compute_premature_broken', store=True)
    
    notes = fields.Text('Notes')
    
    @api.depends('name', 'request_date')
    def _compute_reference(self):
        for record in self:
            if record.name and record.request_date:
                record.reference = f"TOOL/{record.request_date.strftime('%Y%m%d')}/{record.name.replace(' ', '_')}"
    
    @api.depends('purchase_date', 'expected_lifetime')
    def _compute_depreciation_end(self):
        for record in self:
            if record.purchase_date and record.expected_lifetime:
                record.depreciation_end_date = record.purchase_date + timedelta(days=30.44 * record.expected_lifetime)
            else:
                record.depreciation_end_date = False
    
    @api.depends('broken_date', 'depreciation_end_date')
    def _compute_premature_broken(self):
        for record in self:
            if record.broken_date and record.depreciation_end_date:
                record.is_premature_broken = record.broken_date < record.depreciation_end_date
            else:
                record.is_premature_broken = False
    
    # Add these fields to the PitcarTools class
    status_log_ids = fields.One2many('pitcar.tools.status.log', 'tool_id', 'Status Logs')
    allow_state_change = fields.Boolean('Allow State Change', compute='_compute_allow_state_change')

    # Add this compute method to the PitcarTools class
    @api.depends('state')
    def _compute_allow_state_change(self):
        for record in self:
            # Default to allowing state changes
            record.allow_state_change = True
            
            # For tools in broken or deprecated state, only admins can change state
            if record.state in ['broken', 'deprecated']:
                record.allow_state_change = self.env.user.has_group('base.group_system')

    # Modify the existing action methods to log state changes
    def action_request(self):
        old_state = self.state
        self.write({
            'state': 'requested',
            'requester_id': self.env.user.employee_id.id
        })
        self._log_state_change(old_state, 'requested')

    def action_approve(self):
        old_state = self.state
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.employee_id.id
        })
        self._log_state_change(old_state, 'approved')

    def action_purchase(self):
        if not self.purchase_date or not self.purchase_price:
            raise ValidationError('Please set purchase date and price before marking as purchased')
        old_state = self.state
        self.write({'state': 'purchased'})
        self._log_state_change(old_state, 'purchased')

    def action_in_use(self):
        old_state = self.state
        # Validate state change - prevent changing from broken/deprecated to in_use
        if old_state in ['broken', 'deprecated'] and not self.env.user.has_group('base.group_system'):
            raise ValidationError('Cannot change state from Broken or Deprecated to In Use without admin privileges')
        
        self.write({'state': 'in_use'})
        self._log_state_change(old_state, 'in_use')

    def action_broken(self):
        old_state = self.state
        self.write({
            'state': 'broken',
            'broken_date': fields.Date.today()
        })
        self._log_state_change(old_state, 'broken')

    def action_deprecate(self):
        old_state = self.state
        self.write({'state': 'deprecated'})
        self._log_state_change(old_state, 'deprecated')

    # Add a new method to log state changes
    def _log_state_change(self, old_state, new_state, notes=None):
        self.env['pitcar.tools.status.log'].sudo().create({
            'tool_id': self.id,
            'user_id': self.env.user.id,
            'old_state': old_state,
            'new_state': new_state,
            'notes': notes or ''
        })

    # Add a method to directly change state with validation
    def change_state(self, new_state, notes=None):
        old_state = self.state
        
        # Prevent invalid state transitions
        invalid_transitions = {
            'broken': ['in_use', 'purchased', 'approved', 'requested', 'draft'],
            'deprecated': ['in_use', 'purchased', 'approved', 'requested', 'draft', 'broken']
        }
        
        # Check if user is attempting an invalid transition
        if old_state in invalid_transitions and new_state in invalid_transitions[old_state] and not self.env.user.has_group('base.group_system'):
            raise ValidationError(f'Cannot change state from {old_state} to {new_state} without admin privileges')
        
        # Call appropriate action method based on the requested state
        if new_state == 'requested':
            self.action_request()
        elif new_state == 'approved':
            self.action_approve()
        elif new_state == 'purchased':
            self.action_purchase()
        elif new_state == 'in_use':
            self.action_in_use()
        elif new_state == 'broken':
            self.action_broken()
        elif new_state == 'deprecated':
            self.action_deprecate()
        else:
            # Direct state change with logging
            self.write({'state': new_state})
            self._log_state_change(old_state, new_state, notes)

# models/pitcar_tools.py
# Add this class to the existing file

class PitcarToolsStatusLog(models.Model):
    _name = 'pitcar.tools.status.log'
    _description = 'Tool Status Change Log'
    _order = 'change_date desc, id desc'
    
    tool_id = fields.Many2one('pitcar.tools', 'Tool', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', 'Changed By', required=True, default=lambda self: self.env.user)
    change_date = fields.Datetime('Change Date', required=True, default=fields.Datetime.now)
    
    old_state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('purchased', 'Purchased'),
        ('in_use', 'In Use'),
        ('broken', 'Broken'),
        ('deprecated', 'Deprecated')
    ], 'Old Status')
    
    new_state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('purchased', 'Purchased'),
        ('in_use', 'In Use'),
        ('broken', 'Broken'),
        ('deprecated', 'Deprecated')
    ], 'New Status', required=True)
    
    notes = fields.Text('Notes')