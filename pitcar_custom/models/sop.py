# models/pitcar_sop.py
# =====================================
# COMPLETE SOP MODEL WITH SOFT MIGRATION
# =====================================

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
    notes = fields.Text('Catatan', tracking=True)
    
    # ===== SOFT MIGRATION FIELDS =====
    # OLD DEPARTMENT - Keep for backward compatibility
    department_old = fields.Selection([
        ('service', 'Service'),
        ('sparepart', 'Spare Part'),
        ('cs', 'Customer Service')
    ], string='Department (Legacy)', tracking=True, 
       help="Legacy department field - will be deprecated")
    
    # NEW DEPARTMENT - The future structure
    department_new = fields.Selection([
        ('mekanik', 'Mekanik'),
        ('support', 'Support')
    ], string='Department (New)', tracking=True,
       help="New department structure")
    
    # COMPUTED DEPARTMENT - Active field that handles both
    department = fields.Selection([
        ('service', 'Service'),
        ('sparepart', 'Spare Part'),
        ('cs', 'Customer Service'),
        ('mekanik', 'Mekanik'),
        ('support', 'Support')
    ], string='Department', required=True, tracking=True,
       compute='_compute_department', store=True, readonly=False)
    
    # Migration control flags
    is_migrated = fields.Boolean('Is Migrated', default=False, 
                                help="True if record has been migrated to new structure")
    migration_date = fields.Datetime('Migration Date', readonly=True)
    
    # ===== ROLE FIELD (Updated for new structure) =====
    role = fields.Selection([
        ('sa', 'Service Advisor'),
        ('mechanic', 'Mechanic'),
        ('lead_mechanic', 'Lead Mechanic'),
        ('valet', 'Valet Parking'),
        ('part_support', 'Part Support'),
        ('cs', 'Customer Service'),
        ('lead_cs', 'Lead Customer Service'),
        ('head_workshop', 'Kepala Bengkel')
    ], string='Role', required=True, tracking=True)

    # Other existing fields...
    activity_type = fields.Selection([
        ('pembuatan', 'Pembuatan'),
        ('revisi', 'Revisi'),
        ('update', 'Update')
    ], string='Aktivitas', default='pembuatan', tracking=True)
    
    date_start = fields.Date('Tanggal Mulai', tracking=True)
    date_end = fields.Date('Tanggal Selesai', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    review_state = fields.Selection([
        ('waiting', 'Waiting for Review'),
        ('in_review', 'In Review'),
        ('done', 'Done'),
        ('rejected', 'Rejected')
    ], string='Status Review', default='waiting', tracking=True)
    
    revision_state = fields.Selection([
        ('no_revision', 'No Revision'),
        ('revising', 'In Revision'),
        ('done', 'Done')
    ], string='Status Revisi', default='no_revision', tracking=True)
    
    # Document and socialization fields
    document_url = fields.Char('Dokumen URL', tracking=True, 
                               help="Link to Google Drive or other storage with SOP document")
    
    socialization_state = fields.Selection([
        ('not_started', 'Belum Dimulai'),
        ('scheduled', 'Dijadwalkan'),
        ('in_progress', 'Sedang Berlangsung'),
        ('done', 'Selesai')
    ], string='Status Sosialisasi', default='not_started', tracking=True)
    
    socialization_date = fields.Date('Tanggal Sosialisasi', tracking=True)
    socialization_target_date = fields.Date('Target Waktu Sosialisasi', tracking=True, 
                                           help="Tanggal target kapan SOP harus sudah disosialisasikan")
    
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

    # Computed fields for statistics
    days_to_complete = fields.Integer('Hari Penyelesaian', compute='_compute_days_to_complete', store=True)
    socialization_status = fields.Selection([
        ('on_time', 'Tepat Waktu'),
        ('delayed', 'Terlambat'),
        ('not_due', 'Belum Jatuh Tempo')
    ], string='Status Target Sosialisasi', compute='_compute_socialization_status', store=True)
    
    # ===== COMPUTED DEPARTMENT LOGIC =====
    @api.depends('department_new', 'department_old', 'is_migrated')
    def _compute_department(self):
        """Compute department based on migration status"""
        for record in self:
            if record.is_migrated and record.department_new:
                # Use new department if migrated
                record.department = record.department_new
            elif record.department_old:
                # Use old department if not migrated
                record.department = record.department_old
            else:
                # Default fallback
                record.department = record.department_old or 'support'

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

    @api.depends('date_start', 'date_end', 'state')
    def _compute_days_to_complete(self):
        """Compute days taken to complete the SOP"""
        for record in self:
            if record.date_start and record.date_end and record.state == 'done':
                delta = record.date_end - record.date_start
                record.days_to_complete = delta.days
            else:
                record.days_to_complete = 0
    
    @api.depends('socialization_target_date', 'socialization_date', 'socialization_state')
    def _compute_socialization_status(self):
        """Compute socialization status based on target date and actual date"""
        today = fields.Date.today()
        for record in self:
            if record.socialization_state == 'done' and record.socialization_date and record.socialization_target_date:
                if record.socialization_date <= record.socialization_target_date:
                    record.socialization_status = 'on_time'
                else:
                    record.socialization_status = 'delayed'
            elif record.socialization_target_date:
                if today > record.socialization_target_date and record.socialization_state != 'done':
                    record.socialization_status = 'delayed'
                else:
                    record.socialization_status = 'not_due'
            else:
                record.socialization_status = 'not_due'
    
    # ===== MIGRATION METHODS =====
    def migrate_to_new_structure(self):
        """Migrate individual record to new department structure"""
        for record in self:
            if record.is_migrated:
                continue
                
            # Determine new department based on role (SA masuk support)
            if record.role in ['mechanic', 'lead_mechanic', 'head_workshop']:
                new_dept = 'mekanik'
            else:  # SA, valet, part_support, cs, lead_cs
                new_dept = 'support'
            
            # Update fields
            record.write({
                'department_new': new_dept,
                'is_migrated': True,
                'migration_date': fields.Datetime.now()
            })
            
            # Log migration
            record.message_post(
                body=f"Migrated from {record.department_old} to {new_dept}",
                subject="Department Migration"
            )
    
    def bulk_migrate_department(self):
        """Bulk migrate all records"""
        unmigrated = self.search([('is_migrated', '=', False)])
        
        for record in unmigrated:
            record.migrate_to_new_structure()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Successfully migrated {len(unmigrated)} records',
                'type': 'success'
            }
        }
    
    def rollback_migration(self):
        """Rollback migration for this record"""
        for record in self:
            if record.is_migrated:
                record.write({
                    'department_new': False,
                    'is_migrated': False,
                    'migration_date': False
                })
                
                record.message_post(
                    body=f"Migration rolled back to {record.department_old}",
                    subject="Migration Rollback"
                )
    
    def get_migration_status(self):
        """Get migration status summary"""
        total_records = self.search_count([])
        migrated_records = self.search_count([('is_migrated', '=', True)])
        
        return {
            'total': total_records,
            'migrated': migrated_records,
            'pending': total_records - migrated_records,
            'progress': (migrated_records / total_records * 100) if total_records > 0 else 0
        }
    
    # ===== UPDATED CONSTRAINTS =====
    def _get_valid_role_combinations(self):
        """Get valid role combinations for both old and new structure"""
        return {
            # Old structure
            'service': ['sa', 'mechanic', 'lead_mechanic', 'head_workshop'],
            'cs': ['valet', 'part_support', 'cs', 'lead_cs'],
            'sparepart': ['part_support'],
            
            # New structure
            'mekanik': ['mechanic', 'lead_mechanic', 'head_workshop'],
            'support': ['sa', 'valet', 'part_support', 'cs', 'lead_cs']
        }
    
    @api.constrains('department', 'role')
    def _check_role_department_compatibility(self):
        """Ensure role is compatible with department (both old and new)"""
        valid_combinations = self._get_valid_role_combinations()
        
        for record in self:
            current_dept = record.department
            valid_roles = valid_combinations.get(current_dept, [])
            
            if record.role not in valid_roles:
                dept_label = dict(record._fields['department'].selection).get(current_dept)
                role_label = dict(record._fields['role'].selection).get(record.role)
                
                raise ValidationError(
                    f'Role {role_label} tidak valid untuk department {dept_label}.\n'
                    f'Valid roles: {[dict(record._fields["role"].selection).get(r) for r in valid_roles]}'
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

    @api.onchange('department')
    def _onchange_department(self):
        """Update available roles based on department"""
        if self.department:
            valid_combinations = self._get_valid_role_combinations()
            valid_roles = valid_combinations.get(self.department, [])
            
            return {
                'domain': {
                    'role': [('role', 'in', valid_roles)]
                }
            }

    # ===== STATE CHANGE METHODS =====
    def action_start_sop(self):
        """Start SOP development process"""
        self.write({
            'state': 'in_progress',
            'date_start': fields.Date.today() if not self.date_start else self.date_start
        })
    
    def action_complete_sop(self):
        """Mark SOP as completed"""
        self.write({
            'state': 'done',
            'date_end': fields.Date.today() if not self.date_end else self.date_end
        })
    
    def action_start_review(self):
        """Start the review process"""
        self.write({
            'review_state': 'in_review'
        })
    
    def action_approve_review(self):
        """Approve the SOP after review"""
        self.write({
            'review_state': 'done'
        })
    
    def action_reject_review(self):
        """Reject the SOP, require revisions"""
        self.write({
            'review_state': 'rejected',
            'revision_state': 'revising'
        })
    
    def action_complete_revision(self):
        """Mark revisions as completed"""
        self.write({
            'revision_state': 'done'
        })
    
    def action_schedule_socialization(self):
        """Schedule socialization for the SOP"""
        return {
            'name': 'Schedule Socialization',
            'type': 'ir.actions.act_window',
            'res_model': 'sop.socialization.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sop_id': self.id}
        }
    
    def action_complete_socialization(self):
        """Mark socialization as completed"""
        self.write({
            'socialization_state': 'done'
        })


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


