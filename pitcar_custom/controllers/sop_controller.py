from odoo import http, fields
from odoo.http import request, Response
import logging
import pytz
from datetime import datetime
import math

_logger = logging.getLogger(__name__)

class SOPController(http.Controller):
    def _get_request_data(self):
        """Helper to handle JSONRPC request data"""
        try:
            if request.jsonrequest:
                params = request.jsonrequest.get('params', {})
                _logger.info(f"JSONRPC Params received: {params}")
                return params
            return {}
        except Exception as e:
            _logger.error(f"Error parsing request data: {str(e)}")
            return {}

    @http.route('/web/sop/master/list', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sop_list(self, **kw):
        """Get list of SOPs"""
        try:
            params = self._get_request_data()
            page = int(params.get('page', 1))
            limit = int(params.get('limit', 25))
            search = params.get('search', '').strip()
            department = params.get('department')
            is_sa = params.get('is_sa')

            domain = [('active', '=', True)]
            if search:
                domain += ['|', '|',
                    ('name', 'ilike', search),
                    ('code', 'ilike', search),
                    ('description', 'ilike', search)
                ]
            if department:
                domain.append(('department', '=', department))
            if is_sa is not None:
                domain.append(('is_sa', '=', is_sa))

            SOP = request.env['pitcar.sop']
            total_count = SOP.search_count(domain)
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            offset = (page - 1) * limit

            sops = SOP.search(domain, limit=limit, offset=offset)
            rows = [{
                'id': sop.id,
                'code': sop.code,
                'name': sop.name,
                'description': sop.description,
                'department': sop.department,
                'is_sa': sop.is_sa
            } for sop in sops]

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': total_pages,
                        'current_page': page,
                        'items_per_page': limit
                    }
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_sop_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/available-orders', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_available_orders(self, **kw):
        """Get list of available sale orders for sampling"""
        try:
            # Extract parameters dari kw
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 25))
            search = kw.get('search', '').strip()
            is_sa = kw.get('is_sa')  # Filter untuk SOP SA/Mekanik

            # Base domain untuk sale orders yang aktif
            domain = [('state', 'in', ['sale', 'done'])]
            
            # Search filter
            if search:
                domain += ['|', '|', '|', '|',
                    ('name', 'ilike', search),
                    ('partner_car_id.number_plate', 'ilike', search),
                    ('mechanic_id.name', 'ilike', search),
                    ('service_advisor_id.name', 'ilike', search)
                ]

            # Filter berdasarkan tipe SOP (SA/Mekanik)
            if is_sa is not None:
                if is_sa:
                    domain.append(('service_advisor_id', '!=', False))
                else:
                    domain.append(('car_mechanic_id_new', '!=', False))

            # Hitung total dan pagination
            SaleOrder = request.env['sale.order']
            total_count = SaleOrder.search_count(domain)
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            offset = (page - 1) * limit

            # Get records
            orders = SaleOrder.search(domain, limit=limit, offset=offset)
            
            # Format response
            rows = [{
                'id': order.id,
                'name': order.name,
                'date': order.create_date.strftime('%Y-%m-%d %H:%M:%S'),
                'car_info': {
                    'plate': order.partner_car_id.number_plate if order.partner_car_id else None,
                    'brand': order.partner_car_brand.name if order.partner_car_brand else None,
                    'type': order.partner_car_brand_type.name if order.partner_car_brand_type else None
                },
                'employee_info': {
                    'mechanic': [{
                        'id': mech.id,
                        'name': mech.name,
                        'sampling_count': len(order.sop_sampling_ids.filtered(
                            lambda s: not s.sop_id.is_sa and mech.id in s.mechanic_id.ids
                        ))
                    } for mech in order.car_mechanic_id_new] if order.car_mechanic_id_new else [],
                    'service_advisor': [{
                        'id': sa.id,
                        'name': sa.name,
                        'sampling_count': len(order.sop_sampling_ids.filtered(
                            lambda s: s.sop_id.is_sa and sa.id in s.sa_id.ids
                        ))
                    } for sa in order.service_advisor_id] if order.service_advisor_id else []
                },
                'sampling_count': len(order.sop_sampling_ids)
            } for order in orders]

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': total_pages,
                        'current_page': page,
                        'items_per_page': limit
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_available_orders: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_sampling(self, **kw):
        """Create new SOP sampling"""
        try:
            # Extract parameters langsung dari kw
            sale_order_id = kw.get('sale_order_id')
            sop_id = kw.get('sop_id')
            notes = kw.get('notes')

            # Validate required fields
            if not sale_order_id:
                return {'status': 'error', 'message': 'Sale order ID is required'}
            if not sop_id:
                return {'status': 'error', 'message': 'SOP ID is required'}

            # Get Sale Order dan SOP
            sale_order = request.env['sale.order'].browse(sale_order_id)
            sop = request.env['pitcar.sop'].browse(sop_id)

            if not sale_order.exists():
                return {'status': 'error', 'message': 'Sale order not found'}
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP not found'}

            # Get controller employee from current user
            controller = request.env.user.employee_id
            if not controller:
                return {'status': 'error', 'message': 'Current user has no employee record'}

            # Create sampling dengan values yang sudah termasuk SA/Mekanik
            values = {
                'sale_order_id': sale_order_id,
                'sop_id': sop_id,
                'controller_id': controller.id,
                'notes': notes,
                'state': 'draft'
            }

            # Tambahkan SA/Mekanik sesuai tipe SOP
            if sop.is_sa:
                if not sale_order.service_advisor_id:
                    return {'status': 'error', 'message': 'Sale order has no Service Advisor assigned'}
                values['sa_id'] = [(6, 0, sale_order.service_advisor_id.ids)]
            else:
                if not sale_order.car_mechanic_id_new:
                    return {'status': 'error', 'message': 'Sale order has no Mechanic assigned'}
                values['mechanic_id'] = [(6, 0, sale_order.car_mechanic_id_new.ids)]

            sampling = request.env['pitcar.sop.sampling'].create(values)

            return {
                'status': 'success',
                'data': {
                    'id': sampling.id,
                    'name': sampling.name,
                    'sale_order_id': sampling.sale_order_id.id,
                    'sop_id': sampling.sop_id.id,
                    'employee_info': {
                        'sa_id': sampling.sa_id.ids if sampling.sa_id else [],
                        'mechanic_id': sampling.mechanic_id.ids if sampling.mechanic_id else []
                    },
                    'state': sampling.state
                }
            }

        except Exception as e:
            _logger.error(f"Error in create_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}
      
    @http.route('/web/sop/sampling/bulk-create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_bulk_sampling(self, **kw):
        """Create multiple SOP samplings for one sale order"""
        try:
            # Extract parameters
            sale_order_id = kw.get('sale_order_id')
            sampling_data = kw.get('samplings', [])  # List of SOP samplings to create

            if not sale_order_id:
                return {'status': 'error', 'message': 'Sale order ID is required'}
            if not sampling_data:
                return {'status': 'error', 'message': 'No sampling data provided'}

            sale_order = request.env['sale.order'].browse(sale_order_id)
            if not sale_order.exists():
                return {'status': 'error', 'message': 'Sale order not found'}

            # Get controller
            controller = request.env.user.employee_id
            if not controller:
                return {'status': 'error', 'message': 'Current user has no employee record'}

            created_samplings = []
            for data in sampling_data:
                sop_id = data.get('sop_id')
                notes = data.get('notes')

                if not sop_id:
                    continue

                sop = request.env['pitcar.sop'].browse(sop_id)
                if not sop.exists():
                    continue

                # Prepare values
                values = {
                    'sale_order_id': sale_order_id,
                    'sop_id': sop_id,
                    'controller_id': controller.id,
                    'notes': notes,
                    'state': 'draft'
                }

                # Set SA/Mechanic based on SOP type
                if sop.is_sa:
                    if sale_order.service_advisor_id:
                        values['sa_id'] = [(6, 0, sale_order.service_advisor_id.ids)]
                else:
                    if sale_order.car_mechanic_id_new:
                        values['mechanic_id'] = [(6, 0, sale_order.car_mechanic_id_new.ids)]

                # Create sampling
                sampling = request.env['pitcar.sop.sampling'].create(values)
                created_samplings.append({
                    'id': sampling.id,
                    'name': sampling.name,
                    'sop_id': sampling.sop_id.id,
                    'employee_info': {
                        'sa_id': sampling.sa_id.ids if sampling.sa_id else [],
                        'mechanic_id': sampling.mechanic_id.ids if sampling.mechanic_id else []
                    }
                })

            return {
                'status': 'success',
                'data': {
                    'sale_order_id': sale_order_id,
                    'samplings': created_samplings
                }
            }

        except Exception as e:
            _logger.error(f"Error in create_bulk_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/list', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sampling_list(self, **kw):
        """Get list of sampling records"""
        try:
            params = self._get_request_data()
            page = int(params.get('page', 1))
            limit = int(params.get('limit', 25))
            search = params.get('search', '').strip()
            month = params.get('month')
            is_sa = params.get('is_sa')

            domain = []
            if month:
                domain.append(('month', '=', month))
            if search:
                domain += ['|', '|', '|',
                    ('sale_order_id.name', 'ilike', search),
                    ('sa_id.name', 'ilike', search),
                    ('mechanic_id.name', 'ilike', search),
                    ('sop_id.name', 'ilike', search)
                ]
            if is_sa is not None:
                domain.append(('sop_id.is_sa', '=', is_sa))

            Sampling = request.env['pitcar.sop.sampling']
            total_count = Sampling.search_count(domain)
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            offset = (page - 1) * limit

            samplings = Sampling.search(domain, limit=limit, offset=offset)
            rows = [{
                'id': sampling.id,
                'name': sampling.name,
                'date': sampling.date.strftime('%Y-%m-%d'),
                'sale_order': {
                    'id': sampling.sale_order_id.id,
                    'name': sampling.sale_order_id.name,
                    'car_plate': sampling.sale_order_id.partner_car_id.number_plate if sampling.sale_order_id.partner_car_id else None
                },
                'sop': {
                    'id': sampling.sop_id.id,
                    'name': sampling.sop_id.name,
                    'code': sampling.sop_id.code,
                    'is_sa': sampling.sop_id.is_sa
                },
                'employee': {
                    'service_advisor': [{
                        'id': sa.id,
                        'name': sa.name
                    } for sa in sampling.sa_id] if sampling.sa_id else [],
                    'mechanic': [{
                        'id': mech.id,
                        'name': mech.name
                    } for mech in sampling.mechanic_id] if sampling.mechanic_id else []
                },
                'controller': {
                    'id': sampling.controller_id.id,
                    'name': sampling.controller_id.name
                } if sampling.controller_id else None,
                'state': sampling.state,
                'result': sampling.result,
                'notes': sampling.notes
            } for sampling in samplings]

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': total_pages,
                        'current_page': page,
                        'items_per_page': limit
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_sampling_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/validate', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def validate_sampling(self, **kw):
        """Validate sampling result"""
        try:
            params = self._get_request_data()
            
            # Get parameters from both kw and params
            sampling_id = kw.get('sampling_id') or params.get('sampling_id')
            result = kw.get('result') or params.get('result')
            notes = kw.get('notes') or params.get('notes')
            
            # Validate required parameters
            if not sampling_id:
                return {'status': 'error', 'message': 'Sampling ID is required'}
            if not result:
                return {'status': 'error', 'message': 'Result is required'}

            sampling = request.env['pitcar.sop.sampling'].browse(sampling_id)
            if not sampling.exists():
                return {'status': 'error', 'message': 'Sampling not found'}

            # Update sampling
            values = {
                'state': 'done',
                'result': result,
                'notes': notes
            }

            sampling.write(values)
            
            # Return updated data
            return {
                'status': 'success',
                'data': {
                    'id': sampling.id,
                    'name': sampling.name,
                    'result': sampling.result,
                    'state': sampling.state,
                    'notes': sampling.notes
                }
            }

        except Exception as e:
            _logger.error(f"Error in validate_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/summary', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sampling_summary(self, **kw):
        """Get sampling summary statistics"""
        try:
            params = self._get_request_data()
            
            # Get month parameter from both kw and params
            month = kw.get('month') or params.get('month')  # Format: YYYY-MM
            
            # Validate required parameter
            if not month:
                return {'status': 'error', 'message': 'Month parameter is required'}

            Sampling = request.env['pitcar.sop.sampling']
            
            # Get all samplings for the month
            domain = [
                ('month', '=', month),
                ('state', '=', 'done')
            ]
            
            samplings = Sampling.search(domain)
            
            # Prepare summary data
            summary = {
                'total_sampling': len(samplings),
                'total_pass': len(samplings.filtered(lambda s: s.result == 'pass')),
                'total_fail': len(samplings.filtered(lambda s: s.result == 'fail')),
                'sa_sampling': {
                    'total': len(samplings.filtered(lambda s: s.sop_id.is_sa)),
                    'pass': len(samplings.filtered(lambda s: s.sop_id.is_sa and s.result == 'pass')),
                    'fail': len(samplings.filtered(lambda s: s.sop_id.is_sa and s.result == 'fail'))
                },
                'mechanic_sampling': {
                    'total': len(samplings.filtered(lambda s: not s.sop_id.is_sa)),
                    'pass': len(samplings.filtered(lambda s: not s.sop_id.is_sa and s.result == 'pass')),
                    'fail': len(samplings.filtered(lambda s: not s.sop_id.is_sa and s.result == 'fail'))
                }
            }

            # Calculate percentages
            if summary['total_sampling'] > 0:
                summary['pass_rate'] = round((summary['total_pass'] / summary['total_sampling']) * 100, 2)
                summary['fail_rate'] = round((summary['total_fail'] / summary['total_sampling']) * 100, 2)
            else:
                summary['pass_rate'] = 0
                summary['fail_rate'] = 0

            return {
                'status': 'success',
                'data': summary
            }

        except Exception as e:
            _logger.error(f"Error in get_sampling_summary: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    # CRUD MASTER
    @http.route('/web/sop/master/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_sop(self, **kw):
        """Create new SOP"""
        try:
            # Extract parameters langsung dari kw
            name = kw.get('name')
            code = kw.get('code')
            department = kw.get('department')
            description = kw.get('description')
            is_sa = kw.get('is_sa', False)
            sequence = kw.get('sequence', 10)

            # Validate required fields
            if not name or not code or not department:
                return {
                    'status': 'error',
                    'message': 'Name, code, and department are required'
                }

            # Create SOP
            values = {
                'name': name,
                'code': code,
                'department': department,
                'description': description,
                'is_sa': is_sa,
                'sequence': sequence,
                'active': True
            }

            sop = request.env['pitcar.sop'].create(values)

            return {
                'status': 'success',
                'data': {
                    'id': sop.id,
                    'name': sop.name,
                    'code': sop.code,
                    'department': sop.department,
                    'is_sa': sop.is_sa,
                    'description': sop.description
                }
            }

        except Exception as e:
            _logger.error(f"Error in create_sop: {str(e)}")
            return {
                'status': 'error', 
                'message': str(e)
            }

    @http.route('/web/sop/master/<int:sop_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sop_detail(self, sop_id, **kw):
        """Get SOP detail by ID"""
        try:
            sop = request.env['pitcar.sop'].browse(sop_id)
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP not found'}

            return {
                'status': 'success',
                'data': {
                    'id': sop.id,
                    'name': sop.name,
                    'code': sop.code,
                    'department': sop.department,
                    'is_sa': sop.is_sa,
                    'description': sop.description,
                    'sequence': sop.sequence,
                    'active': sop.active
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_sop_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/update', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def update_sop(self, **kw):
        """Update existing SOP"""
        try:
            # Extract parameters langsung dari kw
            sop_id = kw.get('id')
            values = {}
            
            # Fields yang bisa diupdate
            update_fields = ['name', 'code', 'department', 'description', 'is_sa', 'sequence', 'active']
            for field in update_fields:
                if field in kw:
                    values[field] = kw[field]

            if not sop_id:
                return {'status': 'error', 'message': 'SOP ID is required'}

            sop = request.env['pitcar.sop'].browse(sop_id)
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP not found'}

            sop.write(values)

            return {
                'status': 'success',
                'data': {
                    'id': sop.id,
                    'name': sop.name,
                    'code': sop.code,
                    'department': sop.department,
                    'is_sa': sop.is_sa,
                    'description': sop.description,
                    'sequence': sop.sequence,
                    'active': sop.active
                }
            }

        except Exception as e:
            _logger.error(f"Error in update_sop: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/delete/<int:sop_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def delete_sop(self, sop_id, **kw):
        """Delete/Archive SOP"""
        try:
            sop = request.env['pitcar.sop'].browse(sop_id)
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP not found'}

            # Check if SOP is used in any sampling
            if request.env['pitcar.sop.sampling'].search_count([('sop_id', '=', sop_id)]) > 0:
                # Just archive if SOP is used
                sop.write({'active': False})
                return {
                    'status': 'success',
                    'message': 'SOP has been archived because it is used in sampling records'
                }
            else:
                # Delete if not used
                sop.unlink()
                return {
                    'status': 'success',
                    'message': 'SOP has been deleted successfully'
                }

        except Exception as e:
            _logger.error(f"Error in delete_sop: {str(e)}")
            return {'status': 'error', 'message': str(e)}