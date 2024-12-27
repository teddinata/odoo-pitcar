from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PitcarSOP(models.Model):
    _name = 'pitcar.sop'
    _description = 'SOP Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence'

    name = fields.Char('Nama SOP', required=True, tracking=True)
    sequence = fields.Integer('Sequence', default=10)
    code = fields.Char('Kode SOP', required=True, tracking=True)
    description = fields.Text('Deskripsi', tracking=True)
    department = fields.Selection([
        ('service', 'Service'),
        ('sparepart', 'Spare Part'),
        ('cs', 'Customer Service')
    ], string='Department', required=True, tracking=True)
    is_sa = fields.Boolean('Service Advisor SOP', help="Tandai jika SOP ini untuk Service Advisor")
    active = fields.Boolean('Active', default=True)

    @api.constrains('code')
    def _check_unique_code(self):
        for record in self:
            existing = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError('Kode SOP harus unik!')

class PitcarSOPSampling(models.Model):
    _name = 'pitcar.sop.sampling'
    _description = 'SOP Sampling'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Nama', compute='_compute_name', store=True)
    date = fields.Date('Tanggal', default=fields.Date.context_today, required=True, tracking=True)
    month = fields.Char('Bulan', compute='_compute_month', store=True)
    
    # Relations
    sale_order_id = fields.Many2one('sale.order', 'No. Invoice', required=True, tracking=True)
    sop_id = fields.Many2one('pitcar.sop', 'SOP', required=True, tracking=True)
    
    # Employee relations based on role
    sa_id = fields.Many2many('pitcar.service.advisor', string='Service Advisor', tracking=True)
    mechanic_id = fields.Many2many('pitcar.mechanic.new', string='Mechanic', tracking=True)
    controller_id = fields.Many2one('hr.employee', 'Controller', tracking=True)
    
    # Status fields
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done')
    ], default='draft', tracking=True)
    
    result = fields.Selection([
        ('pass', 'Lulus'),
        ('fail', 'Tidak Lulus')
    ], tracking=True)
    
    notes = fields.Text('Catatan')
    
    @api.depends('date')
    def _compute_month(self):
        for record in self:
            if record.date:
                record.month = record.date.strftime('%Y-%m')
    
    @api.depends('sop_id', 'sale_order_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.sop_id and record.sale_order_id and record.date:
                employee_type = "SA" if record.sop_id.is_sa else "Mekanik"
                record.name = f"{record.sop_id.name} - {record.sale_order_id.name} ({employee_type}) - {record.date.strftime('%Y-%m-%d')}"

    @api.onchange('sop_id', 'sale_order_id')
    def _onchange_sop_sale_order(self):
        """Populate SA/Mechanic based on SOP type and sale order"""
        if self.sop_id and self.sale_order_id:
            if self.sop_id.is_sa:
                self.sa_id = self.sale_order_id.service_advisor_id
                self.mechanic_id = False
            else:
                self.mechanic_id = self.sale_order_id.car_mechanic_id_new
                self.sa_id = False

    @api.constrains('sop_id', 'sa_id', 'mechanic_id')
    def _check_employee_compatibility(self):
        for record in self:
            if record.sop_id.is_sa and not record.sa_id:
                raise ValidationError('Service Advisor harus diisi untuk SOP SA')
            if not record.sop_id.is_sa and not record.mechanic_id:
                raise ValidationError('Mekanik harus diisi untuk SOP Mekanik')