# =====================================
# MIGRATION WIZARD
# =====================================

class SOPMigrationWizard(models.TransientModel):
    _name = 'sop.migration.wizard'
    _description = 'SOP Department Migration Wizard'
    
    migration_type = fields.Selection([
        ('preview', 'Preview Migration'),
        ('execute', 'Execute Migration'),
        ('rollback', 'Rollback Migration')
    ], string='Migration Type', required=True, default='preview')
    
    department_filter = fields.Selection([
        ('all', 'All Departments'),
        ('service', 'Service Only'),
        ('sparepart', 'Sparepart Only'),
        ('cs', 'Customer Service Only')
    ], string='Department Filter', default='all')
    
    # Preview results
    preview_results = fields.Text('Preview Results', readonly=True)
    
    def action_preview_migration(self):
        """Preview what will be migrated"""
        domain = [('is_migrated', '=', False)]
        
        if self.department_filter != 'all':
            domain.append(('department_old', '=', self.department_filter))
        
        records = self.env['pitcar.sop'].search(domain)
        
        preview = []
        migration_summary = {'mekanik': 0, 'support': 0}
        
        for record in records:
            if record.role in ['mechanic', 'lead_mechanic', 'head_workshop']:
                new_dept = 'mekanik'
            else:
                new_dept = 'support'
            
            preview.append(f"SOP: {record.code} | {record.name} | {record.department_old} → {new_dept}")
            migration_summary[new_dept] += 1
        
        result_text = f"Migration Preview:\n"
        result_text += f"Total records to migrate: {len(records)}\n"
        result_text += f"Will move to Mekanik: {migration_summary['mekanik']}\n"
        result_text += f"Will move to Support: {migration_summary['support']}\n\n"
        result_text += "Details:\n" + "\n".join(preview)
        
        self.preview_results = result_text
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sop.migration.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }
    
    def action_execute_migration(self):
        """Execute the migration"""
        domain = [('is_migrated', '=', False)]
        
        if self.department_filter != 'all':
            domain.append(('department_old', '=', self.department_filter))
        
        records = self.env['pitcar.sop'].search(domain)
        
        for record in records:
            record.migrate_to_new_structure()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Successfully migrated {len(records)} SOP records',
                'type': 'success'
            }
        }
    
    def action_rollback_migration(self):
        """Rollback migration"""
        domain = [('is_migrated', '=', True)]
        
        if self.department_filter != 'all':
            domain.append(('department_old', '=', self.department_filter))
        
        records = self.env['pitcar.sop'].search(domain)
        
        for record in records:
            record.rollback_migration()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Successfully rolled back {len(records)} SOP records',
                'type': 'success'
            }
        }