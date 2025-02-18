# models/cs_leads.py
from odoo import models, fields, api
from datetime import datetime

class CSLeads(models.Model):
    _name = 'cs.leads'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = 'Customer Service Leads'
    _order = 'create_date desc'

    name = fields.Char('Lead Reference', required=True, copy=False, readonly=True, 
                      default=lambda self: self.env['ir.sequence'].next_by_code('cs.leads'))
    
    # Basic Information
    customer_name = fields.Char('Customer Name', required=True, tracking=True)
    phone = fields.Char('Phone/WhatsApp', tracking=True)
    
    # Channel & Timing Information
    channel = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('workshop', 'Workshop')
    ], string='Channel', tracking=True)
    
    tanggal_chat = fields.Date('Tanggal Chat/Datang', tracking=True)
    jam_chat = fields.Float('Jam Chat/Datang', tracking=True)
    
    # Booking Information
    is_booking = fields.Boolean('Booking', tracking=True)
    tanggal_booking = fields.Date('Tanggal Booking', tracking=True)
    
    # Category & Revenue
    category = fields.Selection([
        ('loyal', 'Loyal'),
        ('new', 'New Customer')
    ], string='Category', tracking=True)
    
    omzet = fields.Float('Omzet', tracking=True)
    tanggal_pembayaran = fields.Date('Tanggal Pembayaran', tracking=True)
    
    # Lead Status and Follow-up
    state = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('converted', 'Converted'),
        ('lost', 'Lost')
    ], string='Status', default='new', tracking=True)

    lost_reason = fields.Selection([
        ('price', 'Price too high'),
        ('competition', 'Went to competitor'),
        ('timing', 'Bad timing'),
        ('not_interested', 'Not interested'),
        ('other', 'Other')
    ], string='Lost Reason')
    
    alasan_tidak_booking = fields.Text('Alasan Tidak Booking')
    detail_alasan = fields.Text('Detail Alasan')

    # Conversion tracking
    is_converted = fields.Boolean('Is Converted', compute='_compute_is_converted', store=True)
    conversion_date = fields.Datetime('Conversion Date', readonly=True)
    
    # Related Sale Order (existing)
    sale_order_id = fields.Many2one('sale.order', string='Related Sale Order', tracking=True)

    # Follow-up Information (existing)
    followup_ids = fields.One2many('cs.leads.followup', 'lead_id', string='Follow-ups')
    last_followup_date = fields.Datetime('Last Follow-up', compute='_compute_last_followup')
    next_followup_date = fields.Datetime('Next Follow-up')
    service_advisor_id = fields.Many2one('pitcar.service.advisor', string='Service Advisor')
    mechanic_id = fields.Many2one('pitcar.mechanic', string='Mechanic')
    source = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('website', 'Website'),
        ('other', 'Other')
    ], string='Lead Source', required=False, tracking=True, default='other')
    
    # CS and Timestamps
    cs_id = fields.Many2one('hr.employee', string='CS Staff', required=True, tracking=True)
    date = fields.Date('Lead Date', required=True, default=fields.Date.context_today)
    create_date = fields.Datetime('Created On', readonly=True)
    write_date = fields.Datetime('Last Updated', readonly=True)
    
    # Car Information
    car_brand = fields.Many2one('res.partner.car.brand', string='Car Brand')
    car_type = fields.Many2one('res.partner.car.type', string='Car Type')
    car_transmission = fields.Many2one('res.partner.car.transmission', string='Transmission')
    
    # Additional Info
    notes = fields.Text('Notes')
    lost_reason = fields.Selection([
        ('price', 'Price too high'),
        ('competition', 'Went to competitor'),
        ('timing', 'Bad timing'),
        ('not_interested', 'Not interested'),
        ('other', 'Other')
    ], string='Lost Reason')
    # Tambahan field di model cs.leads
    follow_up_status = fields.Selection([
        ('pending', 'Pending'),
        ('contacted', 'Sudah Dihubungi'),
        ('no_response', 'Tidak Respon'),
        ('interested', 'Tertarik'),
        ('not_interested', 'Tidak Tertarik')
    ], string='Status Follow Up', default='pending')
    reminder_sent = fields.Boolean('Reminder Terkirim')
    reminder_sent_date = fields.Datetime('Tanggal Kirim Reminder')
    reminder_sent_by = fields.Many2one('res.users', string='Dikirim Oleh')
    
    @api.depends('state')
    def _compute_is_converted(self):
        for lead in self:
            lead.is_converted = lead.state == 'converted'
            if lead.is_converted and not lead.conversion_date:
                lead.conversion_date = fields.Datetime.now()
                
    @api.depends('followup_ids')
    def _compute_last_followup(self):
        for lead in self:
            if lead.followup_ids:
                lead.last_followup_date = max(lead.followup_ids.mapped('create_date'))
            else:
                lead.last_followup_date = False

    def action_convert_to_sale(self):
        """Convert lead to sale order"""
        self.ensure_one()
        vals = {
            'partner_name': self.customer_name,
            'phone': self.phone,
            'service_advisor_id': self.service_advisor_id.id,
            'mechanic_id': self.mechanic_id.id,
        }
        sale_order = self.env['sale.order'].create(vals)
        self.write({
            'state': 'converted',
            'sale_order_id': sale_order.id,
            'conversion_date': fields.Datetime.now()
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

class CSLeadsFollowup(models.Model):
    _name = 'cs.leads.followup'
    _description = 'Lead Follow-up'
    _order = 'create_date desc'

    lead_id = fields.Many2one('cs.leads', string='Lead', required=True, ondelete='cascade')
    notes = fields.Text('Follow-up Notes', required=True)
    result = fields.Selection([
        ('interested', 'Interested'),
        ('thinking', 'Still Thinking'),
        ('not_interested', 'Not Interested'),
        ('no_response', 'No Response'),
        ('other', 'Other')
    ], string='Result', required=True)
    next_action = fields.Text('Next Action')
    next_action_date = fields.Datetime('Next Action Date')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    create_date = fields.Datetime('Created On', readonly=True)