"""
Powerful Workshop Accounting API Controller
==========================================
Hybrid approach with powerful but focused endpoints
Perfect for n8n automation and MCP integration
"""

from odoo import http, fields
from odoo.http import request, Response
import logging
import json
import math
from datetime import datetime, timedelta
from io import StringIO
import csv

_logger = logging.getLogger(__name__)

class PowerfulAccountingAPI(http.Controller):
    
    def _authenticate_api(self):
        """API authentication check"""
        api_key = request.httprequest.headers.get('X-API-Key')
        if not api_key:
            return {'authenticated': False, 'error': 'API Key required'}
        
        stored_key = request.env['ir.config_parameter'].sudo().get_param('workshop.api.key', 'default-key')
        if api_key != stored_key:
            return {'authenticated': False, 'error': 'Invalid API Key'}
        
        return {'authenticated': True}
    
    def _get_request_data(self):
        """Helper to handle JSONRPC request data"""
        try:
            if request.jsonrequest:
                return request.jsonrequest.get('params', {})
            return {}
        except Exception as e:
            _logger.error(f"Error parsing request data: {str(e)}")
            return {}
    
    def _build_domain_from_filters(self, filters, model_name='account.move'):
        """Smart domain builder from various filter types"""
        domain = []
        
        # Basic filters
        if filters.get('ids'):
            domain.append(('id', 'in', filters['ids']))
        
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        
        if filters.get('move_type'):
            domain.append(('move_type', '=', filters['move_type']))
        
        # Date filters
        if filters.get('date_from'):
            domain.append(('date', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('date', '<=', filters['date_to']))
        
        # Partner filters
        if filters.get('partner_id'):
            domain.append(('partner_id', '=', filters['partner_id']))
        if filters.get('partner_ids'):
            domain.append(('partner_id', 'in', filters['partner_ids']))
        
        # Workshop specific filters
        if filters.get('has_car'):
            domain.append(('partner_car_id', '!=' if filters['has_car'] else '=', False))
        
        if filters.get('has_service_advisor'):
            domain.append(('service_advisor_id', '!=' if filters['has_service_advisor'] else '=', False))
        
        if filters.get('has_mechanic'):
            domain.append(('car_mechanic_id_new', '!=' if filters['has_mechanic'] else '=', False))
        
        if filters.get('service_advisor_ids'):
            domain.append(('service_advisor_id', 'in', filters['service_advisor_ids']))
        
        if filters.get('mechanic_ids'):
            domain.append(('car_mechanic_id_new', 'in', filters['mechanic_ids']))
        
        # Vendor filters
        if filters.get('vendor_id'):
            domain.append(('vendor_id', '=', filters['vendor_id']))
        if filters.get('vendor_ids'):
            domain.append(('vendor_id', 'in', filters['vendor_ids']))
        
        # Audit filters
        if filters.get('is_stock_audit') is not None:
            domain.append(('is_stock_audit', '=', filters['is_stock_audit']))
        
        if filters.get('audit_type'):
            domain.append(('audit_type', '=', filters['audit_type']))
        
        if filters.get('within_tolerance') is not None:
            domain.append(('is_within_tolerance', '=', filters['within_tolerance']))
        
        # Amount filters
        if filters.get('amount_min'):
            domain.append(('amount_total', '>=', filters['amount_min']))
        if filters.get('amount_max'):
            domain.append(('amount_total', '<=', filters['amount_max']))
        
        # Search filter
        if filters.get('search'):
            search_terms = filters['search'].split()
            for term in search_terms:
                domain.extend(['|', '|', '|', '|', '|',
                    ('name', 'ilike', term),
                    ('ref', 'ilike', term),
                    ('partner_id.name', 'ilike', term),
                    ('vendor_id.name', 'ilike', term),
                    ('invoice_origin', 'ilike', term),
                    ('partner_car_id.number_plate', 'ilike', term)
                ])
        
        return domain
    
    def _serialize_comprehensive_move(self, move, detail_level='basic'):
        """Comprehensive move serialization with different detail levels"""
        # Basic data (always included)
        data = {
            'id': move.id,
            'name': move.name,
            'ref': move.ref,
            'date': move.date.isoformat() if move.date else None,
            'move_type': move.move_type,
            'state': move.state,
            'amount_total': move.amount_total,
            'amount_untaxed': move.amount_untaxed,
            'amount_tax': move.amount_tax,
            'invoice_origin': move.invoice_origin,
            'created_date': move.create_date.isoformat() if move.create_date else None
        }
        
        # Standard data (included in 'standard' and 'full' levels)
        if detail_level in ['standard', 'full']:
            data.update({
                'partner': {
                    'id': move.partner_id.id,
                    'name': move.partner_id.name,
                    'phone': move.partner_id.phone,
                    'mobile': move.partner_id.mobile,
                    'email': move.partner_id.email
                } if move.partner_id else None,
                
                'vendor': {
                    'id': move.vendor_id.id,
                    'name': move.vendor_id.name
                } if move.vendor_id else None,
                
                'car_info': {
                    'id': move.partner_car_id.id,
                    'number_plate': move.partner_car_id.number_plate,
                    'brand': move.partner_car_brand.name if move.partner_car_brand else None,
                    'brand_type': move.partner_car_brand_type.name if move.partner_car_brand_type else None,
                    'year': move.partner_car_year,
                    'odometer': move.partner_car_odometer
                } if move.partner_car_id else None,
                
                'employees': {
                    'service_advisors': [{
                        'id': sa.id,
                        'name': sa.name
                    } for sa in move.service_advisor_id],
                    'mechanics': [{
                        'id': mech.id,
                        'name': mech.name
                    } for mech in move.car_mechanic_id_new],
                    'team_names': move.generated_mechanic_team
                },
                
                'audit_info': {
                    'is_stock_audit': move.is_stock_audit,
                    'audit_type': move.audit_type,
                    'audit_difference': move.audit_difference,
                    'is_within_tolerance': move.is_within_tolerance
                },
                
                'timestamps': {
                    'date_sale_completed': move.date_sale_completed.isoformat() if move.date_sale_completed else None,
                    'date_sale_quotation': move.date_sale_quotation.isoformat() if move.date_sale_quotation else None,
                    'car_arrival_time': move.car_arrival_time.isoformat() if move.car_arrival_time else None,
                    'write_date': move.write_date.isoformat() if move.write_date else None
                }
            })
        
        # Full data (included only in 'full' level)
        if detail_level == 'full':
            # Add move lines
            lines = []
            for line in move.line_ids:
                lines.append({
                    'id': line.id,
                    'name': line.name,
                    'account': {
                        'id': line.account_id.id,
                        'code': line.account_id.code,
                        'name': line.account_id.name
                    } if line.account_id else None,
                    'debit': line.debit,
                    'credit': line.credit,
                    'balance': line.balance,
                    'partner': {
                        'id': line.partner_id.id,
                        'name': line.partner_id.name
                    } if line.partner_id else None,
                    'vendor': {
                        'id': line.vendor_id.id,
                        'name': line.vendor_id.name
                    } if line.vendor_id else None,
                    'customer_info': {
                        'phone': line.customer_phone,
                        'source': line.customer_source,
                        'is_loyal': line.is_loyal_customer
                    }
                })
            
            data['lines'] = lines
            data['line_count'] = len(lines)
            
            # Add recommendations if available
            if move.recommendation_ids:
                data['recommendations'] = [{
                    'id': rec.id,
                    'name': getattr(rec, 'name', str(rec))
                } for rec in move.recommendation_ids]
            
            # Add totals validation
            data['totals_validation'] = {
                'debit_total': sum(line.debit for line in move.line_ids),
                'credit_total': sum(line.credit for line in move.line_ids),
                'balance_check': sum(line.debit - line.credit for line in move.line_ids),
                'is_balanced': abs(sum(line.debit - line.credit for line in move.line_ids)) < 0.01
            }
        
        return data

    # =====================================
    # MAIN POWERFUL ENDPOINT
    # =====================================

    @http.route('/api/accounting/query', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def accounting_query(self, **kw):
        """
        POWERFUL COMPREHENSIVE ACCOUNTING QUERY ENDPOINT
        
        Supports multiple operations in one call:
        - search/filter moves with complex criteria
        - get statistics
        - get related data (partners, cars, employees)
        - export capabilities
        - real-time analytics
        
        Parameters:
        - operation: 'search', 'statistics', 'export', 'related_data'
        - filters: comprehensive filtering object
        - options: output formatting and detail options
        """
        try:
            # Get parameters
            params = self._get_request_data()
            operation = params.get('operation', 'search')
            filters = params.get('filters', {})
            options = params.get('options', {})
            
            # Authentication check
            auth_result = self._authenticate_api()
            if not auth_result.get('authenticated'):
                return auth_result
            
            _logger.info(f"Accounting query: operation={operation}, filters={filters}")
            
            # Route to appropriate handler
            if operation == 'search':
                return self._handle_search_operation(filters, options)
            elif operation == 'statistics':
                return self._handle_statistics_operation(filters, options)
            elif operation == 'export':
                return self._handle_export_operation(filters, options)
            elif operation == 'related_data':
                return self._handle_related_data_operation(filters, options)
            elif operation == 'multi':
                return self._handle_multi_operation(params)
            else:
                return {
                    'status': 'error',
                    'message': f"Unknown operation: {operation}",
                    'supported_operations': ['search', 'statistics', 'export', 'related_data', 'multi']
                }
        
        except Exception as e:
            _logger.error(f"Error in accounting_query: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_search_operation(self, filters, options):
        """Handle search/filter operation"""
        try:
            # Pagination
            page = max(1, int(options.get('page', 1)))
            limit = max(1, min(100, int(options.get('limit', 25))))
            offset = (page - 1) * limit
            
            # Detail level
            detail_level = options.get('detail_level', 'standard')  # basic, standard, full
            
            # Sorting
            sort_by = options.get('sort_by', 'date')
            sort_order = options.get('sort_order', 'desc')
            
            # Build domain
            domain = self._build_domain_from_filters(filters)
            
            # Get data
            AccountMove = request.env['account.move'].sudo()
            total_count = AccountMove.search_count(domain)
            
            # Apply sorting
            valid_sort_fields = {
                'name': 'name', 'date': 'date', 'partner': 'partner_id',
                'amount': 'amount_total', 'state': 'state', 'created': 'create_date'
            }
            sort_field = valid_sort_fields.get(sort_by, 'date')
            order_string = f"{sort_field} {sort_order}"
            
            moves = AccountMove.search(domain, limit=limit, offset=offset, order=order_string)
            
            # Serialize data
            rows = []
            for move in moves:
                rows.append(self._serialize_comprehensive_move(move, detail_level))
            
            # Quick statistics for this search
            quick_stats = None
            if options.get('include_quick_stats', False):
                all_moves = AccountMove.search(domain)
                quick_stats = {
                    'total_count': len(all_moves),
                    'total_amount': sum(all_moves.mapped('amount_total')),
                    'avg_amount': sum(all_moves.mapped('amount_total')) / len(all_moves) if all_moves else 0,
                    'by_state': {},
                    'by_type': {}
                }
                
                # Count by state and type
                for state in ['draft', 'posted', 'cancel']:
                    quick_stats['by_state'][state] = len(all_moves.filtered(lambda m: m.state == state))
                
                for move_type in ['entry', 'out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
                    quick_stats['by_type'][move_type] = len(all_moves.filtered(lambda m: m.move_type == move_type))
            
            return {
                'status': 'success',
                'operation': 'search',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit) if total_count > 0 else 1,
                        'current_page': page,
                        'items_per_page': limit,
                        'has_next': page * limit < total_count,
                        'has_previous': page > 1
                    },
                    'quick_statistics': quick_stats,
                    'query_info': {
                        'filters_applied': len([k for k, v in filters.items() if v]),
                        'detail_level': detail_level,
                        'sort': {'by': sort_by, 'order': sort_order}
                    }
                }
            }
        
        except Exception as e:
            _logger.error(f"Error in search operation: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_statistics_operation(self, filters, options):
        """Handle comprehensive statistics operation"""
        try:
            # Build domain
            domain = self._build_domain_from_filters(filters)
            AccountMove = request.env['account.move'].sudo()
            MoveLine = request.env['account.move.line'].sudo()
            
            # Get moves for analysis
            moves = AccountMove.search(domain)
            
            if not moves:
                return {
                    'status': 'success',
                    'operation': 'statistics',
                    'data': {'message': 'No data found for the given filters'}
                }
            
            # Basic statistics
            stats = {
                'overview': {
                    'total_moves': len(moves),
                    'total_amount': sum(moves.mapped('amount_total')),
                    'average_amount': sum(moves.mapped('amount_total')) / len(moves),
                    'date_range': {
                        'from': min(moves.mapped('date')).isoformat() if moves.mapped('date') else None,
                        'to': max(moves.mapped('date')).isoformat() if moves.mapped('date') else None
                    }
                },
                
                'by_state': {},
                'by_type': {},
                'by_month': {},
                
                'workshop_analytics': {
                    'with_cars': len(moves.filtered('partner_car_id')),
                    'with_service_advisors': len(moves.filtered('service_advisor_id')),
                    'with_mechanics': len(moves.filtered('car_mechanic_id_new')),
                    'stock_audits': len(moves.filtered('is_stock_audit')),
                    'within_tolerance': len(moves.filtered('is_within_tolerance'))
                },
                
                'financial_summary': {
                    'invoices_amount': sum(moves.filtered(lambda m: m.move_type in ['out_invoice', 'in_invoice']).mapped('amount_total')),
                    'refunds_amount': sum(moves.filtered(lambda m: m.move_type in ['out_refund', 'in_refund']).mapped('amount_total')),
                    'net_amount': sum(moves.filtered(lambda m: m.move_type in ['out_invoice']).mapped('amount_total')) - sum(moves.filtered(lambda m: m.move_type in ['out_refund']).mapped('amount_total'))
                }
            }
            
            # Count by state
            for state in ['draft', 'posted', 'cancel']:
                count = len(moves.filtered(lambda m: m.state == state))
                amount = sum(moves.filtered(lambda m: m.state == state).mapped('amount_total'))
                stats['by_state'][state] = {'count': count, 'amount': amount}
            
            # Count by type
            for move_type in ['entry', 'out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
                filtered_moves = moves.filtered(lambda m: m.move_type == move_type)
                stats['by_type'][move_type] = {
                    'count': len(filtered_moves),
                    'amount': sum(filtered_moves.mapped('amount_total'))
                }
            
            # Monthly breakdown
            if options.get('include_monthly', True):
                monthly_data = {}
                for move in moves:
                    if move.date:
                        month_key = move.date.strftime('%Y-%m')
                        if month_key not in monthly_data:
                            monthly_data[month_key] = {'count': 0, 'amount': 0}
                        monthly_data[month_key]['count'] += 1
                        monthly_data[month_key]['amount'] += move.amount_total
                
                stats['by_month'] = monthly_data
            
            # Top partners/vendors analysis
            if options.get('include_top_analysis', True):
                # Top customers
                partner_stats = {}
                for move in moves.filtered('partner_id'):
                    partner_id = move.partner_id.id
                    if partner_id not in partner_stats:
                        partner_stats[partner_id] = {
                            'name': move.partner_id.name,
                            'count': 0,
                            'amount': 0
                        }
                    partner_stats[partner_id]['count'] += 1
                    partner_stats[partner_id]['amount'] += move.amount_total
                
                # Sort and get top 10
                top_partners = sorted(partner_stats.values(), key=lambda x: x['amount'], reverse=True)[:10]
                stats['top_customers'] = top_partners
                
                # Top vendors
                vendor_stats = {}
                for move in moves.filtered('vendor_id'):
                    vendor_id = move.vendor_id.id
                    if vendor_id not in vendor_stats:
                        vendor_stats[vendor_id] = {
                            'name': move.vendor_id.name,
                            'count': 0,
                            'amount': 0
                        }
                    vendor_stats[vendor_id]['count'] += 1
                    vendor_stats[vendor_id]['amount'] += move.amount_total
                
                top_vendors = sorted(vendor_stats.values(), key=lambda x: x['amount'], reverse=True)[:10]
                stats['top_vendors'] = top_vendors
            
            # Customer source analysis (from move lines)
            if options.get('include_customer_analysis', True):
                move_ids = moves.ids
                lines = MoveLine.search([('move_id', 'in', move_ids), ('customer_source', '!=', False)])
                
                source_stats = {}
                for line in lines:
                    source = line.customer_source
                    if source not in source_stats:
                        source_stats[source] = 0
                    source_stats[source] += 1
                
                stats['customer_sources'] = source_stats
                stats['loyal_customers'] = {
                    'count': len(lines.filtered('is_loyal_customer')),
                    'percentage': (len(lines.filtered('is_loyal_customer')) / len(lines) * 100) if lines else 0
                }
            
            return {
                'status': 'success',
                'operation': 'statistics',
                'data': stats,
                'meta': {
                    'generated_at': datetime.now().isoformat(),
                    'filters_applied': filters,
                    'options_used': options
                }
            }
        
        except Exception as e:
            _logger.error(f"Error in statistics operation: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_export_operation(self, filters, options):
        """Handle export operation - returns data ready for CSV/Excel"""
        try:
            # Build domain
            domain = self._build_domain_from_filters(filters)
            moves = request.env['account.move'].sudo().search(domain, order='date desc')
            
            if not moves:
                return {
                    'status': 'success',
                    'operation': 'export',
                    'data': {'message': 'No data to export'}
                }
            
            export_format = options.get('format', 'structured')  # structured, csv_ready, excel_ready
            include_lines = options.get('include_lines', False)
            
            if export_format == 'csv_ready':
                # Return CSV-ready data
                csv_data = []
                headers = [
                    'Number', 'Date', 'Reference', 'Partner', 'Type', 'State',
                    'Amount Total', 'Amount Tax', 'Car Plate', 'Car Brand',
                    'Service Advisors', 'Mechanics', 'Vendor', 'Is Audit',
                    'Created Date'
                ]
                
                for move in moves:
                    row = [
                        move.name,
                        move.date.strftime('%Y-%m-%d') if move.date else '',
                        move.ref or '',
                        move.partner_id.name if move.partner_id else '',
                        move.move_type,
                        move.state,
                        move.amount_total,
                        move.amount_tax,
                        move.partner_car_id.number_plate if move.partner_car_id else '',
                        move.partner_car_brand.name if move.partner_car_brand else '',
                        ', '.join(move.service_advisor_id.mapped('name')),
                        move.generated_mechanic_team or '',
                        move.vendor_id.name if move.vendor_id else '',
                        'Yes' if move.is_stock_audit else 'No',
                        move.create_date.strftime('%Y-%m-%d %H:%M:%S') if move.create_date else ''
                    ]
                    csv_data.append(row)
                
                return {
                    'status': 'success',
                    'operation': 'export',
                    'format': 'csv_ready',
                    'data': {
                        'headers': headers,
                        'rows': csv_data,
                        'total_rows': len(csv_data)
                    }
                }
            
            else:
                # Return structured data for further processing
                export_data = []
                for move in moves:
                    move_data = self._serialize_comprehensive_move(move, 'full' if include_lines else 'standard')
                    export_data.append(move_data)
                
                return {
                    'status': 'success',
                    'operation': 'export',
                    'format': 'structured',
                    'data': {
                        'moves': export_data,
                        'total_count': len(export_data),
                        'summary': {
                            'total_amount': sum(moves.mapped('amount_total')),
                            'date_range': {
                                'from': min(moves.mapped('date')).isoformat() if moves.mapped('date') else None,
                                'to': max(moves.mapped('date')).isoformat() if moves.mapped('date') else None
                            }
                        }
                    }
                }
        
        except Exception as e:
            _logger.error(f"Error in export operation: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_related_data_operation(self, filters, options):
        """Handle getting related data (partners, cars, employees, etc.)"""
        try:
            data_type = options.get('data_type', 'all')  # partners, cars, employees, vendors, all
            search_term = options.get('search', '')
            limit = min(int(options.get('limit', 50)), 200)
            
            result = {}
            
            if data_type in ['partners', 'all']:
                # Get partners
                partner_domain = []
                if search_term:
                    partner_domain.extend(['|', '|',
                        ('name', 'ilike', search_term),
                        ('email', 'ilike', search_term),
                        ('phone', 'ilike', search_term)
                    ])
                
                partners = request.env['res.partner'].sudo().search(partner_domain, limit=limit)
                result['partners'] = [{
                    'id': p.id,
                    'name': p.name,
                    'email': p.email,
                    'phone': p.phone,
                    'mobile': p.mobile,
                    'is_customer': p.customer_rank > 0,
                    'is_vendor': p.supplier_rank > 0
                } for p in partners]
            
            if data_type in ['cars', 'all']:
                # Get cars
                car_domain = []
                if search_term:
                    car_domain.extend(['|', '|',
                        ('number_plate', 'ilike', search_term),
                        ('brand.name', 'ilike', search_term),
                        ('partner_id.name', 'ilike', search_term)
                    ])
                
                cars = request.env['res.partner.car'].sudo().search(car_domain, limit=limit)
                result['cars'] = [{
                    'id': c.id,
                    'number_plate': c.number_plate,
                    'brand': c.brand.name if c.brand else None,
                    'brand_type': c.brand_type.name if c.brand_type else None,
                    'year': c.year,
                    'partner': {
                        'id': c.partner_id.id,
                        'name': c.partner_id.name
                    } if c.partner_id else None
                } for c in cars]
            
            if data_type in ['employees', 'all']:
                # Get service advisors
                sa_domain = []
                if search_term:
                    sa_domain.append(('name', 'ilike', search_term))
                
                sas = request.env['pitcar.service.advisor'].sudo().search(sa_domain, limit=limit)
                
                # Get mechanics
                mech_domain = []
                if search_term:
                    mech_domain.append(('name', 'ilike', search_term))
                
                mechanics = request.env['pitcar.mechanic.new'].sudo().search(mech_domain, limit=limit)
                
                result['employees'] = {
                    'service_advisors': [{
                        'id': sa.id,
                        'name': sa.name,
                        'type': 'service_advisor'
                    } for sa in sas],
                    'mechanics': [{
                        'id': m.id,
                        'name': m.name,
                        'type': 'mechanic'
                    } for m in mechanics]
                }
            
            if data_type in ['vendors', 'all']:
                # Get vendors (partners with supplier_rank > 0)
                vendor_domain = [('supplier_rank', '>', 0)]
                if search_term:
                    vendor_domain.extend(['|', '|',
                        ('name', 'ilike', search_term),
                        ('email', 'ilike', search_term),
                        ('phone', 'ilike', search_term)
                    ])
                
                vendors = request.env['res.partner'].sudo().search(vendor_domain, limit=limit)
                result['vendors'] = [{
                    'id': v.id,
                    'name': v.name,
                    'email': v.email,
                    'phone': v.phone
                } for v in vendors]
            
            return {
                'status': 'success',
                'operation': 'related_data',
                'data': result
            }
        
        except Exception as e:
            _logger.error(f"Error in related_data operation: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_multi_operation(self, params):
        """Handle multiple operations in one call"""
        try:
            operations = params.get('operations', [])
            results = {}
            
            for op in operations:
                op_name = op.get('name')
                op_type = op.get('operation')
                op_filters = op.get('filters', {})
                op_options = op.get('options', {})
                
                if op_type == 'search':
                    results[op_name] = self._handle_search_operation(op_filters, op_options)
                elif op_type == 'statistics':
                    results[op_name] = self._handle_statistics_operation(op_filters, op_options)
                elif op_type == 'export':
                    results[op_name] = self._handle_export_operation(op_filters, op_options)
                elif op_type == 'related_data':
                    results[op_name] = self._handle_related_data_operation(op_filters, op_options)
            
            return {
                'status': 'success',
                'operation': 'multi',
                'data': results
            }
        
        except Exception as e:
            _logger.error(f"Error in multi operation: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # =====================================
    # OPERATIONS ENDPOINT (CREATE/UPDATE/DELETE)
    # =====================================

    @http.route('/api/accounting/operations', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def accounting_operations(self, **kw):
        """
        POWERFUL OPERATIONS ENDPOINT
        
        Handles all write operations:
        - create: Create new moves
        - update: Update existing moves
        - post: Post moves
        - cancel: Cancel moves
        - bulk_operations: Multiple operations at once
        """
        try:
            # Get parameters
            params = self._get_request_data()
            operation = params.get('operation')
            data = params.get('data', {})
            options = params.get('options', {})
            
            # Authentication check
            auth_result = self._authenticate_api()
            if not auth_result.get('authenticated'):
                return auth_result
            
            if operation == 'create':
                return self._handle_create_move(data, options)
            elif operation == 'update':
                return self._handle_update_move(data, options)
            elif operation == 'post':
                return self._handle_post_moves(data, options)
            elif operation == 'cancel':
                return self._handle_cancel_moves(data, options)
            elif operation == 'bulk':
                return self._handle_bulk_operations(data, options)
            else:
                return {
                    'status': 'error',
                    'message': f"Unknown operation: {operation}",
                    'supported_operations': ['create', 'update', 'post', 'cancel', 'bulk']
                }
        
        except Exception as e:
            _logger.error(f"Error in accounting_operations: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_create_move(self, data, options):
        """Handle move creation"""
        try:
            # Validate required fields
            required_fields = ['move_type', 'partner_id']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return {
                    'status': 'error',
                    'message': f"Missing required fields: {', '.join(missing_fields)}"
                }
            
            # Prepare values
            vals = {
                'move_type': data['move_type'],
                'partner_id': int(data['partner_id']),
                'date': data.get('date', fields.Date.today()),
                'ref': data.get('ref'),
                'invoice_origin': data.get('invoice_origin'),
            }
            
            # Workshop specific fields
            if data.get('service_advisor_ids'):
                vals['service_advisor_id'] = [(6, 0, data['service_advisor_ids'])]
            
            if data.get('partner_car_id'):
                vals['partner_car_id'] = int(data['partner_car_id'])
                vals['partner_car_odometer'] = float(data.get('partner_car_odometer', 0))
            
            if data.get('car_mechanic_ids'):
                vals['car_mechanic_id_new'] = [(6, 0, data['car_mechanic_ids'])]
            
            if data.get('vendor_id'):
                vals['vendor_id'] = int(data['vendor_id'])
            
            if data.get('is_stock_audit'):
                vals['is_stock_audit'] = True
                vals['audit_type'] = data.get('audit_type')
            
            # Create move
            new_move = request.env['account.move'].sudo().create(vals)
            
            # Auto-post if requested
            if options.get('auto_post', False) and new_move.state == 'draft':
                new_move.action_post()
            
            return {
                'status': 'success',
                'operation': 'create',
                'data': {
                    'id': new_move.id,
                    'name': new_move.name,
                    'state': new_move.state,
                    'created': True
                }
            }
        
        except Exception as e:
            _logger.error(f"Error creating move: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_update_move(self, data, options):
        """Handle move update"""
        try:
            move_id = data.get('id')
            if not move_id:
                return {'status': 'error', 'message': 'Move ID is required'}
            
            move = request.env['account.move'].sudo().browse(int(move_id))
            if not move.exists():
                return {'status': 'error', 'message': 'Move not found'}
            
            if move.state == 'posted' and not options.get('allow_posted_edit', False):
                return {'status': 'error', 'message': 'Cannot update posted moves'}
            
            # Prepare update values
            vals = {}
            
            update_fields = [
                'ref', 'invoice_origin', 'partner_car_odometer', 'car_arrival_time',
                'vendor_id', 'is_stock_audit', 'audit_type'
            ]
            
            for field in update_fields:
                if field in data:
                    vals[field] = data[field]
            
            # Handle Many2many fields
            if 'service_advisor_ids' in data:
                vals['service_advisor_id'] = [(6, 0, data['service_advisor_ids'])]
            
            if 'car_mechanic_ids' in data:
                vals['car_mechanic_id_new'] = [(6, 0, data['car_mechanic_ids'])]
            
            # Update move
            move.write(vals)
            
            return {
                'status': 'success',
                'operation': 'update',
                'data': {
                    'id': move.id,
                    'name': move.name,
                    'updated': True
                }
            }
        
        except Exception as e:
            _logger.error(f"Error updating move: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_post_moves(self, data, options):
        """Handle posting moves"""
        try:
            move_ids = data.get('move_ids', [])
            if not move_ids:
                return {'status': 'error', 'message': 'Move IDs are required'}
            
            moves = request.env['account.move'].sudo().browse(move_ids)
            draft_moves = moves.filtered(lambda m: m.state == 'draft')
            
            if not draft_moves:
                return {'status': 'error', 'message': 'No draft moves found to post'}
            
            # Post moves
            posted_moves = []
            failed_moves = []
            
            for move in draft_moves:
                try:
                    move.action_post()
                    posted_moves.append({
                        'id': move.id,
                        'name': move.name,
                        'status': 'posted'
                    })
                except Exception as e:
                    failed_moves.append({
                        'id': move.id,
                        'name': move.name,
                        'error': str(e)
                    })
            
            return {
                'status': 'success',
                'operation': 'post',
                'data': {
                    'posted_moves': posted_moves,
                    'failed_moves': failed_moves,
                    'total_posted': len(posted_moves),
                    'total_failed': len(failed_moves)
                }
            }
        
        except Exception as e:
            _logger.error(f"Error posting moves: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_cancel_moves(self, data, options):
        """Handle canceling moves"""
        try:
            move_ids = data.get('move_ids', [])
            if not move_ids:
                return {'status': 'error', 'message': 'Move IDs are required'}
            
            moves = request.env['account.move'].sudo().browse(move_ids)
            cancelable_moves = moves.filtered(lambda m: m.state in ['draft', 'posted'])
            
            canceled_moves = []
            failed_moves = []
            
            for move in cancelable_moves:
                try:
                    move.button_cancel()
                    canceled_moves.append({
                        'id': move.id,
                        'name': move.name,
                        'status': 'canceled'
                    })
                except Exception as e:
                    failed_moves.append({
                        'id': move.id,
                        'name': move.name,
                        'error': str(e)
                    })
            
            return {
                'status': 'success',
                'operation': 'cancel',
                'data': {
                    'canceled_moves': canceled_moves,
                    'failed_moves': failed_moves,
                    'total_canceled': len(canceled_moves),
                    'total_failed': len(failed_moves)
                }
            }
        
        except Exception as e:
            _logger.error(f"Error canceling moves: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_bulk_operations(self, data, options):
        """Handle multiple operations in sequence"""
        try:
            operations = data.get('operations', [])
            results = []
            
            for op in operations:
                op_type = op.get('operation')
                op_data = op.get('data', {})
                op_options = op.get('options', {})
                
                if op_type == 'create':
                    result = self._handle_create_move(op_data, op_options)
                elif op_type == 'update':
                    result = self._handle_update_move(op_data, op_options)
                elif op_type == 'post':
                    result = self._handle_post_moves(op_data, op_options)
                elif op_type == 'cancel':
                    result = self._handle_cancel_moves(op_data, op_options)
                else:
                    result = {'status': 'error', 'message': f'Unknown operation: {op_type}'}
                
                results.append({
                    'operation': op_type,
                    'result': result
                })
                
                # Stop on first error if requested
                if result.get('status') == 'error' and options.get('stop_on_error', False):
                    break
            
            return {
                'status': 'success',
                'operation': 'bulk',
                'data': {
                    'operations': results,
                    'total_operations': len(results),
                    'successful': len([r for r in results if r['result'].get('status') == 'success']),
                    'failed': len([r for r in results if r['result'].get('status') == 'error'])
                }
            }
        
        except Exception as e:
            _logger.error(f"Error in bulk operations: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # =====================================
    # HEALTH CHECK & UTILITY
    # =====================================

    @http.route('/api/accounting/health', type='json', auth='user', methods=['GET', 'POST'], csrf=False, cors='*')
    def health_check(self, **kw):
        """Comprehensive health check for the API"""
        try:
            # Database connectivity
            request.env.cr.execute("SELECT 1")
            
            # Model accessibility tests
            move_count = request.env['account.move'].sudo().search_count([])
            line_count = request.env['account.move.line'].sudo().search_count([])
            partner_count = request.env['res.partner'].sudo().search_count([])
            
            # Workshop specific model tests
            sa_count = request.env['pitcar.service.advisor'].sudo().search_count([])
            mechanic_count = request.env['pitcar.mechanic.new'].sudo().search_count([])
            car_count = request.env['res.partner.car'].sudo().search_count([])
            
            return {
                'status': 'success',
                'data': {
                    'api_status': 'OK',
                    'database_status': 'OK',
                    'timestamp': datetime.now().isoformat(),
                    'model_counts': {
                        'account_moves': move_count,
                        'move_lines': line_count,
                        'partners': partner_count,
                        'service_advisors': sa_count,
                        'mechanics': mechanic_count,
                        'cars': car_count
                    },
                    'api_endpoints': [
                        '/api/accounting/query',
                        '/api/accounting/operations',
                        '/api/accounting/health'
                    ]
                }
            }
        
        except Exception as e:
            _logger.error(f"Health check failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }