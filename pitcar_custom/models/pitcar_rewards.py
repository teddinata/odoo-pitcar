from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class PitcarRewardCategory(models.Model):
    """
    Kategori untuk reward (Merchandise, Service, Voucher, dll)
    """
    _name = 'pitcar.reward.category'
    _description = 'Pitcar Reward Category'
    _order = 'sequence, name'
    
    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Category Code', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    icon = fields.Char(string='Icon', help='Font Awesome icon class (e.g., fa-gift)')
    
    # Computed
    reward_count = fields.Integer(string='Rewards Count', compute='_compute_reward_count')
    
    @api.depends('reward_ids')
    def _compute_reward_count(self):
        for category in self:
            category.reward_count = len(category.reward_ids)
    
    # Relations
    reward_ids = fields.One2many('pitcar.rewards.catalog', 'category_id', string='Rewards')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Category code must be unique!'),
        ('name_unique', 'unique(name)', 'Category name must be unique!')
    ]


class PitcarRewardsCatalog(models.Model):
    """
    Katalog reward yang bisa ditukar dengan points
    """
    _name = 'pitcar.rewards.catalog'
    _description = 'Pitcar Rewards Catalog'
    _order = 'points_required asc, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic Info
    name = fields.Char(string='Reward Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    image = fields.Image(string='Reward Image')
    category_id = fields.Many2one('pitcar.reward.category', string='Category', required=True)
    
    # Points & Pricing
    points_required = fields.Integer(string='Points Required', required=True, tracking=True)
    
    # Stock Management
    stock_quantity = fields.Integer(
        string='Stock Quantity', 
        default=-1, 
        help="-1 = Unlimited stock, 0+ = Limited stock",
        tracking=True
    )
    available_stock = fields.Integer(
        string='Available Stock', 
        compute='_compute_available_stock', 
        store=True
    )
    max_redeem_per_customer = fields.Integer(
        string='Max Redeem per Customer',
        default=0,
        help="0 = No limit"
    )
    
    # Validity
    valid_from = fields.Date(string='Valid From', default=fields.Date.today)
    valid_until = fields.Date(string='Valid Until')
    is_active = fields.Boolean(string='Active', default=True, tracking=True)
    
    # Terms
    terms_conditions = fields.Html(string='Terms & Conditions')
    
    # Relations
    product_id = fields.Many2one('product.product', string='Related Product')
    redemption_ids = fields.One2many('pitcar.points.redemption', 'reward_id', string='Redemptions')
    
    # Computed
    redemption_count = fields.Integer(string='Redemption Count', compute='_compute_redemption_count')
    
    @api.depends('redemption_ids')
    def _compute_redemption_count(self):
        for reward in self:
            reward.redemption_count = len(reward.redemption_ids.filtered(lambda r: r.status != 'cancelled'))
    
    @api.depends('stock_quantity', 'redemption_ids.status')
    def _compute_available_stock(self):
        for reward in self:
            if reward.stock_quantity == -1:  # Unlimited
                reward.available_stock = 999999
            else:
                redeemed = len(reward.redemption_ids.filtered(lambda r: r.status in ['approved', 'delivered']))
                reward.available_stock = max(0, reward.stock_quantity - redeemed)
    
    @api.constrains('points_required')
    def _check_points_required(self):
        for reward in self:
            if reward.points_required <= 0:
                raise ValidationError(_('Points required must be greater than zero.'))
    
    @api.constrains('valid_from', 'valid_until')
    def _check_validity_dates(self):
        for reward in self:
            if reward.valid_until and reward.valid_from and reward.valid_until < reward.valid_from:
                raise ValidationError(_('Valid until date cannot be earlier than valid from date.'))


class PitcarPointsRedemption(models.Model):
    """
    Model untuk tracking redemption points customer
    Enhanced untuk support manual redemption
    """
    _name = 'pitcar.points.redemption'
    _description = 'Pitcar Points Redemption'
    _order = 'create_date desc'
    _rec_name = 'redemption_code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic Info
    customer_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Customer',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    customer_name = fields.Char(related='customer_id.display_name', string='Customer Name', store=True)
    
    # Reward Info
    reward_id = fields.Many2one(
        'pitcar.rewards.catalog',
        string='Reward',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    reward_name = fields.Char(related='reward_id.name', string='Reward Name', store=True)
    
    # Redemption Details
    redemption_code = fields.Char(
        string='Redemption Code',
        copy=False,
        index=True,
        readonly=True
    )
    redemption_date = fields.Datetime(
        string='Redemption Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )
    points_used = fields.Integer(
        string='Points Used',
        required=True,
        tracking=True
    )
    
    # Status
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='pending', tracking=True, required=True)
    
    # Processing Info
    redeemed_by_user_id = fields.Many2one('res.users', string='Processed By', default=lambda self: self.env.user)
    expiry_date = fields.Date(string='Expiry Date', help='When this redemption expires')
    
    # Delivery Info
    delivery_address = fields.Text(string='Delivery Address')
    tracking_number = fields.Char(string='Tracking Number')
    delivery_date = fields.Datetime(string='Delivery Date', readonly=True)
    
    # Notes
    processing_notes = fields.Text(string='Processing Notes')
    
    # Manual Redemption Helper Fields
    customer_current_points = fields.Integer(
        string='Customer Points',
        related='customer_id.total_points',
        readonly=True
    )
    reward_available_stock = fields.Integer(
        string='Available Stock',
        related='reward_id.available_stock',
        readonly=True
    )
    
    # Validation Fields untuk Manual Redemption
    sufficient_points = fields.Boolean(
        string='Sufficient Points',
        compute='_compute_manual_redemption_validation'
    )
    can_process_redemption = fields.Boolean(
        string='Can Process',
        compute='_compute_manual_redemption_validation'
    )
    
    @api.depends('customer_current_points', 'points_used', 'reward_available_stock')
    def _compute_manual_redemption_validation(self):
        """Compute validation untuk manual redemption"""
        for record in self:
            # Check sufficient points
            if record.customer_current_points and record.points_used:
                record.sufficient_points = record.customer_current_points >= record.points_used
            else:
                record.sufficient_points = False
            
            # Check stock
            stock_ok = record.reward_available_stock > 0 if record.reward_id else False
            
            # Overall validation
            record.can_process_redemption = record.sufficient_points and stock_ok
    
    @api.model
    def create(self, vals):
        """Generate redemption code saat create"""
        if not vals.get('redemption_code'):
            vals['redemption_code'] = self._generate_redemption_code()
        
        # Auto-set points dari reward jika belum diisi
        if vals.get('reward_id') and not vals.get('points_used'):
            reward = self.env['pitcar.rewards.catalog'].browse(vals['reward_id'])
            vals['points_used'] = reward.points_required
        
        return super().create(vals)
    
    def _generate_redemption_code(self):
        """Generate unique redemption code"""
        sequence = self.env['ir.sequence'].next_by_code('pitcar.points.redemption') or '001'
        return f"RDM{fields.Date.today().strftime('%y%m%d')}{sequence}"
    
    @api.onchange('reward_id')
    def _onchange_reward_id(self):
        """Auto-fill points dan alamat"""
        if self.reward_id:
            self.points_used = self.reward_id.points_required
            
            # Auto-fill delivery address
            if self.customer_id and self.customer_id.partner_id:
                partner = self.customer_id.partner_id
                address_parts = []
                if partner.street:
                    address_parts.append(partner.street)
                if partner.street2:
                    address_parts.append(partner.street2)
                if partner.city:
                    address_parts.append(partner.city)
                if partner.zip:
                    address_parts.append(partner.zip)
                self.delivery_address = '\n'.join(address_parts) if address_parts else ''
    
    def action_process_manual_redemption(self):
        """Process manual redemption langsung"""
        self.ensure_one()
        
        # Basic validation
        if not self.customer_id:
            raise UserError(_('Please select a customer.'))
        if not self.reward_id:
            raise UserError(_('Please select a reward.'))
        if not self.sufficient_points:
            raise UserError(_('Customer does not have sufficient points.'))
        if self.reward_available_stock <= 0:
            raise UserError(_('Reward is out of stock.'))
        
        try:
            # 1. Create points transaction
            self.env['pitcar.points.transaction'].create({
                'customer_id': self.customer_id.id,
                'transaction_type': 'redeem',
                'points': -self.points_used,
                'description': f'Manual redemption: {self.reward_name}',
                'reference_code': self.redemption_code,
                'status': 'active'
            })
            
            # 2. Update redemption status
            self.write({
                'status': 'delivered',
                'delivery_date': fields.Datetime.now(),
                'processing_notes': f'Manual redemption by {self.env.user.name}\n{self.processing_notes or ""}'
            })
            
            # 3. Update stock
            if self.reward_id.stock_quantity >= 0:
                self.reward_id._compute_available_stock()
            
            # 4. Success notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Manual Redemption Success!',
                    'message': f'Customer: {self.customer_name}\nReward: {self.reward_name}\nPoints deducted: {self.points_used}',
                    'type': 'success',
                    'sticky': True
                }
            }
            
        except Exception as e:
            _logger.error(f"Manual redemption error: {str(e)}")
            raise UserError(f'Failed to process: {str(e)}')
    
    def action_approve(self):
        """Approve redemption"""
        for redemption in self:
            if redemption.status == 'pending':
                redemption.status = 'approved'
    
    def action_deliver(self):
        """Mark as delivered"""
        for redemption in self:
            if redemption.status == 'approved':
                redemption.write({
                    'status': 'delivered',
                    'delivery_date': fields.Datetime.now()
                })
    
    def action_cancel(self):
        """Cancel redemption"""
        for redemption in self:
            if redemption.status in ['pending', 'approved']:
                redemption.status = 'cancelled'

