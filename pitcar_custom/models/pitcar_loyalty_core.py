from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid
import string
import random

_logger = logging.getLogger(__name__)


class PitcarLoyaltyConfig(models.Model):
    """
    Konfigurasi sistem loyalty - standalone, tidak memodifikasi tabel existing
    """
    _name = 'pitcar.loyalty.config'
    _description = 'Pitcar Loyalty System Configuration'
    _rec_name = 'name'

    name = fields.Char(string='Configuration Name', required=True, default='Main Config')
    
    # Point Earning Configuration
    points_per_rupiah = fields.Float(
        string='Points per Rupiah',
        default=0.0001,
        help='0.001 = 1 point per 10,000 IDR (sesuai requirements)',
        required=True
    )
    min_transaction_for_points = fields.Float(
        string='Minimum Transaction for Points (IDR)',
        default=50000.0,
        help='Transaksi minimum untuk mendapat points'
    )
    
    # Points Expiry Configuration
    points_expiry_months = fields.Integer(
        string='Points Expiry (Months)',
        default=6,
        help='Berapa bulan points akan expire',
        required=True
    )
    
    # Membership Level Thresholds (berdasarkan spending 6 bulan terakhir)
    membership_bronze_threshold = fields.Float(
        string='Bronze Level Threshold (IDR)',
        default=0,
        help='Bronze adalah level default untuk semua customer baru',
        readonly=True
    )
    membership_silver_threshold = fields.Float(
        string='Silver Level Threshold (IDR)', 
        default=2500000.0,
        help='Rp 2.5 juta spending dalam 6 bulan terakhir untuk Silver'
    )
    membership_gold_threshold = fields.Float(
        string='Gold Level Threshold (IDR)',
        default=5000000.0,
        help='Rp 5 juta spending dalam 6 bulan terakhir untuk Gold'
    )
    membership_platinum_threshold = fields.Float(
        string='Platinum Level Threshold (IDR)',
        default=10000000.0,
        help='Rp 10 juta spending dalam 6 bulan terakhir untuk Platinum'
    )
    
    # System Status
    is_system_active = fields.Boolean(
        string='Loyalty System Active',
        default=True,
        help='Enable/disable seluruh sistem loyalty'
    )
    
    # Referral Configuration
    referrer_bonus_points = fields.Integer(
        string='Referrer Bonus Points',
        default=10,
        help='Points untuk yang mereferensikan (10 points)'
    )
    referee_bonus_points = fields.Integer(
        string='Referee Bonus Points', 
        default=10,
        help='Points untuk customer baru yang direferensikan (10 points)'
    )
    referral_min_transaction = fields.Float(
        string='Min Transaction for Referral Bonus (IDR)',
        default=100000.0,
        help='Transaksi minimum referee untuk qualify bonus'
    )
    
    # Constraint untuk hanya 1 config - hanya untuk create, tidak untuk edit
    # @api.model
    # def create(self, vals):
    #     existing_config = self.search([], limit=1)
    #     if existing_config:
    #         raise ValidationError(_('Hanya boleh ada satu konfigurasi loyalty system. Silakan edit konfigurasi yang sudah ada.'))
    #     return super().create(vals)

    @api.model
    def create(self, vals):
        # Skip validation during module installation/upgrade/data loading
        if (self.env.context.get('install_mode') or 
            self.env.context.get('module_data_installation') or
            self.env.context.get('noupdate') is not None):
            return super().create(vals)
        
        # Check for existing config only in normal create operations
        existing_config = self.search([], limit=1)
        if existing_config:
            raise ValidationError(_('Hanya boleh ada satu konfigurasi loyalty system. Silakan edit konfigurasi yang sudah ada.'))
        
        return super().create(vals)
    
    def write(self, vals):
        # Allow editing existing config tanpa validation
        return super(PitcarLoyaltyConfig, self).write(vals)
    
    def unlink(self):
        # Prevent deletion of config jika ada customer aktif
        active_customers = self.env['pitcar.loyalty.customer'].search_count([('status', '=', 'active')])
        if active_customers > 0:
            raise ValidationError(_('Tidak dapat menghapus konfigurasi karena masih ada customer loyalty aktif.'))
        return super().unlink()
    
    @api.model
    def get_config(self):
        """Helper method untuk mengambil konfigurasi aktif"""
        config = self.search([], limit=1)
        if not config:
            # Create default config jika belum ada
            config = self.create({
                'name': 'Default Pitcar Loyalty Config',
                'points_per_rupiah': 0.001,  # 1 point per 1K IDR
            })
        return config
    
    @api.model
    def get_active_config(self):
        """Alias untuk get_config untuk konsistensi"""
        return self.get_config()
    
    def get_membership_level(self, six_month_spending):
        """Determine membership level based on 6-month spending (IDR)"""
        if six_month_spending >= self.membership_platinum_threshold:
            return 'platinum'
        elif six_month_spending >= self.membership_gold_threshold:
            return 'gold'
        elif six_month_spending >= self.membership_silver_threshold:
            return 'silver'
        else:
            return 'bronze'
    
    def get_points_multiplier(self, membership_level):
        """Get points multiplier based on membership level"""
        multipliers = {
            'bronze': 1.0,    # No bonus untuk Bronze
            'silver': 1.0,    # **SEMENTARA DISABLED - Set ke 1.0**
            'gold': 1.0,      # **SEMENTARA DISABLED - Set ke 1.0** 
            'platinum': 1.0   # **SEMENTARA DISABLED - Set ke 1.0**
        }
        multiplier = multipliers.get(membership_level, 1.0)
        _logger.info(f"Membership {membership_level} multiplier: {multiplier}")
        return multiplier
    
    def open_config_form(self):
        """Method untuk membuka form config yang sudah ada"""
        config = self.get_config()
        return {
            'name': 'Loyalty System Configuration',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.loyalty.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'current',
            'context': {
                'create': False,
                'delete': False
            }
        }


