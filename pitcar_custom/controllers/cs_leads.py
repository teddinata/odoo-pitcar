# controllers/leads_api.py
from odoo import http, fields
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)

class LeadsAPI(http.Controller):
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
        required_fields = ['customer_name', 'cs_id', 'source']
        if not all(data.get(field) for field in required_fields):
            return {'status': 'error', 'message': 'Missing required fields'}

        values = {
            'customer_name': data['customer_name'],
            'cs_id': int(data['cs_id']),
            'source': data['source'],
            'phone': data.get('phone'),
            'state': 'new'
        }

        # Optional fields
        optional_fields = [
            'car_brand', 'car_type', 'car_transmission',
            'notes', 'next_followup_date'
        ]
        
        for field in optional_fields:
            if data.get(field):
                values[field] = data[field]

        lead = request.env['cs.leads'].sudo().create(values)

        # Create initial followup if provided
        if data.get('initial_notes'):
            followup_vals = {
                'lead_id': lead.id,
                'notes': data['initial_notes'],
                'result': data.get('initial_result', 'interested'),
                'next_action': data.get('next_action'),
                'next_action_date': data.get('next_action_date')
            }
            request.env['cs.leads.followup'].sudo().create(followup_vals)

        return {
            'status': 'success',
            'data': {
                'id': lead.id,
                'name': lead.name
            }
        }

    def _get_leads(self, data):
        """Get leads with filters"""
        domain = []
        
        if data.get('cs_id'):
            domain.append(('cs_id', '=', int(data['cs_id'])))
        if data.get('date_from'):
            domain.append(('date', '>=', data['date_from']))
        if data.get('date_to'):
            domain.append(('date', '<=', data['date_to']))
        if data.get('state'):
            domain.append(('state', '=', data['state']))
        if data.get('is_converted') is not None:
            domain.append(('is_converted', '=', data['is_converted']))

        leads = request.env['cs.leads'].sudo().search(domain)
        
        return {
            'status': 'success',
            'data': [{
                'id': lead.id,
                'name': lead.name,
                'customer_name': lead.customer_name,
                'phone': lead.phone,
                'source': lead.source,
                'cs_id': lead.cs_id.id,
                'cs_name': lead.cs_id.name,
                'date': lead.date,
                'state': lead.state,
                'is_converted': lead.is_converted,
                'sale_order_id': lead.sale_order_id.id if lead.sale_order_id else False,
                'service_advisor_id': lead.service_advisor_id.id if lead.service_advisor_id else False,
                'mechanic_id': lead.mechanic_id.id if lead.mechanic_id else False,
                'notes': lead.notes,
                'last_followup_date': lead.last_followup_date,
                'next_followup_date': lead.next_followup_date,
                'followups': [{
                    'id': f.id,
                    'notes': f.notes,
                    'result': f.result,
                    'next_action': f.next_action,
                    'next_action_date': f.next_action_date,
                    'created_by': f.created_by.name,
                    'create_date': f.create_date
                } for f in lead.followup_ids]
            } for lead in leads]
        }

    def _update_lead(self, data):
        """Update existing lead"""
        if not data.get('id'):
            return {'status': 'error', 'message': 'Missing lead ID'}

        lead = request.env['cs.leads'].sudo().browse(int(data['id']))
        if not lead.exists():
            return {'status': 'error', 'message': 'Lead not found'}

        update_values = {}
        allowed_fields = [
            'customer_name', 'phone', 'source', 'state',
            'service_advisor_id', 'mechanic_id', 'notes',
            'next_followup_date', 'lost_reason'
        ]

        for field in allowed_fields:
            if field in data:
                update_values[field] = data[field]

        # Add new followup if provided
        if data.get('followup_notes'):
            request.env['cs.leads.followup'].sudo().create({
                'lead_id': lead.id,
                'notes': data['followup_notes'],
                'result': data.get('followup_result', 'other'),
                'next_action': data.get('next_action'),
                'next_action_date': data.get('next_action_date')
            })

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
        lead = request.env['cs.leads'].sudo().browse(int(data['lead_id']))
        
        lead.write({
            'next_follow_up': data['schedule_date'],
            'notes': data.get('notes'),
        })
        
        return {
            'status': 'success',
            'message': 'Follow up scheduled'
        }

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
                'notes': lead.notes
            } for lead in leads]
        }