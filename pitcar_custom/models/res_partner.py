from odoo import models, fields, api, _
from datetime import datetime, timedelta
from random import randint, choices
import string  # Juga perlu import string untuk karakter yang akan digunakan
from odoo.exceptions import ValidationError, AccessError, UserError
import logging
_logger = logging.getLogger(__name__)

class CustomerSumberInfo(models.Model):
    _name = 'customer.sumber.info'
    _description = 'Customer Sumber Info'
    _rec_name = 'partner_id'
    
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade', index=True)
    sumber = fields.Selection([
        ('loyal', 'Loyal'),
        ('fb_ads', 'FB Ads'),
        ('referral', 'Referral'),
        ('all_b2b', 'All B2B'),
        ('ig_ads', 'IG Ads'),
        ('google_maps', 'Google Maps'),
        ('tiktok_ads', 'Tiktok Ads'),
        ('ig_organic', 'IG Organic'),
        ('beli_part', 'Beli Part'),
        ('web_paid_ads', 'Web - Paid Ads'),
        ('web_organic', 'Web - Organic'),
        ('workshop', 'Workshop'),
        ('relation', 'Relation'),
        ('youtube', 'Youtube'),
        ('tidak_dapat_info', 'Tidak Dapat Info'),
    ], string="Sumber Info", required=True)
    tanggal_daftar = fields.Date(string='Tanggal Pendaftaran', default=fields.Date.context_today)
    notes = fields.Text(string='Catatan')
    
    _sql_constraints = [
        ('partner_unique', 'unique(partner_id)', 'Customer sudah memiliki sumber info!')
    ]



class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    partner_count = fields.Integer(string="Partner Count", compute='_compute_partner_count')

    @api.depends('partner_ids')
    def _compute_partner_count(self):
        for category in self:
            category.partner_count = len(category.partner_ids)


class ResPartnerSource(models.Model):
    _name = 'res.partner.source'
    _description = 'Source of partner'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

