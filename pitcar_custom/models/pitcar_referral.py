from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
from datetime import datetime, timedelta
import uuid

_logger = logging.getLogger(__name__)


class PitcarReferralProgram(models.Model):
    """
    Program referral dengan konfigurasi bonus dan syarat
    """
    _name = 'pitcar.referral.program'
    _description = 'Pitcar Referral Program'
    _order = 'create_date desc'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic Info
    name = fields.Char(string='Program Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    
    # Points Configuration
    referrer_points = fields.Integer(
        string='Referrer Bonus Points',
        required=True,
        default=10,
        help='Points untuk yang mereferensikan',
        tracking=True
    )
    referee_points = fields.Integer(
        string='Referee Bonus Points',
        required=True,
        default=10,
        help='Points untuk customer baru yang direferensikan',
        tracking=True
    )
    
    # Qualification Requirements
    minimum_transaction = fields.Float(
        string='Minimum Transaction Amount (IDR)',
        required=True,
        default=100000.0,
        help='Transaksi minimum referee untuk qualify bonus',
        tracking=True
    )
    qualification_days = fields.Integer(
        string='Qualification Period (Days)',
        default=30,
        help='Berapa hari referee harus melakukan transaksi qualifying',
        tracking=True
    )
    
    # Program Period
    is_active = fields.Boolean(string='Active', default=True, tracking=True)
    valid_from = fields.Date(string='Valid From', default=fields.Date.today, tracking=True)
    valid_until = fields.Date(string='Valid Until', tracking=True)
    
    # Terms & Conditions
    terms_conditions = fields.Html(string='Terms & Conditions')
    
    # Statistics
    total_referrals = fields.Integer(
        string='Total Referrals',
        compute='_compute_statistics',
        help='Total jumlah referrals dalam program ini'
    )
    qualified_referrals = fields.Integer(
        string='Qualified Referrals',
        compute='_compute_statistics',
        help='Referrals yang sudah memenuhi syarat'
    )
    success_rate = fields.Float(
        string='Success Rate (%)',
        compute='_compute_statistics',
        help='Persentase referrals yang qualified'
    )
    
    # Relations
    referral_tracking_ids = fields.One2many(
        'pitcar.referral.tracking',
        'program_id',
        string='Referral Trackings'
    )
    
    @api.depends('referral_tracking_ids', 'referral_tracking_ids.status')
    def _compute_statistics(self):
        for program in self:
            total = len(program.referral_tracking_ids)
            qualified = len(program.referral_tracking_ids.filtered(lambda r: r.status == 'rewarded'))
            
            program.total_referrals = total
            program.qualified_referrals = qualified
            program.success_rate = (qualified / total * 100) if total else 0
    
    @api.constrains('valid_from', 'valid_until')
    def _check_validity_dates(self):
        for program in self:
            if program.valid_until and program.valid_from and program.valid_until < program.valid_from:
                raise ValidationError(_('Valid until date cannot be earlier than valid from date'))
    
    @api.constrains('referrer_points', 'referee_points', 'minimum_transaction')
    def _check_positive_values(self):
        for program in self:
            if program.referrer_points < 0:
                raise ValidationError(_('Referrer points cannot be negative'))
            if program.referee_points < 0:
                raise ValidationError(_('Referee points cannot be negative'))
            if program.minimum_transaction <= 0:
                raise ValidationError(_('Minimum transaction must be greater than 0'))
    
    @api.model
    def get_active_program(self):
        """Get active referral program"""
        program = self.search([
            ('is_active', '=', True),
            ('valid_from', '<=', fields.Date.today()),
            '|', ('valid_until', '=', False), ('valid_until', '>=', fields.Date.today())
        ], limit=1)
        
        if not program:
            # Create default program
            program = self.create({
                'name': 'Default Referral Program',
                'referrer_points': 10,    # 10 points untuk referrer
                'referee_points': 10,     # 10 points untuk referee
                'minimum_transaction': 100000.0,
                'qualification_days': 30,
                'is_active': True,
                'description': 'Default referral program - refer friends and get 10 bonus points!'
            })
            _logger.info("Created default referral program")
        
        return program
    
    @api.model
    def _update_default_terms(self, program_ids):
        """Update terms and conditions for default program"""
        for program_id in program_ids:
            program = self.browse(program_id)
            if program.exists():
                terms_html = """
                <h3>Syarat dan Ketentuan Program Referral Pitcar</h3>
                <ul>
                    <li><strong>Cara Kerja:</strong> Berikan kode referral Anda kepada teman atau keluarga</li>
                    <li><strong>Bonus Referrer:</strong> Anda mendapat 50 poin ketika referee melakukan transaksi pertama minimal Rp 100.000</li>
                    <li><strong>Bonus Referee:</strong> Teman Anda mendapat 30 poin welcome bonus setelah transaksi pertama</li>
                    <li><strong>Periode Qualifying:</strong> Teman Anda harus melakukan transaksi dalam 30 hari setelah registrasi</li>
                    <li><strong>Unlimited Referrals:</strong> Tidak ada batasan jumlah teman yang bisa Anda referensikan</li>
                    <li><strong>Points Expiry:</strong> Points yang diperoleh akan expire dalam 6 bulan</li>
                    <li><strong>Program Validity:</strong> Program berlaku hingga 31 Desember 2025</li>
                </ul>
                
                <h4>Ketentuan Umum:</h4>
                <ul>
                    <li>Referee harus customer baru yang belum pernah melakukan transaksi di Pitcar</li>
                    <li>Transaksi qualifying harus berupa service kendaraan, bukan pembelian part saja</li>
                    <li>Points akan otomatis masuk ke akun loyalty setelah transaksi qualifying completed</li>
                    <li>Pitcar berhak mengubah syarat dan ketentuan sewaktu-waktu</li>
                    <li>Keputusan Pitcar adalah final untuk semua sengketa terkait program ini</li>
                </ul>
                """
                program.terms_conditions = terms_html
                _logger.info(f"Updated terms and conditions for program: {program.name}")


class PitcarReferralTracking(models.Model):
    """
    Tracking aktivitas referral customer
    """
    _name = 'pitcar.referral.tracking'
    _description = 'Pitcar Referral Activity Tracking'
    _order = 'create_date desc'
    _rec_name = 'tracking_code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic Info
    tracking_code = fields.Char(
        string='Tracking Code',
        required=True,
        copy=False,
        index=True,
        readonly=True
    )
    program_id = fields.Many2one(
        'pitcar.referral.program',
        string='Referral Program',
        required=True,
        ondelete='restrict'
    )
    
    # Referrer Info
    referrer_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Referrer',
        required=True,
        ondelete='cascade',
        help='Customer yang mereferensikan'
    )
    referrer_name = fields.Char(
        related='referrer_id.display_name',
        string='Referrer Name',
        store=True
    )
    referral_code_used = fields.Char(
        string='Referral Code Used',
        help='Kode referral yang digunakan'
    )
    
    # Referee Info
    referee_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Referee',
        required=True,
        ondelete='cascade',
        help='Customer baru yang direferensikan'
    )
    referee_name = fields.Char(
        related='referee_id.display_name',
        string='Referee Name',
        store=True
    )
    referee_partner_id = fields.Many2one(
        related='referee_id.partner_id',
        string='Referee Partner',
        store=True
    )
    
    # Registration & Qualification
    registration_date = fields.Datetime(
        string='Registration Date',
        default=fields.Datetime.now,
        required=True,
        help='Kapan referee pertama kali register'
    )
    first_transaction_date = fields.Datetime(
        string='First Transaction Date',
        help='Kapan referee melakukan transaksi pertama'
    )
    first_transaction_amount = fields.Float(
        string='First Transaction Amount (IDR)',
        help='Nominal transaksi pertama referee'
    )
    qualifying_sale_order_id = fields.Many2one(
        'sale.order',
        string='Qualifying Sale Order',
        help='Sale order yang memenuhi syarat untuk bonus referral'
    )
    
    # Status & Timeline
    status = fields.Selection([
        ('registered', '📝 Registered'),
        ('qualified', '✅ Qualified'),
        ('rewarded', '🎁 Rewarded'),
        ('expired', '⏰ Expired')
    ], string='Status', default='registered', tracking=True, required=True)
    
    qualification_deadline = fields.Datetime(
        string='Qualification Deadline',
        compute='_compute_qualification_deadline',
        store=True,
        help='Batas waktu untuk qualify'
    )
    days_to_qualify = fields.Integer(
        string='Days to Qualify',
        compute='_compute_days_to_qualify',
        help='Sisa hari untuk qualify'
    )
    
    # Rewards Given
    points_awarded_referrer = fields.Integer(
        string='Points Awarded to Referrer',
        default=0,
        help='Points yang diberikan ke referrer'
    )
    points_awarded_referee = fields.Integer(
        string='Points Awarded to Referee',
        default=0,
        help='Points yang diberikan ke referee'
    )
    reward_date = fields.Datetime(
        string='Reward Date',
        help='Kapan bonus diberikan'
    )
    
    # Additional Info
    notes = fields.Text(string='Notes')
    source_channel = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('direct', 'Direct/Word of Mouth'),
        ('website', 'Website'),
        ('other', 'Other')
    ], string='Source Channel', help='Channel dimana referral terjadi')
    
    @api.depends('registration_date', 'program_id.qualification_days')
    def _compute_qualification_deadline(self):
        for tracking in self:
            if tracking.registration_date and tracking.program_id.qualification_days:
                tracking.qualification_deadline = tracking.registration_date + timedelta(
                    days=tracking.program_id.qualification_days
                )
            else:
                tracking.qualification_deadline = False
    
    @api.depends('qualification_deadline')
    def _compute_days_to_qualify(self):
        for tracking in self:
            if tracking.qualification_deadline and tracking.status == 'registered':
                delta = tracking.qualification_deadline.date() - fields.Date.today()
                tracking.days_to_qualify = delta.days
            else:
                tracking.days_to_qualify = 0
    
    @api.model
    def create(self, vals):
        # Generate tracking code
        if not vals.get('tracking_code'):
            vals['tracking_code'] = self._generate_tracking_code()
        
        # Auto-set referral code used from referrer
        if vals.get('referrer_id') and not vals.get('referral_code_used'):
            referrer = self.env['pitcar.loyalty.customer'].browse(vals['referrer_id'])
            vals['referral_code_used'] = referrer.referral_code
        
        return super().create(vals)
    
    def _generate_tracking_code(self):
        """Generate unique tracking code"""
        sequence = self.env['ir.sequence'].next_by_code('pitcar.referral.tracking') or '001'
        return f"REF{fields.Date.today().strftime('%y%m%d')}{sequence}"
    
    def check_qualification(self, sale_order_id, transaction_amount):
        """
        Check if a transaction qualifies this referral for bonus
        """
        self.ensure_one()
        
        if self.status != 'registered':
            return False, f"Referral already processed (status: {self.status})"
        
        # Check if within qualification period
        if self.qualification_deadline and fields.Datetime.now() > self.qualification_deadline:
            self.status = 'expired'
            return False, "Qualification period has expired"
        
        # Check minimum transaction amount
        if transaction_amount < self.program_id.minimum_transaction:
            return False, f"Transaction amount {transaction_amount:,.0f} is below minimum {self.program_id.minimum_transaction:,.0f}"
        
        # All checks passed - qualify the referral
        self.write({
            'status': 'qualified',
            'first_transaction_date': fields.Datetime.now(),
            'first_transaction_amount': transaction_amount,
            'qualifying_sale_order_id': sale_order_id
        })
        
        return True, "Referral qualified for bonus"
    
    def award_referral_bonus(self):
        """
        Award bonus points to both referrer and referee
        """
        self.ensure_one()
        
        if self.status != 'qualified':
            raise UserError(_('Only qualified referrals can be rewarded'))
        
        # Award points to referrer
        referrer_transaction = self.env['pitcar.points.transaction'].create({
            'customer_id': self.referrer_id.id,
            'transaction_type': 'referral_bonus',
            'points': self.program_id.referrer_points,
            'description': f'Referral bonus - Referred: {self.referee_name}',
            'sale_order_id': self.qualifying_sale_order_id.id if self.qualifying_sale_order_id else False,
            'related_customer_id': self.referee_id.id
        })
        
        # Award points to referee
        referee_transaction = self.env['pitcar.points.transaction'].create({
            'customer_id': self.referee_id.id,
            'transaction_type': 'referral_bonus',
            'points': self.program_id.referee_points,
            'description': f'Welcome bonus - Referred by: {self.referrer_name}',
            'sale_order_id': self.qualifying_sale_order_id.id if self.qualifying_sale_order_id else False,
            'related_customer_id': self.referrer_id.id
        })
        
        # Update tracking record
        self.write({
            'status': 'rewarded',
            'points_awarded_referrer': self.program_id.referrer_points,
            'points_awarded_referee': self.program_id.referee_points,
            'reward_date': fields.Datetime.now()
        })
        
        # Log success
        _logger.info(f"Referral bonus awarded - Tracking: {self.tracking_code}")
        
        # Post messages to both customers
        self.referrer_id.message_post(
            body=f"🎉 Referral bonus: {self.program_id.referrer_points} points! Thanks for referring {self.referee_name}"
        )
        self.referee_id.message_post(
            body=f"🎁 Welcome bonus: {self.program_id.referee_points} points! You were referred by {self.referrer_name}"
        )
        
        return {
            'referrer_transaction': referrer_transaction,
            'referee_transaction': referee_transaction
        }
    
    @api.model
    def create_referral_tracking(self, referrer_partner_id, referee_partner_id, program_id=None, source_channel='direct'):
        """
        Helper method to create referral tracking when new customer registers via referral
        """
        # Get or create loyalty customers
        referrer_loyalty = self.env['pitcar.loyalty.customer'].get_or_create_loyalty_customer(referrer_partner_id)
        referee_loyalty = self.env['pitcar.loyalty.customer'].get_or_create_loyalty_customer(referee_partner_id)
        
        if not referrer_loyalty or not referee_loyalty:
            return False
        
        # Get active program if not specified
        if not program_id:
            active_program = self.env['pitcar.referral.program'].get_active_program()
            program_id = active_program.id
        
        # Check if tracking already exists
        existing_tracking = self.search([
            ('referrer_id', '=', referrer_loyalty.id),
            ('referee_id', '=', referee_loyalty.id),
            ('status', 'in', ['registered', 'qualified', 'rewarded'])
        ], limit=1)
        
        if existing_tracking:
            _logger.warning(f"Referral tracking already exists: {existing_tracking.tracking_code}")
            return existing_tracking
        
        # Create tracking record
        tracking = self.create({
            'program_id': program_id,
            'referrer_id': referrer_loyalty.id,
            'referee_id': referee_loyalty.id,
            'source_channel': source_channel
        })
        
        # Update referee's referred_by
        referee_loyalty.referred_by_id = referrer_loyalty.id
        
        _logger.info(f"Created referral tracking: {tracking.tracking_code}")
        
        return tracking
    
    @api.model
    def process_qualifying_transaction(self, partner_id, sale_order_id, transaction_amount):
        """
        Process a transaction to check if it qualifies any pending referrals
        """
        # Find loyalty customer
        loyalty_customer = self.env['pitcar.loyalty.customer'].search([
            ('partner_id', '=', partner_id)
        ], limit=1)
        
        if not loyalty_customer:
            return False
        
        # Find pending referral tracking for this referee
        pending_referral = self.search([
            ('referee_id', '=', loyalty_customer.id),
            ('status', '=', 'registered')
        ], limit=1)
        
        if not pending_referral:
            return False
        
        # Check qualification
        qualified, message = pending_referral.check_qualification(sale_order_id, transaction_amount)
        
        if qualified:
            # Auto-award bonus
            pending_referral.award_referral_bonus()
            _logger.info(f"Auto-awarded referral bonus for tracking: {pending_referral.tracking_code}")
            
        return {
            'tracking': pending_referral,
            'qualified': qualified,
            'message': message
        }
    
    @api.model
    def expire_old_referrals(self):
        """
        Cron job: Mark expired referrals
        """
        expired_referrals = self.search([
            ('status', '=', 'registered'),
            ('qualification_deadline', '<', fields.Datetime.now())
        ])
        
        for referral in expired_referrals:
            referral.status = 'expired'
        
        _logger.info(f"Expired {len(expired_referrals)} referral trackings")
        return len(expired_referrals)


