from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """
    Extend Sale Order dengan Loyalty System & Referral - Integrated dengan Pitcar Loyalty Core
    """
    _inherit = 'sale.order'
    
    # Loyalty Customer Relation
    loyalty_customer_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Loyalty Customer',
        compute='_compute_loyalty_customer',
        store=True
    )
    
    # Membership Level (dari loyalty customer)
    membership_level = fields.Selection(
        related='loyalty_customer_id.membership_level',
        string='Membership Level',
        store=True,
        readonly=True
    )
    
    # Points Information
    customer_current_points = fields.Integer(
        related='loyalty_customer_id.total_points',
        string='Customer Points',
        readonly=True
    )
    
    points_earned_this_order = fields.Integer(
        string='Points to Earn',
        compute='_compute_points_earned',
        store=True,
        help='Points yang akan didapat dari order ini'
    )
    
    # Referral System
    referral_code_used = fields.Char(
        string='Referral Code',
        help='Enter referral code if customer was referred by someone'
    )
    
    referrer_customer_id = fields.Many2one(
        'pitcar.loyalty.customer',
        string='Referred By',
        readonly=True,
        help='Customer who referred this sale'
    )
    
    is_referral_order = fields.Boolean(
        string='Is Referral Order',
        compute='_compute_referral_info',
        store=True
    )
    
    referral_bonus_given = fields.Boolean(
        string='Referral Bonus Given',
        default=False,
        help='Track if referral bonus has been processed'
    )
    
    # Loyalty Processing Status
    loyalty_points_processed = fields.Boolean(
        string='Loyalty Points Processed',
        default=False
    )
    
    @api.depends('partner_id')
    def _compute_loyalty_customer(self):
        """Find or create loyalty customer for partner - konsisten dengan Core"""
        for order in self:
            if order.partner_id:
                # Gunakan method dari loyalty core
                loyalty_customer = self.env['pitcar.loyalty.customer'].get_or_create_loyalty_customer(
                    order.partner_id.id
                )
                order.loyalty_customer_id = loyalty_customer.id if loyalty_customer else False
            else:
                order.loyalty_customer_id = False
    
    @api.depends('amount_total', 'loyalty_customer_id', 'loyalty_customer_id.membership_level')
    def _compute_points_earned(self):
        """Calculate points menggunakan config dari Loyalty Core"""
        for order in self:
            if order.loyalty_customer_id and order.amount_total:
                # Gunakan config dari loyalty core
                config = self.env['pitcar.loyalty.config'].get_config()
                
                # **DEBUG: Log calculation**
                _logger.info(f"=== POINTS CALCULATION DEBUG ===")
                _logger.info(f"Order: {order.name}")
                _logger.info(f"Amount: {order.amount_total}")
                _logger.info(f"Customer: {order.loyalty_customer_id.display_name}")
                _logger.info(f"Membership Level: {order.membership_level}")
                _logger.info(f"Points per Rupiah: {config.points_per_rupiah}")
                
                # Base points calculation
                base_points = int(order.amount_total * config.points_per_rupiah)
                _logger.info(f"Base Points: {base_points}")
                
                # Apply membership multiplier
                multiplier = config.get_points_multiplier(order.membership_level or 'bronze')
                _logger.info(f"Multiplier: {multiplier}")
                
                final_points = int(base_points * multiplier)
                _logger.info(f"Final Points: {final_points}")
                
                order.points_earned_this_order = final_points
                
            else:
                order.points_earned_this_order = 0
    
    @api.depends('referral_code_used')
    def _compute_referral_info(self):
        """Compute referral information"""
        for order in self:
            if order.referral_code_used:
                # Cari referrer dari kode
                referrer = self.env['pitcar.loyalty.customer'].search([
                    ('referral_code', '=', order.referral_code_used),
                    ('status', '=', 'active')
                ], limit=1)
                
                if referrer:
                    order.referrer_customer_id = referrer.id
                    order.is_referral_order = True
                else:
                    order.referrer_customer_id = False
                    order.is_referral_order = False
            else:
                order.referrer_customer_id = False
                order.is_referral_order = False
    
    @api.onchange('referral_code_used')
    def _onchange_referral_code(self):
        """Validate referral code dan auto-create tracking saat diinput"""
        if self.referral_code_used:
            # Cari referrer dari kode
            referrer = self.env['pitcar.loyalty.customer'].search([
                ('referral_code', '=', self.referral_code_used),
                ('status', '=', 'active')
            ], limit=1)
            
            if not referrer:
                self.referral_code_used = False
                return {
                    'warning': {
                        'title': 'Invalid Referral Code',
                        'message': f'Kode Referral "{self.referral_code_used}" tidak ditemukan atau tidak aktif. Silakan periksa kembali.'
                    }
                }
            
            # Check jangan self-referral
            if referrer.partner_id == self.partner_id:
                self.referral_code_used = False
                return {
                    'warning': {
                        'title': 'Invalid Referral',
                        'message': 'Customer tidak bisa menggunakan kode referral sendiri.'
                    }
                }
            
            # Set referrer
            self.referrer_customer_id = referrer.id
            
            # **DEBUG: Log untuk tracking**
            _logger.info(f"=== REFERRAL CODE VALIDATION ===")
            _logger.info(f"Code: {self.referral_code_used}")
            _logger.info(f"Referrer: {referrer.display_name}")
            _logger.info(f"Referee: {self.partner_id.name}")
            _logger.info(f"Loyalty Customer: {self.loyalty_customer_id.display_name if self.loyalty_customer_id else 'None'}")
            
            # Auto-create referral tracking jika belum ada
            if self.loyalty_customer_id:
                existing_tracking = self.env['pitcar.referral.tracking'].search([
                    ('referee_id', '=', self.loyalty_customer_id.id),
                    ('status', '=', 'registered')
                ], limit=1)
                
                _logger.info(f"Existing tracking: {existing_tracking.tracking_code if existing_tracking else 'None'}")
                
                if not existing_tracking:
                    try:
                        # **PERBAIKAN: Pastikan method dipanggil dengan benar**
                        tracking = self.env['pitcar.referral.tracking'].create_referral_tracking(
                            referrer_partner_id=referrer.partner_id.id,
                            referee_partner_id=self.partner_id.id,
                            source_channel='sale_order'  # Ubah dari 'direct' ke 'sale_order'
                        )
                        
                        if tracking:
                            # Update referee's referred_by
                            self.loyalty_customer_id.referred_by_id = referrer.id
                            _logger.info(f"✅ Created referral tracking {tracking.tracking_code} for SO {self.name}")
                            
                            # **TAMBAHAN: Post notification**
                            self.message_post(
                                body=f"🔗 Referral tracking created: {tracking.tracking_code} (Referrer: {referrer.display_name})"
                            )
                        else:
                            _logger.error(f"❌ Failed to create referral tracking for SO {self.name}")
                            
                    except Exception as e:
                        _logger.error(f"❌ Error creating referral tracking: {str(e)}")
                        import traceback
                        _logger.error(traceback.format_exc())
            else:
                _logger.warning(f"⚠️ No loyalty customer found for partner {self.partner_id.name}")
        else:
            self.referrer_customer_id = False
    
    def action_confirm(self):
        """Override confirm untuk process loyalty points dan referral"""
        result = super().action_confirm()
        
        for order in self:
            # Process loyalty points
            if order.loyalty_customer_id and not order.loyalty_points_processed:
                order._process_loyalty_points()
            
            # Process referral bonus
            if order.is_referral_order and not order.referral_bonus_given:
                order._process_referral_bonus()
        
        return result
    
    def _process_loyalty_points(self):
        """Process loyalty points menggunakan method dari Loyalty Core"""
        self.ensure_one()
        
        if not self.loyalty_customer_id or self.loyalty_points_processed:
            return
        
        try:
            # Check loyalty system active
            config = self.env['pitcar.loyalty.config'].get_config()
            if not config.is_system_active:
                _logger.warning(f"Loyalty system inactive - skipping points for SO {self.name}")
                return
            
            # Check minimum transaction
            if self.amount_total < config.min_transaction_for_points:
                _logger.info(f"SO {self.name} amount {self.amount_total} below minimum {config.min_transaction_for_points}")
                self.loyalty_points_processed = True
                return
            
            # Use helper method dari Points Transaction model
            transaction = self.env['pitcar.points.transaction'].create_earning_transaction(
                partner_id=self.partner_id.id,
                sale_order_id=self.id,
                amount=self.amount_total
            )
            
            if transaction:
                self.loyalty_points_processed = True
                _logger.info(f"Loyalty points processed for SO {self.name}: {transaction.points} points via transaction {transaction.reference_code}")
                
                # Post message ke order dengan format konsisten
                self.message_post(
                    body=f"💰 Loyalty Points Earned: {transaction.points} points (Transaction: {transaction.reference_code})"
                )
            else:
                _logger.warning(f"Failed to create earning transaction for SO {self.name}")
            
        except Exception as e:
            _logger.error(f"Error processing loyalty points for SO {self.name}: {str(e)}")
    
    def _process_referral_bonus(self):
        """Process referral bonus menggunakan method dari Referral Core"""
        self.ensure_one()
        
        if not self.is_referral_order or self.referral_bonus_given:
            _logger.info(f"Skipping referral bonus for {self.name}: is_referral={self.is_referral_order}, bonus_given={self.referral_bonus_given}")
            return
        
        try:
            # **DEBUG: Log referral processing**
            _logger.info(f"=== REFERRAL BONUS PROCESSING ===")
            _logger.info(f"Order: {self.name}")
            _logger.info(f"Partner: {self.partner_id.name}")
            _logger.info(f"Amount: {self.amount_total}")
            _logger.info(f"Referrer: {self.referrer_customer_id.display_name if self.referrer_customer_id else 'None'}")
            _logger.info(f"Referral Code Used: {self.referral_code_used}")
            
            # Use helper method dari Referral Tracking model
            referral_result = self.env['pitcar.referral.tracking'].process_qualifying_transaction(
                self.partner_id.id,
                self.id,
                self.amount_total
            )
            
            _logger.info(f"Referral result: {referral_result}")
            
            if referral_result and referral_result.get('qualified'):
                self.referral_bonus_given = True
                tracking = referral_result['tracking']
                
                _logger.info(f"✅ Referral bonus processed for SO {self.name}: {referral_result['message']}")
                
                # Post message ke order dengan format konsisten
                self.message_post(
                    body=f"🎉 Referral Bonus Processed! Tracking: {tracking.tracking_code} - {referral_result['message']}"
                )
                
                # Post ke loyalty customers juga
                if self.referrer_customer_id:
                    self.referrer_customer_id.message_post(
                        body=f"👥 Referral Bonus Earned from SO {self.name}! Your referral {self.loyalty_customer_id.display_name} made a qualifying purchase."
                    )
                
            else:
                message = referral_result.get('message', 'Unknown reason') if referral_result else 'No referral result'
                _logger.info(f"⚠️ Referral not qualified for SO {self.name}: {message}")
            
        except Exception as e:
            _logger.error(f"❌ Error processing referral bonus for SO {self.name}: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
    
    def action_view_loyalty_customer(self):
        """View loyalty customer record"""
        self.ensure_one()
        if not self.loyalty_customer_id:
            raise UserError(_('No loyalty customer found for this order.'))
        
        return {
            'name': f'Loyalty Customer - {self.loyalty_customer_id.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.loyalty.customer',
            'view_mode': 'form',
            'res_id': self.loyalty_customer_id.id,
            'target': 'current'
        }
    
    def action_view_loyalty_points(self):
        """View loyalty points transactions untuk customer ini"""
        self.ensure_one()
        if not self.loyalty_customer_id:
            raise UserError(_('No loyalty customer found for this order.'))
        
        return {
            'name': f'Loyalty Points - {self.loyalty_customer_id.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.points.transaction',
            'view_mode': 'tree,form',
            'domain': [('customer_id', '=', self.loyalty_customer_id.id)],
            'context': {'create': False}
        }
    
    def action_view_referral_history(self):
        """View referral history untuk customer ini"""
        self.ensure_one()
        if not self.loyalty_customer_id:
            raise UserError(_('No loyalty customer found for this order.'))
        
        return {
            'name': f'Referral History - {self.loyalty_customer_id.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pitcar.referral.tracking',
            'view_mode': 'tree,form',
            'domain': ['|', ('referrer_id', '=', self.loyalty_customer_id.id), ('referee_id', '=', self.loyalty_customer_id.id)],
            'context': {'create': False}
        }
    
    def action_reprocess_loyalty(self):
        """Manual reprocess loyalty points (untuk debugging)"""
        self.ensure_one()
        
        if not self.loyalty_customer_id:
            raise UserError(_('No loyalty customer found for this order.'))
        
        # Reset flags
        self.loyalty_points_processed = False
        self.referral_bonus_given = False
        
        # Reprocess
        self._process_loyalty_points()
        
        if self.is_referral_order:
            self._process_referral_bonus()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Poin loyalty dan referral untuk order {self.name} telah diproses ulang.',
                'type': 'success'
            }
        }


class SaleOrderLine(models.Model):
    """
    Extend Sale Order Line - minimal extension, main logic di header
    """
    _inherit = 'sale.order.line'
    
    # Points calculation ada di order header level, tidak per line
    # Ini untuk menjaga simplicity dan konsistensi dengan loyalty core