class ResPartner(models.Model):
    _inherit = ['res.partner']

    gender = fields.Selection(
        [('male', 'Male'), 
         ('female', 'Female'),
        ], string="Gender"
    )
    source = fields.Many2one('res.partner.source', string="Source")
    dob = fields.Date(string="Date of Birth")
    car_ids = fields.One2many('res.partner.car', 'partner_id', string="Cars")
    category_id = fields.Many2many('res.partner.category', column1='partner_id',
                                    column2='category_id', string='Tags', required=True)
    phone = fields.Char(unaccent=False, required=True)

    # Tambahkan relasi one2one ke model baru
    sumber_info_id = fields.One2many('customer.sumber.info', 'partner_id', string='Sumber Info')
    
    # Field untuk antarmuka pengguna (UI)
    sumber_info_ui = fields.Selection([
        ('loyal', 'Loyal'),
        ('fb_ads', 'FB Ads'),
        ('referral', 'Referral'),
        ('all_b2b', 'All B2B'),
        ('ig_ads', 'IG Ads'),
        ('google_maps', 'Google Maps'),
        ('tiktok_ads', 'Tiktok Ads'),
        ('ig_organic', 'IG Organic'),
        ('beli_part', 'Beli Part'),
        ('web_paid_ads', 'Web - Paid Ads'),
        ('web_organic', 'Web - Organic'),
        ('workshop', 'Workshop'),
        ('relation', 'Relation'),
        ('youtube', 'Youtube'),
        ('tidak_dapat_info', 'Tidak Dapat Info'),
    ], string="Sumber Info", compute='_compute_sumber_info_ui', inverse='_inverse_sumber_info_ui', store=False)
    
    @api.depends('sumber_info_id.sumber')
    def _compute_sumber_info_ui(self):
        for partner in self:
            if partner.sumber_info_id:
                partner.sumber_info_ui = partner.sumber_info_id[0].sumber
            else:
                partner.sumber_info_ui = False
    
    def _inverse_sumber_info_ui(self):
        for partner in self:
            if partner.sumber_info_ui:
                # Cek apakah sudah ada record
                if partner.sumber_info_id:
                    # Update record yang sudah ada
                    partner.sumber_info_id[0].sumber = partner.sumber_info_ui
                else:
                    # Buat record baru
                    self.env['customer.sumber.info'].create({
                        'partner_id': partner.id,
                        'sumber': partner.sumber_info_ui,
                    })
            elif partner.sumber_info_id:
                # Hapus record jika field di-clear
                partner.sumber_info_id.unlink()



    # def phone_get_sanitized_number(self, number_fname='phone', country_fname='country_id', force_format='E164'):
    #     """Override to handle context no_phone_validation"""
    #     if self.env.context.get('no_phone_validation'):
    #         return {self[number_fname]: {'sanitized': self[number_fname], 'code': ''}}
    #     return super().phone_get_sanitized_number(number_fname, country_fname, force_format)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle phone validation issues"""
        # Check if phone validation should be skipped
        if self.env.context.get('phone_validation_skip'):
            # Create records without phone validation
            self = self.with_context(mail_notrack=True)
            for vals in vals_list:
                if 'phone' in vals:
                    # Keep the phone as is without validation
                    vals['phone_sanitized'] = vals['phone']
        
        return super(ResPartner, self).create(vals_list)
    
    def _phone_format(self, number, country=None, company=None, force_format=None):
        """Override to handle phone validation skip and force_format parameter"""
        if self.env.context.get('phone_validation_skip'):
            return number
        
        # Panggil super method tanpa force_format karena versi Odoo Anda tidak mendukungnya
        return super(ResPartner, self)._phone_format(number, country, company)
    
    @api.onchange('phone')
    def _onchange_phone_validation(self):
        """Override phone validation onchange to handle formatting issues"""
        if self.phone and not self.env.context.get('phone_validation_skip'):
            try:
                # Coba dengan format yang lebih aman
                self.phone = self._phone_format(self.phone)
            except Exception as e:
                # Log error tapi jangan crash UI
                _logger.error("Phone validation error: %s", str(e))

    def get_customer_level_summary(self):
        """
        Safe method to get customer level summary
        """
        self.ensure_one()
        
        try:
            orders = self.env['sale.order'].search([
                ('partner_id', '=', self.id),
                ('state', 'in', ('sale', 'done'))
            ], order='create_date')
            
            if not orders:
                return {
                    'level': 'new',
                    'total_orders': 0,
                    'total_revenue': 0,
                    'sequences': [],
                    'status': 'success'
                }
            
            return {
                'level': orders[-1].customer_level if hasattr(orders[-1], 'customer_level') else 'new',
                'total_orders': len(orders),
                'total_revenue': sum(orders.mapped('amount_total')),
                'sequences': orders.mapped('customer_transaction_sequence'),
                'first_order_date': orders[0].create_date,
                'last_order_date': orders[-1].create_date,
                'status': 'success'
            }
            
        except Exception as e:
            _logger.error(f"Error getting customer summary for {self.name}: {e}")
            return {
                'level': 'new',
                'total_orders': 0,
                'total_revenue': 0,
                'sequences': [],
                'status': 'error',
                'error_message': str(e)
            }

    def action_view_customer_orders_sequence(self):
        """
        Safe method to view customer orders with transaction sequence
        """
        self.ensure_one()
        
        return {
            'name': f'Transaction History - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'search_default_group_transaction_sequence': 1,
                'default_partner_id': self.id
            },
            'help': f"""
                <p class="o_view_nocontent_smiling_face">
                    Customer Transaction History
                </p>
                <p>
                    Transaction sequence for: {self.name}<br/>
                    View all orders with their transaction sequence numbers.
                </p>
            """
        }

class PitcarMechanic(models.Model):
    _name = 'pitcar.mechanic'
    _description = 'Mechanic'
    _order = 'name'

    name = fields.Char(string="Name", required=True)
    