class PitcarLoyaltyCustomer(models.Model):
    """
    Customer loyalty profile - terpisah dari res.partner untuk keamanan
    """
    _name = 'pitcar.loyalty.customer' 
    _description = 'Pitcar Loyalty Customer Profile'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Tambah mail functionality
    
    # Basic Info - Link ke partner existing tanpa mengubah struktur
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='cascade',
        index=True,
        help='Link ke customer di res.partner'
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    email = fields.Char(string='Email', related='partner_id.email')
    phone = fields.Char(string='Phone', related='partner_id.phone')
    
    # Loyalty Configuration
    is_active = fields.Boolean(string='Active', default=True, tracking=True)
    join_date = fields.Date(string='Join Date', default=fields.Date.today, tracking=True)
    referral_code = fields.Char(string='Referral Code', copy=False, index=True)
    
    # Membership Info (computed berdasarkan spending)
    membership_level = fields.Selection([
        ('bronze', '🥉 Bronze'),
        ('silver', '🥈 Silver'), 
        ('gold', '🥇 Gold'),
        ('platinum', '💎 Platinum')
    ], string='Membership Level', compute='_compute_membership_level', store=True, tracking=True)
    
    # Status
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended')
    ], string='Status', default='active', tracking=True)
    
    # Points Info
    total_points = fields.Integer(
        string='Active Points',
        compute='_compute_statistics',
        store=True,
        help='Total points yang bisa digunakan saat ini',
        tracking=True
    )
    lifetime_points = fields.Integer(
        string='Lifetime Points',
        default=0,
        help='Total points yang pernah diperoleh sepanjang masa',
        readonly=True
    )
    
    # Spending Info (untuk dynamic membership level)
    total_spent = fields.Float(
        string='Total Spent (IDR)',
        default=0.0,
        help='Total uang yang dihabiskan customer sepanjang masa',
        readonly=True,
        tracking=True
    )
    six_month_spending = fields.Float(
        string='6-Month Spending (IDR)',
        compute='_compute_six_month_spending',
        store=True,
        help='Total spending dalam 6 bulan terakhir (untuk membership level)'
    )
    
    # Registration & Activity
    registration_date = fields.Date(
        string='Registration Date',
        default=fields.Date.today,
        readonly=True
    )
    last_activity_date = fields.Date(
        string='Last Activity',
        help='Tanggal aktivitas terakhir (transaksi/redemption)'
    )
    
    # Referral Info
    referred_by_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Referred By',
        help='Customer yang mereferensikan'
    )
    referral_count = fields.Integer(
        string='Successful Referrals',
        compute='_compute_referral_count',
        help='Jumlah customer yang berhasil direferensikan'
    )
    
    # Notifications
    points_expiry_reminder_sent = fields.Boolean(
        string='Expiry Reminder Sent',
        default=False,
        help='Apakah sudah dikirim reminder points akan expire'
    )
    
    # Relations
    points_transaction_ids = fields.One2many('pitcar.points.transaction', 'customer_id', string='Points Transactions')
    sale_order_ids = fields.One2many('sale.order', 'loyalty_customer_id', string='Sale Orders')
    
    # Statistics
    total_orders = fields.Integer(string='Total Orders', compute='_compute_order_statistics')
    avg_order_value = fields.Float(string='Average Order Value', compute='_compute_order_statistics')
    
    # Referral Relations (akan ditambahkan oleh pitcar_referral.py)
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
    
    @api.model
    def create(self, vals):
        """Override create untuk generate referral code"""
        if not vals.get('referral_code'):
            vals['referral_code'] = self._generate_referral_code()
        return super().create(vals)
    
    def _generate_referral_code(self):
        """Generate unique referral code"""
        while True:
            # Generate 6-character code: 2 letters + 4 numbers
            letters = ''.join(random.choices(string.ascii_uppercase, k=2))
            numbers = ''.join(random.choices(string.digits, k=4))
            code = f"PC{letters}{numbers}"
            
            # Check if code already exists
            existing = self.search([('referral_code', '=', code)])
            if not existing:
                return code
    
    @api.depends('partner_id', 'partner_id.name', 'membership_level')
    def _compute_display_name(self):
        for record in self:
            if record.partner_id:
                record.display_name = f"{record.partner_id.name} ({record.membership_level.title() if record.membership_level else 'Bronze'})"
            else:
                record.display_name = "Unknown Customer"
    
    @api.depends('six_month_spending')
    def _compute_membership_level(self):
        """Calculate membership level berdasarkan 6-month spending"""
        for customer in self:
            # Get thresholds from config
            config = self.env['pitcar.loyalty.config'].get_active_config()
            
            if customer.six_month_spending >= config.membership_platinum_threshold:
                customer.membership_level = 'platinum'
            elif customer.six_month_spending >= config.membership_gold_threshold:
                customer.membership_level = 'gold'
            elif customer.six_month_spending >= config.membership_silver_threshold:
                customer.membership_level = 'silver'
            else:
                customer.membership_level = 'bronze'
    
    @api.depends('points_transaction_ids', 'points_transaction_ids.points', 'points_transaction_ids.status')
    def _compute_statistics(self):
        for customer in self:
            active_transactions = customer.points_transaction_ids.filtered(lambda t: t.status == 'active')
            customer.total_points = sum(active_transactions.mapped('points'))
    
    @api.depends('sale_order_ids', 'sale_order_ids.amount_total', 'sale_order_ids.state')
    def _compute_order_statistics(self):
        for customer in self:
            confirmed_orders = customer.sale_order_ids.filtered(lambda o: o.state in ['sale', 'done'])
            customer.total_orders = len(confirmed_orders)
            customer.avg_order_value = sum(confirmed_orders.mapped('amount_total')) / len(confirmed_orders) if confirmed_orders else 0.0
    
    @api.depends('sale_order_ids', 'sale_order_ids.amount_total', 'sale_order_ids.date_order', 'sale_order_ids.state')
    def _compute_six_month_spending(self):
        for customer in self:
            customer.six_month_spending = customer.get_six_month_spending()
    
    @api.depends('points_transaction_ids')
    def _compute_referral_count(self):
        for record in self:
            # Count successful referrals berdasarkan transaction bertipe referral_bonus
            referral_transactions = record.points_transaction_ids.filtered(
                lambda t: t.transaction_type == 'referral_bonus' and t.status == 'active'
            )
            record.referral_count = len(referral_transactions)
    
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
    
    def update_membership_level(self):
        """Update membership level based on spending in last 6 months"""
        config = self.env['pitcar.loyalty.config'].get_config()
        
        # Calculate spending in last 6 months
        from dateutil.relativedelta import relativedelta
        six_months_ago = fields.Date.today() - relativedelta(months=6)
        
        # Get confirmed orders in last 6 months
        recent_orders = self.sale_order_ids.filtered(
            lambda o: o.state in ['sale', 'done'] 
            and o.date_order.date() >= six_months_ago
        )
        recent_spending = sum(recent_orders.mapped('amount_total'))
        
        # Determine new level based on recent spending
        new_level = config.get_membership_level(recent_spending)
        
        if new_level != self.membership_level:
            old_level = self.membership_level
            self.membership_level = new_level
            
            # Log membership change
            level_change = "upgraded" if self._get_level_weight(new_level) > self._get_level_weight(old_level) else "downgraded"
            
            self.message_post(
                body=f"🔄 Membership {level_change} from {old_level} to {new_level}! (Based on 6-month spending: Rp {recent_spending:,.0f})"
            )
            _logger.info(f"Customer {self.display_name} {level_change} to {new_level} (6-month spending: {recent_spending})")
    
    def _get_level_weight(self, level):
        """Get numeric weight for level comparison"""
        weights = {'bronze': 1, 'silver': 2, 'gold': 3, 'platinum': 4}
        return weights.get(level, 1)
    
    def get_six_month_spending(self):
        """Get spending amount in last 6 months"""
        from dateutil.relativedelta import relativedelta
        six_months_ago = fields.Date.today() - relativedelta(months=6)
        
        recent_orders = self.sale_order_ids.filtered(
            lambda o: o.state in ['sale', 'done'] 
            and o.date_order.date() >= six_months_ago
        )
        return sum(recent_orders.mapped('amount_total'))
    
    def action_recalculate_points(self):
        """Recalculate total points (for debugging)"""
        for customer in self:
            active_transactions = customer.points_transaction_ids.filtered(
                lambda t: t.status == 'active'
            )
            
            total_points = sum(active_transactions.mapped('points'))
            lifetime_points = sum(customer.points_transaction_ids.filtered(
                lambda t: t.transaction_type in ['earn', 'bonus', 'referral_bonus']
            ).mapped('points'))
            
            customer.write({
                'total_points': max(0, total_points),  # Tidak boleh negatif
                'lifetime_points': max(0, lifetime_points)
            })
        
        self.ensure_one()
        self._compute_statistics()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Points recalculated. Total: {self.total_points}',
                'type': 'success'
            }
        }
    
    def action_view_transactions(self):
        """View all transactions for this customer"""
        self.ensure_one()
        return {
            'name': f'Transactions - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.points.transaction',
            'view_mode': 'tree,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id}
        }
    
    def action_view_sale_orders(self):
        """View sale orders for this customer"""
        self.ensure_one()
        return {
            'name': f'Sale Orders - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('loyalty_customer_id', '=', self.id)],
            'context': {'default_partner_id': self.partner_id.id}
        }
    
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
    
    @api.model
    def get_or_create_loyalty_customer(self, partner_id):
        """
        Helper method: Dapatkan loyalty customer atau buat baru jika belum ada
        Method ini aman dan tidak mengubah res.partner
        """
        if not partner_id:
            return False
            
        # Cari existing loyalty customer
        loyalty_customer = self.search([('partner_id', '=', partner_id)], limit=1)
        
        if not loyalty_customer:
            # Buat loyalty customer baru
            partner = self.env['res.partner'].browse(partner_id)
            loyalty_customer = self.create({
                'partner_id': partner_id,
                'total_spent': 0.0  # Start with 0 spending = Bronze level
            })
            _logger.info(f"Created new loyalty customer for partner: {partner.name}")
        
        return loyalty_customer
    
    def get_expiring_points(self, days_ahead=30):
        """Get points yang akan expire dalam X hari ke depan"""
        self.ensure_one()
        cutoff_date = fields.Date.today() + timedelta(days=days_ahead)
        
        expiring_transactions = self.points_transaction_ids.filtered(
            lambda t: t.status == 'active' 
            and t.expiry_date 
            and t.expiry_date <= cutoff_date
            and t.points > 0  # Only earning transactions
        )
        
        return sum(expiring_transactions.mapped('points'))
    
    @api.model 
    def auto_update_membership_levels(self):
        """Cron job: Update membership levels for all active customers"""
        active_customers = self.search([('status', '=', 'active')])
        
        updated_count = 0
        for customer in active_customers:
            old_level = customer.membership_level
            customer.update_membership_level()
            if customer.membership_level != old_level:
                updated_count += 1
        
        _logger.info(f"Auto-updated membership levels for {updated_count} customers")
        return updated_count


