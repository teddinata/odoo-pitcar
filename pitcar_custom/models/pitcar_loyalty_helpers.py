from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class PitcarLoyaltyHelpers(models.AbstractModel):
    """
    Helper methods untuk loyalty system integration
    """
    _name = 'pitcar.loyalty.helpers'
    _description = 'Pitcar Loyalty System Helpers'
    
    @api.model
    def register_new_customer_with_referral(self, customer_data, referrer_referral_code=None, source_channel='direct'):
        """
        Register new customer dengan referral code
        
        Args:
            customer_data (dict): Data customer baru {name, phone, email, etc}
            referrer_referral_code (str): Kode referral dari referrer
            source_channel (str): Channel source referral
            
        Returns:
            dict: {success, partner_id, loyalty_customer_id, referral_tracking_id, message}
        """
        try:
            # 1. Create or find partner
            partner = self._create_or_find_partner(customer_data)
            
            # 2. Create loyalty customer
            loyalty_customer = self.env['pitcar.loyalty.customer'].get_or_create_loyalty_customer(partner.id)
            
            result = {
                'success': True,
                'partner_id': partner.id,
                'loyalty_customer_id': loyalty_customer.id,
                'referral_tracking_id': None,
                'message': f'Customer {partner.name} registered successfully'
            }
            
            # 3. Process referral jika ada kode referral
            if referrer_referral_code:
                referral_result = self._process_referral_registration(
                    partner.id, 
                    referrer_referral_code, 
                    source_channel
                )
                
                if referral_result['success']:
                    result['referral_tracking_id'] = referral_result['tracking_id']
                    result['message'] += f" with referral from {referral_result['referrer_name']}"
                else:
                    result['message'] += f" (referral failed: {referral_result['message']})"
            
            _logger.info(f"Successfully registered customer: {result['message']}")
            return result
            
        except Exception as e:
            _logger.error(f"Error registering customer: {str(e)}")
            return {
                'success': False,
                'partner_id': None,
                'loyalty_customer_id': None,
                'referral_tracking_id': None,
                'message': f'Registration failed: {str(e)}'
            }
    
    @api.model
    def _create_or_find_partner(self, customer_data):
        """Create or find existing partner"""
        
        # Required fields
        if not customer_data.get('name'):
            raise ValidationError(_("Customer name is required"))
        
        # Search existing partner by phone or email
        domain = []
        if customer_data.get('phone'):
            domain.append(('phone', '=', customer_data['phone']))
        if customer_data.get('mobile'):
            domain.append(('mobile', '=', customer_data['mobile']))
        if customer_data.get('email'):
            domain.append(('email', '=', customer_data['email']))
        
        if domain:
            partner = self.env['res.partner'].search(['|'] * (len(domain) - 1) + domain, limit=1)
            if partner:
                _logger.info(f"Found existing partner: {partner.name}")
                return partner
        
        # Create new partner
        partner_vals = {
            'name': customer_data['name'],
            'is_company': False,
            'customer_rank': 1,
            'supplier_rank': 0
        }
        
        # Optional fields
        optional_fields = ['phone', 'mobile', 'email', 'street', 'city', 'zip', 'state_id', 'country_id']
        for field in optional_fields:
            if customer_data.get(field):
                partner_vals[field] = customer_data[field]
        
        partner = self.env['res.partner'].create(partner_vals)
        _logger.info(f"Created new partner: {partner.name}")
        
        return partner
    
    @api.model
    def _process_referral_registration(self, referee_partner_id, referrer_referral_code, source_channel):
        """Process referral saat customer registration"""
        
        try:
            # Find referrer by referral code
            referrer_loyalty = self.env['pitcar.loyalty.customer'].search([
                ('referral_code', '=', referrer_referral_code),
                ('is_active', '=', True)
            ], limit=1)
            
            if not referrer_loyalty:
                return {
                    'success': False,
                    'tracking_id': None,
                    'referrer_name': None,
                    'message': f'Referral code {referrer_referral_code} not found or inactive'
                }
            
            # Check if referrer sama dengan referee (self-referral)
            if referrer_loyalty.partner_id.id == referee_partner_id:
                return {
                    'success': False,
                    'tracking_id': None,
                    'referrer_name': referrer_loyalty.display_name,
                    'message': 'Self-referral is not allowed'
                }
            
            # Create referral tracking
            tracking = self.env['pitcar.referral.tracking'].create_referral_tracking(
                referrer_partner_id=referrer_loyalty.partner_id.id,
                referee_partner_id=referee_partner_id,
                source_channel=source_channel
            )
            
            if tracking:
                return {
                    'success': True,
                    'tracking_id': tracking.id,
                    'referrer_name': referrer_loyalty.display_name,
                    'message': f'Referral tracking created: {tracking.tracking_code}'
                }
            else:
                return {
                    'success': False,
                    'tracking_id': None,
                    'referrer_name': referrer_loyalty.display_name,
                    'message': 'Failed to create referral tracking'
                }
                
        except Exception as e:
            _logger.error(f"Error processing referral registration: {str(e)}")
            return {
                'success': False,
                'tracking_id': None,
                'referrer_name': None,
                'message': f'Referral processing error: {str(e)}'
            }
    
    @api.model
    def get_customer_loyalty_summary(self, partner_id):
        """Get comprehensive loyalty summary for a customer"""
        
        loyalty_customer = self.env['pitcar.loyalty.customer'].search([
            ('partner_id', '=', partner_id)
        ], limit=1)
        
        if not loyalty_customer:
            return {
                'has_loyalty': False,
                'message': 'Customer not enrolled in loyalty program'
            }
        
        # Get recent transactions
        recent_transactions = loyalty_customer.transaction_ids.search([
            ('customer_id', '=', loyalty_customer.id)
        ], limit=10, order='create_date desc')
        
        # Get referral stats
        referrals_made = loyalty_customer.referral_trackings_as_referrer
        referred_by = loyalty_customer.referral_trackings_as_referee
        
        return {
            'has_loyalty': True,
            'customer_id': loyalty_customer.id,
            'display_name': loyalty_customer.display_name,
            'referral_code': loyalty_customer.referral_code,
            'total_points': loyalty_customer.total_points,
            'membership_level': loyalty_customer.membership_level,
            'total_spent': loyalty_customer.total_spent,
            'total_orders': loyalty_customer.total_orders,
            'avg_order_value': loyalty_customer.avg_order_value,
            'referrals_made': len(referrals_made),
            'successful_referrals': len(referrals_made.filtered(lambda r: r.status == 'rewarded')),
            'referred_by_name': referred_by[0].referrer_name if referred_by else None,
            'recent_transactions': [
                {
                    'date': t.transaction_date,
                    'type': t.transaction_type,
                    'points': t.points,
                    'description': t.description
                } for t in recent_transactions
            ]
        }
    
    @api.model
    def validate_referral_code(self, referral_code):
        """Validate if referral code exists and is active"""
        
        if not referral_code:
            return {'valid': False, 'message': 'Referral code is required'}
        
        referrer = self.env['pitcar.loyalty.customer'].search([
            ('referral_code', '=', referral_code),
            ('is_active', '=', True)
        ], limit=1)
        
        if referrer:
            return {
                'valid': True,
                'referrer_id': referrer.id,
                'referrer_name': referrer.display_name,
                'message': f'Valid referral code from {referrer.display_name}'
            }
        else:
            return {
                'valid': False,
                'message': 'Invalid or inactive referral code'
            }
    
    @api.model
    def get_active_rewards_for_customer(self, partner_id):
        """Get available rewards yang bisa di-redeem customer"""
        
        loyalty_customer = self.env['pitcar.loyalty.customer'].search([
            ('partner_id', '=', partner_id)
        ], limit=1)
        
        if not loyalty_customer:
            return []
        
        # Get active rewards yang affordable
        available_rewards = self.env['pitcar.rewards.catalog'].search([
            ('is_active', '=', True),
            ('points_required', '<=', loyalty_customer.total_points),
            '|', ('valid_until', '=', False), ('valid_until', '>=', fields.Date.today()),
            '|', ('stock_quantity', '=', -1), ('available_stock', '>', 0)
        ])
        
        return [
            {
                'id': reward.id,
                'name': reward.name,
                'points_required': reward.points_required,
                'category': reward.category_id.name,
                'description': reward.description,
                'available_stock': reward.available_stock,
                'can_redeem': loyalty_customer.total_points >= reward.points_required
            } for reward in available_rewards
        ]