class PitcarMechanicNew(models.Model):
    _name = 'pitcar.mechanic.new'
    _description = 'Mechanic'
    _order = 'name'
    
    def _get_default_color(self):
        return randint(1, 11)
    
    active = fields.Boolean(string='Active', default=True)

    name = fields.Char(string="Name", required=True, tracking=True)
    color = fields.Integer('Color', default=_get_default_color)
    position_id = fields.Many2one('pitcar.position', string="Position", required=True)
    position_code = fields.Selection(
        related='position_id.code',
        string='Position Code',
        store=True
    )
    leader_id = fields.Many2one(
        'pitcar.mechanic.new',
        string='Team Leader',
        domain="[('position_code', '=', 'leader')]"
    )
    team_member_ids = fields.One2many(
        'pitcar.mechanic.new',
        'leader_id',
        string='Team Members'
    )
    monthly_target = fields.Float(
        string='Monthly Target',
        compute='_compute_monthly_target',
        store=True
    )
    current_revenue = fields.Float(
        string='Current Revenue',
        compute='_compute_revenue_metrics'
    )
    target_achievement = fields.Float(
        string='Target Achievement (%)',
        compute='_compute_revenue_metrics'
    )

    # New fields for HR integration
    employee_id = fields.Many2one('hr.employee', string='Employee Reference', required=False)
    attendance_ids = fields.One2many(
        'hr.attendance', 
        related='employee_id.attendance_ids',
        string='Attendance Records'
    )
    attendance_state = fields.Selection(
        related='employee_id.attendance_state',
        string='Attendance Status'
    )
    current_attendance_id = fields.Many2one(
        'hr.attendance',
        related='employee_id.last_attendance_id'
    )
    hours_today = fields.Float(
        compute='_compute_hours_today',
        string='Working Hours Today'
    )
    total_attendance_hours = fields.Float(
        compute='_compute_total_hours',
        string='Total Attendance Hours'
    )
    work_hours_target = fields.Float(
        string='Target Working Hours',
        default=8.0,
        help="Target working hours per day for attendance achievement calculation"
    )
    attendance_achievement = fields.Float(
        string='Attendance Achievement (%)',
        compute='_compute_attendance_achievement'
    )
    work_location_ids = fields.Many2many(
        'pitcar.work.location',
        string='Allowed Work Locations'
    )
    user_id = fields.Many2one('res.users', string='Related User', ondelete='restrict')
    temp_password = fields.Char('Temporary Password', readonly=True)

     # Field baru untuk utilization
    labor_utilization = fields.Float(
        string='Labor Utilization (%)', 
        compute='_compute_labor_utilization',
        store=True,
        help='Persentase waktu produktif dari total waktu kehadiran'
    )
    productive_hours = fields.Float(
        string='Productive Hours',
        compute='_compute_labor_utilization'
    )
    attendance_hours = fields.Float(
        string='Attendance Hours',
        compute='_compute_labor_utilization'
    )

    @api.depends('employee_id.attendance_ids')
    def _compute_labor_utilization(self):
        for mechanic in self:
            # Get attendance hours
            attendances = mechanic.employee_id.attendance_ids
            total_attendance_hours = sum(att.worked_hours for att in attendances if att.check_out)

            # Get productive hours from sale orders
            domain = [
                ('car_mechanic_id_new', 'in', [mechanic.id]),
                ('state', '=', 'sale'),
                ('controller_mulai_servis', '!=', False),
                ('controller_selesai', '!=', False)
            ]
            orders = self.env['sale.order'].search(domain)
            
            total_productive_hours = 0
            for order in orders:
                work_duration = (order.controller_selesai - order.controller_mulai_servis).total_seconds() / 3600
                mechanic_count = len(order.car_mechanic_id_new)
                total_productive_hours += work_duration / mechanic_count

            mechanic.productive_hours = total_productive_hours
            mechanic.attendance_hours = total_attendance_hours
            mechanic.labor_utilization = (total_productive_hours / total_attendance_hours * 100) if total_attendance_hours > 0 else 0

    @api.depends('position_id', 'team_member_ids')
    def _compute_monthly_target(self):
        for mechanic in self:
            if mechanic.position_code == 'leader':
                mechanic.monthly_target = len(mechanic.team_member_ids) * 64000000
            else:
                mechanic.monthly_target = 64000000

    @api.depends('monthly_target')
    def _compute_revenue_metrics(self):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        
        for mechanic in self:
            # Calculate revenue
            if mechanic.position_code == 'leader':
                domain = [
                    ('car_mechanic_id_new', 'in', mechanic.team_member_ids.ids),
                    ('date_order', '>=', first_day),
                    ('date_order', '<=', today),
                    ('state', '=', 'sale')
                ]
            else:
                domain = [
                    ('car_mechanic_id_new', '=', mechanic.id),
                    ('date_order', '>=', first_day),
                    ('date_order', '<=', today),
                    ('state', '=', 'sale')
                ]

            orders = self.env['sale.order'].search(domain)
            mechanic.current_revenue = sum(orders.mapped('amount_total'))
            
            # Calculate achievement percentage
            if mechanic.monthly_target:
                mechanic.target_achievement = (mechanic.current_revenue / mechanic.monthly_target) * 100
            else:
                mechanic.target_achievement = 0

    def create_user_account(self):
        """Create user account for mechanic"""
        for mechanic in self:
            if not mechanic.user_id:
                # Create employee jika belum ada
                if not mechanic.employee_id:
                    # Create employee baru
                    employee_vals = {
                        'name': mechanic.name,
                        'work_email': f"{mechanic.name.lower().replace(' ', '.')}@pitcar.co.id",
                        # Tambahkan field lain yang diperlukan
                        'job_title': mechanic.position_id.name,
                    }
                    employee = self.env['hr.employee'].sudo().create(employee_vals)
                    # Link employee ke mechanic
                    mechanic.employee_id = employee.id
                
                # Generate username (email)
                email = f"{mechanic.name.lower().replace(' ', '.')}@pitcar.co.id"
                
                # Generate random password
                temp_password = ''.join(choices(string.ascii_letters + string.digits, k=10))
                
                # Create user
                user_values = {
                    'name': mechanic.name,
                    'login': email,
                    'password': temp_password,
                    'employee_id': mechanic.employee_id.id,
                    'groups_id': [(6, 0, [self.env.ref('pitcar_custom.group_mechanic').id])]
                }
                
                try:
                    user = self.env['res.users'].sudo().create(user_values)
                    
                    # Update mechanic
                    mechanic.write({
                        'user_id': user.id,
                        'temp_password': temp_password
                    })
                    
                    # Update employee
                    mechanic.employee_id.write({
                        'user_id': user.id,
                    })
                    
                    return user
                except Exception as e:
                    raise UserError(_("Failed to create user account: %s") % str(e))

    def action_view_credentials(self):
        """Open credential wizard"""
        self.ensure_one()
        return {
            'name': 'Mechanic Credentials',
            'type': 'ir.actions.act_window',
            'res_model': 'mechanic.credential.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_mechanic_id': self.id}
        }

    # New compute methods for attendance
    @api.depends('attendance_ids')
    def _compute_hours_today(self):
        for mechanic in self:
            attendance = mechanic.current_attendance_id
            if attendance:
                mechanic.hours_today = attendance.worked_hours
            else:
                mechanic.hours_today = 0.0

    @api.depends('attendance_ids')
    def _compute_total_hours(self):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        for mechanic in self:
            attendances = mechanic.attendance_ids.filtered(
                lambda x: x.check_in.date() >= first_day
            )
            mechanic.total_attendance_hours = sum(attendances.mapped('worked_hours'))

    @api.depends('total_attendance_hours', 'work_hours_target')
    def _compute_attendance_achievement(self):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        
        for mechanic in self:
            # Hitung jumlah hari kerja dalam sebulan (asumsi Senin-Jumat)
            working_days = 0
            current_date = first_day
            while current_date <= today:
                # 0 = Monday, 6 = Sunday
                if current_date.weekday() < 5:  # Senin-Jumat
                    working_days += 1
                current_date += timedelta(days=1)
            
            target_hours = working_days * mechanic.work_hours_target
            if target_hours:
                mechanic.attendance_achievement = (mechanic.total_attendance_hours / target_hours) * 100
            else:
                mechanic.attendance_achievement = 0

    def verify_location(self, latitude, longitude):
        """
        Verifikasi apakah lokasi valid untuk absensi
        """
        if not self.work_location_ids:
            return True  # Jika tidak ada lokasi yang didefinisikan, izinkan semua

        for location in self.work_location_ids:
            distance = location.calculate_distance(latitude, longitude)
            if distance <= location.radius:
                return True

        return False

    # Action methods
    def action_view_attendances(self):
        self.ensure_one()
        return {
            'name': _('Attendances'),
            'res_model': 'hr.attendance',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.employee_id.id)],
            'type': 'ir.actions.act_window',
            'context': {'create': False}
        }
    
    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Mechanic name already exists !"),
    ]