class PitcarPointsTransaction(models.Model):
    """
    Transaction history untuk points - untuk audit trail yang lengkap
    """
    _name = 'pitcar.points.transaction'
    _description = 'Pitcar Points Transaction History'
    _order = 'create_date desc, id desc'
    _rec_name = 'reference_code'
    
    # Basic Info
    customer_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Loyalty Customer', 
        required=True,
        ondelete='cascade',
        index=True
    )
    customer_name = fields.Char(
        related='customer_id.display_name',
        string='Customer Name',
        readonly=True,
        store=True
    )
    
    # Transaction Details
    transaction_type = fields.Selection([
        ('earn', '💰 Earn from Purchase'),
        ('redeem', '🎁 Redeem for Reward'),
        ('expire', '⏰ Points Expired'),
        ('bonus', '🎉 Bonus Points'),
        ('referral_bonus', '👥 Referral Bonus'),
        ('level_up', '⬆️ Level Up Bonus'),
        ('manual_adjust', '⚙️ Manual Adjustment'),
    ], string='Transaction Type', required=True, tracking=True)
    
    points = fields.Integer(
        string='Points',
        required=True,
        help='Positif untuk earn, negatif untuk redeem/expire'
    )
    
    description = fields.Text(
        string='Description',
        required=True,
        help='Deskripsi detail transaksi'
    )
    
    # Dates
    transaction_date = fields.Datetime(
        string='Transaction Date',
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    expiry_date = fields.Date(
        string='Points Expiry Date',
        help='Tanggal expire untuk points yang di-earn'
    )
    
    # Status
    status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'), 
        ('redeemed', 'Fully Redeemed')
    ], string='Status', default='active', tracking=True)
    
    # References
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Related Sale Order',
        help='Sale order yang terkait dengan earning points',
        ondelete='set null'
    )
    reference_code = fields.Char(
        string='Reference Code',
        help='Kode referensi unik untuk transaksi',
        readonly=True,
        copy=False
    )
    
    # Additional Data
    original_amount = fields.Float(
        string='Original Amount (IDR)',
        help='Nominal asli transaksi (untuk earn from purchase)'
    )
    related_customer_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Related Customer',
        help='Customer terkait (untuk referral bonus)'
    )
    
    @api.model
    def create(self, vals):
        # Generate reference code
        if not vals.get('reference_code'):
            vals['reference_code'] = self._generate_reference_code(vals.get('transaction_type', 'manual'))
        
        # Set expiry date untuk earning transactions
        if vals.get('transaction_type') in ['earn', 'bonus', 'referral_bonus'] and vals.get('points', 0) > 0:
            if not vals.get('expiry_date'):
                config = self.env['pitcar.loyalty.config'].get_config()
                vals['expiry_date'] = fields.Date.today() + relativedelta(months=config.points_expiry_months)
        
        transaction = super().create(vals)
        
        # Update customer points setelah transaction
        transaction._update_customer_points()
        
        return transaction
    
    def write(self, vals):
        result = super().write(vals)
        
        # Update customer points jika ada perubahan status atau points
        if 'status' in vals or 'points' in vals:
            for transaction in self:
                transaction._update_customer_points()
        
        return result
    
    def _generate_reference_code(self, transaction_type):
        """Generate reference code berdasarkan tipe transaksi"""
        type_prefix = {
            'earn': 'ERN',
            'redeem': 'RDM', 
            'expire': 'EXP',
            'bonus': 'BON',
            'referral_bonus': 'REF',
            'level_up': 'LVL',
            'manual_adjust': 'ADJ'
        }
        
        prefix = type_prefix.get(transaction_type, 'TXN')
        timestamp = datetime.now().strftime('%y%m%d%H%M')
        sequence = self.env['ir.sequence'].next_by_code('pitcar.points.transaction') or '001'
        
        return f"{prefix}{timestamp}{sequence}"
    
    def _update_customer_points(self):
        """Update total points di customer setelah transaction"""
        for transaction in self:
            customer = transaction.customer_id
            if customer:
                customer.action_recalculate_points()
                customer.update_membership_level()
                customer.last_activity_date = fields.Date.today()
    
    @api.model
    def create_earning_transaction(self, partner_id, sale_order_id, amount):
        """
        Helper method: Create earning transaction dari sale order
        Method ini aman dan tidak mengubah sale.order existing
        """
        config = self.env['pitcar.loyalty.config'].get_config()
        
        if not config.is_system_active:
            return False
            
        if amount < config.min_transaction_for_points:
            return False
        
        # Get atau create loyalty customer
        loyalty_customer = self.env['pitcar.loyalty.customer'].get_or_create_loyalty_customer(partner_id)
        if not loyalty_customer:
            return False
        
        # Calculate points
        points_earned = int(amount * config.points_per_rupiah)
        if points_earned <= 0:
            return False
        
        # Create transaction
        transaction = self.create({
            'customer_id': loyalty_customer.id,
            'sale_order_id': sale_order_id,
            'transaction_type': 'earn',
            'points': points_earned,
            'description': f'Points earned from purchase - Order #{self.env["sale.order"].browse(sale_order_id).name}',
            'original_amount': amount,
        })
        
        # Update customer spending
        loyalty_customer.total_spent += amount
        
        _logger.info(f"Created earning transaction: {points_earned} points for {loyalty_customer.display_name}")
        
        return transaction
    
    @api.model 
    def expire_old_points(self):
        """Cron job: Expire points yang sudah melewati tanggal expire"""
        today = fields.Date.today()
        
        # Cari transactions yang perlu di-expire
        expiring_transactions = self.search([
            ('status', '=', 'active'),
            ('expiry_date', '<', today),
            ('points', '>', 0),  # Only positive points can expire
        ])
        
        expired_count = 0
        for transaction in expiring_transactions:
            # Create expiry transaction
            self.create({
                'customer_id': transaction.customer_id.id,
                'transaction_type': 'expire',
                'points': -transaction.points,  # Negative untuk mengurangi
                'description': f'Points expired - Originally from: {transaction.description}',
                'status': 'active'
            })
            
            # Mark original transaction as expired
            transaction.status = 'expired'
            expired_count += 1
        
        _logger.info(f"Expired {expired_count} point transactions")
        return expired_count


