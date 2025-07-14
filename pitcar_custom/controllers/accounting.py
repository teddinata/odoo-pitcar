"""
Simplified Workshop Accounting API Controller
============================================
Following campaign API pattern - no API key required, auth='user'
Same endpoint URLs as before
"""

from odoo import http, fields
from odoo.http import request, Response
import logging
import json
import math
from datetime import datetime, timedelta
from io import StringIO
import csv
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger(__name__)

class WorkshopAccountingAPI(http.Controller):
    
    @http.route('/web/accounting/query', type='json', auth='user', methods=['POST'], csrf=False)
    def accounting_query_operations(self, **kw):
        """Main endpoint for accounting query operations"""
        try:
            operation = kw.get('operation', 'search')
            
            if operation == 'search':
                return self._search_moves(kw)
            elif operation == 'statistics':
                return self._get_statistics(kw)
            elif operation == 'export':
                return self._export_data(kw)
            elif operation == 'related_data':
                return self._get_related_data(kw)
            elif operation == 'multi':
                return self._multi_operations(kw)
            else:
                return {
                    'status': 'error',
                    'message': f'Operation "{operation}" not supported. Available: search, statistics, export, related_data, multi'
                }
                
        except Exception as e:
            _logger.error('Error in accounting query API: %s', str(e))
            return {
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }

    @http.route('/web/accounting/operations', type='json', auth='user', methods=['POST'], csrf=False)
    def accounting_write_operations(self, **kw):
        """Main endpoint for accounting write operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                return self._create_move(kw)
            elif operation == 'update':
                return self._update_move(kw)
            elif operation == 'post':
                return self._post_moves(kw)
            elif operation == 'cancel':
                return self._cancel_moves(kw)
            elif operation == 'bulk':
                return self._bulk_operations(kw)
            else:
                return {
                    'status': 'error',
                    'message': f'Operation "{operation}" not supported. Available: create, update, post, cancel, bulk'
                }
                
        except Exception as e:
            _logger.error('Error in accounting operations API: %s', str(e))
            return {
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }

    @http.route('/web/accounting/health', type='json', auth='user', methods=['POST'], csrf=False)
    def health_check(self, **kw):
        """Health check endpoint"""
        try:
            # Basic database connectivity test
            request.env.cr.execute("SELECT 1")
            
            # Test model access
            move_count = request.env['account.move'].search_count([])
            line_count = request.env['account.move.line'].search_count([])
            
            # Workshop specific model tests
            try:
                sa_count = request.env['pitcar.service.advisor'].search_count([])
                mechanic_count = request.env['pitcar.mechanic.new'].search_count([])
                car_count = request.env['res.partner.car'].search_count([])
                workshop_models_accessible = True
            except:
                sa_count = mechanic_count = car_count = 0
                workshop_models_accessible = False
            
            return {
                'status': 'success',
                'data': {
                    'api_status': 'OK',
                    'database_status': 'OK',
                    'user_info': {
                        'user_id': request.env.user.id,
                        'user_name': request.env.user.name,
                        'login': request.env.user.login
                    },
                    'model_counts': {
                        'account_moves': move_count,
                        'move_lines': line_count,
                        'service_advisors': sa_count,
                        'mechanics': mechanic_count,
                        'cars': car_count
                    },
                    'workshop_models_accessible': workshop_models_accessible,
                    'timestamp': datetime.now().isoformat(),
                    'api_endpoints': [
                        '/web/accounting/query',
                        '/web/accounting/operations',
                        '/web/accounting/health'
                    ]
                }
            }
            
        except Exception as e:
            _logger.error('Health check failed: %s', str(e))
            return {
                'status': 'error',
                'message': f'Health check failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }

    # =====================================
    # QUERY OPERATION HANDLERS
    # =====================================

    def _search_moves(self, data):
        """Search account moves with filters"""
        try:
            # Build domain
            domain = self._build_search_domain(data)
            
            # Pagination
            page = max(1, int(data.get('page', 1)))
            limit = max(1, min(100, int(data.get('limit', 25))))
            offset = (page - 1) * limit
            
            # Detail level
            detail_level = data.get('detail_level', 'standard')  # basic, standard, full
            
            # Sorting
            sort_by = data.get('sort_by', 'date')
            sort_order = data.get('sort_order', 'desc')
            order_string = self._build_order_string(sort_by, sort_order)
            
            # Get data
            AccountMove = request.env['account.move']
            total_count = AccountMove.search_count(domain)
            moves = AccountMove.search(domain, limit=limit, offset=offset, order=order_string)
            
            # Serialize data
            rows = []
            for move in moves:
                rows.append(self._serialize_move(move, detail_level))
            
            # Quick statistics if requested
            quick_stats = None
            if data.get('include_quick_stats', False):
                quick_stats = self._calculate_quick_stats(domain)
            
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
                        'filters_applied': len([k for k, v in data.items() if k.startswith(('date_', 'has_', 'is_', 'amount_')) and v]),
                        'detail_level': detail_level,
                        'sort': {'by': sort_by, 'order': sort_order}
                    }
                }
            }
            
        except Exception as e:
            _logger.error('Error in search moves: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error searching moves: {str(e)}'
            }

    def _get_statistics(self, data):
        """Get comprehensive statistics"""
        try:
            # Build domain
            domain = self._build_search_domain(data)
            
            # Get moves for analysis
            moves = request.env['account.move'].search(domain)
            
            if not moves:
                return {
                    'status': 'success',
                    'operation': 'statistics',
                    'data': {'message': 'No data found for the given filters'}
                }
            
            # Calculate statistics
            stats = self._calculate_comprehensive_stats(moves, data)
            
            return {
                'status': 'success',
                'operation': 'statistics',
                'data': stats,
                'meta': {
                    'generated_at': datetime.now().isoformat(),
                    'total_moves_analyzed': len(moves),
                    'date_range': {
                        'from': min(moves.mapped('date')).isoformat() if moves.mapped('date') else None,
                        'to': max(moves.mapped('date')).isoformat() if moves.mapped('date') else None
                    }
                }
            }
            
        except Exception as e:
            _logger.error('Error getting statistics: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error getting statistics: {str(e)}'
            }

    def _export_data(self, data):
        """Export data in various formats"""
        try:
            # Build domain
            domain = self._build_search_domain(data)
            moves = request.env['account.move'].search(domain, order='date desc')
            
            if not moves:
                return {
                    'status': 'success',
                    'operation': 'export',
                    'data': {'message': 'No data to export'}
                }
            
            export_format = data.get('format', 'structured')  # structured, csv_ready
            include_lines = data.get('include_lines', False)
            
            if export_format == 'csv_ready':
                return self._export_csv_format(moves)
            else:
                return self._export_structured_format(moves, include_lines)
                
        except Exception as e:
            _logger.error('Error exporting data: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error exporting data: {str(e)}'
            }

    def _get_related_data(self, data):
        """Get related data (partners, cars, employees, etc.)"""
        try:
            data_type = data.get('data_type', 'all')  # partners, cars, employees, vendors, all
            search_term = data.get('search', '')
            limit = min(int(data.get('limit', 50)), 200)
            
            result = {}
            
            if data_type in ['partners', 'all']:
                result['partners'] = self._get_partners_data(search_term, limit)
            
            if data_type in ['cars', 'all']:
                result['cars'] = self._get_cars_data(search_term, limit)
            
            if data_type in ['employees', 'all']:
                result['employees'] = self._get_employees_data(search_term, limit)
            
            if data_type in ['vendors', 'all']:
                result['vendors'] = self._get_vendors_data(search_term, limit)
            
            return {
                'status': 'success',
                'operation': 'related_data',
                'data': result
            }
            
        except Exception as e:
            _logger.error('Error getting related data: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error getting related data: {str(e)}'
            }

    def _multi_operations(self, data):
        """Execute multiple operations in one call"""
        try:
            operations = data.get('operations', [])
            if not operations:
                return {
                    'status': 'error',
                    'message': 'operations field is required and must be a list'
                }
            
            results = {}
            
            for op in operations:
                op_name = op.get('name', f'operation_{len(results)}')
                op_type = op.get('operation')
                op_data = op.get('data', {})
                op_data.update(op.get('filters', {}))  # Merge filters into data
                op_data.update(op.get('options', {}))  # Merge options into data
                
                try:
                    if op_type == 'search':
                        results[op_name] = self._search_moves(op_data)
                    elif op_type == 'statistics':
                        results[op_name] = self._get_statistics(op_data)
                    elif op_type == 'export':
                        results[op_name] = self._export_data(op_data)
                    elif op_type == 'related_data':
                        results[op_name] = self._get_related_data(op_data)
                    else:
                        results[op_name] = {
                            'status': 'error',
                            'message': f'Unknown operation type: {op_type}'
                        }
                except Exception as e:
                    results[op_name] = {
                        'status': 'error',
                        'message': f'Error in {op_type}: {str(e)}'
                    }
            
            return {
                'status': 'success',
                'operation': 'multi',
                'data': results
            }
            
        except Exception as e:
            _logger.error('Error in multi operations: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error in multi operations: {str(e)}'
            }

    # =====================================
    # WRITE OPERATION HANDLERS
    # =====================================

    def _create_move(self, data):
        """Create new account move"""
        try:
            # Validate required fields
            required_fields = ['move_type', 'partner_id']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return {
                    'status': 'error',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }
            
            # Prepare values
            values = self._prepare_move_values(data)
            
            # Create move
            new_move = request.env['account.move'].create(values)
            
            # Auto-post if requested
            if data.get('auto_post', False) and new_move.state == 'draft':
                new_move.action_post()
            
            return {
                'status': 'success',
                'operation': 'create',
                'data': self._serialize_move(new_move, 'standard'),
                'message': f'Account move "{new_move.name}" created successfully'
            }
            
        except ValidationError as ve:
            return {
                'status': 'error',
                'message': f'Validation error: {str(ve)}'
            }
        except Exception as e:
            _logger.error('Error creating move: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error creating move: {str(e)}'
            }

    def _update_move(self, data):
        """Update existing account move"""
        try:
            move_id = data.get('move_id') or data.get('id')
            if not move_id:
                return {
                    'status': 'error',
                    'message': 'move_id or id is required'
                }
            
            move = request.env['account.move'].browse(int(move_id))
            if not move.exists():
                return {
                    'status': 'error',
                    'message': 'Account move not found'
                }
            
            # Check if move can be updated
            if move.state == 'posted' and not data.get('allow_posted_edit', False):
                return {
                    'status': 'error',
                    'message': 'Cannot update posted moves unless allow_posted_edit is True'
                }
            
            # Prepare update values
            update_values = self._prepare_update_values(data)
            
            if update_values:
                move.write(update_values)
                return {
                    'status': 'success',
                    'operation': 'update',
                    'data': self._serialize_move(move, 'standard'),
                    'message': f'Account move "{move.name}" updated successfully'
                }
            else:
                return {
                    'status': 'error',
                    'message': 'No valid fields to update'
                }
                
        except Exception as e:
            _logger.error('Error updating move: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error updating move: {str(e)}'
            }

    def _post_moves(self, data):
        """Post account moves"""
        try:
            move_ids = data.get('move_ids', [])
            if not move_ids:
                return {
                    'status': 'error',
                    'message': 'move_ids is required and must be a list'
                }
            
            moves = request.env['account.move'].browse(move_ids)
            draft_moves = moves.filtered(lambda m: m.state == 'draft')
            
            if not draft_moves:
                return {
                    'status': 'error',
                    'message': 'No draft moves found to post'
                }
            
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
                'status': 'partial_success' if failed_moves else 'success',
                'operation': 'post',
                'data': {
                    'posted_moves': posted_moves,
                    'failed_moves': failed_moves,
                    'total_posted': len(posted_moves),
                    'total_failed': len(failed_moves)
                },
                'message': f'Posted {len(posted_moves)} moves, {len(failed_moves)} failed'
            }
            
        except Exception as e:
            _logger.error('Error posting moves: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error posting moves: {str(e)}'
            }

    def _cancel_moves(self, data):
        """Cancel account moves"""
        try:
            move_ids = data.get('move_ids', [])
            if not move_ids:
                return {
                    'status': 'error',
                    'message': 'move_ids is required and must be a list'
                }
            
            moves = request.env['account.move'].browse(move_ids)
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
                'status': 'partial_success' if failed_moves else 'success',
                'operation': 'cancel',
                'data': {
                    'canceled_moves': canceled_moves,
                    'failed_moves': failed_moves,
                    'total_canceled': len(canceled_moves),
                    'total_failed': len(failed_moves)
                },
                'message': f'Canceled {len(canceled_moves)} moves, {len(failed_moves)} failed'
            }
            
        except Exception as e:
            _logger.error('Error canceling moves: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error canceling moves: {str(e)}'
            }

    def _bulk_operations(self, data):
        """Execute bulk operations in sequence"""
        try:
            operations = data.get('operations', [])
            if not operations:
                return {
                    'status': 'error',
                    'message': 'operations field is required and must be a list'
                }
            
            results = []
            stop_on_error = data.get('stop_on_error', False)
            
            for i, op in enumerate(operations):
                op_type = op.get('operation')
                op_data = op.get('data', {})
                
                try:
                    if op_type == 'create':
                        result = self._create_move(op_data)
                    elif op_type == 'update':
                        result = self._update_move(op_data)
                    elif op_type == 'post':
                        result = self._post_moves(op_data)
                    elif op_type == 'cancel':
                        result = self._cancel_moves(op_data)
                    else:
                        result = {
                            'status': 'error',
                            'message': f'Unknown operation: {op_type}'
                        }
                    
                    results.append({
                        'index': i,
                        'operation': op_type,
                        'result': result
                    })
                    
                    # Stop on first error if requested
                    if result.get('status') == 'error' and stop_on_error:
                        break
                        
                except Exception as e:
                    error_result = {
                        'index': i,
                        'operation': op_type,
                        'result': {
                            'status': 'error',
                            'message': str(e)
                        }
                    }
                    results.append(error_result)
                    
                    if stop_on_error:
                        break
            
            successful = len([r for r in results if r['result'].get('status') == 'success'])
            failed = len([r for r in results if r['result'].get('status') == 'error'])
            
            return {
                'status': 'partial_success' if failed > 0 else 'success',
                'operation': 'bulk',
                'data': {
                    'operations': results,
                    'summary': {
                        'total_operations': len(results),
                        'successful': successful,
                        'failed': failed
                    }
                },
                'message': f'Executed {len(results)} operations: {successful} successful, {failed} failed'
            }
            
        except Exception as e:
            _logger.error('Error in bulk operations: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error in bulk operations: {str(e)}'
            }

    # =====================================
    # UTILITY METHODS
    # =====================================

    def _build_search_domain(self, data):
        """Build search domain from filters"""
        domain = []
        
        # Basic filters
        if data.get('ids'):
            domain.append(('id', 'in', data['ids']))
        
        if data.get('state'):
            domain.append(('state', '=', data['state']))
        
        if data.get('move_type'):
            domain.append(('move_type', '=', data['move_type']))
        
        # Date filters
        if data.get('date_from'):
            domain.append(('date', '>=', data['date_from']))
        if data.get('date_to'):
            domain.append(('date', '<=', data['date_to']))
        
        # Partner filters
        if data.get('partner_id'):
            domain.append(('partner_id', '=', data['partner_id']))
        if data.get('partner_ids'):
            domain.append(('partner_id', 'in', data['partner_ids']))
        
        # Workshop specific filters
        if data.get('has_car') is not None:
            domain.append(('partner_car_id', '!=' if data['has_car'] else '=', False))
        
        if data.get('has_service_advisor') is not None:
            domain.append(('service_advisor_id', '!=' if data['has_service_advisor'] else '=', False))
        
        if data.get('has_mechanic') is not None:
            domain.append(('car_mechanic_id_new', '!=' if data['has_mechanic'] else '=', False))
        
        if data.get('service_advisor_ids'):
            domain.append(('service_advisor_id', 'in', data['service_advisor_ids']))
        
        if data.get('mechanic_ids'):
            domain.append(('car_mechanic_id_new', 'in', data['mechanic_ids']))
        
        # Vendor filters
        if data.get('vendor_id'):
            domain.append(('vendor_id', '=', data['vendor_id']))
        if data.get('vendor_ids'):
            domain.append(('vendor_id', 'in', data['vendor_ids']))
        
        # Audit filters
        if data.get('is_stock_audit') is not None:
            domain.append(('is_stock_audit', '=', data['is_stock_audit']))
        
        if data.get('audit_type'):
            domain.append(('audit_type', '=', data['audit_type']))
        
        if data.get('within_tolerance') is not None:
            domain.append(('is_within_tolerance', '=', data['within_tolerance']))
        
        # Amount filters
        if data.get('amount_min'):
            domain.append(('amount_total', '>=', data['amount_min']))
        if data.get('amount_max'):
            domain.append(('amount_total', '<=', data['amount_max']))
        
        # Search filter
        if data.get('search'):
            search_terms = data['search'].split()
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

    def _build_order_string(self, sort_by, sort_order):
        """Build order string for search"""
        valid_sort_fields = {
            'name': 'name',
            'date': 'date', 
            'partner': 'partner_id',
            'amount': 'amount_total',
            'state': 'state',
            'created': 'create_date'
        }
        
        sort_field = valid_sort_fields.get(sort_by, 'date')
        return f"{sort_field} {sort_order}"

    def _serialize_move(self, move, detail_level='basic'):
        """Serialize account move to dict"""
        # Basic data
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
        
        # Standard data
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
        
        # Full data
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
            if hasattr(move, 'recommendation_ids') and move.recommendation_ids:
                data['recommendations'] = [{
                    'id': rec.id,
                    'name': getattr(rec, 'name', str(rec))
                } for rec in move.recommendation_ids]
        
        return data

    def _prepare_move_values(self, data):
        """Prepare values for move creation"""
        values = {
            'move_type': data['move_type'],
            'partner_id': int(data['partner_id']),
            'date': data.get('date', fields.Date.today()),
            'ref': data.get('ref'),
            'invoice_origin': data.get('invoice_origin'),
        }
        
        # Workshop specific fields
        if data.get('service_advisor_ids'):
            values['service_advisor_id'] = [(6, 0, data['service_advisor_ids'])]
        
        if data.get('partner_car_id'):
            values['partner_car_id'] = int(data['partner_car_id'])
            values['partner_car_odometer'] = float(data.get('partner_car_odometer', 0))
        
        if data.get('car_mechanic_ids'):
            values['car_mechanic_id_new'] = [(6, 0, data['car_mechanic_ids'])]
        
        if data.get('vendor_id'):
            values['vendor_id'] = int(data['vendor_id'])
        
        if data.get('is_stock_audit'):
            values['is_stock_audit'] = True
            values['audit_type'] = data.get('audit_type')
        
        if data.get('car_arrival_time'):
            values['car_arrival_time'] = data['car_arrival_time']
        
        return values

    def _prepare_update_values(self, data):
        """Prepare values for move update"""
        values = {}
        
        updatable_fields = [
            'ref', 'invoice_origin', 'partner_car_odometer', 'car_arrival_time',
            'vendor_id', 'is_stock_audit', 'audit_type'
        ]
        
        for field in updatable_fields:
            if field in data:
                values[field] = data[field]
        
        # Handle Many2many fields
        if 'service_advisor_ids' in data:
            values['service_advisor_id'] = [(6, 0, data['service_advisor_ids'])]
        
        if 'car_mechanic_ids' in data:
            values['car_mechanic_id_new'] = [(6, 0, data['car_mechanic_ids'])]
        
        return values

    def _calculate_quick_stats(self, domain):
        """Calculate quick statistics for search results"""
        moves = request.env['account.move'].search(domain)
        
        stats = {
            'total_count': len(moves),
            'total_amount': sum(moves.mapped('amount_total')),
            'avg_amount': sum(moves.mapped('amount_total')) / len(moves) if moves else 0,
            'by_state': {},
            'by_type': {}
        }
        
        # Count by state
        for state in ['draft', 'posted', 'cancel']:
            stats['by_state'][state] = len(moves.filtered(lambda m: m.state == state))
        
        # Count by type
        for move_type in ['entry', 'out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            stats['by_type'][move_type] = len(moves.filtered(lambda m: m.move_type == move_type))
        
        return stats

    def _calculate_comprehensive_stats(self, moves, options):
        """Calculate comprehensive statistics"""
        stats = {
            'overview': {
                'total_moves': len(moves),
                'total_amount': sum(moves.mapped('amount_total')),
                'average_amount': sum(moves.mapped('amount_total')) / len(moves) if moves else 0,
            },
            'by_state': {},
            'by_type': {},
            'workshop_analytics': {
                'with_cars': len(moves.filtered('partner_car_id')),
                'with_service_advisors': len(moves.filtered('service_advisor_id')),
                'with_mechanics': len(moves.filtered('car_mechanic_id_new')),
                'stock_audits': len(moves.filtered('is_stock_audit')),
                'within_tolerance': len(moves.filtered('is_within_tolerance'))
            }
        }
        
        # Count by state
        for state in ['draft', 'posted', 'cancel']:
            filtered_moves = moves.filtered(lambda m: m.state == state)
            stats['by_state'][state] = {
                'count': len(filtered_moves),
                'amount': sum(filtered_moves.mapped('amount_total'))
            }
        
        # Count by type
        for move_type in ['entry', 'out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            filtered_moves = moves.filtered(lambda m: m.move_type == move_type)
            stats['by_type'][move_type] = {
                'count': len(filtered_moves),
                'amount': sum(filtered_moves.mapped('amount_total'))
            }
        
        # Monthly breakdown if requested
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
        
        # Top analysis if requested
        if options.get('include_top_analysis', True):
            stats['top_customers'] = self._get_top_partners(moves, 'customer')
            stats['top_vendors'] = self._get_top_partners(moves, 'vendor')
        
        # Customer analysis if requested
        if options.get('include_customer_analysis', True):
            stats['customer_analysis'] = self._get_customer_analysis(moves)
        
        return stats

    def _get_top_partners(self, moves, partner_type='customer'):
        """Get top partners by transaction volume"""
        partner_stats = {}
        
        if partner_type == 'customer':
            partner_moves = moves.filtered('partner_id')
            partner_field = 'partner_id'
        else:  # vendor
            partner_moves = moves.filtered('vendor_id')
            partner_field = 'vendor_id'
        
        for move in partner_moves:
            partner = getattr(move, partner_field)
            partner_id = partner.id
            
            if partner_id not in partner_stats:
                partner_stats[partner_id] = {
                    'id': partner_id,
                    'name': partner.name,
                    'count': 0,
                    'amount': 0
                }
            
            partner_stats[partner_id]['count'] += 1
            partner_stats[partner_id]['amount'] += move.amount_total
        
        # Sort by amount and return top 10
        return sorted(partner_stats.values(), key=lambda x: x['amount'], reverse=True)[:10]

    def _get_customer_analysis(self, moves):
        """Get customer source analysis"""
        # Get move lines for customer analysis
        move_ids = moves.ids
        lines = request.env['account.move.line'].search([
            ('move_id', 'in', move_ids),
            ('customer_source', '!=', False)
        ])
        
        source_stats = {}
        for line in lines:
            source = line.customer_source
            if source not in source_stats:
                source_stats[source] = 0
            source_stats[source] += 1
        
        loyal_count = len(lines.filtered('is_loyal_customer'))
        total_count = len(lines)
        
        return {
            'customer_sources': source_stats,
            'loyal_customers': {
                'count': loyal_count,
                'percentage': (loyal_count / total_count * 100) if total_count > 0 else 0
            }
        }

    def _export_csv_format(self, moves):
        """Export in CSV-ready format"""
        headers = [
            'Number', 'Date', 'Reference', 'Partner', 'Type', 'State',
            'Amount Total', 'Amount Tax', 'Car Plate', 'Car Brand',
            'Service Advisors', 'Mechanics', 'Vendor', 'Is Audit',
            'Created Date'
        ]
        
        csv_data = []
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

    def _export_structured_format(self, moves, include_lines):
        """Export in structured format"""
        export_data = []
        for move in moves:
            move_data = self._serialize_move(move, 'full' if include_lines else 'standard')
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

    def _get_partners_data(self, search_term, limit):
        """Get partners data"""
        domain = []
        if search_term:
            domain.extend(['|', '|',
                ('name', 'ilike', search_term),
                ('email', 'ilike', search_term),
                ('phone', 'ilike', search_term)
            ])
        
        partners = request.env['res.partner'].search(domain, limit=limit)
        return [{
            'id': p.id,
            'name': p.name,
            'email': p.email,
            'phone': p.phone,
            'mobile': p.mobile,
            'is_customer': p.customer_rank > 0,
            'is_vendor': p.supplier_rank > 0
        } for p in partners]

    def _get_cars_data(self, search_term, limit):
        """Get cars data"""
        domain = []
        if search_term:
            domain.extend(['|', '|',
                ('number_plate', 'ilike', search_term),
                ('brand.name', 'ilike', search_term),
                ('partner_id.name', 'ilike', search_term)
            ])
        
        cars = request.env['res.partner.car'].search(domain, limit=limit)
        return [{
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

    def _get_employees_data(self, search_term, limit):
        """Get employees data"""
        # Get service advisors
        sa_domain = []
        if search_term:
            sa_domain.append(('name', 'ilike', search_term))
        
        sas = request.env['pitcar.service.advisor'].search(sa_domain, limit=limit)
        
        # Get mechanics
        mech_domain = []
        if search_term:
            mech_domain.append(('name', 'ilike', search_term))
        
        mechanics = request.env['pitcar.mechanic.new'].search(mech_domain, limit=limit)
        
        return {
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

    def _get_vendors_data(self, search_term, limit):
        """Get vendors data"""
        domain = [('supplier_rank', '>', 0)]
        if search_term:
            domain.extend(['|', '|',
                ('name', 'ilike', search_term),
                ('email', 'ilike', search_term),
                ('phone', 'ilike', search_term)
            ])
        
        vendors = request.env['res.partner'].search(domain, limit=limit)
        return [{
            'id': v.id,
            'name': v.name,
            'email': v.email,
            'phone': v.phone
        } for v in vendors]