class CustomerDataCleanup(models.Model):
    _name = 'customer.data.cleanup'
    _description = 'Customer Data Cleanup Service'

    @api.model
    def run_daily_cleanup(self):
        """
        Daily cleanup of redundant customer data
        Can be scheduled as cron job
        """
        _logger.info("Starting daily customer data cleanup...")
        
        # Clean up redundant customer data
        self.env['sale.order'].cleanup_redundant_customer_data()
        
        # Validate data consistency
        validation_result = self.env['sale.order'].validate_customer_data_consistency()
        
        if not validation_result['validation_passed']:
            # Send notification about issues
            _logger.warning(f"Customer data validation failed: {validation_result['total_issues']} issues found")
            
            # Could send email notification here
            # self.env['mail.mail'].create({...}).send()
        
        _logger.info("Daily customer data cleanup completed")
        
        return validation_result

    @api.model
    def recompute_transaction_sequences(self):
        """
        Recompute transaction sequences for all customers
        """
        _logger.info("Starting transaction sequence recomputation...")
        
        customers = self.env['res.partner'].search([
            ('customer_rank', '>', 0)
        ])
        
        for customer in customers:
            orders = self.env['sale.order'].search([
                ('partner_id', '=', customer.id)
            ], order='create_date')
            
            for i, order in enumerate(orders, 1):
                if order.customer_transaction_sequence != i:
                    order.customer_transaction_sequence = i
        
        _logger.info("Transaction sequence recomputation completed")

