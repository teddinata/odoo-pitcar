# wizard/campaign_import_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import csv
import io
import base64
from datetime import datetime

_logger = logging.getLogger(__name__)

class CampaignImportWizard(models.TransientModel):
    _name = 'campaign.import.wizard'
    _description = 'Campaign Analytics Import Wizard'

    import_type = fields.Selection([
        ('csv_file', 'Upload CSV File'),
        ('csv_text', 'Paste CSV Data'),
        ('manual', 'Manual Entry'),
        ('sample', 'Create Sample Data')
    ], string='Import Type', default='csv_file', required=True)

    csv_file = fields.Binary(string='CSV File', help='Upload CSV file containing campaign data')
    csv_filename = fields.Char(string='Filename')
    csv_data = fields.Text(string='CSV Data', help='Paste CSV content here')
    
    # Sample data options
    sample_count = fields.Integer(string='Number of Sample Records', default=5, help='Number of sample records to create')
    sample_category = fields.Selection([
        ('mixed', 'Mixed Categories'),
        ('ac_service', 'AC Service Only'),
        ('periodic_service', 'Periodic Service Only'),
        ('tune_up', 'Tune Up Only')
    ], string='Sample Category', default='mixed')

    # Results
    import_result = fields.Text(string='Import Result', readonly=True)
    success_count = fields.Integer(string='Success Count', readonly=True)
    error_count = fields.Integer(string='Error Count', readonly=True)
    created_campaign_ids = fields.Many2many('campaign.analytics', string='Created Campaigns', readonly=True)

    # Manual entry fields
    campaign_name = fields.Char(string='Campaign Name')
    adset_name = fields.Char(string='Adset Name')
    ad_name = fields.Char(string='Ad Name')
    spend = fields.Float(string='Spend')
    reach = fields.Integer(string='Reach')
    impressions = fields.Integer(string='Impressions')
    date_start = fields.Date(string='Start Date', default=fields.Date.today)
    date_stop = fields.Date(string='End Date', default=fields.Date.today)

    @api.onchange('import_type')
    def _onchange_import_type(self):
        """Clear fields when import type changes"""
        if self.import_type != 'csv_file':
            self.csv_file = False
            self.csv_filename = False
        if self.import_type != 'csv_text':
            self.csv_data = False

    def action_import(self):
        """Execute import based on selected type"""
        self.ensure_one()
        
        if self.import_type == 'csv_file':
            return self._import_from_file()
        elif self.import_type == 'csv_text':
            return self._import_from_text()
        elif self.import_type == 'manual':
            return self._import_manual()
        elif self.import_type == 'sample':
            return self._create_sample_data()

    def _import_from_file(self):
        """Import data from uploaded CSV file"""
        if not self.csv_file:
            raise ValidationError(_("Please upload a CSV file"))
        
        try:
            # Decode file content
            file_content = base64.b64decode(self.csv_file).decode('utf-8')
            return self._process_csv_content(file_content)
        except Exception as e:
            raise ValidationError(_("Error reading CSV file: %s") % str(e))

    def _import_from_text(self):
        """Import data from pasted CSV text"""
        if not self.csv_data:
            raise ValidationError(_("Please provide CSV data"))
        
        return self._process_csv_content(self.csv_data)

    def _process_csv_content(self, csv_content):
        """Process CSV content and create records"""
        try:
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            campaigns_data = []
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    campaign_values = self._parse_csv_row(row)
                    campaigns_data.append(campaign_values)
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

            if not campaigns_data:
                raise ValidationError(_("No valid data found in CSV"))

            # Create campaigns
            created_campaigns = []
            creation_errors = []

            for i, values in enumerate(campaigns_data):
                try:
                    campaign = self.env['campaign.analytics'].create(values)
                    created_campaigns.append(campaign)
                except Exception as e:
                    creation_errors.append(f"Record {i+1}: {str(e)}")

            # Update wizard with results
            result_text = f"Import completed!\n"
            result_text += f"Successfully created: {len(created_campaigns)} records\n"
            result_text += f"Errors: {len(errors) + len(creation_errors)}\n"
            
            if errors:
                result_text += f"\nParsing Errors:\n" + "\n".join(errors[:5])
            if creation_errors:
                result_text += f"\nCreation Errors:\n" + "\n".join(creation_errors[:5])

            self.write({
                'import_result': result_text,
                'success_count': len(created_campaigns),
                'error_count': len(errors) + len(creation_errors),
                'created_campaign_ids': [(6, 0, [c.id for c in created_campaigns])]
            })

            return self._return_wizard_action()

        except Exception as e:
            raise ValidationError(_("Error processing CSV: %s") % str(e))

    def _parse_csv_row(self, row):
        """Parse a single CSV row into campaign values"""
        # Field mapping from CSV headers to model fields
        field_mapping = {
            'campaign_name': 'campaign_name',
            'adset_name': 'adset_name',
            'ad_name': 'ad_name',
            'spend': 'spend',
            'reach': 'reach',
            'impressions': 'impressions',
            'frequency': 'frequency',
            'cpm': 'cpm',
            'date_start': 'date_start',
            'date_stop': 'date_stop',
            'onsite_conversion.messaging_conversation_started_7d': 'messaging_conversation_started_7d',
            'cost_per_onsite_conversion.messaging_conversation_started_7d': 'cost_per_messaging_conversion',
            'purchase': 'purchase',
            'add_to_cart': 'add_to_cart',
            'cost_per_purchase': 'cost_per_purchase',
            'cost_per_add_to_cart': 'cost_per_add_to_cart',
            'purchase_value': 'purchase_value'
        }

        values = {}
        
        for csv_field, model_field in field_mapping.items():
            if csv_field in row and row[csv_field]:
                raw_value = row[csv_field].strip()
                
                if model_field in ['date_start', 'date_stop']:
                    values[model_field] = self._parse_date(raw_value)
                elif model_field in ['reach', 'impressions', 'messaging_conversation_started_7d', 'purchase', 'add_to_cart']:
                    values[model_field] = int(float(raw_value)) if raw_value else 0
                elif model_field in ['spend', 'frequency', 'cpm', 'cost_per_messaging_conversion',
                                   'cost_per_purchase', 'cost_per_add_to_cart', 'purchase_value']:
                    values[model_field] = float(raw_value) if raw_value else 0.0
                else:
                    values[model_field] = raw_value

        return values

    def _parse_date(self, date_string):
        """Parse date string to date object"""
        if not date_string:
            return fields.Date.today()
            
        date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_string, fmt).date()
            except ValueError:
                continue
        
        raise ValueError(f'Unable to parse date: {date_string}')

    def _import_manual(self):
        """Import single record from manual input"""
        # Validate required fields
        if not all([self.campaign_name, self.adset_name, self.ad_name, self.date_start, self.date_stop]):
            raise ValidationError(_("Please fill in all required fields"))

        values = {
            'campaign_name': self.campaign_name,
            'adset_name': self.adset_name,
            'ad_name': self.ad_name,
            'spend': self.spend,
            'reach': self.reach,
            'impressions': self.impressions,
            'date_start': self.date_start,
            'date_stop': self.date_stop,
        }

        try:
            campaign = self.env['campaign.analytics'].create(values)
            
            self.write({
                'import_result': f"Successfully created campaign: {campaign.campaign_name}",
                'success_count': 1,
                'error_count': 0,
                'created_campaign_ids': [(6, 0, [campaign.id])]
            })

            return self._return_wizard_action()

        except Exception as e:
            raise ValidationError(_("Error creating campaign: %s") % str(e))

    def _create_sample_data(self):
        """Create sample campaign data for testing"""
        sample_data = self._get_sample_data()
        created_campaigns = []
        errors = []

        for data in sample_data[:self.sample_count]:
            try:
                campaign = self.env['campaign.analytics'].create(data)
                created_campaigns.append(campaign)
            except Exception as e:
                errors.append(str(e))

        result_text = f"Created {len(created_campaigns)} sample campaigns"
        if errors:
            result_text += f"\nErrors: {len(errors)}"

        self.write({
            'import_result': result_text,
            'success_count': len(created_campaigns),
            'error_count': len(errors),
            'created_campaign_ids': [(6, 0, [c.id for c in created_campaigns])]
        })

        return self._return_wizard_action()

    def _get_sample_data(self):
        """Generate sample campaign data"""
        import random
        from datetime import timedelta

        base_date = fields.Date.today()
        
        if self.sample_category == 'mixed':
            categories = ['AC Service', 'Servis Berkala', 'Tune Up', 'Flushing', 'Ganti Oli']
        elif self.sample_category == 'ac_service':
            categories = ['AC Service']
        elif self.sample_category == 'periodic_service':
            categories = ['Servis Berkala']
        else:
            categories = ['Tune Up']

        sample_data = []
        
        for i in range(10):  # Generate 10 samples, wizard will limit by sample_count
            category = random.choice(categories)
            
            # Generate realistic data based on category
            if 'AC' in category:
                base_spend = random.randint(500000, 1000000)
                base_reach = random.randint(10000, 20000)
                purchase_rate = random.uniform(0.001, 0.005)
            elif 'Servis' in category:
                base_spend = random.randint(200000, 600000)
                base_reach = random.randint(8000, 15000)
                purchase_rate = random.uniform(0.002, 0.008)
            else:
                base_spend = random.randint(300000, 800000)
                base_reach = random.randint(5000, 12000)
                purchase_rate = random.uniform(0.001, 0.006)

            reach = base_reach + random.randint(-2000, 2000)
            impressions = int(reach * random.uniform(1.2, 2.5))
            purchases = int(reach * purchase_rate)
            
            data = {
                'campaign_name': f"{category} Campaign {i+1}",
                'adset_name': f"Target Audience {i+1}",
                'ad_name': f"Ad Creative {i+1}",
                'spend': base_spend + random.randint(-100000, 100000),
                'reach': reach,
                'impressions': impressions,
                'frequency': round(impressions / reach, 3),
                'cpm': round((base_spend / impressions) * 1000, 2),
                'date_start': base_date - timedelta(days=random.randint(1, 30)),
                'date_stop': base_date - timedelta(days=random.randint(0, 5)),
                'purchase': purchases,
                'purchase_value': purchases * random.randint(200000, 500000),
                'messaging_conversation_started_7d': random.randint(0, 10),
                'add_to_cart': random.randint(purchases, purchases * 3),
                'notes': f"Sample campaign data for {category} category"
            }
            sample_data.append(data)

        return sample_data

    def _return_wizard_action(self):
        """Return action to keep wizard open and show results"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'campaign.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }

    def action_view_created_campaigns(self):
        """View the created campaigns"""
        if not self.created_campaign_ids:
            raise UserError(_("No campaigns were created"))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Campaigns'),
            'res_model': 'campaign.analytics',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.created_campaign_ids.ids)],
            'context': {'create': False}
        }

    def action_download_template(self):
        """Download CSV template for import"""
        template_data = """campaign_name,adset_name,ad_name,spend,reach,impressions,frequency,cpm,date_start,date_stop,onsite_conversion.messaging_conversation_started_7d,cost_per_onsite_conversion.messaging_conversation_started_7d,purchase,add_to_cart,cost_per_purchase,cost_per_add_to_cart,purchase_value
AC Service Promo,Car Enthusiast,AC Cuci Tanpa Bongkar,791752,16181,18188,1.124,43521.67,2025-06-01,2025-06-01,0,0,0,0,0,0,0
Servis Berkala Juni,Car Owner,Hemat Service Berkala,143838,8410,10061,1.196,14297.21,2025-06-01,2025-06-01,0,0,0,0,0,0,0"""

        return {
            'type': 'ir.actions.act_url',
            'url': f'data:text/csv;base64,{base64.b64encode(template_data.encode()).decode()}',
            'target': 'new',
        }