# Sequence definitions untuk loyalty system
class IrSequence(models.Model):
    _inherit = 'ir.sequence'
    
    @api.model
    def create_loyalty_sequences(self):
        """Create sequences for loyalty system"""
        sequences_to_create = [
            {
                'name': 'Pitcar Points Transaction',
                'code': 'pitcar.points.transaction',
                'prefix': '',
                'suffix': '',
                'padding': 3,
                'number_increment': 1,
                'implementation': 'standard',
            },
            {
                'name': 'Pitcar Referral Tracking',
                'code': 'pitcar.referral.tracking',
                'prefix': '',
                'suffix': '',
                'padding': 3,
                'number_increment': 1,
                'implementation': 'standard',
            }
        ]
        
        for seq_data in sequences_to_create:
            existing = self.search([('code', '=', seq_data['code'])])
            if not existing:
                self.create(seq_data)
                _logger.info(f"Created sequence: {seq_data['name']}")
    
    @api.model
    def init_loyalty_system(self):
        """Initialize loyalty system with default data"""
        try:
            # Create sequences
            self.create_loyalty_sequences()
            
            # Create default loyalty config
            config = self.env['pitcar.loyalty.config'].get_active_config()
            _logger.info(f"Loyalty config initialized: {config.name}")
            
            # Create default referral program jika ada model referral
            if 'pitcar.referral.program' in self.env:
                program = self.env['pitcar.referral.program'].get_active_program()
                _logger.info(f"Referral program initialized: {program.name}")
            
            return True
            
        except Exception as e:
            _logger.error(f"Error initializing loyalty system: {str(e)}")
            return False

# Sequence untuk reference code
class IrSequence(models.Model):
    _inherit = 'ir.sequence'
    
    @api.model
    def _get_default_sequences(self):
        """Extend untuk menambahkan sequence loyalty points"""
        sequences = super()._get_default_sequences()
        sequences.update({
            'pitcar.points.transaction': {
                'name': 'Pitcar Points Transaction',
                'code': 'pitcar.points.transaction', 
                'prefix': '',
                'suffix': '',
                'padding': 3,
                'number_increment': 1,
            }
        })
        return sequences