class CustomerDataMaintenance(models.Model):
    _name = 'customer.data.maintenance'
    _description = 'Safe Customer Data Maintenance'

    @api.model
    def run_safe_daily_maintenance(self):
        """
        Safe daily maintenance of customer data
        """
        try:
            _logger.info("Starting safe daily customer data maintenance...")
            
            # Safe cleanup
            cleanup_result = self.env['sale.order'].cleanup_redundant_customer_data()
            
            # Safe validation
            validation_result = self.env['sale.order'].validate_customer_data_consistency()
            
            # Log results
            if validation_result['validation_passed']:
                _logger.info("Daily maintenance completed successfully - no issues found")
            else:
                _logger.warning(f"Daily maintenance found {validation_result['total_issues']} issues")
            
            return {
                'cleanup_result': cleanup_result,
                'validation_result': validation_result,
                'status': 'completed'
            }
            
        except Exception as e:
            _logger.error(f"Error in daily maintenance: {e}")
            return {
                'status': 'error',
                'error_message': str(e)
            }

    @api.model
    def fix_missing_transaction_sequences(self):
        """
        Safe method to fix missing transaction sequences
        """
        try:
            _logger.info("Fixing missing transaction sequences...")
            
            customers = self.env['res.partner'].search([
                ('customer_rank', '>', 0)
            ])
            
            fixed_count = 0
            for customer in customers:
                orders = self.env['sale.order'].search([
                    ('partner_id', '=', customer.id)
                ], order='create_date')
                
                for i, order in enumerate(orders, 1):
                    if order.customer_transaction_sequence != i:
                        order.customer_transaction_sequence = i
                        fixed_count += 1
            
            _logger.info(f"Fixed {fixed_count} transaction sequences")
            return {'fixed_count': fixed_count, 'status': 'success'}
            
        except Exception as e:
            _logger.error(f"Error fixing sequences: {e}")
            return {'fixed_count': 0, 'status': 'error', 'error_message': str(e)}