# Update PitcarLoyaltyCustomer untuk point-based membership
class PitcarLoyaltyCustomer(models.Model):
    _inherit = 'pitcar.loyalty.customer'
    
    # Override membership computation untuk point-based system
    def _update_membership_level(self):
        """Update membership level berdasarkan lifetime points (bukan spending)"""        
        for customer in self:
            old_level = customer.membership_level
            
            # Point-based membership sesuai gambar
            if customer.lifetime_points >= 1000:
                new_level = 'platinum'
            elif customer.lifetime_points >= 500:
                new_level = 'gold'
            elif customer.lifetime_points >= 250:
                new_level = 'silver'
            else:
                new_level = 'bronze'
            
            if old_level != new_level:
                customer.membership_level = new_level
                # Log membership level up
                self.env['pitcar.points.transaction'].create({
                    'customer_id': customer.id,
                    'transaction_type': 'level_up',
                    'points': 0,
                    'description': f'Membership level upgraded from {old_level} to {new_level} (based on {customer.lifetime_points} lifetime points)',
                    'status': 'active'
                })
                _logger.info(f"Customer {customer.display_name} level up: {old_level} → {new_level}")
    
    # Add redemption relations
    redemption_ids = fields.One2many('pitcar.points.redemption', 'customer_id', string='Redemption History')
    total_redeemed_points = fields.Integer(string='Total Redeemed Points', compute='_compute_redemption_stats')
    successful_redemptions = fields.Integer(string='Successful Redemptions', compute='_compute_redemption_stats')
    
    @api.depends('redemption_ids', 'redemption_ids.status', 'redemption_ids.points_used')
    def _compute_redemption_stats(self):
        for customer in self:
            successful = customer.redemption_ids.filtered(lambda r: r.status in ['approved', 'delivered'])
            customer.successful_redemptions = len(successful)
            customer.total_redeemed_points = sum(successful.mapped('points_used'))
    
    def action_redeem_reward(self, reward_id):
        """
        Redeem reward dengan validasi lengkap
        """
        self.ensure_one()
        reward = self.env['pitcar.rewards.catalog'].browse(reward_id)
        
        # Check reward availability
        available, message = reward.is_available_for_redemption(self.id)
        if not available:
            raise UserError(_(message))
        
        # Check customer points
        if self.total_points < reward.points_required:
            raise UserError(_('Insufficient points. Required: %d, Available: %d') % (reward.points_required, self.total_points))
        
        # Create redemption
        redemption = self.env['pitcar.points.redemption'].create({
            'customer_id': self.id,
            'reward_id': reward.id,
            'points_used': reward.points_required,
        })
        
        return redemption