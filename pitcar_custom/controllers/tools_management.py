# controllers/tools_api.py
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class ToolsManagementAPI(http.Controller):
    @http.route('/web/v2/tools/management', type='json', auth='user', methods=['POST'], csrf=False)
    def tools_management(self, **kw):
        """Handle tools management operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                return self._create_tool(kw)
            elif operation == 'get':
                return self._get_tools(kw)
            elif operation == 'update':
                return self._update_tool(kw)
            elif operation == 'delete':
                return self._delete_tool(kw)
            else:
                return {'status': 'error', 'message': 'Invalid operation'}
                
        except Exception as e:
            _logger.error(f"Error in tools_management: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _create_tool(self, data):
        """Create new tool record"""
        required_fields = ['name', 'tool_type', 'expected_lifetime']
        if not all(data.get(field) for field in required_fields):
            return {'status': 'error', 'message': 'Missing required fields'}

        values = {
            'name': data['name'],
            'tool_type': data['tool_type'],
            'expected_lifetime': int(data['expected_lifetime']),
            'requester_id': request.env.user.employee_id.id,
            'notes': data.get('notes', ''),
        }
        
        # Optional fields
        if data.get('purchase_date'):
            values['purchase_date'] = data['purchase_date']
        if data.get('purchase_price'):
            values['purchase_price'] = float(data['purchase_price'])

        tool = request.env['pitcar.tools'].sudo().create(values)
        
        # Handle automatic state changes based on request
        if data.get('state') == 'requested':
            tool.action_request()
        
        return {
            'status': 'success',
            'data': {
                'id': tool.id,
                'reference': tool.reference,
                'name': tool.name,
                'state': tool.state
            }
        }

    def _get_tools(self, data):
        """Get tools records with filtering"""
        domain = []
        
        # Apply filters if provided
        if data.get('tool_type'):
            domain.append(('tool_type', '=', data['tool_type']))
        if data.get('state'):
            domain.append(('state', '=', data['state']))
        if data.get('requester_id'):
            domain.append(('requester_id', '=', int(data['requester_id'])))
        if data.get('approver_id'):
            domain.append(('approver_id', '=', int(data['approver_id'])))
        if data.get('is_premature_broken') is not None:
            domain.append(('is_premature_broken', '=', data['is_premature_broken']))
        if data.get('date_from'):
            domain.append(('request_date', '>=', data['date_from']))
        if data.get('date_to'):
            domain.append(('request_date', '<=', data['date_to']))

        # Get records based on domain
        tools = request.env['pitcar.tools'].sudo().search(domain)
        
        return {
            'status': 'success',
            'data': [{
                'id': record.id,
                'reference': record.reference,
                'name': record.name,
                'request_date': record.request_date,
                'requester_id': record.requester_id.id,
                'requester_name': record.requester_id.name,
                'approver_id': record.approver_id.id if record.approver_id else False,
                'approver_name': record.approver_id.name if record.approver_id else '',
                'tool_type': record.tool_type,
                'expected_lifetime': record.expected_lifetime,
                'depreciation_end_date': record.depreciation_end_date,
                'purchase_date': record.purchase_date,
                'purchase_price': record.purchase_price,
                'state': record.state,
                'broken_date': record.broken_date,
                'is_premature_broken': record.is_premature_broken,
                'notes': record.notes
            } for record in tools]
        }
    
    def _update_tool(self, data):
      """Update existing tool record"""
      if not data.get('id'):
          return {'status': 'error', 'message': 'Missing tool ID'}

      tool = request.env['pitcar.tools'].sudo().browse(int(data['id']))
      if not tool.exists():
          return {'status': 'error', 'message': 'Tool not found'}

      # Check permissions - only admin can update certain states
      is_admin = request.env.user.has_group('base.group_system')
      current_state = tool.state
      
      # Prevent non-admins from updating tools in terminal states
      if not is_admin and current_state in ['broken', 'deprecated']:
          return {'status': 'error', 'message': 'You do not have permission to update this tool in its current state'}

      update_values = {}
      
      # Fields that can be updated
      if 'name' in data:
          update_values['name'] = data['name']
      if 'tool_type' in data:
          update_values['tool_type'] = data['tool_type']
      if 'expected_lifetime' in data:
          update_values['expected_lifetime'] = int(data['expected_lifetime'])
      if 'purchase_date' in data:
          update_values['purchase_date'] = data['purchase_date']
      if 'purchase_price' in data:
          update_values['purchase_price'] = float(data['purchase_price'])
      if 'notes' in data:
          update_values['notes'] = data['notes']

      if update_values:
          tool.write(update_values)

      # Handle state changes if requested
      new_state = data.get('state')
      if new_state and new_state != current_state:
          try:
              # Use the method that includes validation and logging
              tool.change_state(new_state, data.get('status_notes'))
          except Exception as e:
              return {'status': 'error', 'message': str(e)}

      return {
          'status': 'success',
          'data': {
              'id': tool.id,
              'reference': tool.reference,
              'name': tool.name,
              'state': tool.state,
              'is_premature_broken': tool.is_premature_broken
          }
      }

    # Add a new method to get status logs
    def _get_tool_logs(self, data):
        """Get status logs for a specific tool"""
        if not data.get('tool_id'):
            return {'status': 'error', 'message': 'Missing tool ID'}
        
        tool_id = int(data['tool_id'])
        logs = request.env['pitcar.tools.status.log'].sudo().search([
            ('tool_id', '=', tool_id)
        ], order='change_date desc, id desc')
        
        return {
            'status': 'success',
            'data': [{
                'id': log.id,
                'tool_id': log.tool_id.id,
                'tool_name': log.tool_id.name,
                'user_id': log.user_id.id,
                'user_name': log.user_id.name,
                'change_date': log.change_date,
                'old_state': log.old_state,
                'new_state': log.new_state,
                'notes': log.notes
            } for log in logs]
        }

    # Add a new endpoint for tool logs
    @http.route('/web/v2/tools/logs', type='json', auth='user', methods=['POST'], csrf=False)
    def tools_logs(self, **kw):
        """Get tool status logs"""
        try:
            return self._get_tool_logs(kw)
        except Exception as e:
            _logger.error(f"Error in tools_logs: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _delete_tool(self, data):
        """Delete existing tool record"""
        if not data.get('id'):
            return {'status': 'error', 'message': 'Missing tool ID'}

        tool = request.env['pitcar.tools'].sudo().browse(int(data['id']))
        if not tool.exists():
            return {'status': 'error', 'message': 'Tool not found'}

        # Check if user is admin
        is_admin = request.env.user.has_group('base.group_system')
        if not is_admin:
            return {'status': 'error', 'message': 'Only administrators can delete tools'}

        try:
            tool.unlink()
            return {
                'status': 'success',
                'message': 'Tool successfully deleted'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to delete tool: {str(e)}'
            }
            
    @http.route('/web/v2/tools/analytics', type='json', auth='user', methods=['POST'], csrf=False)
    def tools_analytics(self, **kw):
        """Get analytics for tools management"""
        try:
            # Get total counts
            all_tools = request.env['pitcar.tools'].sudo().search([])
            premature_broken = request.env['pitcar.tools'].sudo().search([('is_premature_broken', '=', True)])
            
            # Calculate the percentage of tools that break prematurely
            premature_broken_rate = 0
            if all_tools:
                premature_broken_rate = (len(premature_broken) / len(all_tools)) * 100
            
            # Get tools by state
            tools_by_state = {}
            states = ['draft', 'requested', 'approved', 'purchased', 'in_use', 'broken', 'deprecated']
            for state in states:
                count = request.env['pitcar.tools'].sudo().search_count([('state', '=', state)])
                tools_by_state[state] = count
            
            # Get tools by type
            tools_by_type = {}
            types = ['mechanical', 'electrical', 'diagnostic', 'other']
            for tool_type in types:
                count = request.env['pitcar.tools'].sudo().search_count([('tool_type', '=', tool_type)])
                tools_by_type[tool_type] = count
            
            return {
                'status': 'success',
                'data': {
                    'total_tools': len(all_tools),
                    'premature_broken_count': len(premature_broken),
                    'premature_broken_rate': premature_broken_rate,
                    'tools_by_state': tools_by_state,
                    'tools_by_type': tools_by_type
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in tools_analytics: {str(e)}")
            return {'status': 'error', 'message': str(e)}