# Update PitcarLoyaltyCustomer untuk referral integration
class PitcarLoyaltyCustomer(models.Model):
    _inherit = 'pitcar.loyalty.customer'
    
    # Referral Relations
    referral_trackings_as_referrer = fields.One2many(
        'pitcar.referral.tracking',
        'referrer_id',
        string='My Referrals'
    )
    referral_trackings_as_referee = fields.One2many(
        'pitcar.referral.tracking',
        'referee_id',
        string='Referred By'
    )
    
    # Enhanced Referral Stats
    total_referrals_made = fields.Integer(
        string='Total Referrals Made',
        compute='_compute_referral_stats'
    )
    successful_referrals = fields.Integer(
        string='Successful Referrals',
        compute='_compute_referral_stats'
    )
    referral_success_rate = fields.Float(
        string='Referral Success Rate (%)',
        compute='_compute_referral_stats'
    )
    total_referral_bonus_earned = fields.Integer(
        string='Total Referral Bonus Earned',
        compute='_compute_referral_stats'
    )
    
    @api.depends('referral_trackings_as_referrer', 'referral_trackings_as_referrer.status')
    def _compute_referral_stats(self):
        for customer in self:
            referrals = customer.referral_trackings_as_referrer
            total = len(referrals)
            successful = len(referrals.filtered(lambda r: r.status == 'rewarded'))
            total_bonus = sum(referrals.filtered(lambda r: r.status == 'rewarded').mapped('points_awarded_referrer'))
            
            customer.total_referrals_made = total
            customer.successful_referrals = successful
            customer.referral_success_rate = (successful / total * 100) if total else 0
            customer.total_referral_bonus_earned = total_bonus
    
    def action_view_my_referrals(self):
        """View referrals made by this customer"""
        self.ensure_one()
        return {
            'name': f'My Referrals - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.referral.tracking',
            'view_mode': 'tree,form',
            'domain': [('referrer_id', '=', self.id)],
            'context': {'default_referrer_id': self.id}
        }