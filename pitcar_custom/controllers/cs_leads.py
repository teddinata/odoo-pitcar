# controllers/leads_api.py
from odoo import http, fields
from odoo.http import request
import logging
import json
import datetime

_logger = logging.getLogger(__name__)

class LeadsAPI(http.Controller):
    @http.route('/web/v1/utm/data', type='json', auth='user', methods=['POST'])
    def get_utm_data(self, **kw):
        """Get all UTM related data for dropdowns"""
        try:
            # Get UTM data
            campaigns = request.env['utm.campaign'].sudo().search_read(
                [], ['id', 'name']
            )
            
            sources = request.env['utm.source'].sudo().search_read(
                [], ['id', 'name']
            )
            
            mediums = request.env['utm.medium'].sudo().search_read(
                [], ['id', 'name']
            )

            return {
                'status': 'success',
                'data': {
                    'campaigns': campaigns,
                    'sources': sources,
                    'mediums': mediums
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    # Endpoint untuk create source baru jika belum ada
    @http.route('/web/v1/utm/source/create', type='json', auth='user', methods=['POST'])
    def create_utm_source(self, **kw):
        """Create new UTM source if not exists"""
        try:
            name = kw.get('name')
            if not name:
                return {'status': 'error', 'message': 'Name is required'}

            # Check if exists
            existing = request.env['utm.source'].sudo().search([
                ('name', '=', name)
            ], limit=1)

            if existing:
                return {
                    'status': 'success',
                    'data': {
                        'id': existing.id,
                        'name': existing.name
                    }
                }

            # Create new
            new_source = request.env['utm.source'].sudo().create({
                'name': name
            })

            return {
                'status': 'success',
                'data': {
                    'id': new_source.id,
                    'name': new_source.name
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    # Modifikasi create lead untuk handle UTM
    def _create_lead(self, data):
        """Create new lead with UTM tracking"""
        try:
            values = {
                'customer_name': data['customer_name'],
                'phone': data.get('phone'),
                'state': 'new'
            }

            # Handle UTM
            if data.get('source'):
                # Auto create source if not exists
                source = request.env['utm.source'].sudo().search([
                    ('name', '=', data['source'])
                ], limit=1)
                
                if not source:
                    source = request.env['utm.source'].sudo().create({
                        'name': data['source']
                    })
                values['source_id'] = source.id

            # Optional UTM fields
            if data.get('campaign_id'):
                values['campaign_id'] = int(data['campaign_id'])
            if data.get('medium_id'):
                values['medium_id'] = int(data['medium_id'])

            # Create lead
            lead = request.env['cs.leads'].sudo().create(values)

            return {
                'status': 'success',
                'data': {
                    'id': lead.id,
                    'name': lead.name
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/leads', type='json', auth='user', methods=['POST'])
    def handle_leads(self, **kw):
        """Handle leads operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                return self._create_lead(kw)
            elif operation == 'read':
                return self._get_leads(kw)
            elif operation == 'update':
                return self._update_lead(kw)
            elif operation == 'delete':
                return self._delete_lead(kw)
            elif operation == 'convert':
                return self._convert_to_sale(kw)
            else:
                return {'status': 'error', 'message': 'Invalid operation'}
                
        except Exception as e:
            _logger.error(f"Error in leads API: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _create_lead(self, data):
        """Create new lead"""
        required_fields = ['customer_name', 'phone']
        if not all(data.get(field) for field in required_fields):
            return {'status': 'error', 'message': 'Missing required fields'}

        try:
            # Get employee ID from current user
            current_user = request.env.user
             # Generate name sequence
            sequence = request.env['ir.sequence'].sudo().next_by_code('cs.leads')

            values = {
                'name': sequence,  # Add name field
                'customer_name': data['customer_name'],
                'phone': data['phone'],
                'cs_id': request.env.user.employee_id.id,
                'state': 'new',
                'date': fields.Date.today(),  # Required field
                'source_id': data.get('source_id'),
                'channel': data.get('channel'),
                'tanggal_chat': data.get('tanggal_chat'),
                'jam_chat': data.get('jam_chat'),
                'is_booking': data.get('is_booking', False),
                'tanggal_booking': data.get('tanggal_booking'),
                'category': data.get('category'),
                'campaign_id': data.get('campaign_id'),
                'medium_id': data.get('medium_id'),
                'notes': data.get('notes'),
                'follow_up_status': 'pending'  # Set default value
            }

            lead = request.env['cs.leads'].sudo().create(values)

            # Create initial followup if provided
            if data.get('initial_notes'):
                followup_vals = {
                    'lead_id': lead.id,
                    'notes': data['initial_notes'],
                    'result': 'interested',
                    'created_by': current_user.id
                }
                request.env['cs.leads.followup'].sudo().create(followup_vals)

            return {
                'status': 'success',
                'data': {
                    'id': lead.id,
                    'name': lead.name
                }
            }
        except Exception as e:
            _logger.error(f"Error creating lead: {str(e)}")
            return {'status': 'error', 'message': str(e)}


    def _get_leads(self, data):
        """Get leads with filters and pagination"""
        try:
            domain = []
            
            # Apply filters
            if data.get('channel'):
                domain.append(('channel', '=', data['channel']))
            if data.get('category'):
                domain.append(('category', '=', data['category']))
            if data.get('is_booking') is not None:
                domain.append(('is_booking', '=', data['is_booking']))
            if data.get('date_from'):
                domain.append(('tanggal_chat', '>=', data['date_from']))
            if data.get('date_to'):
                domain.append(('tanggal_chat', '<=', data['date_to']))
            if data.get('state'):
                domain.append(('state', '=', data['state']))
                
            # Apply search if provided
            if data.get('search'):
                search_domain = ['|', '|', '|',
                    ('name', 'ilike', data['search']),
                    ('customer_name', 'ilike', data['search']),
                    ('phone', 'ilike', data['search'])
                ]
                domain.extend(search_domain)

            # Get total count before pagination
            total_count = request.env['cs.leads'].sudo().search_count(domain)

            # Apply pagination
            page = int(data.get('page', 1))
            limit = int(data.get('limit', 20))
            offset = (page - 1) * limit

            # Get paginated records
            leads = request.env['cs.leads'].sudo().search(
                domain, 
                order=data.get('sort_by', 'create_date desc'),
                offset=offset,
                limit=limit
            )
            
            # Prepare response
            return {
                'status': 'success',
                'data': [{
                    'id': lead.id,
                    'name': lead.name,
                    'customer_name': lead.customer_name,
                    'phone': lead.phone,
                    'channel': lead.channel,
                    'source': {
                        'id': lead.source_id.id,
                        'name': lead.source_id.name
                    } if lead.source_id else None,
                    'campaign': {
                        'id': lead.campaign_id.id,
                        'name': lead.campaign_id.name
                    } if lead.campaign_id else None,
                    'tanggal_chat': lead.tanggal_chat,
                    'jam_chat': lead.jam_chat,
                    'is_booking': lead.is_booking,
                    'tanggal_booking': lead.tanggal_booking,
                    'category': lead.category,
                    'omzet': lead.omzet,
                    'state': lead.state,
                    'is_converted': lead.is_converted,
                    'campaign_id': lead.campaign_id.id,
                    'source_id': lead.source_id.id,
                    'medium_id': lead.medium_id.id,
                    'last_followup_date': lead.last_followup_date,
                    'next_followup_date': lead.next_followup_date
                } for lead in leads],
                'pagination': {
                    'total_items': total_count,
                    'current_page': page,
                    'total_pages': (total_count + limit - 1) // limit,
                    'items_per_page': limit
                }
            }


        except Exception as e:
            _logger.error(f"Error in _get_leads: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _update_lead(self, data):
        """Update existing lead"""
        if not data.get('id'):
            return {'status': 'error', 'message': 'Missing lead ID'}

        lead = request.env['cs.leads'].sudo().browse(int(data['id']))
        if not lead.exists():
            return {'status': 'error', 'message': 'Lead not found'}

        update_values = {}
        allowed_fields = [
            'customer_name', 'phone', 'channel', 'state',
            'tanggal_chat', 'jam_chat', 'is_booking', 
            'tanggal_booking', 'category', 'omzet',
            'tanggal_pembayaran', 'campaign_id',
            'source_id', 'medium_id', 'lost_reason',
            'alasan_tidak_booking', 'detail_alasan'
        ]

        for field in allowed_fields:
            if field in data:
                update_values[field] = data[field]

        lead.write(update_values)

        return {
            'status': 'success',
            'data': {
                'id': lead.id,
                'name': lead.name,
                'state': lead.state
            }
        }

    def _delete_lead(self, data):
        """Delete existing lead"""
        if not data.get('id'):
            return {'status': 'error', 'message': 'Missing lead ID'}

        lead = request.env['cs.leads'].sudo().browse(int(data['id']))
        if not lead.exists():
            return {'status': 'error', 'message': 'Lead not found'}

        try:
            # Delete followups first
            lead.followup_ids.unlink()
            # Then delete the lead
            lead.unlink()
            return {'status': 'success', 'message': 'Lead deleted successfully'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error deleting lead: {str(e)}'}

    def _convert_to_sale(self, data):
        """Convert lead to sale order"""
        if not data.get('id'):
            return {'status': 'error', 'message': 'Missing lead ID'}

        lead = request.env['cs.leads'].sudo().browse(int(data['id']))
        if not lead.exists():
            return {'status': 'error', 'message': 'Lead not found'}

        if lead.is_converted:
            return {'status': 'error', 'message': 'Lead already converted'}

        try:
            # Create sale order
            sale_order_vals = {
                'partner_name': lead.customer_name,
                'phone': lead.phone,
                'origin': lead.name,
                'date_order': fields.Datetime.now(),
            }

            # Add optional fields if provided
            if data.get('service_advisor_id'):
                sale_order_vals['service_advisor_id'] = int(data['service_advisor_id'])
            if data.get('mechanic_id'):
                sale_order_vals['mechanic_id'] = int(data['mechanic_id'])

            # Create sale order
            sale_order = request.env['sale.order'].sudo().create(sale_order_vals)

            # Update lead
            lead.write({
                'state': 'converted',
                'is_converted': True,
                'sale_order_id': sale_order.id,
                'conversion_date': fields.Datetime.now(),
                'service_advisor_id': sale_order_vals.get('service_advisor_id'),
                'mechanic_id': sale_order_vals.get('mechanic_id')
            })

            return {
                'status': 'success',
                'data': {
                    'lead_id': lead.id,
                    'sale_order_id': sale_order.id,
                    'sale_order_name': sale_order.name
                }
            }

        except Exception as e:
            return {'status': 'error', 'message': f'Error converting lead: {str(e)}'}

    @http.route('/web/v1/leads/statistics', type='json', auth='user', methods=['POST'])
    def get_leads_statistics(self, **kw):
        """Get leads statistics"""
        try:
            domain = []
            if kw.get('date_from'):
                domain.append(('date', '>=', kw['date_from']))
            if kw.get('date_to'):
                domain.append(('date', '<=', kw['date_to']))
            if kw.get('cs_id'):
                domain.append(('cs_id', '=', int(kw['cs_id'])))

            leads = request.env['cs.leads'].sudo().search(domain)
            
            # Calculate statistics
            total_leads = len(leads)
            converted_leads = len(leads.filtered(lambda l: l.is_converted))
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0

            # Group by source
            source_stats = {}
            for lead in leads:
                source_stats[lead.source] = source_stats.get(lead.source, 0) + 1

            # Group by CS
            cs_stats = {}
            for lead in leads:
                cs_name = lead.cs_id.name
                if cs_name not in cs_stats:
                    cs_stats[cs_name] = {
                        'total': 0,
                        'converted': 0
                    }
                cs_stats[cs_name]['total'] += 1
                if lead.is_converted:
                    cs_stats[cs_name]['converted'] += 1

            return {
                'status': 'success',
                'data': {
                    'total_leads': total_leads,
                    'converted_leads': converted_leads,
                    'conversion_rate': round(conversion_rate, 2),
                    'source_distribution': source_stats,
                    'cs_performance': cs_stats
                }
            }

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/leads/sale-orders', type='json', auth='user', methods=['POST'])
    def get_linkable_sale_orders(self, **kw):
        """Get list of sale orders that can be linked to leads"""
        try:
            # Filter parameters
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            customer_name = kw.get('customer_name')
            phone = kw.get('phone')

            domain = [('state', 'not in', ['cancel', 'draft'])]
            
            if date_from:
                domain.append(('date_order', '>=', date_from))
            if date_to:
                domain.append(('date_order', '<=', date_to))
            if customer_name:
                domain.append(('partner_name', 'ilike', customer_name))
            if phone:
                domain.append(('phone', 'ilike', phone))

            # Get sale orders
            sale_orders = request.env['sale.order'].sudo().search(domain)

            return {
                'status': 'success',
                'data': [{
                    'id': order.id,
                    'name': order.name,
                    'date_order': order.date_order,
                    'partner_name': order.partner_name,
                    'phone': order.phone,
                    'amount_total': order.amount_total,
                    'service_advisor': {
                        'id': order.service_advisor_id.id,
                        'name': order.service_advisor_id.name
                    } if order.service_advisor_id else False,
                    'mechanic': {
                        'id': order.mechanic_id.id,
                        'name': order.mechanic_id.name
                    } if order.mechanic_id else False,
                    'state': order.state,
                    'services': [{
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.name,
                        'quantity': line.product_uom_qty,
                        'price': line.price_unit,
                        'subtotal': line.price_subtotal
                    } for line in order.order_line]
                } for order in sale_orders]
            }

        except Exception as e:
            _logger.error(f"Error getting linkable sale orders: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v1/leads/link-sale-order', type='json', auth='user', methods=['POST'])
    def link_sale_order(self, **kw):
        """Link an existing sale order to a lead"""
        try:
            if not kw.get('lead_id') or not kw.get('sale_order_id'):
                return {'status': 'error', 'message': 'Missing lead_id or sale_order_id'}

            lead = request.env['cs.leads'].sudo().browse(int(kw['lead_id']))
            sale_order = request.env['sale.order'].sudo().browse(int(kw['sale_order_id']))

            if not lead.exists() or not sale_order.exists():
                return {'status': 'error', 'message': 'Lead or Sale Order not found'}

            # Update lead with sale order information
            lead.write({
                'state': 'converted',
                'is_converted': True,
                'sale_order_id': sale_order.id,
                'service_advisor_id': sale_order.service_advisor_id.id,
                'mechanic_id': sale_order.mechanic_id.id,
                'conversion_date': fields.Datetime.now()
            })

            # Add a follow-up note about the linking
            request.env['cs.leads.followup'].sudo().create({
                'lead_id': lead.id,
                'notes': f'Linked to existing Sale Order {sale_order.name}',
                'result': 'converted',
                'created_by': request.env.user.id
            })

            return {
                'status': 'success',
                'data': {
                    'lead_id': lead.id,
                    'lead_name': lead.name,
                    'sale_order_id': sale_order.id,
                    'sale_order_name': sale_order.name,
                    'conversion_date': lead.conversion_date
                }
            }

        except Exception as e:
            _logger.error(f"Error linking sale order to lead: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    @http.route('/web/v1/leads/follow-up', type='json', auth='user', methods=['POST'])
    def handle_follow_up(self, **kw):
        try:
            operation = kw.get('operation')
            lead_id = kw.get('lead_id')
            
            if operation == 'schedule':
                return self._schedule_follow_up(kw)
            elif operation == 'mark_contacted':
                return self._mark_lead_contacted(kw)
            elif operation == 'get_pending':
                return self._get_pending_follow_ups(kw)
                
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _schedule_follow_up(self, data):
        """Schedule follow up for a lead"""
        if not data.get('lead_id'):
            return {'status': 'error', 'message': 'Lead ID is required'}
            
        try:
            lead = request.env['cs.leads'].sudo().browse(int(data['lead_id']))
            if not lead.exists():
                return {'status': 'error', 'message': 'Lead not found'}
            
            schedule_date = datetime.strptime(
                data['schedule_date'], 
                '%Y-%m-%dT%H:%M'
            ).strftime('%Y-%m-%d %H:%M:00')

            values = {
                'next_follow_up': schedule_date,
                'follow_up_notes': data.get('notes'),
                'follow_up_reminder': data.get('reminder', False)
            }
            
            lead.write(values)
            
            # Create follow up record
            request.env['cs.leads.followup'].sudo().create({
                'lead_id': lead.id,
                'notes': data.get('notes', ''),
                'result': 'thinking',
                'next_action_date': data['schedule_date'],
                'created_by': request.env.user.id
            })
            
            return {
                'status': 'success',
                'message': 'Follow up scheduled'
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


    def _mark_lead_contacted(self, data):
        lead = request.env['cs.leads'].sudo().browse(int(data['lead_id']))
        
        result = data.get('result', 'contacted') # contacted/interested/not_interested
        
        lead.write({
            'follow_up_status': result,
            'last_follow_up': fields.Datetime.now(),
            'notes': data.get('notes')
        })
        
        return {
            'status': 'success',
            'message': 'Lead marked as contacted'
        }

    def _get_pending_follow_ups(self, data):
        """Get pending follow ups"""
        try:
            domain = [
                ('next_follow_up', '!=', False),
                ('next_follow_up', '<=', fields.Datetime.now()),
                ('state', 'not in', ['converted', 'lost'])
            ]
            
            leads = request.env['cs.leads'].sudo().search(domain)
            
            return {
                'status': 'success',
                'data': [{
                    'id': lead.id,
                    'name': lead.name,
                    'customer_name': lead.customer_name,
                    'phone': lead.phone,
                    'next_follow_up': lead.next_follow_up,
                    'follow_up_notes': lead.follow_up_notes
                } for lead in leads]
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v1/leads/reorder', type='json', auth='user', methods=['POST'])
    def reorder_leads(self, **kw):
        """Reorder leads position"""
        try:
            if not kw.get('lead_id') or 'new_position' not in kw:
                return {'status': 'error', 'message': 'Missing required parameters'}

            lead = request.env['cs.leads'].sudo().browse(int(kw['lead_id']))
            if not lead.exists():
                return {'status': 'error', 'message': 'Lead not found'}

            # Add sequence field to model if not exists
            if not hasattr(lead, 'sequence'):
                request.env.cr.execute("""
                    ALTER TABLE cs_leads 
                    ADD COLUMN sequence INTEGER;
                    UPDATE cs_leads SET sequence = id;
                """)

            # Update sequence
            new_position = int(kw['new_position'])
            leads = request.env['cs.leads'].sudo().search([])
            
            # Reorder sequences
            for idx, l in enumerate(leads):
                if l.id == lead.id:
                    l.sequence = new_position
                elif idx >= new_position:
                    l.sequence = idx + 1

            return {
                'status': 'success',
                'message': 'Lead reordered successfully'
            }

        except Exception as e:
            _logger.error(f"Error reordering lead: {str(e)}")
            return {'status': 'error', 'message': str(e)}
