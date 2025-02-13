from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CSChatSampling(models.Model):
    _name = 'cs.chat.sampling'
    _description = 'Customer Service Chat Sampling'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char('Reference', compute='_compute_name', store=True)
    date = fields.Date('Sampling Date', required=True, default=fields.Date.context_today, tracking=True)
    cs_id = fields.Many2one('hr.employee', 'Customer Service', 
        domain="[('job_id.name', 'ilike', 'customer service')]", required=True, tracking=True)
    controller_id = fields.Many2one('hr.employee', 'Checked By', tracking=True)
    
    total_chats = fields.Integer('Total Chats', required=True)
    responded_ontime = fields.Integer('Responded On Time')
    response_rate = fields.Float('Response Rate (%)', compute='_compute_rate', store=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ], default='draft', tracking=True)
    
    notes = fields.Text('Notes')

    @api.depends('cs_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.cs_id and record.date:
                record.name = f"CHAT/{record.date.strftime('%Y%m%d')}/{record.cs_id.name}"
    
    @api.depends('total_chats', 'responded_ontime')
    def _compute_rate(self):
        for record in self:
            record.response_rate = (record.responded_ontime / record.total_chats * 100) if record.total_chats else 0
    
    @api.constrains('total_chats', 'responded_ontime')
    def _check_values(self):
        for record in self:
            if record.responded_ontime > record.total_chats:
                raise ValidationError('Responded chats cannot be greater than total chats')
    
    def action_done(self):
        self.write({
            'state': 'done',
            'controller_id': self.env.user.employee_id.id
        })