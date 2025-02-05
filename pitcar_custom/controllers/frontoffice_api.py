from odoo import http
from odoo.http import request
import logging
import pytz
from datetime import datetime
import math

_logger = logging.getLogger(__name__)

class FrontOfficeController(http.Controller):
    @http.route('/web/front-office/equipment/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_equipment(self, **kw):
        """Create new front office equipment"""
        try:
            if not kw.get('name'):
                return {'status': 'error', 'message': 'Equipment name is required'}
                
            values = {
                'name': kw['name'],
                'description': kw.get('description'),
                'active': kw.get('active', True)
            }
            
            equipment = request.env['pitcar.front.office.equipment'].sudo().create(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': equipment.id,
                    'name': equipment.name,
                    'description': equipment.description,
                    'active': equipment.active
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in create_equipment: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/front-office/equipment/list', type='json', auth='user', methods=['POST'], csrf=False)
    def get_equipment_list(self, **kw):
        """Get list of front office equipment"""
        try:
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            search = kw.get('search', '').strip()
            show_inactive = kw.get('show_inactive', False)
            
            domain = [] if show_inactive else [('active', '=', True)]
            if search:
                domain += [
                    '|', '|',
                    ('name', 'ilike', search),
                    ('description', 'ilike', search)
                ]
            
            Equipment = request.env['pitcar.front.office.equipment'].sudo()
            total_count = Equipment.search_count(domain)
            equipment = Equipment.search(domain, limit=limit, offset=(page-1)*limit)
            
            rows = [{
                'id': eq.id,
                'name': eq.name,
                'description': eq.description,
                'active': eq.active
            } for eq in equipment]
            
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
            _logger.error(f"Error in get_equipment_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/front-office/equipment/<int:equipment_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_equipment_detail(self, equipment_id, **kw):
        """Get equipment detail"""
        try:
            equipment = request.env['pitcar.front.office.equipment'].sudo().browse(equipment_id)
            if not equipment.exists():
                return {'status': 'error', 'message': 'Equipment not found'}
            
            return {
                'status': 'success',
                'data': {
                    'id': equipment.id,
                    'name': equipment.name,
                    'description': equipment.description,
                    'active': equipment.active
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_equipment_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/front-office/equipment/<int:equipment_id>/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_equipment(self, equipment_id, **kw):
        """Update equipment"""
        try:
            equipment = request.env['pitcar.front.office.equipment'].sudo().browse(equipment_id)
            if not equipment.exists():
                return {'status': 'error', 'message': 'Equipment not found'}
            
            values = {}
            if 'name' in kw:
                values['name'] = kw['name']
            if 'description' in kw:
                values['description'] = kw['description']
            if 'active' in kw:
                values['active'] = kw['active']
            
            if not values:
                return {'status': 'error', 'message': 'No values to update'}
                
            equipment.write(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': equipment.id,
                    'name': equipment.name,
                    'description': equipment.description,
                    'active': equipment.active
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in update_equipment: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/front-office/check/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_check(self, **kw):
        """Create new front office daily check"""
        try:
            required = ['valet_id', 'date']
            if not all(kw.get(field) for field in required):
                return {'status': 'error', 'message': 'Missing required fields'}
            
            values = {
                'valet_id': int(kw['valet_id']),
                'date': kw['date'],
                'notes': kw.get('notes')
            }
            
            check = request.env['pitcar.front.office.check'].sudo().create(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': check.id,
                    'name': check.name,
                    'date': check.date.strftime('%Y-%m-%d'),
                    'valet_id': check.valet_id.id,
                    'state': check.state
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in create_check: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/front-office/check/list', type='json', auth='user', methods=['POST'], csrf=False)
    def get_check_list(self, **kw):
        """Get list of equipment checks"""
        try:
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            search = kw.get('search', '').strip()
            month = kw.get('month')
            valet_id = kw.get('valet_id')
            state = kw.get('state')
            
            domain = []
            if month:
                domain.append(('month', '=', month))
            if valet_id:
                domain.append(('valet_id', '=', int(valet_id)))
            if state:
                domain.append(('state', '=', state))
            if search:
                domain += [
                    '|', '|', '|',
                    ('name', 'ilike', search),
                    ('valet_id.name', 'ilike', search),
                    ('controller_id.name', 'ilike', search),
                    ('notes', 'ilike', search)
                ]
            
            Check = request.env['pitcar.front.office.check'].sudo()
            total_count = Check.search_count(domain)
            checks = Check.search(domain, limit=limit, offset=(page-1)*limit, order='date desc')
            
            rows = []
            for check in checks:
                rows.append({
                    'id': check.id,
                    'name': check.name,
                    'date': check.date.strftime('%Y-%m-%d'),
                    'valet': {
                        'id': check.valet_id.id,
                        'name': check.valet_id.name
                    },
                    'controller': {
                        'id': check.controller_id.id,
                        'name': check.controller_id.name
                    } if check.controller_id else None,
                    'metrics': {
                        'total_items': check.total_items,
                        'complete_items': check.complete_items,
                        'completeness_rate': round(check.completeness_rate, 2)
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
            _logger.error(f"Error in get_check_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/front-office/check/<int:check_id>/detail', type='json', auth='user', methods=['POST'], csrf=False)
    def get_check_detail(self, check_id, **kw):
        """Get equipment check detail"""
        try:
            check = request.env['pitcar.front.office.check'].sudo().browse(check_id)
            if not check.exists():
                return {'status': 'error', 'message': 'Check record not found'}
            
            check_lines = []
            for line in check.check_line_ids:
                check_lines.append({
                    'id': line.id,
                    'equipment': {
                        'id': line.equipment_id.id,
                        'name': line.equipment_id.name
                    },
                    'is_complete': line.is_complete,
                    'notes': line.notes
                })
            
            return {
                'status': 'success',
                'data': {
                    'id': check.id,
                    'name': check.name,
                    'date': check.date.strftime('%Y-%m-%d'),
                    'valet': {
                        'id': check.valet_id.id,
                        'name': check.valet_id.name
                    },
                    'controller': {
                        'id': check.controller_id.id,
                        'name': check.controller_id.name
                    } if check.controller_id else None,
                    'metrics': {
                        'total_items': check.total_items,
                        'complete_items': check.complete_items,
                        'completeness_rate': round(check.completeness_rate, 2)
                    },
                    'state': check.state,
                    'notes': check.notes,
                    'check_lines': check_lines
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_check_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/front-office/check/<int:check_id>/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_check(self, check_id, **kw):
        """Update equipment check"""
        try:
            check = request.env['pitcar.front.office.check'].sudo().browse(check_id)
            if not check.exists():
                return {'status': 'error', 'message': 'Check record not found'}
            
            if check.state == 'done':
                return {'status': 'error', 'message': 'Cannot update completed check'}
            
            # Update check lines
            check_lines = kw.get('check_lines', [])
            for line_data in check_lines:
                line = request.env['pitcar.front.office.check.line'].sudo().browse(line_data['id'])
                if line.exists() and line.check_id.id == check_id:
                    line.write({
                        'is_complete': line_data.get('is_complete', False),
                        'notes': line_data.get('notes')
                    })
            
            # Update main check record
            values = {}
            if 'notes' in kw:
                values['notes'] = kw['notes']
                
            if values:
                check.write(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': check.id,
                    'name': check.name,
                    'completeness_rate': round(check.completeness_rate, 2),
                    'state': check.state
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in update_check: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/front-office/check/<int:check_id>/complete', type='json', auth='user', methods=['POST'], csrf=False)
    def complete_check(self, check_id, **kw):
        """Complete equipment check"""
        try:
            check = request.env['pitcar.front.office.check'].sudo().browse(check_id)
            if not check.exists():
                return {'status': 'error', 'message': 'Check record not found'}
            
            check.action_done()
            
            return {
                'status': 'success',
                'data': {
                    'id': check.id,
                    'name': check.name,
                    'state': check.state,
                    'controller': {
                        'id': check.controller_id.id,
                        'name': check.controller_id.name
                    }
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in complete_check: {str(e)}")
            return {'status': 'error', 'message': str(e)}