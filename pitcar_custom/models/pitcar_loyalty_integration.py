from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLoyalty(models.Model):
    """
    Extend sale.order untuk integrasi loyalty system
    """
    _inherit = 'sale.order'
    
    # Loyalty Integration Fields
    loyalty_customer_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Loyalty Customer',
        compute='_compute_loyalty_customer',
        store=True,
        help='Link ke loyalty customer profile'
    )
    loyalty_points_earned = fields.Integer(
        string='Points Earned',
        compute='_compute_loyalty_points_earned',
        store=True,
        help='Points yang diperoleh dari order ini'
    )
    loyalty_points_transaction_id = fields.Many2one(
        'pitcar.points.transaction',
        string='Points Transaction',
        readonly=True,
        help='Transaction record untuk points dari order ini'
    )
    is_loyalty_processed = fields.Boolean(
        string='Loyalty Processed',
        default=False,
        help='Apakah loyalty points sudah diproses'
    )
    
    # === TAMBAHAN FIELDS UNTUK REFERRAL ===
    referral_code_used = fields.Char(
        string='Referral Code',
        help='Kode referral yang digunakan customer'
    )
    referrer_customer_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Referrer',
        help='Customer yang mereferensikan'
    )
    is_referral_order = fields.Boolean(
        string='Is Referral Order',
        default=False,
        help='Apakah ini order dari referral'
    )
    referral_bonus_given = fields.Boolean(
        string='Referral Bonus Given',
        default=False,
        help='Apakah bonus referral sudah diberikan'
    )
    
    # === FIELDS UNTUK VIEW ===
    membership_level = fields.Selection(
        related='loyalty_customer_id.membership_level',
        string='Membership Level',
        readonly=True
    )
    customer_current_points = fields.Integer(
        related='loyalty_customer_id.total_points',
        string='Current Points',
        readonly=True
    )
    points_earned_this_order = fields.Integer(
        string='Points to Earn',
        compute='_compute_points_earned_this_order',
        store=True
    )
    loyalty_points_processed = fields.Boolean(
        string='Points Processed',
        compute='_compute_loyalty_points_processed',
        search='_search_loyalty_points_processed'
    )
    
    # Referral Integration Fields
    referral_tracking_id = fields.Many2one(
        'pitcar.referral.tracking',
        string='Referral Tracking',
        readonly=True,
        help='Referral tracking jika customer ini adalah referee'
    )
    is_referral_qualifying = fields.Boolean(
        string='Referral Qualifying Transaction',
        compute='_compute_referral_qualifying',
        store=True,
        help='Apakah transaksi ini qualify untuk referral bonus'
    )

    @api.depends('partner_id')
    def _compute_loyalty_customer(self):
        """Get or create loyalty customer untuk partner"""
        for order in self:
            if order.partner_id:
                # Cari existing loyalty customer
                loyalty_customer = self.env['pitcar.loyalty.customer'].search([
                    ('partner_id', '=', order.partner_id.id)
                ], limit=1)
                
                if not loyalty_customer:
                    # Create loyalty customer baru jika belum ada
                    loyalty_customer = self.env['pitcar.loyalty.customer'].create({
                        'partner_id': order.partner_id.id
                    })
                    _logger.info(f"Created loyalty customer for {order.partner_id.name}")
                
                order.loyalty_customer_id = loyalty_customer.id
            else:
                order.loyalty_customer_id = False

    @api.depends('amount_total', 'state')
    def _compute_loyalty_points_earned(self):
        """Calculate points earned from this order"""
        for order in self:
            if order.state in ('sale', 'done') and order.amount_total > 0:
                config = self.env['pitcar.loyalty.config'].get_config()
                
                if config.is_system_active and order.amount_total >= config.min_transaction_for_points:
                    order.loyalty_points_earned = int(order.amount_total * config.points_per_rupiah)
                else:
                    order.loyalty_points_earned = 0
            else:
                order.loyalty_points_earned = 0
    
    @api.depends('amount_total', 'state')
    def _compute_points_earned_this_order(self):
        """Compute points yang akan diperoleh dari order ini"""
        for order in self:
            if order.state in ('sale', 'done') and order.amount_total > 0:
                config = self.env['pitcar.loyalty.config'].get_config()
                if config.is_system_active and order.amount_total >= config.min_transaction_for_points:
                    order.points_earned_this_order = int(order.amount_total * config.points_per_rupiah)
                else:
                    order.points_earned_this_order = 0
            else:
                order.points_earned_this_order = 0
    
    @api.depends('is_loyalty_processed', 'loyalty_points_transaction_id')
    def _compute_loyalty_points_processed(self):
        """Check if loyalty points sudah diproses"""
        for order in self:
            order.loyalty_points_processed = order.is_loyalty_processed or bool(order.loyalty_points_transaction_id)
    
    def _search_loyalty_points_processed(self, operator, value):
        """Search method untuk loyalty_points_processed"""
        if operator == '=' and value:
            # Cari order yang sudah diproses
            return ['|', ('is_loyalty_processed', '=', True), ('loyalty_points_transaction_id', '!=', False)]
        elif operator == '=' and not value:
            # Cari order yang belum diproses
            return [('is_loyalty_processed', '=', False), ('loyalty_points_transaction_id', '=', False)]
        else:
            return []

    @api.depends('amount_total', 'referral_tracking_id')
    def _compute_referral_qualifying(self):
        """Check if this transaction qualifies for referral bonus"""
        for order in self:
            if order.referral_tracking_id and order.amount_total > 0:
                program = self.env['pitcar.referral.program'].get_active_program()
                order.is_referral_qualifying = order.amount_total >= program.minimum_transaction
            else:
                order.is_referral_qualifying = False
    
    @api.onchange('referral_code_used')
    def _onchange_referral_code(self):
        """Validate referral code dan set referrer"""
        if self.referral_code_used:
            # Find referrer by code
            referrer = self.env['pitcar.loyalty.customer'].search([
                ('referral_code', '=', self.referral_code_used),
                ('is_active', '=', True)
            ], limit=1)
            
            if referrer:
                # Check self-referral
                if referrer.partner_id.id == self.partner_id.id:
                    self.referral_code_used = False
                    self.referrer_customer_id = False
                    return {
                        'warning': {
                            'title': 'Invalid Referral',
                            'message': 'You cannot use your own referral code!'
                        }
                    }
                
                self.referrer_customer_id = referrer.id
                self.is_referral_order = True
                
                return {
                    'warning': {
                        'title': 'Referral Code Valid',
                        'message': f'Referral from: {referrer.display_name}'
                    }
                }
            else:
                self.referrer_customer_id = False
                self.is_referral_order = False
                return {
                    'warning': {
                        'title': 'Invalid Code',
                        'message': 'Referral code not found or inactive'
                    }
                }
        else:
            self.referrer_customer_id = False
            self.is_referral_order = False

    def action_confirm(self):
        """Override confirm untuk process loyalty points dan referrals"""
        result = super().action_confirm()
        
        # Process loyalty points untuk setiap confirmed order
        for order in self:
            try:
                order._process_loyalty_points()
                # FIXED: Perbaiki referral processing
                order._process_referral_qualification_fixed()
            except Exception as e:
                _logger.error(f"Error processing loyalty for order {order.name}: {str(e)}")
                # Jangan break confirmation process, hanya log error
                
        return result

    def _process_loyalty_points(self):
        """Process loyalty points earning untuk order ini"""
        self.ensure_one()
        
        # Skip jika sudah diproses atau tidak ada customer
        if self.is_loyalty_processed or not self.loyalty_customer_id:
            return
        
        # Skip jika tidak ada points yang diperoleh
        if self.loyalty_points_earned <= 0:
            return
        
        try:
            # Create points transaction
            transaction = self.env['pitcar.points.transaction'].create({
                'customer_id': self.loyalty_customer_id.id,
                'sale_order_id': self.id,
                'transaction_type': 'earn',
                'points': self.loyalty_points_earned,
                'description': f'Points earned from order #{self.name}',
                'original_amount': self.amount_total,
                'status': 'active'
            })
            
            # Update spending di loyalty customer
            self.loyalty_customer_id.total_spent += self.amount_total
            
            # Mark sebagai processed
            self.write({
                'loyalty_points_transaction_id': transaction.id,
                'is_loyalty_processed': True
            })
            
            _logger.info(f"Processed {self.loyalty_points_earned} loyalty points for order {self.name}")
            
        except Exception as e:
            _logger.error(f"Error creating loyalty points for order {self.name}: {str(e)}")

    def _process_referral_qualification_fixed(self):
        """FIXED: Process referral qualification untuk order ini"""
        self.ensure_one()
        
        if not self.loyalty_customer_id:
            return
        
        # FIXED: Jika ini referral order, create tracking dulu
        if self.is_referral_order and self.referrer_customer_id and not self.referral_tracking_id:
            try:
                # Create referral tracking
                tracking = self._create_referral_tracking()
                if tracking:
                    self.referral_tracking_id = tracking.id
                    _logger.info(f"Created referral tracking {tracking.tracking_code} for order {self.name}")
            except Exception as e:
                _logger.error(f"Error creating referral tracking: {str(e)}")
                return
        
        # Process qualification jika ada tracking
        if self.referral_tracking_id:
            try:
                # Check qualification
                result = self.env['pitcar.referral.tracking'].process_qualifying_transaction(
                    self.partner_id.id,
                    self.id,
                    self.amount_total
                )
                
                if result and result['qualified']:
                    self.referral_bonus_given = True
                    _logger.info(f"Referral qualified for order {self.name}: {result['message']}")
                    
                    # Post message ke order
                    self.message_post(
                        body=f"🎉 Referral bonus awarded! {result['message']}"
                    )
                    
            except Exception as e:
                _logger.error(f"Error processing referral for order {self.name}: {str(e)}")
    
    def _create_referral_tracking(self):
        """Create referral tracking untuk order ini"""
        self.ensure_one()
        
        if not self.is_referral_order or not self.referrer_customer_id:
            return False
        
        # Check if tracking already exists
        existing = self.env['pitcar.referral.tracking'].search([
            ('referrer_id', '=', self.referrer_customer_id.id),
            ('referee_id', '=', self.loyalty_customer_id.id),
            ('status', 'in', ['registered', 'qualified', 'rewarded'])
        ], limit=1)
        
        if existing:
            return existing
        
        # Create new tracking
        program = self.env['pitcar.referral.program'].get_active_program()
        
        tracking = self.env['pitcar.referral.tracking'].create({
            'program_id': program.id,
            'referrer_id': self.referrer_customer_id.id,
            'referee_id': self.loyalty_customer_id.id,
            'referral_code_used': self.referral_code_used,
            'source_channel': 'direct'
        })
        
        # Update referee's referred_by
        self.loyalty_customer_id.referred_by_id = self.referrer_customer_id.id
        
        return tracking

    def action_view_loyalty_customer(self):
        """Action untuk melihat loyalty customer profile"""
        self.ensure_one()
        if not self.loyalty_customer_id:
            raise UserError(_("No loyalty customer associated with this order"))
        
        return {
            'name': f'Loyalty Customer - {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.loyalty.customer',
            'view_mode': 'form',
            'res_id': self.loyalty_customer_id.id,
            'target': 'current'
        }

    def action_view_points_transaction(self):
        """Action untuk melihat points transaction"""
        self.ensure_one()
        if not self.loyalty_points_transaction_id:
            raise UserError(_("No points transaction associated with this order"))
        
        return {
            'name': f'Points Transaction - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.points.transaction',
            'view_mode': 'form',
            'res_id': self.loyalty_points_transaction_id.id,
            'target': 'new'
        }
    
    # === METHODS UNTUK VIEW ===
    def action_view_loyalty_points(self):
        """View points history for this customer"""
        self.ensure_one()
        if not self.loyalty_customer_id:
            raise UserError(_("No loyalty customer found"))
            
        return {
            'name': f'Points History - {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.points.transaction',
            'view_mode': 'tree,form',
            'domain': [('customer_id', '=', self.loyalty_customer_id.id)],
            'context': {'default_customer_id': self.loyalty_customer_id.id}
        }
    
    def action_view_referral_history(self):
        """View referral history for this customer"""
        self.ensure_one()
        if not self.loyalty_customer_id:
            raise UserError(_("No loyalty customer found"))
            
        return {
            'name': f'Referral History - {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.referral.tracking',
            'view_mode': 'tree,form',
            'domain': ['|', ('referrer_id', '=', self.loyalty_customer_id.id), 
                      ('referee_id', '=', self.loyalty_customer_id.id)],
        }

    def action_manual_process_loyalty(self):
        """Manual action untuk process loyalty (untuk debug/fix)"""
        self.ensure_one()
        
        if self.state not in ('sale', 'done'):
            raise UserError(_("Order must be confirmed to process loyalty"))
        
        # Reset processed flag
        self.is_loyalty_processed = False
        
        # Re-process
        self._process_loyalty_points()
        self._process_referral_qualification_fixed()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Loyalty processing completed for order {self.name}',
                'type': 'success'
            }
        }


