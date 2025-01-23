from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import pytz

class PartPurchaseLeadtime(models.Model):
    _name = 'part.purchase.leadtime'
    _description = 'Part Purchase Leadtime'
    _order = 'departure_time desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Reference', required=True, copy=False, readonly=True, 
                      default=lambda self: _('New'))
    
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True,
                                   tracking=True)
    partner_id = fields.Many2one(related='sale_order_id.partner_id', 
                                string='Customer', store=True)
    partner_car_id = fields.Many2one(related='sale_order_id.partner_car_id',
                                    string='Car', store=True)

    # Timestamps
    departure_time = fields.Datetime('Jam Berangkat', tracking=True)
    return_time = fields.Datetime('Jam Pulang', tracking=True)
    duration = fields.Float('Durasi Beli Part (jam)', compute='_compute_duration',
                          store=True)
    duration_display = fields.Char('Durasi', compute='_compute_duration_display')

    # Purchase details  
    partman_id = fields.Many2one('hr.employee.public', string='Partman', 
                            domain=[('job_id.name', 'ilike', 'Partman')],
                            tracking=True)
    review_type = fields.Selection([
        ('margin', 'Margin'),
        ('duration_estimated', 'Durasi Estimasi'),
        ('partman_condition', 'Kondisi Partman'),
    ], string='Jenis Review', tracking=True, required=False)
    notes = fields.Text('Keterangan', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('departed', 'Berangkat'),
        ('returned', 'Kembali'),
        ('cancel', 'Dibatalkan')
    ], string='Status', default='draft', tracking=True)

    estimated_departure = fields.Datetime('Estimated Departure')
    estimated_return = fields.Datetime('Estimated Return')
    estimated_duration = fields.Float('Estimated Duration', digits=(12, 2))

    @api.model
    def get_orders_need_part(self):
        """Get sale orders that need part purchase"""
        orders = self.env['sale.order'].search([
            ('need_part_purchase', '=', 'yes'),
            ('part_purchase_status', 'in', ['pending', 'in_progress'])
        ])
        
        return [{
            'id': order.id,
            'name': order.name,
            'customer': order.partner_id.name,
            'car': {
                'brand': order.partner_car_brand.name,
                'type': order.partner_car_brand_type.name,
                'plate': order.partner_car_id.number_plate
            },
            'status': order.part_purchase_status,
            'part_purchases': [{
                'id': pp.id,
                'name': pp.name,
                'departure': self._format_datetime(pp.departure_time),
                'return': self._format_datetime(pp.return_time),
                'state': pp.state,
                'partman': pp.partman_id.name if pp.partman_id else None
            } for pp in order.part_purchase_ids]
        } for order in orders]

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('part.purchase.leadtime') or _('New')
        return super().create(vals)

    @api.depends('departure_time', 'return_time')
    def _compute_duration(self):
        for record in self:
            if record.departure_time and record.return_time:
                duration = record.return_time - record.departure_time
                record.duration = duration.total_seconds() / 3600
            else:
                record.duration = 0

    @api.depends('duration') 
    def _compute_duration_display(self):
        for record in self:
            hours = int(record.duration)
            minutes = int((record.duration - hours) * 60)
            record.duration_display = f"{hours}j {minutes}m"

    def action_depart(self):
        self.ensure_one()
        if not self.departure_time:
            self.write({
                'departure_time': fields.Datetime.now(),
                'state': 'departed'
            })

    def action_return(self):
        self.ensure_one()
        if not self.return_time:
            self.write({
                'return_time': fields.Datetime.now(),
                'state': 'returned'  
            })

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_to_draft(self):
        self.write({
            'state': 'draft',
            'departure_time': False,
            'return_time': False
        })

    @api.constrains('departure_time', 'return_time')
    def _check_times(self):
        for record in self:
            if record.departure_time and record.return_time:
                if record.return_time < record.departure_time:
                    raise ValidationError(_("Jam pulang tidak boleh lebih awal dari jam berangkat"))

    # Add to Sale Order
    def _compute_part_purchase_count(self):
        for record in self:
            record.part_purchase_count = self.env['part.purchase.leadtime'].search_count([
                ('sale_order_id', '=', record.id)
            ])

    part_purchase_count = fields.Integer(string='Part Purchases',
                                       compute='_compute_part_purchase_count')