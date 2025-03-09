from odoo import http, fields
from odoo.http import request
import logging
import pytz
from datetime import datetime, timedelta
import math
import json

_logger = logging.getLogger(__name__)

class MechanicToolsController(http.Controller):
    
    # ================ TOOL MANAGEMENT ENDPOINTS ================
    
    @http.route('/web/mechanic/tools/master', type='json', auth='user', methods=['POST'], csrf=False)
    def handle_tool_operations(self, **kw):
        """Handle all tool operations with jsonrpc 2.0 format"""
        try:
            _logger.info(f"Received tool request kw: {kw}")
            
            # Get operation from kw (this is where params are stored in Odoo JSONRPC)
            operation = kw.get('operation')
            
            if not operation:
                return {
                    'status': 'error',
                    'message': 'Operation is required'
                }
            
            # Route to appropriate method based on operation
            if operation == 'create':
                return self._create_tool(kw)
            elif operation == 'update':
                return self._update_tool(kw)
            elif operation == 'get':
                return self._get_tool_detail(kw)
            elif operation == 'list':
                return self._get_tools_list(kw)
            elif operation == 'delete':
                return self._delete_tool(kw)
            elif operation == 'assign':
                return self._assign_tool(kw)
            elif operation == 'return':
                return self._return_tool(kw)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown operation: {operation}'
                }
                
        except Exception as e:
            _logger.error(f"Error in handle_tool_operations: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _create_tool(self, params):
        """Create a new tool from jsonrpc params"""
        try:
            # Check required fields
            if not params.get('name'):
                return {
                    'status': 'error',
                    'message': 'Tool name is required'
                }
            
            # Prepare values with all possible fields from params
            values = {
                'name': params.get('name'),
                'code': params.get('code'),
                'description': params.get('description'),
                'active': params.get('active', True),
                'qty_expected': params.get('qty_expected', 1),
                'location': params.get('location'),
                'serial_number': params.get('serial_number'),
                'notes': params.get('notes'),
            }
            
            # Handle category
            if params.get('category_id'):
                values['category_id'] = params.get('category_id')
            
            # Handle mechanic assignment
            if params.get('mechanic_id'):
                values['mechanic_id'] = params.get('mechanic_id')
                values['date_assigned'] = params.get('date_assigned') or date.today()
                values['state'] = 'assigned'
            
            # Handle dates
            date_fields = ['purchase_date', 'warranty_end_date', 'last_maintenance_date']
            for field in date_fields:
                if params.get(field):
                    values[field] = params.get(field)
            
            # Handle maintenance frequency
            if params.get('maintenance_frequency'):
                values['maintenance_frequency'] = params.get('maintenance_frequency')
            
            # Handle state
            if params.get('state'):
                values['state'] = params.get('state')
            
            # Remove None values
            values = {k: v for k, v in values.items() if v is not None}
            
            # Create the tool
            tool = request.env['pitcar.mechanic.hand.tool'].sudo().create(values)
            
            # Return success response
            return {
                'status': 'success',
                'data': {
                    'id': tool.id,
                    'name': tool.name,
                    'code': tool.code,
                    'state': tool.state
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _create_tool: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _get_tools_list(self, params):
        """Get list of tools with filtering and pagination"""
        try:
            # Get parameters
            page = max(1, int(params.get('page', 1)))
            limit = max(1, min(100, int(params.get('limit', 25))))
            search = (params.get('search') or '').strip()
            category_id = params.get('category_id')
            mechanic_id = params.get('mechanic_id')
            state = params.get('state')
            show_inactive = params.get('show_inactive', False)
            
            # Base domain
            domain = [] if show_inactive else [('active', '=', True)]

            # Add filters
            if category_id:
                domain.append(('category_id', '=', int(category_id)))
            if mechanic_id:
                domain.append(('mechanic_id', '=', int(mechanic_id)))
            if state:
                domain.append(('state', '=', state))

            # Add search domain
            if search:
                domain += ['|', '|', '|', '|',
                    ('name', 'ilike', search),
                    ('code', 'ilike', search),
                    ('description', 'ilike', search),
                    ('serial_number', 'ilike', search),
                    ('location', 'ilike', search)]
            
            Tools = request.env['pitcar.mechanic.hand.tool'].sudo()
            total_count = Tools.search_count(domain)
            tools = Tools.search(domain, limit=limit, offset=(page-1)*limit)
            
            rows = []
            for tool in tools:
                rows.append({
                    'id': tool.id,
                    'name': tool.name,
                    'code': tool.code,
                    'category': {
                        'id': tool.category_id.id,
                        'name': tool.category_id.name
                    } if tool.category_id else None,
                    'qty_expected': tool.qty_expected,
                    'mechanic': {
                        'id': tool.mechanic_id.id,
                        'name': tool.mechanic_id.name
                    } if tool.mechanic_id else None,
                    'location': tool.location,
                    'state': tool.state,
                    'active': tool.active
                })
            
            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit),
                        'current_page': page,
                        'items_per_page': limit
                    }
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _get_tools_list: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _get_tool_detail(self, params):
        """Get detailed information about a tool"""
        try:
            tool_id = params.get('id')
            if not tool_id:
                return {
                    'status': 'error',
                    'message': 'Tool ID is required'
                }
            
            tool = request.env['pitcar.mechanic.hand.tool'].sudo().browse(int(tool_id))
            if not tool.exists():
                return {
                    'status': 'error',
                    'message': 'Tool not found'
                }
            
            return {
                'status': 'success',
                'data': {
                    'id': tool.id,
                    'name': tool.name,
                    'code': tool.code,
                    'category': {
                        'id': tool.category_id.id,
                        'name': tool.category_id.name
                    } if tool.category_id else None,
                    'description': tool.description,
                    'qty_expected': tool.qty_expected,
                    'mechanic': {
                        'id': tool.mechanic_id.id,
                        'name': tool.mechanic_id.name
                    } if tool.mechanic_id else None,
                    'date_assigned': tool.date_assigned.strftime('%Y-%m-%d') if tool.date_assigned else None,
                    'location': tool.location,
                    'serial_number': tool.serial_number,
                    'purchase_date': tool.purchase_date.strftime('%Y-%m-%d') if tool.purchase_date else None,
                    'warranty_end_date': tool.warranty_end_date.strftime('%Y-%m-%d') if tool.warranty_end_date else None,
                    'maintenance_frequency': tool.maintenance_frequency,
                    'last_maintenance_date': tool.last_maintenance_date.strftime('%Y-%m-%d') if tool.last_maintenance_date else None,
                    'next_maintenance_date': tool.next_maintenance_date.strftime('%Y-%m-%d') if tool.next_maintenance_date else None,
                    'state': tool.state,
                    'notes': tool.notes,
                    'active': tool.active
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _get_tool_detail: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _update_tool(self, params):
        """Update an existing tool"""
        try:
            tool_id = params.get('id')
            if not tool_id:
                return {
                    'status': 'error',
                    'message': 'Tool ID is required'
                }
            
            tool = request.env['pitcar.mechanic.hand.tool'].sudo().browse(int(tool_id))
            if not tool.exists():
                return {
                    'status': 'error',
                    'message': 'Tool not found'
                }
            
            # Prepare values with all possible fields from params
            allowed_fields = [
                'name', 'code', 'category_id', 'description', 'active', 'qty_expected',
                'mechanic_id', 'date_assigned', 'location', 'serial_number',
                'purchase_date', 'warranty_end_date', 'maintenance_frequency',
                'last_maintenance_date', 'state', 'notes'
            ]
            
            values = {k: params.get(k) for k in allowed_fields if k in params}
            
            if not values:
                return {
                    'status': 'error',
                    'message': 'No values to update'
                }
                
            tool.write(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': tool.id,
                    'name': tool.name,
                    'code': tool.code,
                    'state': tool.state,
                    'active': tool.active
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _update_tool: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _assign_tool(self, params):
        """Assign a tool to a mechanic"""
        try:
            tool_id = params.get('id')
            if not tool_id:
                return {
                    'status': 'error',
                    'message': 'Tool ID is required'
                }
            
            tool = request.env['pitcar.mechanic.hand.tool'].sudo().browse(int(tool_id))
            if not tool.exists():
                return {
                    'status': 'error',
                    'message': 'Tool not found'
                }
            
            mechanic_id = params.get('mechanic_id')
            if not mechanic_id:
                return {
                    'status': 'error',
                    'message': 'Mechanic ID is required'
                }
                
            tool.action_assign(mechanic_id)
            
            return {
                'status': 'success',
                'data': {
                    'id': tool.id,
                    'name': tool.name,
                    'state': tool.state,
                    'mechanic': {
                        'id': tool.mechanic_id.id,
                        'name': tool.mechanic_id.name
                    }
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _assign_tool: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _return_tool(self, params):
        """Return a tool from a mechanic"""
        try:
            tool_id = params.get('id')
            if not tool_id:
                return {
                    'status': 'error',
                    'message': 'Tool ID is required'
                }
            
            tool = request.env['pitcar.mechanic.hand.tool'].sudo().browse(int(tool_id))
            if not tool.exists():
                return {
                    'status': 'error',
                    'message': 'Tool not found'
                }
                
            tool.action_return()
            
            return {
                'status': 'success',
                'data': {
                    'id': tool.id,
                    'name': tool.name,
                    'state': tool.state
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _return_tool: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _delete_tool(self, params):
        """Delete or archive a tool"""
        try:
            tool_id = params.get('id')
            if not tool_id:
                return {
                    'status': 'error',
                    'message': 'Tool ID is required'
                }
            
            tool = request.env['pitcar.mechanic.hand.tool'].sudo().browse(int(tool_id))
            if not tool.exists():
                return {
                    'status': 'error',
                    'message': 'Tool not found'
                }

            # Check if tool is used in any checks
            if request.env['pitcar.mechanic.tool.check.line'].sudo().search_count([('tool_id', '=', tool_id)]) > 0:
                # Just archive if tool is used in check records
                tool.write({'active': False})
                return {
                    'status': 'success',
                    'message': 'Tool has been archived because it is used in check records'
                }
            else:
                # Delete if not used
                tool.unlink()
                return {
                    'status': 'success',
                    'message': 'Tool has been deleted successfully'
                }

        except Exception as e:
            _logger.error(f"Error in _delete_tool: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
            
class MechanicCategories(http.Controller):
    @http.route('/web/mechanic/categories/master', type='json', auth='user', methods=['POST'], csrf=False)
    def handle_category_operations(self, **kw):
        """Handle all category operations with jsonrpc 2.0 format"""
        try:
            _logger.info(f"Received category request kw: {kw}")
            
            # Get operation from kw
            operation = kw.get('operation')
            
            if not operation:
                return {
                    'status': 'error',
                    'message': 'Operation is required'
                }
            
            # Route to appropriate method based on operation
            if operation == 'list':
                return self._get_tool_categories(kw)
            elif operation == 'create':
                return self._create_category(kw)
            elif operation == 'update':
                return self._update_category(kw)
            elif operation == 'delete':
                return self._delete_category(kw)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown operation: {operation}'
                }
                
        except Exception as e:
            _logger.error(f"Error in handle_category_operations: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
            
    def _get_tool_categories(self, params):
        """Get list of tool categories"""
        try:
            search = (params.get('search') or '').strip()
            
            domain = []
            if search:
                domain += [
                    '|',
                    ('name', 'ilike', search),
                    ('description', 'ilike', search)
                ]
            
            categories = request.env['pitcar.tool.category'].sudo().search(domain)
            
            results = []
            for category in categories:
                results.append({
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'parent_id': category.parent_id.id if category.parent_id else None
                })
            
            return {
                'status': 'success',
                'data': results
            }
            
        except Exception as e:
            _logger.error(f"Error in _get_tool_categories: {str(e)}")
            return {'status': 'error', 'message': str(e)}

            
    def _create_category(self, params):
        """Create a new tool category"""
        try:
            if not params.get('name'):
                return {
                    'status': 'error',
                    'message': 'Category name is required'
                }
                
            values = {
                'name': params.get('name'),
                'description': params.get('description'),
            }
            
            # Handle parent_id if provided
            if params.get('parent_id'):
                values['parent_id'] = params.get('parent_id')
                
            category = request.env['pitcar.tool.category'].sudo().create(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'parent_id': category.parent_id.id if category.parent_id else None
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _create_category: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _update_category(self, params):
        """Update an existing tool category"""
        try:
            category_id = params.get('id')
            if not category_id:
                return {
                    'status': 'error',
                    'message': 'Category ID is required'
                }
                
            category = request.env['pitcar.tool.category'].sudo().browse(int(category_id))
            if not category.exists():
                return {
                    'status': 'error',
                    'message': 'Category not found'
                }
                
            values = {}
            if 'name' in params:
                values['name'] = params.get('name')
            if 'description' in params:
                values['description'] = params.get('description')
            if 'parent_id' in params:
                values['parent_id'] = params.get('parent_id')
                
            if not values:
                return {
                    'status': 'error',
                    'message': 'No values to update'
                }
                
            category.write(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'parent_id': category.parent_id.id if category.parent_id else None
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _update_category: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _delete_category(self, params):
        """Delete a tool category"""
        try:
            category_id = params.get('id')
            if not category_id:
                return {
                    'status': 'error',
                    'message': 'Category ID is required'
                }
                
            category = request.env['pitcar.tool.category'].sudo().browse(int(category_id))
            if not category.exists():
                return {
                    'status': 'error',
                    'message': 'Category not found'
                }
                
            # Check if category is used in any tools
            if request.env['pitcar.mechanic.hand.tool'].sudo().search_count([('category_id', '=', category_id)]) > 0:
                return {
                    'status': 'error',
                    'message': 'Cannot delete category that is used by tools'
                }
                
            # Check if category has children
            if request.env['pitcar.tool.category'].sudo().search_count([('parent_id', '=', category_id)]) > 0:
                return {
                    'status': 'error',
                    'message': 'Cannot delete category that has sub-categories'
                }
                
            category.unlink()
            
            return {
                'status': 'success',
                'message': 'Category deleted successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in _delete_category: {str(e)}")
            return {'status': 'error', 'message': str(e)}


class MechanicChecks(http.Controller):
    @http.route('/web/mechanic/checks/master', type='json', auth='user', methods=['POST'], csrf=False)
    def handle_check_operations(self, **kw):
        """Handle all check operations with jsonrpc 2.0 format"""
        try:
            _logger.info(f"Received check request kw: {kw}")
            
            # Get operation from kw
            operation = kw.get('operation')
            
            if not operation:
                return {
                    'status': 'error',
                    'message': 'Operation is required'
                }
            
            # Route to appropriate method based on operation
            if operation == 'create':
                return self._create_check(kw)
            elif operation == 'list':
                return self._get_checks_list(kw)
            elif operation == 'detail':
                return self._get_check_detail(kw)
            elif operation == 'update':
                return self._update_check(kw)
            elif operation == 'complete':
                return self._complete_check(kw)
            elif operation == 'kpi':
                return self._get_check_kpi(kw)
            elif operation == 'dashboard':
                return self._get_dashboard_data(kw)
            elif operation == 'delete':
                return self._delete_check(kw)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown operation: {operation}'
                }
                
        except Exception as e:
            _logger.error(f"Error in handle_check_operations: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }


            
    def _create_check(self, params):
        """Create new mechanic tool check"""
        try:
            required = ['mechanic_id', 'date']
            if not all(params.get(field) for field in required):
                return {'status': 'error', 'message': 'Missing required fields'}
            
            values = {
                'mechanic_id': int(params['mechanic_id']),
                'date': params['date'],
                'notes': params.get('notes')
            }
            
            check = request.env['pitcar.mechanic.tool.check'].sudo().create(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': check.id,
                    'name': check.name,
                    'date': check.date.strftime('%Y-%m-%d'),
                    'mechanic_id': check.mechanic_id.id,
                    'state': check.state
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _create_check: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    def _delete_check(self, params):
        """Delete mechanic tool check"""
        try:
            check_id = params.get('id')
            if not check_id:
                return {
                    'status': 'error',
                    'message': 'Check ID is required'
                }
                
            check = request.env['pitcar.mechanic.tool.check'].sudo().browse(int(check_id))
            if not check.exists():
                return {'status': 'error', 'message': 'Check record not found'}
            
            if check.state == 'done':
                return {'status': 'error', 'message': 'Cannot delete completed check'}
                
            check.unlink()
            
            return {
                'status': 'success',
                'message': 'Check deleted successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in _delete_check: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _get_checks_list(self, params):
        """Get list of mechanic tool checks"""
        try:
            page = max(1, int(params.get('page', 1)))
            limit = max(1, min(100, int(params.get('limit', 25))))
            search = params.get('search', '').strip()
            month = params.get('month')
            mechanic_id = params.get('mechanic_id')
            state = params.get('state')
            
            domain = []
            if month:
                domain.append(('month', '=', month))
            if mechanic_id:
                domain.append(('mechanic_id', '=', int(mechanic_id)))
            if state:
                domain.append(('state', '=', state))
            if search:
                domain += [
                    '|', '|', '|',
                    ('name', 'ilike', search),
                    ('mechanic_id.name', 'ilike', search),
                    ('supervisor_id.name', 'ilike', search),
                    ('notes', 'ilike', search)
                ]
            
            Check = request.env['pitcar.mechanic.tool.check'].sudo()
            total_count = Check.search_count(domain)
            checks = Check.search(domain, limit=limit, offset=(page-1)*limit, order='date desc')
            
            rows = []
            for check in checks:
                rows.append({
                    'id': check.id,
                    'name': check.name,
                    'date': check.date.strftime('%Y-%m-%d'),
                    'mechanic': {
                        'id': check.mechanic_id.id,
                        'name': check.mechanic_id.name
                    },
                    'supervisor': {
                        'id': check.supervisor_id.id,
                        'name': check.supervisor_id.name
                    } if check.supervisor_id else None,
                    'metrics': {
                        'total_items': check.total_items,
                        'matched_items': check.matched_items,
                        'accuracy_rate': round(check.accuracy_rate, 2)
                    },
                    'state': check.state,
                    'notes': check.notes
                })
            
            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit),
                        'current_page': page,
                        'items_per_page': limit
                    }
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _get_checks_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _get_check_detail(self, params):
        """Get mechanic tool check detail"""
        try:
            check_id = params.get('id')
            if not check_id:
                return {
                    'status': 'error',
                    'message': 'Check ID is required'
                }
                
            check = request.env['pitcar.mechanic.tool.check'].sudo().browse(int(check_id))
            if not check.exists():
                return {'status': 'error', 'message': 'Check record not found'}
            
            check_lines = []
            for line in check.check_line_ids:
                check_lines.append({
                    'id': line.id,
                    'tool': {
                        'id': line.tool_id.id,
                        'name': line.tool_id.name,
                        'code': line.tool_id.code
                    },
                    'qty_expected': line.qty_expected,
                    'qty_actual': line.qty_actual,
                    'qty_matched': line.qty_matched,
                    'physical_condition': line.physical_condition,
                    'notes': line.notes
                })
            
            return {
                'status': 'success',
                'data': {
                    'id': check.id,
                    'name': check.name,
                    'date': check.date.strftime('%Y-%m-%d'),
                    'mechanic': {
                        'id': check.mechanic_id.id,
                        'name': check.mechanic_id.name
                    },
                    'supervisor': {
                        'id': check.supervisor_id.id,
                        'name': check.supervisor_id.name
                    } if check.supervisor_id else None,
                    'metrics': {
                        'total_items': check.total_items,
                        'matched_items': check.matched_items,
                        'accuracy_rate': round(check.accuracy_rate, 2)
                    },
                    'state': check.state,
                    'notes': check.notes,
                    'check_lines': check_lines
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _get_check_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _update_check(self, params):
        """Update mechanic tool check"""
        try:
            check_id = params.get('id')
            if not check_id:
                return {
                    'status': 'error',
                    'message': 'Check ID is required'
                }
                
            check = request.env['pitcar.mechanic.tool.check'].sudo().browse(int(check_id))
            if not check.exists():
                return {'status': 'error', 'message': 'Check record not found'}
            
            if check.state == 'done':
                return {'status': 'error', 'message': 'Cannot update completed check'}
            
            # Update check lines
            check_lines = params.get('check_lines', [])
            for line_data in check_lines:
                line_id = line_data.get('id')
                if not line_id:
                    continue
                    
                line = request.env['pitcar.mechanic.tool.check.line'].sudo().browse(int(line_id))
                if line.exists() and line.check_id.id == check.id:
                    line_values = {}
                    
                    if 'qty_actual' in line_data:
                        line_values['qty_actual'] = line_data['qty_actual']
                    if 'physical_condition' in line_data:
                        line_values['physical_condition'] = line_data['physical_condition']
                    if 'notes' in line_data:
                        line_values['notes'] = line_data['notes']
                    
                    if line_values:
                        line.write(line_values)
            
            # Update main check record
            values = {}
            if 'notes' in params:
                values['notes'] = params['notes']
                
            if values:
                check.write(values)
            
            # Refresh the record to get updated computed fields
            check.invalidate_cache()
            
            return {
                'status': 'success',
                'data': {
                    'id': check.id,
                    'name': check.name,
                    'accuracy_rate': round(check.accuracy_rate, 2),
                    'state': check.state
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _update_check: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _complete_check(self, params):
        """Complete mechanic tool check"""
        try:
            check_id = params.get('id')
            if not check_id:
                return {
                    'status': 'error',
                    'message': 'Check ID is required'
                }
                
            check = request.env['pitcar.mechanic.tool.check'].sudo().browse(int(check_id))
            if not check.exists():
                return {'status': 'error', 'message': 'Check record not found'}
            
            check.action_done()
            
            return {
                'status': 'success',
                'data': {
                    'id': check.id,
                    'name': check.name,
                    'state': check.state,
                    'supervisor': {
                        'id': check.supervisor_id.id,
                        'name': check.supervisor_id.name
                    } if check.supervisor_id else None
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _complete_check: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _get_check_kpi(self, params):
        """Get KPI data for mechanic tool checks"""
        try:
            # Parameters
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            mechanic_id = params.get('mechanic_id')
            group_by = params.get('group_by', 'mechanic')  # 'mechanic', 'date', 'month'
            
            # Build domain
            domain = [('state', '=', 'done')]
            if start_date:
                domain.append(('date', '>=', start_date))
            if end_date:
                domain.append(('date', '<=', end_date))
            if mechanic_id:
                domain.append(('mechanic_id', '=', int(mechanic_id)))
            
            # Get all check records matching the domain
            checks = request.env['pitcar.mechanic.tool.check'].sudo().search(domain)
            
            # Group data based on the group_by parameter
            grouped_data = {}
            
            if group_by == 'mechanic':
                for check in checks:
                    mechanic_name = check.mechanic_id.name
                    if mechanic_name not in grouped_data:
                        grouped_data[mechanic_name] = {
                            'mechanic_id': check.mechanic_id.id,
                            'total_checks': 0,
                            'total_items': 0,
                            'matched_items': 0
                        }
                    
                    grouped_data[mechanic_name]['total_checks'] += 1
                    grouped_data[mechanic_name]['total_items'] += check.total_items
                    grouped_data[mechanic_name]['matched_items'] += check.matched_items
            
            elif group_by == 'date':
                for check in checks:
                    date_str = check.date.strftime('%Y-%m-%d')
                    if date_str not in grouped_data:
                        grouped_data[date_str] = {
                            'date': date_str,
                            'total_checks': 0,
                            'total_items': 0,
                            'matched_items': 0
                        }
                    
                    grouped_data[date_str]['total_checks'] += 1
                    grouped_data[date_str]['total_items'] += check.total_items
                    grouped_data[date_str]['matched_items'] += check.matched_items
            
            elif group_by == 'month':
                for check in checks:
                    month_str = check.month
                    if month_str not in grouped_data:
                        grouped_data[month_str] = {
                            'month': month_str,
                            'total_checks': 0,
                            'total_items': 0,
                            'matched_items': 0
                        }
                    
                    grouped_data[month_str]['total_checks'] += 1
                    grouped_data[month_str]['total_items'] += check.total_items
                    grouped_data[month_str]['matched_items'] += check.matched_items
            
            # Calculate accuracy rates
            result = []
            for key, data in grouped_data.items():
                accuracy_rate = 0
                if data['total_items'] > 0:
                    accuracy_rate = (data['matched_items'] / data['total_items']) * 100
                
                data['accuracy_rate'] = round(accuracy_rate, 2)
                result.append(data)
            
            # Sort by group_by field
            if group_by == 'mechanic':
                result.sort(key=lambda x: x['mechanic_id'])
            elif group_by == 'date':
                result.sort(key=lambda x: x['date'])
            elif group_by == 'month':
                result.sort(key=lambda x: x['month'])
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"Error in _get_check_kpi: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _get_dashboard_data(self, params):
        """Get dashboard data for mechanic tool checks"""
        try:
            # Parameters
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            mechanic_id = params.get('mechanic_id')
            
            # Current date for defaults
            today = fields.Date.today()
            start_of_month = today.replace(day=1)
            
            # Use provided dates or defaults
            start_date = start_date or start_of_month.strftime('%Y-%m-%d')
            end_date = end_date or today.strftime('%Y-%m-%d')
            
            # Base domain for all queries
            base_domain = [
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ]
            
            if mechanic_id:
                base_domain.append(('mechanic_id', '=', int(mechanic_id)))
            
            ToolCheck = request.env['pitcar.mechanic.tool.check'].sudo()
            
            # Get total checks
            total_checks = ToolCheck.search_count(base_domain)
            
            # Get completed checks
            completed_domain = base_domain + [('state', '=', 'done')]
            completed_checks = ToolCheck.search_count(completed_domain)
            
            # Get completion rate
            completion_rate = (completed_checks / total_checks * 100) if total_checks else 0
            
            # Get average accuracy rate
            completed_checks_data = ToolCheck.search(completed_domain)
            total_items = sum(check.total_items for check in completed_checks_data)
            matched_items = sum(check.matched_items for check in completed_checks_data)
            avg_accuracy_rate = (matched_items / total_items * 100) if total_items else 0
            
            # Get top performers
            performers = {}
            for check in completed_checks_data:
                mechanic_id = check.mechanic_id.id
                mechanic_name = check.mechanic_id.name
                
                if mechanic_id not in performers:
                    performers[mechanic_id] = {
                        'id': mechanic_id,
                        'name': mechanic_name,
                        'total_items': 0,
                        'matched_items': 0,
                        'check_count': 0
                    }
                
                performers[mechanic_id]['total_items'] += check.total_items
                performers[mechanic_id]['matched_items'] += check.matched_items
                performers[mechanic_id]['check_count'] += 1
            
            # Calculate accuracy rate for each mechanic
            top_performers = []
            for mechanic_data in performers.values():
                if mechanic_data['total_items'] > 0:
                    mechanic_data['accuracy_rate'] = round(
                        (mechanic_data['matched_items'] / mechanic_data['total_items'] * 100), 2
                    )
                    top_performers.append(mechanic_data)
            
            # Sort by accuracy rate and get top 5
            top_performers.sort(key=lambda x: x['accuracy_rate'], reverse=True)
            top_performers = top_performers[:5]
            
            # Get daily trend data
            trend_data = []
            current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            while current_date <= end_date_obj:
                date_str = current_date.strftime('%Y-%m-%d')
                
                day_domain = base_domain + [('date', '=', date_str)]
                day_checks = ToolCheck.search(day_domain)
                
                day_total_items = sum(check.total_items for check in day_checks)
                day_matched_items = sum(check.matched_items for check in day_checks)
                day_rate = (day_matched_items / day_total_items * 100) if day_total_items else 0
                
                trend_data.append({
                    'date': date_str,
                    'check_count': len(day_checks),
                    'accuracy_rate': round(day_rate, 2)
                })
                
                current_date += timedelta(days=1)
            
            return {
                'status': 'success',
                'data': {
                    'summary': {
                        'total_checks': total_checks,
                        'completed_checks': completed_checks,
                        'completion_rate': round(completion_rate, 2),
                        'avg_accuracy_rate': round(avg_accuracy_rate, 2)
                    },
                    'top_performers': top_performers,
                    'trend_data': trend_data
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in _get_dashboard_data: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/mechanic/checks/export', type='http', auth='user')
    def export_tool_check_data(self, **kw):
        """Export mechanic tool check data as Excel file"""
        try:
            import xlsxwriter
            import io
            import base64
            
            # Parameters
            start_date = kw.get('start_date')
            end_date = kw.get('end_date')
            mechanic_id = kw.get('mechanic_id')
            
            # Build domain
            domain = []
            if start_date:
                domain.append(('date', '>=', start_date))
            if end_date:
                domain.append(('date', '<=', end_date))
            if mechanic_id:
                domain.append(('mechanic_id', '=', int(mechanic_id)))
            
            # Get check records
            checks = request.env['pitcar.mechanic.tool.check'].sudo().search(domain, order='date desc, mechanic_id')
            
            # Create Excel file
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            
            # Add styles
            header_style = workbook.add_format({
                'bold': True, 
                'bg_color': '#EFEFEF', 
                'border': 1
            })
            
            cell_style = workbook.add_format({
                'border': 1
            })
            
            percentage_style = workbook.add_format({
                'border': 1,
                'num_format': '0.00%'
            })
            
            # Summary sheet
            worksheet_summary = workbook.add_worksheet('Summary')
            
            # Headers
            worksheet_summary.write(0, 0, 'Date', header_style)
            worksheet_summary.write(0, 1, 'Reference', header_style)
            worksheet_summary.write(0, 2, 'Mechanic', header_style)
            worksheet_summary.write(0, 3, 'Supervisor', header_style)
            worksheet_summary.write(0, 4, 'Total Tools', header_style)
            worksheet_summary.write(0, 5, 'Matched Tools', header_style)
            worksheet_summary.write(0, 6, 'Accuracy Rate', header_style)
            worksheet_summary.write(0, 7, 'State', header_style)
            worksheet_summary.write(0, 8, 'Notes', header_style)
            
            # Data rows
            row = 1
            for check in checks:
                worksheet_summary.write(row, 0, check.date.strftime('%Y-%m-%d'), cell_style)
                worksheet_summary.write(row, 1, check.name, cell_style)
                worksheet_summary.write(row, 2, check.mechanic_id.name, cell_style)
                worksheet_summary.write(row, 3, check.supervisor_id.name if check.supervisor_id else '', cell_style)
                worksheet_summary.write(row, 4, check.total_items, cell_style)
                worksheet_summary.write(row, 5, check.matched_items, cell_style)
                worksheet_summary.write(row, 6, check.accuracy_rate / 100, percentage_style)
                worksheet_summary.write(row, 7, check.state, cell_style)
                worksheet_summary.write(row, 8, check.notes or '', cell_style)
                row += 1
            
            # Adjust column widths
            worksheet_summary.set_column(0, 0, 12)
            worksheet_summary.set_column(1, 1, 20)
            worksheet_summary.set_column(2, 3, 15)
            worksheet_summary.set_column(4, 6, 12)
            worksheet_summary.set_column(7, 7, 10)
            worksheet_summary.set_column(8, 8, 30)
            
            # Details sheet
            worksheet_details = workbook.add_worksheet('Details')
            
            # Headers
            worksheet_details.write(0, 0, 'Date', header_style)
            worksheet_details.write(0, 1, 'Reference', header_style)
            worksheet_details.write(0, 2, 'Mechanic', header_style)
            worksheet_details.write(0, 3, 'Tool', header_style)
            worksheet_details.write(0, 4, 'Tool Code', header_style)
            worksheet_details.write(0, 5, 'Expected Qty', header_style)
            worksheet_details.write(0, 6, 'Actual Qty', header_style)
            worksheet_details.write(0, 7, 'Matched', header_style)
            worksheet_details.write(0, 8, 'Condition', header_style)
            worksheet_details.write(0, 9, 'Line Notes', header_style)
            
            # Data rows
            row = 1
            for check in checks:
                for line in check.check_line_ids:
                    worksheet_details.write(row, 0, check.date.strftime('%Y-%m-%d'), cell_style)
                    worksheet_details.write(row, 1, check.name, cell_style)
                    worksheet_details.write(row, 2, check.mechanic_id.name, cell_style)
                    worksheet_details.write(row, 3, line.tool_id.name, cell_style)
                    worksheet_details.write(row, 4, line.tool_id.code or '', cell_style)
                    worksheet_details.write(row, 5, line.qty_expected, cell_style)
                    worksheet_details.write(row, 6, line.qty_actual, cell_style)
                    worksheet_details.write(row, 7, 'Yes' if line.qty_matched else 'No', cell_style)
                    worksheet_details.write(row, 8, line.physical_condition or '', cell_style)
                    worksheet_details.write(row, 9, line.notes or '', cell_style)
                    row += 1
            
            # Adjust column widths
            worksheet_details.set_column(0, 0, 12)
            worksheet_details.set_column(1, 1, 20)
            worksheet_details.set_column(2, 2, 15)
            worksheet_details.set_column(3, 3, 25)
            worksheet_details.set_column(4, 4, 12)
            worksheet_details.set_column(5, 6, 12)
            worksheet_details.set_column(7, 8, 12)
            worksheet_details.set_column(9, 9, 30)
            
            workbook.close()
            output.seek(0)
            
            filename = f"mechanic_tool_checks_{datetime.now().strftime('%Y%m%d')}.xlsx"
            
            response = request.make_response(
                output.read(),
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', f'attachment; filename={filename}')
                ]
            )
            output.close()
        except Exception as e:
            _logger.error(f"Error in export_tool_check_data: {str(e)}")
            return request.not_found()
        return response