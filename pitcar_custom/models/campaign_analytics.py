# models/campaign_analytics.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class CampaignAnalytics(models.Model):
    _name = 'campaign.analytics'
    _description = 'Campaign Analytics Data'
    _order = 'date_start desc, id desc'
    _rec_name = 'campaign_name'

    # Basic Campaign Info
    campaign_name = fields.Char(
        string='Campaign Name',
        required=True,
        index=True,
        help='Nama kampanye iklan'
    )
    
    adset_name = fields.Char(
        string='Adset Name',
        required=True,
        index=True,
        help='Nama adset dalam kampanye'
    )
    
    ad_name = fields.Char(
        string='Ad Name',
        required=True,
        help='Nama iklan spesifik'
    )

    # Financial Metrics
    spend = fields.Float(
        string='Spend (Rp)',
        digits=(12, 2),
        help='Total pengeluaran untuk iklan'
    )
    
    cost_per_messaging_conversion = fields.Float(
        string='Cost per Messaging Conversion',
        digits=(12, 2),
        help='Biaya per konversi messaging'
    )
    
    cost_per_purchase = fields.Float(
        string='Cost per Purchase',
        digits=(12, 2),
        help='Biaya per pembelian'
    )
    
    cost_per_add_to_cart = fields.Float(
        string='Cost per Add to Cart',
        digits=(12, 2),
        help='Biaya per penambahan ke keranjang'
    )

    # Performance Metrics
    reach = fields.Integer(
        string='Reach',
        help='Jumlah orang yang melihat iklan'
    )
    
    impressions = fields.Integer(
        string='Impressions',
        help='Jumlah tayangan iklan'
    )
    
    frequency = fields.Float(
        string='Frequency',
        digits=(8, 6),
        help='Rata-rata berapa kali setiap orang melihat iklan'
    )
    
    cpm = fields.Float(
        string='CPM (Cost per Mille)',
        digits=(12, 6),
        help='Biaya per 1000 tayangan'
    )

    # Date Fields
    date_start = fields.Date(
        string='Start Date',
        required=True,
        index=True,
        help='Tanggal mulai kampanye'
    )
    
    date_stop = fields.Date(
        string='Stop Date', 
        required=True,
        index=True,
        help='Tanggal berakhir kampanye'
    )

    # Conversion Metrics
    messaging_conversation_started_7d = fields.Integer(
        string='Messaging Conversations (7d)',
        help='Jumlah percakapan yang dimulai dalam 7 hari'
    )
    
    purchase = fields.Integer(
        string='Purchases',
        help='Jumlah pembelian'
    )
    
    add_to_cart = fields.Integer(
        string='Add to Cart',
        help='Jumlah penambahan ke keranjang'
    )
    
    purchase_value = fields.Float(
        string='Purchase Value (Rp)',
        digits=(12, 2),
        help='Total nilai pembelian'
    )

    # Computed Fields
    campaign_duration = fields.Integer(
        string='Campaign Duration (Days)',
        compute='_compute_campaign_duration',
        store=True,
        help='Durasi kampanye dalam hari'
    )
    
    daily_spend = fields.Float(
        string='Daily Spend (Rp)',
        compute='_compute_daily_metrics',
        store=True,
        digits=(12, 2),
        help='Rata-rata pengeluaran per hari'
    )
    
    daily_reach = fields.Float(
        string='Daily Reach',
        compute='_compute_daily_metrics',
        store=True,
        digits=(12, 2),
        help='Rata-rata reach per hari'
    )
    
    roas = fields.Float(
        string='ROAS (Return on Ad Spend)',
        compute='_compute_roas',
        store=True,
        digits=(8, 2),
        help='Return on Ad Spend ratio'
    )
    
    conversion_rate = fields.Float(
        string='Conversion Rate (%)',
        compute='_compute_conversion_rate',
        store=True,
        digits=(8, 2),
        help='Tingkat konversi dari reach ke purchase'
    )

    # Classification Fields
    campaign_category = fields.Selection([
        ('ac_service', 'AC Service'),
        ('periodic_service', 'Servis Berkala'),
        ('flushing', 'Flushing'),
        ('tune_up', 'Tune Up'),
        ('oil_change', 'Ganti Oli'),
        ('other', 'Other')
    ], string='Campaign Category', compute='_compute_campaign_category', store=True)
    
    performance_rating = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'), 
        ('average', 'Average'),
        ('poor', 'Poor')
    ], string='Performance Rating', compute='_compute_performance_rating', store=True)

    # Meta Fields
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes', help='Catatan tambahan untuk kampanye')
    
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Created Date', readonly=True)

    # Constraints
    _sql_constraints = [
        ('positive_spend', 'CHECK(spend >= 0)', 'Spend must be positive'),
        ('positive_reach', 'CHECK(reach >= 0)', 'Reach must be positive'),
        ('positive_impressions', 'CHECK(impressions >= 0)', 'Impressions must be positive'),
        ('date_check', 'CHECK(date_stop >= date_start)', 'End date must be after start date'),
    ]

    @api.depends('date_start', 'date_stop')
    def _compute_campaign_duration(self):
        for record in self:
            if record.date_start and record.date_stop:
                record.campaign_duration = (record.date_stop - record.date_start).days + 1
            else:
                record.campaign_duration = 0

    @api.depends('spend', 'reach', 'campaign_duration')
    def _compute_daily_metrics(self):
        for record in self:
            duration = record.campaign_duration or 1
            record.daily_spend = record.spend / duration
            record.daily_reach = record.reach / duration

    @api.depends('purchase_value', 'spend')
    def _compute_roas(self):
        for record in self:
            if record.spend > 0:
                record.roas = record.purchase_value / record.spend
            else:
                record.roas = 0

    @api.depends('purchase', 'reach')
    def _compute_conversion_rate(self):
        for record in self:
            if record.reach > 0:
                record.conversion_rate = (record.purchase / record.reach) * 100
            else:
                record.conversion_rate = 0

    @api.depends('campaign_name')
    def _compute_campaign_category(self):
        for record in self:
            name_lower = record.campaign_name.lower() if record.campaign_name else ''
            
            if 'ac' in name_lower and 'cuci' in name_lower:
                record.campaign_category = 'ac_service'
            elif 'servis berkala' in name_lower or 'service berkala' in name_lower:
                record.campaign_category = 'periodic_service'
            elif 'flushing' in name_lower or 'kuras' in name_lower:
                record.campaign_category = 'flushing'
            elif 'tune up' in name_lower:
                record.campaign_category = 'tune_up'
            elif 'oli' in name_lower:
                record.campaign_category = 'oil_change'
            else:
                record.campaign_category = 'other'

    @api.depends('roas', 'conversion_rate', 'cpm')
    def _compute_performance_rating(self):
        for record in self:
            score = 0
            
            # ROAS scoring (40% weight)
            if record.roas >= 4:
                score += 40
            elif record.roas >= 3:
                score += 30
            elif record.roas >= 2:
                score += 20
            elif record.roas >= 1:
                score += 10
            
            # Conversion rate scoring (35% weight)
            if record.conversion_rate >= 5:
                score += 35
            elif record.conversion_rate >= 3:
                score += 25
            elif record.conversion_rate >= 1:
                score += 15
            elif record.conversion_rate >= 0.5:
                score += 10
            
            # CPM scoring (25% weight) - lower is better
            if record.cpm <= 10000:  # 10k IDR
                score += 25
            elif record.cpm <= 20000:  # 20k IDR
                score += 20
            elif record.cpm <= 30000:  # 30k IDR
                score += 15
            elif record.cpm <= 50000:  # 50k IDR
                score += 10
            
            # Assign rating based on total score
            if score >= 80:
                record.performance_rating = 'excellent'
            elif score >= 60:
                record.performance_rating = 'good'
            elif score >= 40:
                record.performance_rating = 'average'
            else:
                record.performance_rating = 'poor'

    @api.constrains('date_start', 'date_stop')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_stop and record.date_start > record.date_stop:
                raise ValidationError(_('Start date must be before or equal to stop date.'))

    @api.model
    def get_campaign_summary(self, date_from=None, date_to=None, category=None):
        """Get campaign performance summary"""
        domain = []
        
        if date_from:
            domain.append(('date_start', '>=', date_from))
        if date_to:
            domain.append(('date_stop', '<=', date_to))
        if category:
            domain.append(('campaign_category', '=', category))
            
        campaigns = self.search(domain)
        
        if not campaigns:
            return {
                'total_campaigns': 0,
                'total_spend': 0,
                'total_reach': 0,
                'total_purchases': 0,
                'avg_roas': 0,
                'avg_conversion_rate': 0
            }
        
        return {
            'total_campaigns': len(campaigns),
            'total_spend': sum(campaigns.mapped('spend')),
            'total_reach': sum(campaigns.mapped('reach')),
            'total_purchases': sum(campaigns.mapped('purchase')),
            'total_purchase_value': sum(campaigns.mapped('purchase_value')),
            'avg_roas': sum(campaigns.mapped('roas')) / len(campaigns),
            'avg_conversion_rate': sum(campaigns.mapped('conversion_rate')) / len(campaigns),
            'avg_cpm': sum(campaigns.mapped('cpm')) / len(campaigns),
            'by_category': campaigns.read_group(
                [('id', 'in', campaigns.ids)],
                ['campaign_category', 'spend:sum', 'reach:sum', 'purchase:sum'],
                ['campaign_category']
            )
        }

    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            name = f"{record.campaign_name} - {record.ad_name}"
            if record.date_start:
                name += f" ({record.date_start})"
            result.append((record.id, name))
        return result

    @api.model
    def create_from_csv_data(self, csv_data):
        """Helper method to create records from CSV data"""
        created_records = []
        errors = []
        
        for row_data in csv_data:
            try:
                record = self.create(row_data)
                created_records.append(record)
            except Exception as e:
                errors.append({
                    'data': row_data,
                    'error': str(e)
                })
                _logger.error(f"Error creating campaign record: {str(e)}")
        
        return {
            'created_records': created_records,
            'errors': errors,
            'success_count': len(created_records),
            'error_count': len(errors)
        }