from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PitcarSOP(models.Model):
    _name = 'pitcar.sop'
    _description = 'SOP Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence'

    # Basic fields
    name = fields.Char('Nama SOP', required=True, tracking=True)
    code = fields.Char('Kode SOP', required=True, tracking=True)
    description = fields.Text('Deskripsi', tracking=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    # Classification fields
    department = fields.Selection([
        ('service', 'Service'),
        ('sparepart', 'Spare Part'),
        ('cs', 'Customer Service')
    ], string='Department', required=True, tracking=True)

    role = fields.Selection([
        ('sa', 'Service Advisor'),
        ('mechanic', 'Mechanic'),
        ('lead_mechanic', 'Lead Mechanic'),  # New role
        ('valet', 'Valet Parking'),
        ('part_support', 'Part Support'),
        ('cs', 'Customer Service'),
        ('lead_cs', 'Lead Customer Service'),  # New role
        ('head_workshop', 'Kepala Bengkel')  # New role
    ], string='Role', required=True, tracking=True)

    # Sampling type
    sampling_type = fields.Selection([
        ('kaizen', 'Kaizen Team'),
        ('lead', 'Leader'),
        ('both', 'Both')
    ], string='Sampling Type', default='both', required=True, tracking=True,
       help="Who can perform sampling for this SOP")

    # Backward compatibility
    is_sa = fields.Boolean(
        'Is Service Advisor', 
        compute='_compute_is_sa', 
        store=True
    )

    # Is this a leadership role?
    is_lead_role = fields.Boolean(
        'Is Leadership Role',
        compute='_compute_is_lead_role',
        store=True
    )

    @api.depends('role')
    def _compute_is_sa(self):
        """Compute is_sa based on role for backward compatibility"""
        for record in self:
            record.is_sa = record.role == 'sa'
    
    @api.depends('role')
    def _compute_is_lead_role(self):
        """Compute if this is a leadership role"""
        for record in self:
            record.is_lead_role = record.role in ['lead_mechanic', 'lead_cs', 'head_workshop']

    @api.onchange('department')
    def _onchange_department(self):
        """Update available roles based on department"""
        if self.department == 'service':
            return {'domain': {'role': [('role', 'in', ['sa', 'mechanic', 'lead_mechanic', 'head_workshop'])]}}
        elif self.department == 'cs':
            return {'domain': {'role': [('role', 'in', ['valet', 'part_support', 'cs', 'lead_cs'])]}}
        elif self.department == 'sparepart':
            return {'domain': {'role': [('role', 'in', ['part_support'])]}}

    @api.constrains('department', 'role')
    def _check_role_department_compatibility(self):
        """Ensure role is compatible with department"""
        valid_combinations = {
            'service': ['sa', 'mechanic', 'lead_mechanic', 'head_workshop'],
            'cs': ['valet', 'part_support', 'cs', 'lead_cs'],
            'sparepart': ['part_support']
        }
        for record in self:
            if record.role not in valid_combinations.get(record.department, []):
                raise ValidationError(
                    f'Role {dict(record._fields["role"].selection).get(record.role)} '
                    f'tidak valid untuk department {dict(record._fields["department"].selection).get(record.department)}'
                )

    @api.constrains('code')
    def _check_unique_code(self):
        """Ensure SOP code is unique"""
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

    # Basic fields
    name = fields.Char('Nama', compute='_compute_name', store=True)
    date = fields.Date('Tanggal', default=fields.Date.context_today, required=True, tracking=True)
    month = fields.Char('Bulan', compute='_compute_month', store=True)
    notes = fields.Text('Catatan')

    # Relations
    sale_order_id = fields.Many2one('sale.order', 'No. Invoice', required=True, tracking=True)
    sop_id = fields.Many2one('pitcar.sop', 'SOP', required=True, tracking=True)
    controller_id = fields.Many2one('hr.employee', 'Controller', tracking=True)
    
    # New fields for sampling type
    sampling_type = fields.Selection([
        ('kaizen', 'Kaizen Team'),
        ('lead', 'Leader')
    ], string='Sampling Type', default='kaizen', required=True, tracking=True,
       help="Who performed this sampling")

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

    # Role-based employee relations
    sa_id = fields.Many2many('pitcar.service.advisor', string='Service Advisor', tracking=True)
    mechanic_id = fields.Many2many('pitcar.mechanic.new', string='Mechanic', tracking=True)
    valet_id = fields.Many2many(
        'hr.employee', 
        'sop_sampling_valet_rel',
        'sampling_id',
        'employee_id',
        string='Valet Staff',
        domain="[('job_id.name', 'ilike', 'valet')]",
        tracking=True
    )
    part_support_id = fields.Many2many(
        'hr.employee',
        'sop_sampling_part_support_rel',
        'sampling_id',
        'employee_id',
        string='Part Support',
        domain="[('job_id.name', 'ilike', 'part')]",
        tracking=True
    )
    cs_id = fields.Many2many(
        'hr.employee',
        'sop_sampling_cs_rel',
        'sampling_id',
        'employee_id', 
        string='Customer Service',
        domain="[('job_id.name', 'ilike', 'customer service')]",
        tracking=True
    )
    
    # New fields for leadership roles
    lead_mechanic_id = fields.Many2many(
        'hr.employee',
        'sop_sampling_lead_mechanic_rel',
        'sampling_id',
        'employee_id',
        string='Lead Mechanic',
        domain="[('job_id.name', 'ilike', 'lead mechanic')]",
        tracking=True
    )
    lead_cs_id = fields.Many2many(
        'hr.employee',
        'sop_sampling_lead_cs_rel',
        'sampling_id',
        'employee_id',
        string='Lead Customer Service',
        domain="[('job_id.name', 'ilike', 'lead customer service')]",
        tracking=True
    )
    head_workshop_id = fields.Many2many(
        'hr.employee',
        'sop_sampling_head_workshop_rel',
        'sampling_id',
        'employee_id',
        string='Kepala Bengkel',
        domain="[('job_id.name', 'ilike', 'kepala bengkel')]",
        tracking=True
    )

    # Timestamps
    create_date = fields.Datetime('Created Date', readonly=True)
    write_date = fields.Datetime('Last Updated', readonly=True)
    validation_date = fields.Datetime('Validation Date', readonly=True, tracking=True)

    @api.depends('date')
    def _compute_month(self):
        """Compute month from date for grouping"""
        for record in self:
            if record.date:
                record.month = record.date.strftime('%Y-%m')

    @api.depends('sop_id', 'sale_order_id', 'date', 'sampling_type')
    def _compute_name(self):
        """Generate sampling name with role and sampling type information"""
        for record in self:
            if record.sop_id and record.sale_order_id and record.date:
                role_name = dict(record.sop_id._fields['role'].selection).get(
                    record.sop_id.role, ''
                )
                sampling_type = dict(record._fields['sampling_type'].selection).get(
                    record.sampling_type, ''
                )
                record.name = (
                    f"{record.sop_id.name} - {record.sale_order_id.name} "
                    f"({role_name}) - {sampling_type} - {record.date.strftime('%Y-%m-%d')}"
                )

    @api.onchange('sop_id')
    def _onchange_sop(self):
        """Set appropriate sampling_type based on SOP configuration"""
        if self.sop_id:
            # If SOP is specific to one sampling type, set it automatically
            if self.sop_id.sampling_type == 'kaizen':
                self.sampling_type = 'kaizen'
            elif self.sop_id.sampling_type == 'lead':
                self.sampling_type = 'lead'
            # If 'both', keep current or default to kaizen

    @api.onchange('sop_id', 'sale_order_id')
    def _onchange_sop_sale_order(self):
        """Handle employee assignment based on role"""
        if not self.sop_id or not self.sale_order_id:
            return

        # Reset all employee fields
        self.sa_id = False
        self.mechanic_id = False
        self.valet_id = False
        self.part_support_id = False
        self.cs_id = False
        self.lead_mechanic_id = False
        self.lead_cs_id = False
        self.head_workshop_id = False

        # Auto-assign for SA and Mechanic
        if self.sop_id.role == 'sa' and self.sale_order_id.service_advisor_id:
            self.sa_id = self.sale_order_id.service_advisor_id
        elif self.sop_id.role == 'mechanic' and self.sale_order_id.car_mechanic_id_new:
            self.mechanic_id = self.sale_order_id.car_mechanic_id_new

    @api.constrains('sop_id', 'sa_id', 'mechanic_id', 'valet_id', 'part_support_id', 'cs_id', 
                   'lead_mechanic_id', 'lead_cs_id', 'head_workshop_id', 'sampling_type')
    def _check_employee_assignment(self):
        """Validate employee assignment based on role"""
        for record in self:
            if not record.sop_id:
                continue

            role = record.sop_id.role
            
            # Verify the SOP sampling type is compatible
            if record.sop_id.sampling_type not in ['both', record.sampling_type]:
                raise ValidationError(
                    f'SOP {record.sop_id.name} cannot be sampled by {record.sampling_type}, '
                    f'only by {record.sop_id.sampling_type}'
                )

            # Check specific role requirements
            if role == 'sa' and not record.sa_id:
                raise ValidationError('Service Advisor harus diisi untuk SOP SA')
            elif role == 'mechanic' and not record.mechanic_id:
                raise ValidationError('Mekanik harus diisi untuk SOP Mekanik')
            elif role == 'valet' and not record.valet_id:
                raise ValidationError('Valet staff harus diisi untuk SOP Valet')
            elif role == 'part_support' and not record.part_support_id:
                raise ValidationError('Part Support staff harus diisi untuk SOP Part Support')
            elif role == 'cs' and not record.cs_id:
                raise ValidationError('Customer Service harus diisi untuk SOP CS')
            elif role == 'lead_mechanic' and not record.lead_mechanic_id:
                raise ValidationError('Lead Mechanic harus diisi untuk SOP Lead Mechanic')
            elif role == 'lead_cs' and not record.lead_cs_id:
                raise ValidationError('Lead Customer Service harus diisi untuk SOP Lead CS')
            elif role == 'head_workshop' and not record.head_workshop_id:
                raise ValidationError('Kepala Bengkel harus diisi untuk SOP Kepala Bengkel')