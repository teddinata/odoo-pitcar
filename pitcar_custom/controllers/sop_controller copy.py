from odoo import http, fields
from odoo.http import request, Response
import logging
import re
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
        
    def _get_employee_domain(self, role):
        """Get domain for employee based on role"""
        domains = {
            'sa': [],  # Using service.advisor model
            'mechanic': [],  # Using mechanic.new model
            'valet': [('job_id.name', 'ilike', 'valet')],
            'part_support': [('job_id.name', 'ilike', 'part')],
            'cs': [('job_id.name', 'ilike', 'customer service')]  # Tambahkan domain untuk CS
        }
        return domains.get(role, [])

    def _get_sop_domain(self, role=None, department=None, search=None):
        """Build domain for SOP search"""
        domain = [('active', '=', True)]
        
        if role:
            domain.append(('role', '=', role))
        if department:
            domain.append(('department', '=', department))
        if search:
            for term in search.split():
                domain.extend(['|', '|',
                    ('name', 'ilike', term),
                    ('code', 'ilike', term),
                    ('description', 'ilike', term)
                ])
        
        return domain

    def _format_employee_info(self, sampling):
        """Format employee info based on role"""
        return {
            'service_advisor': [{
                'id': sa.id,
                'name': sa.name
            } for sa in sampling.sa_id] if sampling.sa_id else [],
            
            'mechanic': [{
                'id': mech.id,
                'name': mech.name
            } for mech in sampling.mechanic_id] if sampling.mechanic_id else [],
            
            'valet': [{
                'id': val.id,
                'name': val.name
            } for val in sampling.valet_id] if sampling.valet_id else [],
            
            'part_support': [{
                'id': ps.id,
                'name': ps.name
            } for ps in sampling.part_support_id] if sampling.part_support_id else [],
            
            'customer_service': [{
                'id': cs.id,
                'name': cs.name
            } for cs in sampling.cs_id] if sampling.cs_id else []
        }

    @http.route('/web/sop/master/list', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sop_list(self, **kw):
        try:
            # Parameters
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            role = kw.get('role')
            department = kw.get('department')
            search = (kw.get('search') or '').strip()
            
            # Sort parameters
            sort_by = kw.get('sort_by', 'code')  # Default sort by code
            sort_order = kw.get('sort_order', 'asc')  # Default ascending
            
            # Validate dan map sort_by ke field yang valid
            valid_sort_fields = {
                'code': 'code',
                'name': 'name',
                'department': 'department',
                'role': 'role'
            }
            
            # Pastikan sort_by valid, jika tidak gunakan default
            sort_field = valid_sort_fields.get(sort_by, 'code')
            
            # Build order string
            order_string = f"{sort_field} {sort_order}"

            # Build domain
            domain = self._get_sop_domain(role, department, search)
            
            # Get data with ordering
            SOP = request.env['pitcar.sop'].sudo()
            total_count = SOP.search_count(domain)
            offset = (page - 1) * limit
            sops = SOP.search(domain, limit=limit, offset=offset, order=order_string)

            # Format response
            rows = []
            for sop in sops:
                rows.append({
                    'id': sop.id,
                    'code': sop.code,
                    'name': sop.name,
                    'description': sop.description,
                    'department': sop.department,
                    'department_label': dict(sop._fields['department'].selection).get(sop.department, ''),
                    'role': sop.role,
                    'role_label': dict(sop._fields['role'].selection).get(sop.role, ''),
                    'sequence': sop.sequence,
                    'active': sop.active
                })

            return {
                'status': 'success',
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
                    'sort': {
                        'sort_by': sort_by,
                        'sort_order': sort_order
                    },
                    'filters': {
                        'departments': [
                            {'value': 'service', 'label': 'Service'},
                            {'value': 'sparepart', 'label': 'Spare Part'},
                            {'value': 'cs', 'label': 'Customer Service'}
                        ],
                        'roles': [
                            {'value': 'sa', 'label': 'Service Advisor'},
                            {'value': 'mechanic', 'label': 'Mechanic'},
                            {'value': 'valet', 'label': 'Valet Parking'},
                            {'value': 'part_support', 'label': 'Part Support'},
                            {'value': 'cs', 'label': 'Customer Service'}  # Tambahkan role CS
                        ]
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
            # Get parameters from request
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            search = (kw.get('search') or '').strip()
            is_sa = kw.get('is_sa')
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')

            # Debug log
            _logger.info(f"Received parameters: {kw}")

            # Base domain untuk sale orders yang aktif
            # domain = [('state', 'in', ['sale', 'done'])]
            domain = [('state', 'in', ['draft', 'sent', 'sale', 'done'])]

            # Search dengan multiple terms
            if search:
                search_terms = search.split()
                for term in search_terms:
                    domain.extend(['|', '|', '|', '|',
                        ('name', 'ilike', term),
                        ('partner_car_id.number_plate', 'ilike', term),
                        ('car_mechanic_id_new.name', 'ilike', term),
                        ('service_advisor_id.name', 'ilike', term),
                        ('partner_id.name', 'ilike', term)
                    ])

            # Filter berdasarkan tipe SOP (SA/Mekanik)
            if isinstance(is_sa, bool):
                if is_sa:
                    domain.append(('service_advisor_id', '!=', False))
                else:
                    domain.append(('car_mechanic_id_new', '!=', False))
            elif isinstance(is_sa, str):
                if is_sa.lower() == 'true':
                    domain.append(('service_advisor_id', '!=', False))
                elif is_sa.lower() == 'false':
                    domain.append(('car_mechanic_id_new', '!=', False))

            # Date range filter
            if date_from:
                try:
                    domain.append(('create_date', '>=', date_from))
                except Exception as e:
                    _logger.warning(f"Invalid date_from format: {date_from}")

            if date_to:
                try:
                    domain.append(('create_date', '<=', date_to))
                except Exception as e:
                    _logger.warning(f"Invalid date_to format: {date_to}")

            # Debug domain
            _logger.info(f"Search domain: {domain}")

            # Use sudo() for consistent access
            SaleOrder = request.env['sale.order'].sudo()
            
            # Get total before pagination
            total_count = SaleOrder.search_count(domain)
            
            # Get records with pagination
            offset = (page - 1) * limit
            orders = SaleOrder.search(domain, limit=limit, offset=offset, order='create_date desc')

            rows = []
            for order in orders:
                # Format mechanic data
                mechanic_data = [{
                    'id': mech.id,
                    'name': mech.name,
                    'sampling_count': len(order.sop_sampling_ids.filtered(
                        lambda s: not s.sop_id.is_sa and mech.id in s.mechanic_id.ids
                    ))
                } for mech in order.car_mechanic_id_new] if order.car_mechanic_id_new else []

                # Format SA data
                sa_data = [{
                    'id': sa.id,
                    'name': sa.name,
                    'sampling_count': len(order.sop_sampling_ids.filtered(
                        lambda s: s.sop_id.is_sa and sa.id in s.sa_id.ids
                    ))
                } for sa in order.service_advisor_id] if order.service_advisor_id else []

                row = {
                    'id': order.id,
                    'name': order.name,
                    'date': order.create_date.strftime('%Y-%m-%d %H:%M:%S') if order.create_date else None,
                    'car_info': {
                        'plate': order.partner_car_id.number_plate if order.partner_car_id else None,
                        'brand': order.partner_car_brand.name if order.partner_car_brand else None,
                        'type': order.partner_car_brand_type.name if order.partner_car_brand_type else None
                    },
                    'customer': {
                        'id': order.partner_id.id,
                        'name': order.partner_id.name
                    } if order.partner_id else None,
                    'employee_info': {
                        'mechanic': mechanic_data,
                        'service_advisor': sa_data
                    },
                    'sampling_count': len(order.sop_sampling_ids)
                }
                rows.append(row)

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit) if total_count > 0 else 1,
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
        try:
            # Required parameters
            sale_order_id = kw.get('sale_order_id')
            sop_id = kw.get('sop_id')
            employee_ids = kw.get('employee_ids', [])
            notes = kw.get('notes')

            if not sale_order_id or not sop_id:
                return {
                    'status': 'error',
                    'message': 'Sale order and SOP are required'
                }

            # Get SOP and validate
            sop = request.env['pitcar.sop'].browse(sop_id)
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP not found'}

            # Base values
            values = {
                'sale_order_id': sale_order_id,
                'sop_id': sop_id,
                'controller_id': request.env.user.employee_id.id,
                'notes': notes,
                'state': 'draft'
            }

            # Role-specific employee assignment
            sale_order = request.env['sale.order'].browse(sale_order_id)
            
            if sop.role == 'sa':
                if not sale_order.service_advisor_id:
                    return {'status': 'error', 'message': 'No Service Advisor assigned'}
                values['sa_id'] = [(6, 0, sale_order.service_advisor_id.ids)]
            
            elif sop.role == 'mechanic':
                if not sale_order.car_mechanic_id_new:
                    return {'status': 'error', 'message': 'No Mechanic assigned'}
                values['mechanic_id'] = [(6, 0, sale_order.car_mechanic_id_new.ids)]
            
            elif sop.role == 'valet':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Valet staff must be selected'}
                values['valet_id'] = [(6, 0, employee_ids)]
            
            elif sop.role == 'part_support':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Part support staff must be selected'}
                values['part_support_id'] = [(6, 0, employee_ids)]

             # Tambahkan handler untuk CS
            elif sop.role == 'cs':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Customer Service staff must be selected'}
                values['cs_id'] = [(6, 0, employee_ids)]

            # Create sampling
            sampling = request.env['pitcar.sop.sampling'].create(values)

            return {
                'status': 'success',
                'data': {
                    'id': sampling.id,
                    'name': sampling.name,
                    'sale_order_id': sampling.sale_order_id.id,
                    'sop_id': sampling.sop_id.id,
                    'employee_info': self._format_employee_info(sampling),
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
        try:
            # Parameters
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            search = (kw.get('search') or '').strip()
            month = kw.get('month', '').strip()
            role = kw.get('role')
            state = kw.get('state')
            result = kw.get('result')

            domain = []

            # Month filter
            if month:
                domain.append(('month', '=', month))

            # Role filter
            if role:
                domain.append(('sop_id.role', '=', role))

            # State filter
            if state and state != 'all':
                domain.append(('state', '=', state))

            # Result filter
            if result and result != 'all':
                domain.append(('result', '=', result))

            # Search filter
            if search:
                domain.extend(['|', '|', '|', '|', '|', '|', '|',
                    ('name', 'ilike', search),
                    ('sale_order_id.name', 'ilike', search),
                    ('sa_id.name', 'ilike', search),
                    ('mechanic_id.name', 'ilike', search),
                    ('valet_id.name', 'ilike', search),
                    ('part_support_id.name', 'ilike', search),
                    ('sop_id.name', 'ilike', search),
                    ('sop_id.code', 'ilike', search)
                ])

            # Get data
            Sampling = request.env['pitcar.sop.sampling'].sudo()
            total_count = Sampling.search_count(domain)
            offset = (page - 1) * limit
            samplings = Sampling.search(domain, limit=limit, offset=offset, order='create_date desc')

            # Format data
            rows = []
            for sampling in samplings:
                controller_data = None
                if sampling.controller_id:
                    controller_data = {
                        'id': sampling.controller_id.id,
                        'name': sampling.controller_id.name
                    }

                row = {
                    'id': sampling.id,
                    'name': sampling.name,
                    'date': sampling.date.strftime('%Y-%m-%d') if sampling.date else None,
                    'timestamps': {
                        'created': sampling.create_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.create_date else None,
                        'updated': sampling.write_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.write_date else None,
                        'validated': sampling.validation_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.validation_date else None
                    },
                    'sale_order': {
                        'id': sampling.sale_order_id.id,
                        'name': sampling.sale_order_id.name,
                        'car_info': {
                            'plate': sampling.sale_order_id.partner_car_id.number_plate if sampling.sale_order_id.partner_car_id else None,
                            'brand': sampling.sale_order_id.partner_car_brand.name if sampling.sale_order_id.partner_car_brand else None,
                            'type': sampling.sale_order_id.partner_car_brand_type.name if sampling.sale_order_id.partner_car_brand_type else None
                        }
                    } if sampling.sale_order_id else None,
                    'sop': {
                        'id': sampling.sop_id.id,
                        'name': sampling.sop_id.name,
                        'code': sampling.sop_id.code,
                        'role': sampling.sop_id.role,
                        'role_label': dict(sampling.sop_id._fields['role'].selection).get(sampling.sop_id.role, ''),
                        'department': sampling.sop_id.department,
                        'department_label': dict(sampling.sop_id._fields['department'].selection).get(sampling.sop_id.department, '')
                    } if sampling.sop_id else None,
                    'employee_info': self._format_employee_info(sampling),
                    'controller': controller_data,
                    'state': sampling.state,
                    'state_label': dict(sampling._fields['state'].selection).get(sampling.state, ''),
                    'result': sampling.result,
                    'result_label': dict(sampling._fields['result'].selection).get(sampling.result, '') if sampling.result else '',
                    'notes': sampling.notes
                }
                rows.append(row)

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit) if total_count > 0 else 1,
                        'current_page': page,
                        'items_per_page': limit
                    },
                    'filters': {
                        'roles': [
                            {'value': 'sa', 'label': 'Service Advisor'},
                            {'value': 'mechanic', 'label': 'Mechanic'},
                            {'value': 'valet', 'label': 'Valet Parking'},
                            {'value': 'part_support', 'label': 'Part Support'}
                        ],
                        'states': [
                            {'value': 'draft', 'label': 'Draft'},
                            {'value': 'in_progress', 'label': 'In Progress'},
                            {'value': 'done', 'label': 'Done'}
                        ],
                        'results': [
                            {'value': 'pass', 'label': 'Lulus'},
                            {'value': 'fail', 'label': 'Tidak Lulus'}
                        ]
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_sampling_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}

        
    @http.route('/web/sop/sampling/validate', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def validate_sampling(self, **kw):
        try:
            sampling_id = kw.get('sampling_id')
            result = kw.get('result')
            notes = kw.get('notes')
            
            if not sampling_id or not result:
                return {'status': 'error', 'message': 'Sampling ID and result are required'}

            # Use sudo() to avoid access right issues
            sampling = request.env['pitcar.sop.sampling'].sudo().browse(sampling_id)
            if not sampling.exists():
                return {'status': 'error', 'message': 'Sampling not found'}

            values = {
                'state': 'done',
                'result': result,
                'notes': notes,
                'validation_date': fields.Datetime.now()
            }

            sampling.write(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': sampling.id,
                    'name': sampling.name,
                    'result': sampling.result,
                    'state': sampling.state,
                    'notes': sampling.notes,
                    'employee_info': self._format_employee_info(sampling)
                }
            }

        except Exception as e:
            _logger.error(f"Error in validate_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/summary', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sampling_summary(self, **kw):
        """Get comprehensive sampling summary statistics for all roles"""
        try:
            params = self._get_request_data()
            month = kw.get('month') or params.get('month')
            
            if not month:
                return {'status': 'error', 'message': 'Month parameter is required'}

            Sampling = request.env['pitcar.sop.sampling'].sudo()
            domain = [
                ('month', '=', month),
                ('state', '=', 'done')
            ]
            
            samplings = Sampling.search(domain)
            
            # Initialize summary structure with all roles
            summary = {
                'total': {
                    'total': 0,
                    'pass': 0,
                    'fail': 0,
                    'pass_rate': 0,
                    'fail_rate': 0
                },
                'roles': {
                    'service_advisor': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Service Advisor',
                        'details': []
                    },
                    'mechanic': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Mechanic',
                        'details': []
                    },
                    'valet': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Valet Parking',
                        'details': []
                    },
                    'part_support': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Part Support',
                        'details': []
                    },
                    'customer_service': {  # Tambahkan CS stats
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Customer Service',
                        'details': []
                    }
                }
            }

            # Helper to update stats
            def update_stats(stats_dict, result):
                stats_dict['total'] += 1
                stats_dict['pass'] += 1 if result == 'pass' else 0
                stats_dict['fail'] += 1 if result == 'fail' else 0

            # Helper to update employee stats
            def update_employee_stats(employee_stats, employee, result):
                if employee.id not in employee_stats:
                    employee_stats[employee.id] = {
                        'id': employee.id,
                        'name': employee.name,
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0
                    }
                update_stats(employee_stats[employee.id], result)

            # Initialize employee stats dictionaries
            employee_stats = {
                'service_advisor': {},
                'mechanic': {},
                'valet': {},
                'part_support': {},
                'customer_service': {}  # Tambahkan CS
            }

            # Process all samplings
            for sampling in samplings:
                role = sampling.sop_id.role
                result = sampling.result
                
                if role not in summary['roles']:
                    continue

                # Update total stats
                update_stats(summary['total'], result)
                
                # Update role stats
                update_stats(summary['roles'][role], result)
                
                # Update employee stats based on role
                if role == 'service_advisor' and sampling.sa_id:
                    for employee in sampling.sa_id:
                        update_employee_stats(employee_stats['service_advisor'], employee, result)
                elif role == 'mechanic' and sampling.mechanic_id:
                    for employee in sampling.mechanic_id:
                        update_employee_stats(employee_stats['mechanic'], employee, result)
                elif role == 'valet' and sampling.valet_id:
                    for employee in sampling.valet_id:
                        update_employee_stats(employee_stats['valet'], employee, result)
                elif role == 'part_support' and sampling.part_support_id:
                    for employee in sampling.part_support_id:
                        update_employee_stats(employee_stats['part_support'], employee, result)
                elif role == 'customer_service' and sampling.cs_id:
                    for employee in sampling.cs_id:
                        update_employee_stats(employee_stats['customer_service'], employee, result)

            # Calculate rates and sort employee details
            def calculate_rates(stats):
                if stats['total'] > 0:
                    stats['pass_rate'] = round((stats['pass'] / stats['total']) * 100, 2)
                    stats['fail_rate'] = round((stats['fail'] / stats['total']) * 100, 2)

            # Calculate rates for overall totals
            calculate_rates(summary['total'])

            # Process each role's stats
            for role in summary['roles']:
                # Calculate rates for role totals
                calculate_rates(summary['roles'][role])
                
                # Process employee details for this role
                details = list(employee_stats[role].values())
                for detail in details:
                    calculate_rates(detail)
                
                # Sort by pass rate (descending)
                details.sort(key=lambda x: x['pass_rate'], reverse=True)
                
                # Add ranking
                for i, detail in enumerate(details, 1):
                    detail['rank'] = i
                
                summary['roles'][role]['details'] = details

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
            # Extract parameters
            name = kw.get('name')
            code = kw.get('code')
            department = kw.get('department')
            description = kw.get('description')
            is_sa = kw.get('is_sa', False)  # Backward compatibility
            sequence = kw.get('sequence', 10)
            role = kw.get('role')  # New field
            
            # Determine role dari is_sa jika role tidak diberikan
            if not role and is_sa is not None:
                role = 'sa' if is_sa else 'mechanic'

            # Validate required fields
            if not all([name, code, department, role]):  # Tambahkan role ke required fields
                return {
                    'status': 'error',
                    'message': 'Name, code, department, and role are required'
                }

            # Validate role-department compatibility
            valid_combinations = {
                'service': ['sa', 'mechanic'],
                'cs': ['valet', 'part_support', 'cs'],  # Tambahkan 'cs'
                'sparepart': ['part_support']
            }
            if role not in valid_combinations.get(department, []):
                return {
                    'status': 'error',
                    'message': f'Role {role} tidak valid untuk department {department}'
                }

            # Create SOP
            values = {
                'name': name,
                'code': code,
                'department': department,
                'description': description,
                'role': role,
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
                    'department_label': dict(sop._fields['department'].selection).get(sop.department, ''),
                    'role': sop.role,
                    'role_label': dict(sop._fields['role'].selection).get(sop.role, ''),
                    'is_sa': sop.is_sa,  # Backward compatibility
                    'description': sop.description,
                    'sequence': sop.sequence,
                    'active': sop.active
                }
            }

        except Exception as e:
            _logger.error(f"Error in create_sop: {str(e)}")
            return {'status': 'error', 'message': str(e)}


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
            sop_id = kw.get('id')
            values = {}
            
            # Fields yang bisa diupdate
            update_fields = ['name', 'code', 'department', 'description', 'role', 'sequence', 'active']
            for field in update_fields:
                if field in kw:
                    values[field] = kw[field]

            if not sop_id:
                return {'status': 'error', 'message': 'SOP ID is required'}

            sop = request.env['pitcar.sop'].browse(sop_id)
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP not found'}

            # Validate role-department compatibility jika ada perubahan
            if 'role' in values or 'department' in values:
                department = values.get('department', sop.department)
                role = values.get('role', sop.role)
                valid_combinations = {
                    'service': ['sa', 'mechanic'],
                    'cs': ['valet', 'part_support', 'cs'],
                    'sparepart': ['part_support']
                }
                if role not in valid_combinations.get(department, []):
                    return {
                        'status': 'error',
                        'message': f'Role {role} tidak valid untuk department {department}'
                    }

            sop.write(values)

            return {
                'status': 'success',
                'data': {
                    'id': sop.id,
                    'name': sop.name,
                    'code': sop.code,
                    'department': sop.department,
                    'department_label': dict(sop._fields['department'].selection).get(sop.department, ''),
                    'role': sop.role,
                    'role_label': dict(sop._fields['role'].selection).get(sop.role, ''),
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
        
    # def get_sop_list(self, **kw):
    #     """Get list of SOPs"""
    #     try:
    #         # Get parameters from request
    #         page = max(1, int(kw.get('page', 1)))
    #         limit = max(1, min(100, int(kw.get('limit', 25))))  # Max 100 records
    #         search = (kw.get('search') or '').strip()
    #         department = kw.get('department')
    #         is_sa = kw.get('is_sa')

    #         # Debug log
    #         _logger.info(f"Received parameters: {kw}")

    #         domain = [('active', '=', True)]

    #         # Search filter - lebih powerful dengan split terms
    #         if search:
    #             search_terms = search.split()
    #             for term in search_terms:
    #                 domain.extend(['|', '|',
    #                     ('name', 'ilike', term),
    #                     ('code', 'ilike', term),
    #                     ('description', 'ilike', term)
    #                 ])
            
    #         # Department filter
    #         if department and department not in ['all', 'false', 'null', '']:
    #             if department in ['service', 'sparepart', 'cs']:
    #                 domain.append(('department', '=', department))
            
    #         # IS SA filter
    #         if isinstance(is_sa, bool):
    #             domain.append(('is_sa', '=', is_sa))
    #         elif isinstance(is_sa, str) and is_sa.lower() in ['true', 'false']:
    #             domain.append(('is_sa', '=', is_sa.lower() == 'true'))

    #         # Debug domain
    #         _logger.info(f"Search domain: {domain}")

    #         # Use sudo() untuk konsistensi akses
    #         SOP = request.env['pitcar.sop'].sudo()
            
    #         # Get total before pagination
    #         total_count = SOP.search_count(domain)
            
    #         # Calculate pagination
    #         offset = (page - 1) * limit
            
    #         # Get records with ordering
    #         sops = SOP.search(domain, limit=limit, offset=offset, order='sequence, name')

    #         rows = []
    #         for sop in sops:
    #             row = {
    #                 'id': sop.id,
    #                 'code': sop.code,
    #                 'name': sop.name,
    #                 'description': sop.description,
    #                 'department': sop.department,
    #                 'department_label': dict(sop._fields['department'].selection).get(sop.department, ''),
    #                 'is_sa': sop.is_sa,
    #                 'sequence': sop.sequence,
    #                 'active': sop.active
    #             }
    #             rows.append(row)

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'rows': rows,
    #                 'pagination': {
    #                     'total_items': total_count,
    #                     'total_pages': math.ceil(total_count / limit) if total_count > 0 else 1,
    #                     'current_page': page,
    #                     'items_per_page': limit
    #                 },
    #                 'filters': {
    #                     'departments': [
    #                         {'value': 'service', 'label': 'Service'},
    #                         {'value': 'sparepart', 'label': 'Spare Part'},
    #                         {'value': 'cs', 'label': 'Customer Service'}
    #                     ]
    #                 }
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in get_sop_list: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}
        
    # def create_sampling(self, **kw):
    #     """Create new SOP sampling"""
    #     try:
    #         # Extract parameters langsung dari kw
    #         sale_order_id = kw.get('sale_order_id')
    #         sop_id = kw.get('sop_id')
    #         notes = kw.get('notes')

    #         # Validate required fields
    #         if not sale_order_id:
    #             return {'status': 'error', 'message': 'Sale order ID is required'}
    #         if not sop_id:
    #             return {'status': 'error', 'message': 'SOP ID is required'}

    #         # Get Sale Order dan SOP
    #         sale_order = request.env['sale.order'].browse(sale_order_id)
    #         sop = request.env['pitcar.sop'].browse(sop_id)

    #         if not sale_order.exists():
    #             return {'status': 'error', 'message': 'Sale order not found'}
    #         if not sop.exists():
    #             return {'status': 'error', 'message': 'SOP not found'}

    #         # Get controller employee from current user
    #         controller = request.env.user.employee_id
    #         if not controller:
    #             return {'status': 'error', 'message': 'Current user has no employee record'}

    #         # Create sampling dengan values yang sudah termasuk SA/Mekanik
    #         values = {
    #             'sale_order_id': sale_order_id,
    #             'sop_id': sop_id,
    #             'controller_id': controller.id,
    #             'notes': notes,
    #             'state': 'draft'
    #         }

    #         # Tambahkan SA/Mekanik sesuai tipe SOP
    #         if sop.is_sa:
    #             if not sale_order.service_advisor_id:
    #                 return {'status': 'error', 'message': 'Sale order has no Service Advisor assigned'}
    #             values['sa_id'] = [(6, 0, sale_order.service_advisor_id.ids)]
    #         else:
    #             if not sale_order.car_mechanic_id_new:
    #                 return {'status': 'error', 'message': 'Sale order has no Mechanic assigned'}
    #             values['mechanic_id'] = [(6, 0, sale_order.car_mechanic_id_new.ids)]

    #         sampling = request.env['pitcar.sop.sampling'].create(values)

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'id': sampling.id,
    #                 'name': sampling.name,
    #                 'sale_order_id': sampling.sale_order_id.id,
    #                 'sop_id': sampling.sop_id.id,
    #                 'employee_info': {
    #                     'sa_id': sampling.sa_id.ids if sampling.sa_id else [],
    #                     'mechanic_id': sampling.mechanic_id.ids if sampling.mechanic_id else []
    #                 },
    #                 'state': sampling.state
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in create_sampling: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}
        
    # def validate_sampling(self, **kw):
    #     """Validate sampling result"""
    #     try:
    #         params = self._get_request_data()
            
    #         # Get parameters from both kw and params
    #         sampling_id = kw.get('sampling_id') or params.get('sampling_id')
    #         result = kw.get('result') or params.get('result')
    #         notes = kw.get('notes') or params.get('notes')
            
    #         # Validate required parameters
    #         if not sampling_id:
    #             return {'status': 'error', 'message': 'Sampling ID is required'}
    #         if not result:
    #             return {'status': 'error', 'message': 'Result is required'}

    #         sampling = request.env['pitcar.sop.sampling'].browse(sampling_id)
    #         if not sampling.exists():
    #             return {'status': 'error', 'message': 'Sampling not found'}

    #         # Update sampling
    #         values = {
    #             'state': 'done',
    #             'result': result,
    #             'notes': notes,
    #             'validation_date': fields.Datetime.now()  # Add validation timestamp
    #         }

    #         sampling.write(values)
            
    #         # Return updated data
    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'id': sampling.id,
    #                 'name': sampling.name,
    #                 'result': sampling.result,
    #                 'state': sampling.state,
    #                 'notes': sampling.notes
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in validate_sampling: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}

    # @http.route('/web/sop/sampling/summary', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    # def get_sampling_summary(self, **kw):
    #     """Get sampling summary statistics"""
    #     try:
    #         params = self._get_request_data()
    #         month = kw.get('month') or params.get('month')
            
    #         if not month:
    #             return {'status': 'error', 'message': 'Month parameter is required'}

    #         Sampling = request.env['pitcar.sop.sampling']
    #         domain = [
    #             ('month', '=', month),
    #             ('state', '=', 'done')
    #         ]
            
    #         samplings = Sampling.search(domain)
            
    #         # Basic summary statistics
    #         summary = {
    #             'total_sampling': len(samplings),
    #             'total_pass': len(samplings.filtered(lambda s: s.result == 'pass')),
    #             'total_fail': len(samplings.filtered(lambda s: s.result == 'fail')),
    #             'sa_sampling': {
    #                 'total': len(samplings.filtered(lambda s: s.sop_id.is_sa)),
    #                 'pass': len(samplings.filtered(lambda s: s.sop_id.is_sa and s.result == 'pass')),
    #                 'fail': len(samplings.filtered(lambda s: s.sop_id.is_sa and s.result == 'fail'))
    #             },
    #             'mechanic_sampling': {
    #                 'total': len(samplings.filtered(lambda s: not s.sop_id.is_sa)),
    #                 'pass': len(samplings.filtered(lambda s: not s.sop_id.is_sa and s.result == 'pass')),
    #                 'fail': len(samplings.filtered(lambda s: not s.sop_id.is_sa and s.result == 'fail'))
    #             }
    #         }

    #         # Calculate overall rates
    #         if summary['total_sampling'] > 0:
    #             summary['pass_rate'] = round((summary['total_pass'] / summary['total_sampling']) * 100, 2)
    #             summary['fail_rate'] = round((summary['total_fail'] / summary['total_sampling']) * 100, 2)
    #         else:
    #             summary['pass_rate'] = summary['fail_rate'] = 0

    #         # Calculate SA rates
    #         if summary['sa_sampling']['total'] > 0:
    #             summary['sa_sampling']['pass_rate'] = round((summary['sa_sampling']['pass'] / summary['sa_sampling']['total']) * 100, 2)
    #             summary['sa_sampling']['fail_rate'] = round((summary['sa_sampling']['fail'] / summary['sa_sampling']['total']) * 100, 2)
    #         else:
    #             summary['sa_sampling']['pass_rate'] = summary['sa_sampling']['fail_rate'] = 0

    #         # Calculate Mechanic rates
    #         if summary['mechanic_sampling']['total'] > 0:
    #             summary['mechanic_sampling']['pass_rate'] = round((summary['mechanic_sampling']['pass'] / summary['mechanic_sampling']['total']) * 100, 2)
    #             summary['mechanic_sampling']['fail_rate'] = round((summary['mechanic_sampling']['fail'] / summary['mechanic_sampling']['total']) * 100, 2)
    #         else:
    #             summary['mechanic_sampling']['pass_rate'] = summary['mechanic_sampling']['fail_rate'] = 0

    #         # Calculate per-mechanic statistics
    #         mechanic_stats = {}
    #         mechanic_samplings = samplings.filtered(lambda s: not s.sop_id.is_sa)
            
    #         for sampling in mechanic_samplings:
    #             for mechanic in sampling.mechanic_id:
    #                 if mechanic.id not in mechanic_stats:
    #                     mechanic_stats[mechanic.id] = {
    #                         'id': mechanic.id,
    #                         'name': mechanic.name,
    #                         'total': 0,
    #                         'pass': 0,
    #                         'fail': 0,
    #                         'pass_rate': 0,
    #                         'fail_rate': 0
    #                     }
                    
    #                 mechanic_stats[mechanic.id]['total'] += 1
    #                 if sampling.result == 'pass':
    #                     mechanic_stats[mechanic.id]['pass'] += 1
    #                 elif sampling.result == 'fail':
    #                     mechanic_stats[mechanic.id]['fail'] += 1

    #         # Calculate per-SA statistics
    #         sa_stats = {}
    #         sa_samplings = samplings.filtered(lambda s: s.sop_id.is_sa)
            
    #         for sampling in sa_samplings:
    #             for sa in sampling.sa_id:
    #                 if sa.id not in sa_stats:
    #                     sa_stats[sa.id] = {
    #                         'id': sa.id,
    #                         'name': sa.name,
    #                         'total': 0,
    #                         'pass': 0,
    #                         'fail': 0,
    #                         'pass_rate': 0,
    #                         'fail_rate': 0
    #                     }
                    
    #                 sa_stats[sa.id]['total'] += 1
    #                 if sampling.result == 'pass':
    #                     sa_stats[sa.id]['pass'] += 1
    #                 elif sampling.result == 'fail':
    #                     sa_stats[sa.id]['fail'] += 1

    #         # Calculate rates and sort by performance
    #         def calculate_rates_and_sort(stats_dict):
    #             stats_list = list(stats_dict.values())
    #             for stat in stats_list:
    #                 if stat['total'] > 0:
    #                     stat['pass_rate'] = round((stat['pass'] / stat['total']) * 100, 2)
    #                     stat['fail_rate'] = round((stat['fail'] / stat['total']) * 100, 2)
                
    #             # Sort by pass rate (descending)
    #             stats_list.sort(key=lambda x: x['pass_rate'], reverse=True)
                
    #             # Add ranking
    #             for i, stat in enumerate(stats_list, 1):
    #                 stat['rank'] = i
                
    #             return stats_list

    #         # Add detailed stats to summary
    #         summary['mechanic_details'] = calculate_rates_and_sort(mechanic_stats)
    #         summary['sa_details'] = calculate_rates_and_sort(sa_stats)

    #         return {
    #             'status': 'success',
    #             'data': summary
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in get_sampling_summary: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}

     # @http.route('/web/sop/master/update', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    # def update_sop(self, **kw):
    #     """Update existing SOP"""
    #     try:
    #         # Extract parameters langsung dari kw
    #         sop_id = kw.get('id')
    #         values = {}
            
    #         # Fields yang bisa diupdate
    #         update_fields = ['name', 'code', 'department', 'description', 'is_sa', 'sequence', 'active']
    #         for field in update_fields:
    #             if field in kw:
    #                 values[field] = kw[field]

    #         if not sop_id:
    #             return {'status': 'error', 'message': 'SOP ID is required'}

    #         sop = request.env['pitcar.sop'].browse(sop_id)
    #         if not sop.exists():
    #             return {'status': 'error', 'message': 'SOP not found'}

    #         sop.write(values)

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'id': sop.id,
    #                 'name': sop.name,
    #                 'code': sop.code,
    #                 'department': sop.department,
    #                 'is_sa': sop.is_sa,
    #                 'description': sop.description,
    #                 'sequence': sop.sequence,
    #                 'active': sop.active
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in update_sop: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}

    # @http.route('/web/sop/master/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    # def create_sop(self, **kw):
    #     """Create new SOP"""
    #     try:
    #         # Extract parameters langsung dari kw
    #         name = kw.get('name')
    #         code = kw.get('code')
    #         department = kw.get('department')
    #         description = kw.get('description')
    #         is_sa = kw.get('is_sa', False)
    #         sequence = kw.get('sequence', 10)

    #         # Validate required fields
    #         if not name or not code or not department:
    #             return {
    #                 'status': 'error',
    #                 'message': 'Name, code, and department are required'
    #             }

    #         # Create SOP
    #         values = {
    #             'name': name,
    #             'code': code,
    #             'department': department,
    #             'description': description,
    #             'is_sa': is_sa,
    #             'sequence': sequence,
    #             'active': True
    #         }

    #         sop = request.env['pitcar.sop'].create(values)

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'id': sop.id,
    #                 'name': sop.name,
    #                 'code': sop.code,
    #                 'department': sop.department,
    #                 'is_sa': sop.is_sa,
    #                 'description': sop.description
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in create_sop: {str(e)}")
    #         return {
    #             'status': 'error', 
    #             'message': str(e)
    #         }

    # def get_sampling_list(self, **kw):
    #     """Get list of sampling records"""
    #     try:
    #         # Get parameters directly from kw
    #         # In Odoo, when using type='json', the parameters are passed directly in kw
    #         page = max(1, int(kw.get('page', 1)))
    #         limit = max(1, min(100, int(kw.get('limit', 25))))  # Max 100 records per page
    #         search = (kw.get('search') or '').strip()
    #         month = kw.get('month', '').strip()
    #         is_sa = kw.get('is_sa')
    #         state = kw.get('state')
    #         result = kw.get('result')

    #         # Debug log
    #         _logger.info(f"Received parameters: {kw}")

    #         domain = []

    #         # Month filter
    #         if month and re.match(r'^\d{4}-\d{2}$', month):
    #             domain.append(('month', '=', month))

    #         # Search filter
    #         if search:
    #             domain.append('|')
    #             domain.append(('name', 'ilike', search))
    #             domain.append('|')
    #             domain.append(('sale_order_id.name', 'ilike', search))
    #             domain.append('|')
    #             domain.append(('sa_id.name', 'ilike', search))
    #             domain.append('|')
    #             domain.append(('mechanic_id.name', 'ilike', search))
    #             domain.append('|')
    #             domain.append(('sop_id.name', 'ilike', search))
    #             domain.append(('sop_id.code', 'ilike', search))

    #         # IS SA filter
    #         if isinstance(is_sa, bool):
    #             domain.append(('sop_id.is_sa', '=', is_sa))

    #         # State filter
    #         if state and state != 'all':
    #             if state in ['draft', 'in_progress', 'done']:
    #                 domain.append(('state', '=', state))

    #         # Result filter
    #         if result and result != 'all':
    #             if result in ['pass', 'fail']:
    #                 domain.append(('result', '=', result))

    #         # Debug domain
    #         _logger.info(f"Search domain: {domain}")

    #         # Use sudo() for consistent access
    #         Sampling = request.env['pitcar.sop.sampling'].sudo()
            
    #         # Get total before pagination
    #         total_count = Sampling.search_count(domain)
            
    #         # Calculate pagination
    #         offset = (page - 1) * limit
            
    #         # Get records
    #         samplings = Sampling.search(domain, limit=limit, offset=offset, order='create_date desc')

    #         rows = []
    #         for sampling in samplings:
    #             # Buat dictionary untuk controller dengan data minimal
    #             controller_data = None
    #             if sampling.controller_id:
    #                 controller_data = {
    #                     'id': sampling.controller_id.id,
    #                     'name': sampling.controller_id.name
    #                 }

    #             row = {
    #                 'id': sampling.id,
    #                 'name': sampling.name,
    #                 'date': sampling.date.strftime('%Y-%m-%d') if sampling.date else None,
    #                 'timestamps': {
    #                     'created': sampling.create_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.create_date else None,
    #                     'updated': sampling.write_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.write_date else None,
    #                     'validated': sampling.validation_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.validation_date else None
    #                 },
    #                 'sale_order': {
    #                     'id': sampling.sale_order_id.id,
    #                     'name': sampling.sale_order_id.name,
    #                     'car_info': {
    #                         'plate': sampling.sale_order_id.partner_car_id.number_plate if sampling.sale_order_id.partner_car_id else None,
    #                         'brand': sampling.sale_order_id.partner_car_brand.name if sampling.sale_order_id.partner_car_brand else None,
    #                         'type': sampling.sale_order_id.partner_car_brand_type.name if sampling.sale_order_id.partner_car_brand_type else None,
    #                     }
    #                 } if sampling.sale_order_id else None,
    #                 'sop': {
    #                     'id': sampling.sop_id.id,
    #                     'name': sampling.sop_id.name,
    #                     'code': sampling.sop_id.code,
    #                     'is_sa': sampling.sop_id.is_sa,
    #                     'department': sampling.sop_id.department,
    #                     'department_label': dict(sampling.sop_id._fields['department'].selection).get(sampling.sop_id.department, '')
    #                 } if sampling.sop_id else None,
    #                 'employee': {
    #                     'service_advisor': [{
    #                         'id': sa.id,
    #                         'name': sa.name
    #                     } for sa in sampling.sa_id] if sampling.sa_id else [],
    #                     'mechanic': [{
    #                         'id': mech.id,
    #                         'name': mech.name
    #                     } for mech in sampling.mechanic_id] if sampling.mechanic_id else []
    #                 },
    #                 'controller': controller_data,
    #                 'state': sampling.state,
    #                 'state_label': dict(sampling._fields['state'].selection).get(sampling.state, ''),
    #                 'result': sampling.result,
    #                 'result_label': dict(sampling._fields['result'].selection).get(sampling.result, '') if sampling.result else '',
    #                 'notes': sampling.notes
    #             }
    #             rows.append(row)

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'rows': rows,
    #                 'pagination': {
    #                     'total_items': total_count,
    #                     'total_pages': math.ceil(total_count / limit) if total_count > 0 else 1,
    #                     'current_page': page,
    #                     'items_per_page': limit
    #                 },
    #                 'filters': {
    #                     'states': [
    #                         {'value': 'draft', 'label': 'Draft'},
    #                         {'value': 'in_progress', 'label': 'In Progress'},
    #                         {'value': 'done', 'label': 'Done'}
    #                     ],
    #                     'results': [
    #                         {'value': 'pass', 'label': 'Lulus'},
    #                         {'value': 'fail', 'label': 'Tidak Lulus'}
    #                     ]
    #                 }
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in get_sampling_list: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}