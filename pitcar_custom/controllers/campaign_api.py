# controllers/campaign_api.py
from odoo import http, fields
from odoo.http import request
import logging
import json
import csv
import io
import base64
from datetime import datetime, date
from odoo.exceptions import ValidationError, AccessError
from odoo.tools import float_utils

_logger = logging.getLogger(__name__)

class CampaignAnalyticsAPI(http.Controller):
    
    @http.route('/web/v1/campaign/analytics', type='json', auth='user', methods=['POST'], csrf=False)
    def campaign_analytics_operations(self, **kw):
        """Main endpoint for campaign analytics operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                return self._create_campaign_record(kw)
            elif operation == 'bulk_create':
                return self._bulk_create_campaigns(kw)
            elif operation == 'import_csv':
                return self._import_csv_data(kw)
            elif operation == 'get':
                return self._get_campaigns(kw)
            elif operation == 'update':
                return self._update_campaign(kw)
            elif operation == 'delete':
                return self._delete_campaign(kw)
            elif operation == 'summary':
                return self._get_campaign_summary(kw)
            else:
                return {
                    'status': 'error',
                    'message': f'Operation "{operation}" not supported'
                }
                
        except Exception as e:
            _logger.error('Error in campaign analytics API: %s', str(e))
            return {
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }

    def _create_campaign_record(self, data):
        """Create single campaign record"""
        try:
            # Validate required fields
            required_fields = ['campaign_name', 'adset_name', 'ad_name', 'date_start', 'date_stop']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return {
                    'status': 'error',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }
            
            # Prepare values for creation
            values = self._prepare_campaign_values(data)
            
            # Create campaign record
            campaign = request.env['campaign.analytics'].sudo().create(values)
            
            return {
                'status': 'success',
                'data': self._prepare_campaign_response(campaign),
                'message': f'Campaign "{campaign.campaign_name}" created successfully'
            }
            
        except ValidationError as ve:
            return {
                'status': 'error',
                'message': f'Validation error: {str(ve)}'
            }
        except Exception as e:
            _logger.error('Error creating campaign: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error creating campaign: {str(e)}'
            }

    def _bulk_create_campaigns(self, data):
        """Create multiple campaign records"""
        try:
            campaigns_data = data.get('campaigns', [])
            
            if not campaigns_data or not isinstance(campaigns_data, list):
                return {
                    'status': 'error',
                    'message': 'campaigns field must be a non-empty list'
                }
            
            created_campaigns = []
            errors = []
            
            for i, campaign_data in enumerate(campaigns_data):
                try:
                    values = self._prepare_campaign_values(campaign_data)
                    campaign = request.env['campaign.analytics'].sudo().create(values)
                    created_campaigns.append(self._prepare_campaign_response(campaign))
                    
                except Exception as e:
                    errors.append({
                        'index': i,
                        'data': campaign_data,
                        'error': str(e)
                    })
                    _logger.error(f'Error creating campaign at index {i}: {str(e)}')
            
            return {
                'status': 'partial_success' if errors else 'success',
                'data': {
                    'created_campaigns': created_campaigns,
                    'errors': errors
                },
                'message': f'Created {len(created_campaigns)} campaigns with {len(errors)} errors'
            }
            
        except Exception as e:
            _logger.error('Error in bulk create: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error in bulk creation: {str(e)}'
            }

    def _import_csv_data(self, data):
        """Import campaign data from CSV"""
        try:
            csv_data = data.get('csv_data')
            csv_file = data.get('csv_file')  # base64 encoded file
            
            if not csv_data and not csv_file:
                return {
                    'status': 'error',
                    'message': 'Either csv_data or csv_file must be provided'
                }
            
            # Parse CSV data
            if csv_file:
                # Decode base64 file
                try:
                    file_content = base64.b64decode(csv_file).decode('utf-8')
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Error decoding CSV file: {str(e)}'
                    }
            else:
                file_content = csv_data
            
            # Parse CSV
            campaigns_data = []
            csv_reader = csv.DictReader(io.StringIO(file_content))
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start from 2 because of header
                try:
                    campaign_values = self._parse_csv_row(row)
                    campaigns_data.append(campaign_values)
                except Exception as e:
                    _logger.error(f'Error parsing CSV row {row_num}: {str(e)}')
                    return {
                        'status': 'error',
                        'message': f'Error parsing CSV row {row_num}: {str(e)}'
                    }
            
            if not campaigns_data:
                return {
                    'status': 'error',
                    'message': 'No valid data found in CSV'
                }
            
            # Create campaigns using model method
            result = request.env['campaign.analytics'].sudo().create_from_csv_data(campaigns_data)
            
            return {
                'status': 'partial_success' if result['errors'] else 'success',
                'data': {
                    'success_count': result['success_count'],
                    'error_count': result['error_count'],
                    'errors': result['errors'][:10]  # Return first 10 errors
                },
                'message': f'Imported {result["success_count"]} campaigns with {result["error_count"]} errors'
            }
            
        except Exception as e:
            _logger.error('Error importing CSV: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error importing CSV: {str(e)}'
            }

    def _get_campaigns(self, data):
        """Get campaign records with filters"""
        try:
            # Build domain for filtering
            domain = []
            
            # Date filters
            if data.get('date_from'):
                domain.append(('date_start', '>=', data['date_from']))
            if data.get('date_to'):
                domain.append(('date_stop', '<=', data['date_to']))
            
            # Campaign filters
            if data.get('campaign_name'):
                domain.append(('campaign_name', 'ilike', data['campaign_name']))
            if data.get('campaign_category'):
                domain.append(('campaign_category', '=', data['campaign_category']))
            if data.get('performance_rating'):
                domain.append(('performance_rating', '=', data['performance_rating']))
            
            # Performance filters
            if data.get('min_spend'):
                domain.append(('spend', '>=', float(data['min_spend'])))
            if data.get('max_spend'):
                domain.append(('spend', '<=', float(data['max_spend'])))
            if data.get('min_roas'):
                domain.append(('roas', '>=', float(data['min_roas'])))
            
            # Pagination
            page = int(data.get('page', 1))
            limit = int(data.get('limit', 50))
            offset = (page - 1) * limit
            
            # Sorting
            order = data.get('order', 'date_start desc')
            
            # Get records
            campaigns = request.env['campaign.analytics'].sudo().search(
                domain, 
                limit=limit, 
                offset=offset, 
                order=order
            )
            
            # Get total count
            total_count = request.env['campaign.analytics'].sudo().search_count(domain)
            total_pages = (total_count + limit - 1) // limit
            
            return {
                'status': 'success',
                'data': {
                    'campaigns': [self._prepare_campaign_response(campaign) for campaign in campaigns],
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total_count,
                        'total_pages': total_pages
                    }
                }
            }
            
        except Exception as e:
            _logger.error('Error getting campaigns: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error retrieving campaigns: {str(e)}'
            }

    def _update_campaign(self, data):
        """Update campaign record"""
        try:
            campaign_id = data.get('campaign_id')
            if not campaign_id:
                return {
                    'status': 'error',
                    'message': 'campaign_id is required'
                }
            
            campaign = request.env['campaign.analytics'].sudo().browse(int(campaign_id))
            if not campaign.exists():
                return {
                    'status': 'error',
                    'message': 'Campaign not found'
                }
            
            # Prepare update values
            update_values = {}
            updatable_fields = [
                'campaign_name', 'adset_name', 'ad_name', 'spend', 'reach', 
                'impressions', 'frequency', 'cpm', 'date_start', 'date_stop',
                'messaging_conversation_started_7d', 'cost_per_messaging_conversion',
                'purchase', 'add_to_cart', 'cost_per_purchase', 'cost_per_add_to_cart',
                'purchase_value', 'notes'
            ]
            
            for field in updatable_fields:
                if field in data:
                    if field in ['date_start', 'date_stop']:
                        update_values[field] = self._parse_date(data[field])
                    elif field in ['spend', 'reach', 'impressions', 'frequency', 'cpm', 
                                  'cost_per_messaging_conversion', 'cost_per_purchase', 
                                  'cost_per_add_to_cart', 'purchase_value']:
                        update_values[field] = float(data[field]) if data[field] else 0
                    elif field in ['messaging_conversation_started_7d', 'purchase', 'add_to_cart']:
                        update_values[field] = int(data[field]) if data[field] else 0
                    else:
                        update_values[field] = data[field]
            
            if update_values:
                campaign.write(update_values)
                return {
                    'status': 'success',
                    'data': self._prepare_campaign_response(campaign),
                    'message': 'Campaign updated successfully'
                }
            else:
                return {
                    'status': 'error',
                    'message': 'No valid fields to update'
                }
                
        except Exception as e:
            _logger.error('Error updating campaign: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error updating campaign: {str(e)}'
            }

    def _delete_campaign(self, data):
        """Delete campaign record"""
        try:
            campaign_id = data.get('campaign_id')
            if not campaign_id:
                return {
                    'status': 'error',
                    'message': 'campaign_id is required'
                }
            
            campaign = request.env['campaign.analytics'].sudo().browse(int(campaign_id))
            if not campaign.exists():
                return {
                    'status': 'error',
                    'message': 'Campaign not found'
                }
            
            campaign_name = campaign.campaign_name
            campaign.unlink()
            
            return {
                'status': 'success',
                'message': f'Campaign "{campaign_name}" deleted successfully'
            }
            
        except Exception as e:
            _logger.error('Error deleting campaign: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error deleting campaign: {str(e)}'
            }

    def _get_campaign_summary(self, data):
        """Get campaign performance summary"""
        try:
            date_from = data.get('date_from')
            date_to = data.get('date_to')
            category = data.get('category')
            
            summary = request.env['campaign.analytics'].sudo().get_campaign_summary(
                date_from=date_from,
                date_to=date_to,
                category=category
            )
            
            return {
                'status': 'success',
                'data': summary
            }
            
        except Exception as e:
            _logger.error('Error getting campaign summary: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error getting summary: {str(e)}'
            }

    def _prepare_campaign_values(self, data):
        """Prepare values for campaign creation/update"""
        values = {}
        
        # String fields
        string_fields = ['campaign_name', 'adset_name', 'ad_name', 'notes']
        for field in string_fields:
            if data.get(field):
                values[field] = str(data[field]).strip()
        
        # Float fields
        float_fields = [
            'spend', 'frequency', 'cpm', 'cost_per_messaging_conversion',
            'cost_per_purchase', 'cost_per_add_to_cart', 'purchase_value'
        ]
        for field in float_fields:
            if field in data:
                values[field] = float(data[field]) if data[field] else 0.0
        
        # Integer fields
        int_fields = ['reach', 'impressions', 'messaging_conversation_started_7d', 'purchase', 'add_to_cart']
        for field in int_fields:
            if field in data:
                values[field] = int(data[field]) if data[field] else 0
        
        # Date fields
        date_fields = ['date_start', 'date_stop']
        for field in date_fields:
            if data.get(field):
                values[field] = self._parse_date(data[field])
        
        return values

    def _parse_csv_row(self, row):
        """Parse a single CSV row into campaign values"""
        # Map CSV headers to model fields
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
                    values[model_field] = int(raw_value) if raw_value else 0
                elif model_field in ['spend', 'frequency', 'cpm', 'cost_per_messaging_conversion', 
                                   'cost_per_purchase', 'cost_per_add_to_cart', 'purchase_value']:
                    values[model_field] = float(raw_value) if raw_value else 0.0
                else:
                    values[model_field] = raw_value
        
        return values

    def _parse_date(self, date_string):
        """Parse date string to date object"""
        if not date_string:
            return None
            
        # Try different date formats
        date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_string, fmt).date()
            except ValueError:
                continue
        
        raise ValueError(f'Unable to parse date: {date_string}')

    def _prepare_campaign_response(self, campaign):
        """Prepare campaign data for API response"""
        return {
            'id': campaign.id,
            'campaign_name': campaign.campaign_name,
            'adset_name': campaign.adset_name,
            'ad_name': campaign.ad_name,
            'spend': campaign.spend,
            'reach': campaign.reach,
            'impressions': campaign.impressions,
            'frequency': campaign.frequency,
            'cpm': campaign.cpm,
            'date_start': campaign.date_start.strftime('%Y-%m-%d') if campaign.date_start else None,
            'date_stop': campaign.date_stop.strftime('%Y-%m-%d') if campaign.date_stop else None,
            'messaging_conversation_started_7d': campaign.messaging_conversation_started_7d,
            'cost_per_messaging_conversion': campaign.cost_per_messaging_conversion,
            'purchase': campaign.purchase,
            'add_to_cart': campaign.add_to_cart,
            'cost_per_purchase': campaign.cost_per_purchase,
            'cost_per_add_to_cart': campaign.cost_per_add_to_cart,
            'purchase_value': campaign.purchase_value,
            'campaign_duration': campaign.campaign_duration,
            'daily_spend': campaign.daily_spend,
            'daily_reach': campaign.daily_reach,
            'roas': campaign.roas,
            'conversion_rate': campaign.conversion_rate,
            'campaign_category': campaign.campaign_category,
            'performance_rating': campaign.performance_rating,
            'notes': campaign.notes,
            'created_by': campaign.created_by.name if campaign.created_by else None,
            'create_date': campaign.create_date.strftime('%Y-%m-%d %H:%M:%S') if campaign.create_date else None
        }