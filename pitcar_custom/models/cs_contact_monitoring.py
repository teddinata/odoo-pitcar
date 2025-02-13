from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CSContactMonitoring(models.Model):
    _name = 'cs.contact.monitoring'
    _description = 'Customer Service Contact & Broadcast Monitoring'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char('Reference', compute='_compute_name', store=True)
    date = fields.Date('Monitoring Date', required=True, default=fields.Date.context_today, tracking=True)
    cs_id = fields.Many2one('hr.employee', 'Customer Service', 
        domain="[('job_id.name', 'ilike', 'customer service')]", required=True, tracking=True)
    controller_id = fields.Many2one('hr.employee', 'Checked By', tracking=True)
    
    # Sampling Data
    total_customers = fields.Integer('Total Customers Sampled', required=True)
    contacts_saved = fields.Integer('Contacts Saved')
    story_posted = fields.Integer('Story Posted')
    broadcast_sent = fields.Integer('Broadcast Sent')
    
    compliance_rate = fields.Float('Compliance Rate (%)', compute='_compute_metrics', store=True)
    
    monitoring_line_ids = fields.One2many('cs.contact.monitoring.line', 'monitoring_id', 'Monitoring Details')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ], default='draft', tracking=True)
    
    notes = fields.Text('Notes')

    @api.depends('total_customers', 'contacts_saved', 'story_posted', 'broadcast_sent')
    def _compute_metrics(self):
        for record in self:
            if record.total_customers:
                # Calculate compliance based on all three criteria
                contact_rate = (record.contacts_saved / record.total_customers * 100) if record.contacts_saved else 0
                story_rate = (record.story_posted / record.total_customers * 100) if record.story_posted else 0
                broadcast_rate = (record.broadcast_sent / record.total_customers * 100) if record.broadcast_sent else 0
                
                # Average of all rates
                record.compliance_rate = (contact_rate + story_rate + broadcast_rate) / 3
            else:
                record.compliance_rate = 0

    @api.depends('cs_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.cs_id and record.date:
                record.name = f"CONTACT/{record.date.strftime('%Y%m%d')}/{record.cs_id.name}"

    def action_done(self):
        self.write({
            'state': 'done',
            'controller_id': self.env.user.employee_id.id
        })

class CSContactMonitoringLine(models.Model):
    _name = 'cs.contact.monitoring.line'
    _description = 'Customer Service Contact Monitoring Line'
    
    monitoring_id = fields.Many2one('cs.contact.monitoring', 'Monitoring', required=True, ondelete='cascade')
    customer_name = fields.Char('Customer Name')
    contact_saved = fields.Boolean('Contact Saved')
    story_posted = fields.Boolean('Story Posted')
    broadcast_sent = fields.Boolean('Broadcast Sent')
    notes = fields.Text('Notes')