class ResPartnerLoyalty(models.Model):
    """
    Extend res.partner untuk loyalty integration
    """
    _inherit = 'res.partner'
    
    # Computed fields untuk menampilkan loyalty info
    loyalty_customer_id = fields.One2many(
        'pitcar.loyalty.customer',
        'partner_id',
        string='Loyalty Profile'
    )
    loyalty_points = fields.Integer(
        string='Loyalty Points',
        compute='_compute_loyalty_info',
        help='Current active loyalty points'
    )
    loyalty_level = fields.Selection([
        ('bronze', '🥉 Bronze'),
        ('silver', '🥈 Silver'),
        ('gold', '🥇 Gold'),
        ('platinum', '💎 Platinum')
    ], string='Loyalty Level', compute='_compute_loyalty_info')
    
    loyalty_referral_code = fields.Char(
        string='My Referral Code',
        compute='_compute_loyalty_info',
        help='Unique referral code for this customer'
    )

    @api.depends('loyalty_customer_id', 'loyalty_customer_id.total_points', 
                 'loyalty_customer_id.membership_level', 'loyalty_customer_id.referral_code')
    def _compute_loyalty_info(self):
        for partner in self:
            if partner.loyalty_customer_id:
                loyalty = partner.loyalty_customer_id[0]
                partner.loyalty_points = loyalty.total_points
                partner.loyalty_level = loyalty.membership_level
                partner.loyalty_referral_code = loyalty.referral_code
            else:
                partner.loyalty_points = 0
                partner.loyalty_level = 'bronze'
                partner.loyalty_referral_code = False

    def action_view_loyalty_profile(self):
        """Action untuk melihat loyalty profile"""
        self.ensure_one()
        
        # Get or create loyalty customer
        loyalty_customer = self.env['pitcar.loyalty.customer'].get_or_create_loyalty_customer(self.id)
        
        if not loyalty_customer:
            raise UserError(_("Unable to create loyalty profile"))
        
        return {
            'name': f'Loyalty Profile - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.loyalty.customer',
            'view_mode': 'form',
            'res_id': loyalty_customer.id,
            'target': 'current'
        }

    def action_create_referral_link(self, referee_partner_id, source_channel='direct'):
        """
        Helper method untuk create referral link
        Dipanggil dari external systems (WhatsApp bot, website, etc.)
        """
        self.ensure_one()
        
        # Get loyalty customer for referrer
        referrer_loyalty = self.env['pitcar.loyalty.customer'].get_or_create_loyalty_customer(self.id)
        
        if not referrer_loyalty:
            raise UserError(_("Unable to create loyalty profile for referrer"))
        
        # Create referral tracking
        tracking = self.env['pitcar.referral.tracking'].create_referral_tracking(
            referrer_partner_id=self.id,
            referee_partner_id=referee_partner_id,
            source_channel=source_channel
        )
        
        return tracking