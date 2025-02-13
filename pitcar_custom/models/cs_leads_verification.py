from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CSLeadsVerification(models.Model):
    _name = 'cs.leads.verification'
    _description = 'Customer Service Leads Verification'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char('Reference', compute='_compute_name', store=True)
    date = fields.Date('Verification Date', required=True, default=fields.Date.context_today, tracking=True)
    cs_id = fields.Many2one('hr.employee', 'Customer Service', 
        domain="[('job_id.name', 'ilike', 'customer service')]", required=True, tracking=True)
    controller_id = fields.Many2one('hr.employee', 'Checked By', tracking=True)
    
    # Perhitungan Leads - semua field optional
    system_leads_count = fields.Integer('System Leads Count', 
        help="Jumlah leads di sistem")
    actual_leads_count = fields.Integer('Actual Leads Count',
        help="Jumlah leads di rekap manual")
    missing_leads_count = fields.Integer('Missing Leads Count', compute='_compute_metrics')
    accuracy_rate = fields.Float('Accuracy Rate (%)', compute='_compute_metrics', store=True)
    
    # Detail Kesalahan
    verification_line_ids = fields.One2many('cs.leads.verification.line', 'verification_id', 'Verification Details')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ], default='draft', tracking=True)
    
    notes = fields.Text('Notes')

    @api.depends('system_leads_count', 'actual_leads_count')
    def _compute_metrics(self):
        for record in self:
            if record.system_leads_count and record.actual_leads_count:
                record.missing_leads_count = abs(record.system_leads_count - record.actual_leads_count)
                total = max(record.system_leads_count, record.actual_leads_count)
                record.accuracy_rate = ((total - record.missing_leads_count) / total * 100) if total else 0
            else:
                record.missing_leads_count = 0
                record.accuracy_rate = 0

    @api.depends('cs_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.cs_id and record.date:
                record.name = f"LEADS/{record.date.strftime('%Y%m%d')}/{record.cs_id.name}"
                
    def action_done(self):
        self.write({
            'state': 'done',
            'controller_id': self.env.user.employee_id.id
        })

class CSLeadsVerificationLine(models.Model):
    _name = 'cs.leads.verification.line'
    _description = 'Customer Service Leads Verification Line'
    
    verification_id = fields.Many2one('cs.leads.verification', 'Verification', required=True, ondelete='cascade')
    lead_source = fields.Selection([
        ('system', 'System'),
        ('manual', 'Manual Recap')
    ])
    customer_name = fields.Char('Customer Name')
    order_reference = fields.Char('Order Reference')
    problem_type = fields.Selection([
        ('missing_system', 'Missing in System'),
        ('missing_recap', 'Missing in Recap'),
        ('wrong_details', 'Wrong Details')
    ])
    notes = fields.Text('Notes')