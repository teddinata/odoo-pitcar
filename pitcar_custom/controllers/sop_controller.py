from odoo import http, fields
from odoo.http import request, Response
import logging
import re
import pytz
from datetime import datetime, timedelta
import math
from io import StringIO
import csv


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
            'cs': [('job_id.name', 'ilike', 'customer service')],
            'lead_mechanic': [('job_id.name', 'ilike', 'lead mechanic')],
            'lead_cs': [('job_id.name', 'ilike', 'lead customer service')],
            'head_workshop': [('job_id.name', 'ilike', 'kepala bengkel')]
        }
        return domains.get(role, [])

    def _get_sop_domain(self, role=None, department=None, sampling_type=None, search=None):
        """Build domain for SOP search"""
        domain = [('active', '=', True)]
        
        if role:
            domain.append(('role', '=', role))
        if department:
            domain.append(('department', '=', department))
        if sampling_type:
            # If sampling_type is specified, get SOPs valid for that type
            if sampling_type == 'kaizen':
                domain.append(('sampling_type', 'in', ['kaizen', 'both']))
            elif sampling_type == 'lead':
                domain.append(('sampling_type', 'in', ['lead', 'both']))
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
            } for cs in sampling.cs_id] if sampling.cs_id else [],
            
            # Add new leadership roles
            'lead_mechanic': [{
                'id': lm.id,
                'name': lm.name
            } for lm in sampling.lead_mechanic_id] if sampling.lead_mechanic_id else [],
            
            'lead_customer_service': [{
                'id': lcs.id,
                'name': lcs.name
            } for lcs in sampling.lead_cs_id] if sampling.lead_cs_id else [],
            
            'head_workshop': [{
                'id': hw.id,
                'name': hw.name
            } for hw in sampling.head_workshop_id] if sampling.head_workshop_id else [],
        }

    @http.route('/web/sop/master/list', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sop_list(self, **kw):
        try:
            # Parameters
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            role = kw.get('role')
            department = kw.get('department')
            sampling_type = kw.get('sampling_type')
            activity_type = kw.get('activity_type')
            state = kw.get('state')
            review_state = kw.get('review_state')
            socialization_state = kw.get('socialization_state')
            search = (kw.get('search') or '').strip()
            
            # Sort parameters
            sort_by = kw.get('sort_by', 'code')
            sort_order = kw.get('sort_order', 'asc')
            
            # Validate dan map sort_by ke field yang valid
            valid_sort_fields = {
                'code': 'code',
                'name': 'name',
                'department': 'department',
                'role': 'role',
                'sampling_type': 'sampling_type',
                'date_start': 'date_start',
                'date_end': 'date_end',
                'socialization_date': 'socialization_date',
                'socialization_target_date': 'socialization_target_date',
                'state': 'state'
            }
            
            # Pastikan sort_by valid, jika tidak gunakan default
            sort_field = valid_sort_fields.get(sort_by, 'code')
            
            # Build order string
            order_string = f"{sort_field} {sort_order}"

            # Build domain
            domain = [('active', '=', True)]
            
            if role:
                domain.append(('role', '=', role))
            
            if department:
                domain.append(('department', '=', department))
            
            if sampling_type:
                domain.append(('sampling_type', '=', sampling_type))
            
            if activity_type:
                domain.append(('activity_type', '=', activity_type))
            
            if state:
                domain.append(('state', '=', state))
            
            if review_state:
                domain.append(('review_state', '=', review_state))
            
            if socialization_state:
                domain.append(('socialization_state', '=', socialization_state))
            
            if search:
                for term in search.split():
                    domain.extend(['|', '|', '|', '|',
                        ('name', 'ilike', term),
                        ('code', 'ilike', term),
                        ('description', 'ilike', term),
                        ('document_url', 'ilike', term),
                        ('notes', 'ilike', term)
                    ])
            
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
                    'sampling_type': sop.sampling_type,
                    'sampling_type_label': dict(sop._fields['sampling_type'].selection).get(sop.sampling_type, ''),
                    'activity_type': sop.activity_type,
                    'activity_type_label': dict(sop._fields['activity_type'].selection).get(sop.activity_type, ''),
                    'date_start': sop.date_start.strftime('%Y-%m-%d') if sop.date_start else None,
                    'date_end': sop.date_end.strftime('%Y-%m-%d') if sop.date_end else None,
                    'state': sop.state,
                    'state_label': dict(sop._fields['state'].selection).get(sop.state, ''),
                    'review_state': sop.review_state,
                    'review_state_label': dict(sop._fields['review_state'].selection).get(sop.review_state, ''),
                    'revision_state': sop.revision_state,
                    'revision_state_label': dict(sop._fields['revision_state'].selection).get(sop.revision_state, ''),
                    'document_url': sop.document_url,
                    'socialization_state': sop.socialization_state,
                    'socialization_state_label': dict(sop._fields['socialization_state'].selection).get(sop.socialization_state, ''),
                    'socialization_date': sop.socialization_date.strftime('%Y-%m-%d') if sop.socialization_date else None,
                    'socialization_target_date': sop.socialization_target_date.strftime('%Y-%m-%d') if sop.socialization_target_date else None,
                    'socialization_status': sop.socialization_status,
                    'socialization_status_label': dict(sop._fields['socialization_status'].selection).get(sop.socialization_status, ''),
                    'notes': sop.notes,
                    'is_lead_role': sop.is_lead_role,
                    'is_sa': sop.is_sa,
                    'sequence': sop.sequence,
                    'days_to_complete': sop.days_to_complete
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
                            {'value': 'lead_mechanic', 'label': 'Lead Mechanic'},
                            {'value': 'valet', 'label': 'Valet Parking'},
                            {'value': 'part_support', 'label': 'Part Support'},
                            {'value': 'cs', 'label': 'Customer Service'},
                            {'value': 'lead_cs', 'label': 'Lead Customer Service'},
                            {'value': 'head_workshop', 'label': 'Kepala Bengkel'},
                            {'value': 'kasir', 'label': 'Kasir'}
                        ],
                        'sampling_types': [
                            {'value': 'kaizen', 'label': 'Kaizen Team'},
                            {'value': 'lead', 'label': 'Leader'},
                            {'value': 'both', 'label': 'Both'}
                        ],
                        'activity_types': [
                            {'value': 'pembuatan', 'label': 'Pembuatan'},
                            {'value': 'revisi', 'label': 'Revisi'},
                            {'value': 'update', 'label': 'Update'}
                        ],
                        'states': [
                            {'value': 'draft', 'label': 'Draft'},
                            {'value': 'in_progress', 'label': 'In Progress'},
                            {'value': 'done', 'label': 'Done'},
                            {'value': 'cancelled', 'label': 'Cancelled'}
                        ],
                        'review_states': [
                            {'value': 'waiting', 'label': 'Waiting for Review'},
                            {'value': 'in_review', 'label': 'In Review'},
                            {'value': 'done', 'label': 'Done'},
                            {'value': 'rejected', 'label': 'Rejected'}
                        ],
                        'socialization_states': [
                            {'value': 'not_started', 'label': 'Belum Dimulai'},
                            {'value': 'scheduled', 'label': 'Dijadwalkan'},
                            {'value': 'in_progress', 'label': 'Sedang Berlangsung'},
                            {'value': 'done', 'label': 'Selesai'}
                        ],
                        'socialization_statuses': [
                            {'value': 'on_time', 'label': 'Tepat Waktu'},
                            {'value': 'delayed', 'label': 'Terlambat'},
                            {'value': 'not_due', 'label': 'Belum Jatuh Tempo'}
                        ]
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam get_sop_list: {str(e)}")
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
            sampling_type = kw.get('sampling_type')  # New parameter

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
                        lambda s: s.sop_id.role == 'mechanic' and mech.id in s.mechanic_id.ids
                    ))
                } for mech in order.car_mechanic_id_new] if order.car_mechanic_id_new else []

                # Format SA data - Fixed to properly count sampling for service advisors
                sa_data = [{
                    'id': sa.id,
                    'name': sa.name,
                    'sampling_count': len(order.sop_sampling_ids.filtered(
                        lambda s: s.sop_id.role == 'sa' and sa.id in s.sa_id.ids
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
                    'sampling_count': {
                        'total': len(order.sop_sampling_ids),
                        'kaizen': len(order.sop_sampling_ids.filtered(lambda s: s.sampling_type == 'kaizen')),
                        'lead': len(order.sop_sampling_ids.filtered(lambda s: s.sampling_type == 'lead'))
                    }
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
            sampling_type = kw.get('sampling_type', 'kaizen')  # Default to kaizen if not specified

            if not sale_order_id or not sop_id:
                return {
                    'status': 'error',
                    'message': 'Sale order and SOP are required'
                }

            # Get SOP and validate
            sop = request.env['pitcar.sop'].sudo().browse(sop_id)
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP not found'}
            
            # Verifikasi compatibility sampling type
            if sop.sampling_type not in ['both', sampling_type]:
                return {
                    'status': 'error',
                    'message': f'SOP {sop.name} tidak dapat di-sampling oleh {sampling_type}, hanya oleh {sop.sampling_type}'
                }

            # Base values
            values = {
                'sale_order_id': sale_order_id,
                'sop_id': sop_id,
                'controller_id': request.env.user.employee_id.id,
                'notes': notes,
                'state': 'draft',
                'sampling_type': sampling_type
            }

            # Role-specific employee assignment
            sale_order = request.env['sale.order'].sudo().browse(sale_order_id)
            
            # Penanganan Service Advisor - FIX: Pastikan data SA terbawa dengan benar
            if sop.role == 'sa':
                if not sale_order.service_advisor_id:
                    return {'status': 'error', 'message': 'Tidak ada Service Advisor yang ditugaskan'}
                values['sa_id'] = [(6, 0, sale_order.service_advisor_id.ids)]
                # Tambahan log untuk debug
                _logger.info(f"Assigning SA: {sale_order.service_advisor_id.ids} to sampling")
            
            # Penanganan Mekanik
            elif sop.role == 'mechanic':
                if not sale_order.car_mechanic_id_new:
                    return {'status': 'error', 'message': 'Tidak ada Mekanik yang ditugaskan'}
                values['mechanic_id'] = [(6, 0, sale_order.car_mechanic_id_new.ids)]
            
            # Penanganan Valet Parking
            elif sop.role == 'valet':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Staff Valet harus dipilih'}
                values['valet_id'] = [(6, 0, employee_ids)]
            
            # Penanganan Part Support
            elif sop.role == 'part_support':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Staff Part Support harus dipilih'}
                values['part_support_id'] = [(6, 0, employee_ids)]

            # Penanganan Customer Service
            elif sop.role == 'cs':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Staff Customer Service harus dipilih'}
                values['cs_id'] = [(6, 0, employee_ids)]
                
            # Penanganan Lead Mechanic
            elif sop.role == 'lead_mechanic':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Lead Mechanic harus dipilih'}
                values['lead_mechanic_id'] = [(6, 0, employee_ids)]
                
            # Penanganan Lead Customer Service
            elif sop.role == 'lead_cs':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Lead Customer Service harus dipilih'}
                values['lead_cs_id'] = [(6, 0, employee_ids)]
                
            # Penanganan Kepala Bengkel
            elif sop.role == 'head_workshop':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Kepala Bengkel harus dipilih'}
                values['head_workshop_id'] = [(6, 0, employee_ids)]

            # Create sampling dengan sudo untuk menghindari masalah hak akses
            sampling = request.env['pitcar.sop.sampling'].sudo().create(values)
            
            # Verifikasi data service advisor tersimpan dengan benar
            if sop.role == 'sa' and sampling.sa_id:
                _logger.info(f"Verified SA assigned: {sampling.sa_id.ids}")

            return {
                'status': 'success',
                'data': {
                    'id': sampling.id,
                    'name': sampling.name,
                    'sale_order_id': sampling.sale_order_id.id,
                    'sop_id': sampling.sop_id.id,
                    'sampling_type': sampling.sampling_type,
                    'employee_info': self._format_employee_info(sampling),
                    'state': sampling.state
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam create_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

      
    @http.route('/web/sop/sampling/bulk-create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_bulk_sampling(self, **kw):
        """Membuat beberapa SOP sampling untuk satu sale order"""
        try:
            # Extract parameters
            sale_order_id = kw.get('sale_order_id')
            sampling_data = kw.get('samplings', [])  # List of SOP samplings to create
            sampling_type = kw.get('sampling_type', 'kaizen')  # Default sampling type

            if not sale_order_id:
                return {'status': 'error', 'message': 'ID Sale Order wajib diisi'}
            if not sampling_data:
                return {'status': 'error', 'message': 'Tidak ada data sampling yang diberikan'}

            sale_order = request.env['sale.order'].sudo().browse(sale_order_id)
            if not sale_order.exists():
                return {'status': 'error', 'message': 'Sale Order tidak ditemukan'}

            # Dapatkan controller (penilai)
            controller = request.env.user.employee_id
            if not controller:
                return {'status': 'error', 'message': 'User saat ini tidak memiliki data karyawan'}

            created_samplings = []
            for data in sampling_data:
                sop_id = data.get('sop_id')
                notes = data.get('notes')
                data_sampling_type = data.get('sampling_type', sampling_type)  # Bisa individual per SOP

                if not sop_id:
                    continue

                sop = request.env['pitcar.sop'].sudo().browse(sop_id)
                if not sop.exists():
                    continue
                    
                # Verifikasi compatibility sampling type
                if sop.sampling_type not in ['both', data_sampling_type]:
                    _logger.warning(f"Skipping SOP {sop.name}: incompatible sampling type")
                    continue

                # Persiapkan nilai
                values = {
                    'sale_order_id': sale_order_id,
                    'sop_id': sop_id,
                    'controller_id': controller.id,
                    'notes': notes,
                    'state': 'draft',
                    'sampling_type': data_sampling_type
                }

                # Tangani penugasan karyawan berdasarkan role
                if sop.role == 'sa':
                    if sale_order.service_advisor_id:
                        values['sa_id'] = [(6, 0, sale_order.service_advisor_id.ids)]
                        _logger.info(f"Bulk create - assigning SA: {sale_order.service_advisor_id.ids}")
                elif sop.role == 'mechanic':
                    if sale_order.car_mechanic_id_new:
                        values['mechanic_id'] = [(6, 0, sale_order.car_mechanic_id_new.ids)]
                # Catatan: untuk role lain perlu employee_ids dari front-end yang tidak ada dalam bulk create

                # Buat sampling
                sampling = request.env['pitcar.sop.sampling'].sudo().create(values)
                # Verifikasi data
                if sop.role == 'sa':
                    _logger.info(f"Bulk create - Verified SA assigned: {sampling.sa_id.ids}")
                    
                created_samplings.append({
                    'id': sampling.id,
                    'name': sampling.name,
                    'sop_id': sampling.sop_id.id,
                    'sampling_type': sampling.sampling_type,
                    'employee_info': self._format_employee_info(sampling)
                })

            return {
                'status': 'success',
                'data': {
                    'sale_order_id': sale_order_id,
                    'samplings': created_samplings
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam create_bulk_sampling: {str(e)}")
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
            sampling_type = kw.get('sampling_type')  # Filter baru untuk tipe sampling

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
                
            # Sampling type filter
            if sampling_type and sampling_type != 'all':
                domain.append(('sampling_type', '=', sampling_type))

            # Search filter - tambahkan pencarian untuk role baru
            if search:
                domain.extend(['|', '|', '|', '|', '|', '|', '|', '|', '|', '|',
                    ('name', 'ilike', search),
                    ('sale_order_id.name', 'ilike', search),
                    ('sa_id.name', 'ilike', search),
                    ('mechanic_id.name', 'ilike', search),
                    ('valet_id.name', 'ilike', search),
                    ('part_support_id.name', 'ilike', search),
                    ('cs_id.name', 'ilike', search),
                    ('lead_mechanic_id.name', 'ilike', search),
                    ('lead_cs_id.name', 'ilike', search),
                    ('head_workshop_id.name', 'ilike', search),
                    ('sop_id.name', 'ilike', search),
                    ('sop_id.code', 'ilike', search)
                ])

            # Get data dengan sudo untuk akses konsisten
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
                        'department_label': dict(sampling.sop_id._fields['department'].selection).get(sampling.sop_id.department, ''),
                        'sampling_type': sampling.sop_id.sampling_type,
                        'sampling_type_label': dict(sampling.sop_id._fields['sampling_type'].selection).get(sampling.sop_id.sampling_type, '')
                    } if sampling.sop_id else None,
                    'sampling_type': sampling.sampling_type,
                    'sampling_type_label': dict(sampling._fields['sampling_type'].selection).get(sampling.sampling_type, ''),
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
                            {'value': 'lead_mechanic', 'label': 'Lead Mechanic'},
                            {'value': 'valet', 'label': 'Valet Parking'},
                            {'value': 'part_support', 'label': 'Part Support'},
                            {'value': 'cs', 'label': 'Customer Service'},
                            {'value': 'lead_cs', 'label': 'Lead Customer Service'},
                            {'value': 'head_workshop', 'label': 'Kepala Bengkel'}
                        ],
                        'states': [
                            {'value': 'draft', 'label': 'Draft'},
                            {'value': 'in_progress', 'label': 'In Progress'},
                            {'value': 'done', 'label': 'Done'}
                        ],
                        'results': [
                            {'value': 'pass', 'label': 'Lulus'},
                            {'value': 'fail', 'label': 'Tidak Lulus'}
                        ],
                        'sampling_types': [
                            {'value': 'kaizen', 'label': 'Tim Kaizen'},
                            {'value': 'lead', 'label': 'Leader'}
                        ]
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam get_sampling_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}

        
    @http.route('/web/sop/sampling/validate', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def validate_sampling(self, **kw):
        try:
            sampling_id = kw.get('sampling_id')
            result = kw.get('result')
            notes = kw.get('notes')
            
            if not sampling_id or not result:
                return {'status': 'error', 'message': 'ID Sampling dan hasil penilaian wajib diisi'}

            # Use sudo() untuk menghindari masalah hak akses
            sampling = request.env['pitcar.sop.sampling'].sudo().browse(sampling_id)
            if not sampling.exists():
                return {'status': 'error', 'message': 'Sampling tidak ditemukan'}

            # Log untuk debugging Service Advisor issue
            if sampling.sop_id.role == 'sa':
                _logger.info(f"Validating SA sampling: {sampling.id}, Current SA IDs: {sampling.sa_id.ids}")

            values = {
                'state': 'done',
                'result': result,
                'notes': notes,
                'validation_date': fields.Datetime.now()
            }

            # Pastikan nilai Service Advisor masih terbawa
            if sampling.sop_id.role == 'sa' and not sampling.sa_id and sampling.sale_order_id.service_advisor_id:
                _logger.info(f"Fixing missing SA data during validation: {sampling.sale_order_id.service_advisor_id.ids}")
                values['sa_id'] = [(6, 0, sampling.sale_order_id.service_advisor_id.ids)]

            sampling.write(values)
            
            # Verifikasi setelah update
            if sampling.sop_id.role == 'sa':
                _logger.info(f"After validation, SA IDs: {sampling.sa_id.ids}")
            
            return {
                'status': 'success',
                'data': {
                    'id': sampling.id,
                    'name': sampling.name,
                    'result': sampling.result,
                    'state': sampling.state,
                    'notes': sampling.notes,
                    'sampling_type': sampling.sampling_type,
                    'employee_info': self._format_employee_info(sampling)
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam validate_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/summary', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sampling_summary(self, **kw):
        """Dapatkan statistik ringkasan sampling komprehensif dan statistik umum"""
        try:
            params = self._get_request_data()
            month = kw.get('month') or params.get('month')
            sampling_type = kw.get('sampling_type') or params.get('sampling_type')
            include_statistics = kw.get('include_statistics') or params.get('include_statistics', False)
            
            if not month:
                return {'status': 'error', 'message': 'Parameter bulan wajib diisi'}

            Sampling = request.env['pitcar.sop.sampling'].sudo()
            SOP = request.env['pitcar.sop'].sudo()
            
            domain_base = [('month', '=', month)]
            domain_done = domain_base + [('state', '=', 'done')]
            
            # Filter berdasarkan tipe sampling jika ada
            if sampling_type:
                domain_base.append(('sampling_type', '=', sampling_type))
                domain_done.append(('sampling_type', '=', sampling_type))
            
            samplings = Sampling.search(domain_done)
            
            # Inisialisasi struktur ringkasan dengan semua peran
            summary = {
                'total': {
                    'total': 0,
                    'pass': 0,
                    'fail': 0,
                    'pass_rate': 0,
                    'fail_rate': 0
                },
                'month': month,
                'sampling_type': sampling_type,
                'roles': {
                    'sa': {
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
                    'lead_mechanic': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Lead Mechanic',
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
                    'cs': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Customer Service',
                        'details': []
                    },
                    'lead_cs': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Lead Customer Service',
                        'details': []
                    },
                    'head_workshop': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Kepala Bengkel',
                        'details': []
                    }
                }
            }

            # Helper untuk memperbarui statistik
            def update_stats(stats_dict, result):
                stats_dict['total'] += 1
                stats_dict['pass'] += 1 if result == 'pass' else 0
                stats_dict['fail'] += 1 if result == 'fail' else 0

            # Helper untuk memperbarui statistik karyawan
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

            # Inisialisasi kamus statistik karyawan
            employee_stats = {
                'sa': {},
                'mechanic': {},
                'lead_mechanic': {},
                'valet': {},
                'part_support': {},
                'cs': {},
                'lead_cs': {},
                'head_workshop': {}
            }

            # Proses semua sampling
            for sampling in samplings:
                role = sampling.sop_id.role
                result = sampling.result
                
                if role not in summary['roles']:
                    continue

                # Perbarui statistik total
                update_stats(summary['total'], result)
                
                # Perbarui statistik peran
                update_stats(summary['roles'][role], result)
                
                # Perbarui statistik karyawan berdasarkan peran
                if role == 'sa' and sampling.sa_id:
                    for employee in sampling.sa_id:
                        update_employee_stats(employee_stats['sa'], employee, result)
                elif role == 'mechanic' and sampling.mechanic_id:
                    for employee in sampling.mechanic_id:
                        update_employee_stats(employee_stats['mechanic'], employee, result)
                elif role == 'lead_mechanic' and sampling.lead_mechanic_id:
                    for employee in sampling.lead_mechanic_id:
                        update_employee_stats(employee_stats['lead_mechanic'], employee, result)
                elif role == 'valet' and sampling.valet_id:
                    for employee in sampling.valet_id:
                        update_employee_stats(employee_stats['valet'], employee, result)
                elif role == 'part_support' and sampling.part_support_id:
                    for employee in sampling.part_support_id:
                        update_employee_stats(employee_stats['part_support'], employee, result)
                elif role == 'cs' and sampling.cs_id:
                    for employee in sampling.cs_id:
                        update_employee_stats(employee_stats['cs'], employee, result)
                elif role == 'lead_cs' and sampling.lead_cs_id:
                    for employee in sampling.lead_cs_id:
                        update_employee_stats(employee_stats['lead_cs'], employee, result)
                elif role == 'head_workshop' and sampling.head_workshop_id:
                    for employee in sampling.head_workshop_id:
                        update_employee_stats(employee_stats['head_workshop'], employee, result)

            # Hitung tingkat kelulusan dan urut detail karyawan
            def calculate_rates(stats):
                if stats['total'] > 0:
                    stats['pass_rate'] = round((stats['pass'] / stats['total']) * 100, 2)
                    stats['fail_rate'] = round((stats['fail'] / stats['total']) * 100, 2)

            # Hitung tingkat untuk total keseluruhan
            calculate_rates(summary['total'])

            # Proses statistik masing-masing peran
            for role in summary['roles']:
                # Hitung tingkat untuk total peran
                calculate_rates(summary['roles'][role])
                
                # Proses detail karyawan untuk peran ini
                details = list(employee_stats[role].values())
                for detail in details:
                    calculate_rates(detail)
                
                # Urutkan berdasarkan tingkat kelulusan (menurun)
                details.sort(key=lambda x: x['pass_rate'], reverse=True)
                
                # Tambahkan peringkat
                for i, detail in enumerate(details, 1):
                    detail['rank'] = i
                
                summary['roles'][role]['details'] = details

            # Tambahkan statistik umum jika diminta
            if include_statistics:
                # Hitung total SOP aktif
                total_sops = SOP.search_count([('active', '=', True)])
                
                # Hitung total samplings per tipe
                total_samplings = Sampling.search_count(domain_base)
                kaizen_samplings = Sampling.search_count(domain_base + [('sampling_type', '=', 'kaizen')])
                lead_samplings = Sampling.search_count(domain_base + [('sampling_type', '=', 'lead')])
                
                # Hitung status
                done_samplings = Sampling.search_count(domain_base + [('state', '=', 'done')])
                passed_samplings = Sampling.search_count(domain_base + [('result', '=', 'pass')])
                failed_samplings = Sampling.search_count(domain_base + [('result', '=', 'fail')])
                
                # Hitung samplings per departemen
                service_samplings = Sampling.search_count(domain_base + [('sop_id.department', '=', 'service')])
                cs_samplings = Sampling.search_count(domain_base + [('sop_id.department', '=', 'cs')])
                sparepart_samplings = Sampling.search_count(domain_base + [('sop_id.department', '=', 'sparepart')])
                
                # Hitung persentase
                completion_rate = round((done_samplings / total_samplings * 100), 2) if total_samplings > 0 else 0
                pass_rate = round((passed_samplings / done_samplings * 100), 2) if done_samplings > 0 else 0
                
                # Tambahkan ke respons
                summary['statistics'] = {
                    'total_sops': total_sops,
                    'sampling_counts': {
                        'total': total_samplings,
                        'kaizen': kaizen_samplings,
                        'lead': lead_samplings,
                        'done': done_samplings,
                        'pass': passed_samplings,
                        'fail': failed_samplings
                    },
                    'department_counts': {
                        'service': service_samplings,
                        'cs': cs_samplings,
                        'sparepart': sparepart_samplings
                    },
                    'rates': {
                        'completion': completion_rate,
                        'pass': pass_rate
                    }
                }

            return {
                'status': 'success',
                'data': summary
            }

        except Exception as e:
            _logger.error(f"Error dalam get_sampling_summary: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    # CRUD MASTER
    @http.route('/web/sop/master/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_sop(self, **kw):
        """Membuat SOP baru"""
        try:
            # Validasi data wajib
            required_fields = ['name', 'code', 'department', 'role']
            missing_fields = [field for field in required_fields if not kw.get(field)]
            
            if missing_fields:
                return {
                    'status': 'error', 
                    'message': f"Field berikut wajib diisi: {', '.join(missing_fields)}"
                }
            
            # Periksa apakah kode SOP sudah ada
            existing_code = request.env['pitcar.sop'].sudo().search([('code', '=', kw.get('code'))])
            if existing_code:
                return {'status': 'error', 'message': 'Kode SOP sudah digunakan'}
            
            # Siapkan values untuk create
            vals = {
                'name': kw.get('name'),
                'code': kw.get('code'),
                'description': kw.get('description', ''),
                'department': kw.get('department'),
                'role': kw.get('role'),
                'sampling_type': kw.get('sampling_type', 'both'),
                'activity_type': kw.get('activity_type', 'pembuatan'),
                'date_start': kw.get('date_start'),
                'date_end': kw.get('date_end'),
                'state': kw.get('state', 'draft'),
                'review_state': kw.get('review_state', 'waiting'),
                'revision_state': kw.get('revision_state', 'no_revision'),
                'document_url': kw.get('document_url', ''),
                'socialization_state': kw.get('socialization_state', 'not_started'),
                'socialization_date': kw.get('socialization_date'),
                'socialization_target_date': kw.get('socialization_target_date'),
                'notes': kw.get('notes', ''),
                'sequence': kw.get('sequence', 10)
            }
            
            # Buat SOP baru
            new_sop = request.env['pitcar.sop'].sudo().create(vals)
            
            return {
                'status': 'success',
                'message': 'SOP berhasil dibuat',
                'data': {'id': new_sop.id}
            }
        
        except Exception as e:
            _logger.error(f"Error di create_sop: {str(e)}")
            return {'status': 'error', 'message': str(e)}



    @http.route('/web/sop/master/<int:sop_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sop_detail(self, sop_id, **kw):
        """Dapatkan detail SOP berdasarkan ID"""
        try:
            sop = request.env['pitcar.sop'].sudo().browse(sop_id)
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}

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
                    'sampling_type': sop.sampling_type,
                    'sampling_type_label': dict(sop._fields['sampling_type'].selection).get(sop.sampling_type, ''),
                    'is_lead_role': sop.is_lead_role,
                    'is_sa': sop.is_sa,  # Backward compatibility
                    'description': sop.description,
                    'sequence': sop.sequence,
                    'active': sop.active
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam get_sop_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/sop/master/update', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def update_sop(self, **kw):
        """Memperbarui data SOP"""
        try:
            sop_id = kw.get('id')
            if not sop_id:
                return {'status': 'error', 'message': 'ID SOP diperlukan'}
            
            sop = request.env['pitcar.sop'].sudo().browse(int(sop_id))
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}
            
            # Periksa apakah kode SOP yang baru sudah ada (jika kode diubah)
            if kw.get('code') and kw.get('code') != sop.code:
                existing_code = request.env['pitcar.sop'].sudo().search([
                    ('code', '=', kw.get('code')),
                    ('id', '!=', sop.id)
                ])
                if existing_code:
                    return {'status': 'error', 'message': 'Kode SOP sudah digunakan'}
            
            # Siapkan values untuk update
            vals = {}
            
            # Update fields yang diubah
            update_fields = [
                'name', 'code', 'description', 'department', 'role', 'sampling_type',
                'activity_type', 'date_start', 'date_end', 'state', 'review_state',
                'revision_state', 'document_url', 'socialization_state', 'socialization_date', 
                'socialization_target_date', 'notes', 'sequence', 'active'
            ]
            
            for field in update_fields:
                if field in kw:
                    vals[field] = kw[field]
            
            # Update SOP
            sop.write(vals)
            
            return {
                'status': 'success',
                'message': 'SOP berhasil diperbarui'
            }
        
        except Exception as e:
            _logger.error(f"Error di update_sop: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/sop/master/change_state', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def change_sop_state(self, **kw):
        """Mengubah status SOP"""
        try:
            sop_id = kw.get('id')
            action = kw.get('action')
            
            if not sop_id or not action:
                return {'status': 'error', 'message': 'ID SOP dan jenis aksi diperlukan'}
            
            sop = request.env['pitcar.sop'].sudo().browse(int(sop_id))
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}
            
            # Eksekusi aksi yang dipilih
            if action == 'start_sop':
                sop.action_start_sop()
            elif action == 'complete_sop':
                sop.action_complete_sop()
            elif action == 'start_review':
                sop.action_start_review()
            elif action == 'approve_review':
                sop.action_approve_review()
            elif action == 'reject_review':
                sop.action_reject_review()
            elif action == 'complete_revision':
                sop.action_complete_revision()
            elif action == 'schedule_socialization':
                # Untuk schedule_socialization, kita butuh tanggal sosialisasi
                socialization_date = kw.get('socialization_date')
                socialization_target_date = kw.get('socialization_target_date')
                
                if not socialization_date:
                    return {'status': 'error', 'message': 'Tanggal sosialisasi diperlukan'}
                
                sop.write({
                    'socialization_state': 'scheduled',
                    'socialization_date': socialization_date,
                    'socialization_target_date': socialization_target_date
                })
            elif action == 'complete_socialization':
                sop.action_complete_socialization()
            else:
                return {'status': 'error', 'message': 'Aksi tidak valid'}
            
            return {
                'status': 'success',
                'message': 'Status SOP berhasil diubah',
                'data': {
                    'id': sop.id,
                    'state': sop.state,
                    'state_label': dict(sop._fields['state'].selection).get(sop.state, ''),
                    'review_state': sop.review_state,
                    'review_state_label': dict(sop._fields['review_state'].selection).get(sop.review_state, ''),
                    'revision_state': sop.revision_state,
                    'revision_state_label': dict(sop._fields['revision_state'].selection).get(sop.revision_state, ''),
                    'socialization_state': sop.socialization_state,
                    'socialization_state_label': dict(sop._fields['socialization_state'].selection).get(sop.socialization_state, ''),
                    'socialization_date': sop.socialization_date.strftime('%Y-%m-%d') if sop.socialization_date else None,
                    'socialization_target_date': sop.socialization_target_date.strftime('%Y-%m-%d') if sop.socialization_target_date else None,
                    'socialization_status': sop.socialization_status,
                    'socialization_status_label': dict(sop._fields['socialization_status'].selection).get(sop.socialization_status, '')
                }
            }
        
        except Exception as e:
            _logger.error(f"Error di change_sop_state: {str(e)}")
            return {'status': 'error', 'message': str(e)}



    @http.route('/web/sop/master/delete/<int:sop_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def delete_sop(self, sop_id, **kw):
        """Hapus/Arsipkan SOP"""
        try:
            sop = request.env['pitcar.sop'].sudo().browse(int(sop_id))
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}

            # Periksa apakah SOP digunakan dalam sampling
            if request.env['pitcar.sop.sampling'].sudo().search_count([('sop_id', '=', sop_id)]) > 0:
                # Hanya arsipkan jika SOP digunakan
                sop.write({'active': False})
                return {
                    'status': 'success',
                    'message': 'SOP telah diarsipkan karena digunakan dalam catatan sampling'
                }
            else:
                # Hapus jika tidak digunakan
                sop.unlink()
                return {
                    'status': 'success',
                    'message': 'SOP berhasil dihapus'
                }

        except Exception as e:
            _logger.error(f"Error dalam delete_sop: {str(e)}")
        return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/socialization', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def update_sop_socialization(self, **kw):
        """Update informasi sosialisasi SOP"""
        try:
            sop_id = kw.get('id')
            if not sop_id:
                return {'status': 'error', 'message': 'ID SOP diperlukan'}
            
            sop = request.env['pitcar.sop'].sudo().browse(int(sop_id))
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}
            
            # Persiapkan data untuk update
            vals = {}
            if 'socialization_state' in kw:
                vals['socialization_state'] = kw.get('socialization_state')
            
            if 'socialization_date' in kw:
                vals['socialization_date'] = kw.get('socialization_date')
            
            if 'socialization_target_date' in kw:
                vals['socialization_target_date'] = kw.get('socialization_target_date')
                
            if not vals:
                return {'status': 'error', 'message': 'Tidak ada data sosialisasi untuk diupdate'}
            
            # Update SOP
            sop.write(vals)
            
            # Jika state diubah menjadi 'done', update tanggal sosialisasi secara otomatis jika belum diisi
            if vals.get('socialization_state') == 'done' and not sop.socialization_date:
                sop.write({'socialization_date': fields.Date.today()})
            
            return {
                'status': 'success',
                'message': 'Informasi sosialisasi SOP berhasil diperbarui',
                'data': {
                    'id': sop.id,
                    'socialization_state': sop.socialization_state,
                    'socialization_state_label': dict(sop._fields['socialization_state'].selection).get(sop.socialization_state, ''),
                    'socialization_date': sop.socialization_date.strftime('%Y-%m-%d') if sop.socialization_date else None,
                    'socialization_target_date': sop.socialization_target_date.strftime('%Y-%m-%d') if sop.socialization_target_date else None,
                    'socialization_status': sop.socialization_status,
                    'socialization_status_label': dict(sop._fields['socialization_status'].selection).get(sop.socialization_status, '')
                }
            }
        
        except Exception as e:
            _logger.error(f"Error di update_sop_socialization: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/document', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def update_sop_document(self, **kw):
        """Update dokumen URL SOP"""
        try:
            sop_id = kw.get('id')
            document_url = kw.get('document_url')
            
            if not sop_id:
                return {'status': 'error', 'message': 'ID SOP diperlukan'}
            
            if not document_url:
                return {'status': 'error', 'message': 'URL dokumen diperlukan'}
            
            sop = request.env['pitcar.sop'].sudo().browse(int(sop_id))
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}
            
            # Validasi format URL (basic validation)
            if not document_url.startswith(('http://', 'https://')):
                return {'status': 'error', 'message': 'URL dokumen harus dimulai dengan http:// atau https://'}
            
            # Update SOP
            sop.write({'document_url': document_url})
            
            return {
                'status': 'success',
                'message': 'URL dokumen SOP berhasil diperbarui',
                'data': {
                    'id': sop.id,
                    'document_url': sop.document_url
                }
            }
        
        except Exception as e:
            _logger.error(f"Error di update_sop_document: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/bulk-update-state', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def bulk_update_sop_state(self, **kw):
        """Update status untuk beberapa SOP sekaligus"""
        try:
            sop_ids = kw.get('ids')
            state = kw.get('state')
            
            if not sop_ids or not isinstance(sop_ids, list) or not sop_ids:
                return {'status': 'error', 'message': 'Daftar ID SOP diperlukan'}
            
            if not state:
                return {'status': 'error', 'message': 'Status baru diperlukan'}
            
            # Validasi status
            valid_states = [s[0] for s in request.env['pitcar.sop']._fields['state'].selection]
            if state not in valid_states:
                return {'status': 'error', 'message': f'Status {state} tidak valid'}
            
            # Dapatkan SOPs
            sops = request.env['pitcar.sop'].sudo().browse(sop_ids)
            valid_sops = sops.filtered(lambda s: s.exists())
            
            if not valid_sops:
                return {'status': 'error', 'message': 'Tidak ada SOP valid yang ditemukan'}
            
            # Update status
            valid_sops.write({'state': state})
            
            # Jika status adalah 'in_progress', update tanggal mulai jika belum ada
            if state == 'in_progress':
                for sop in valid_sops:
                    if not sop.date_start:
                        sop.write({'date_start': fields.Date.today()})
            
            # Jika status adalah 'done', update tanggal selesai jika belum ada
            if state == 'done':
                for sop in valid_sops:
                    if not sop.date_end:
                        sop.write({'date_end': fields.Date.today()})
            
            # Format pesan berdasarkan jumlah SOP yang diupdate
            message = f"{len(valid_sops)} SOP berhasil diperbarui ke status {dict(valid_sops[0]._fields['state'].selection).get(state, state)}"
            if len(valid_sops) < len(sop_ids):
                message += f" ({len(sop_ids) - len(valid_sops)} SOP tidak ditemukan)"
            
            return {
                'status': 'success',
                'message': message,
                'data': {
                    'updated_ids': valid_sops.ids,
                    'state': state
                }
            }
        
        except Exception as e:
            _logger.error(f"Error di bulk_update_sop_state: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/statistics', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sop_statistics(self, **kw):
        """Mendapatkan statistik SOP secara keseluruhan"""
        try:
            # Filter domain
            domain = [('active', '=', True)]
            
            department = kw.get('department')
            if department:
                domain.append(('department', '=', department))
            
            SOP = request.env['pitcar.sop'].sudo()
            
            # Hitung total SOP
            total_sops = SOP.search_count(domain)
            
            # Statistik berdasarkan state
            stats_by_state = {}
            for state_value, state_label in SOP._fields['state'].selection:
                count = SOP.search_count(domain + [('state', '=', state_value)])
                percentage = round((count / total_sops * 100), 2) if total_sops > 0 else 0
                stats_by_state[state_value] = {
                    'count': count,
                    'percentage': percentage,
                    'label': state_label
                }
            
            # Statistik berdasarkan department
            stats_by_department = {}
            for dept_value, dept_label in SOP._fields['department'].selection:
                count = SOP.search_count(domain + [('department', '=', dept_value)])
                percentage = round((count / total_sops * 100), 2) if total_sops > 0 else 0
                stats_by_department[dept_value] = {
                    'count': count,
                    'percentage': percentage,
                    'label': dept_label
                }
            
            # Statistik berdasarkan role
            stats_by_role = {}
            for role_value, role_label in SOP._fields['role'].selection:
                count = SOP.search_count(domain + [('role', '=', role_value)])
                percentage = round((count / total_sops * 100), 2) if total_sops > 0 else 0
                stats_by_role[role_value] = {
                    'count': count,
                    'percentage': percentage,
                    'label': role_label
                }
            
            # Statistik sosialisasi
            socialization_stats = {
                'scheduled': SOP.search_count(domain + [('socialization_state', '=', 'scheduled')]),
                'in_progress': SOP.search_count(domain + [('socialization_state', '=', 'in_progress')]),
                'done': SOP.search_count(domain + [('socialization_state', '=', 'done')]),
                'not_started': SOP.search_count(domain + [('socialization_state', '=', 'not_started')]),
                'on_time': SOP.search_count(domain + [('socialization_status', '=', 'on_time')]),
                'delayed': SOP.search_count(domain + [('socialization_status', '=', 'delayed')]),
                'not_due': SOP.search_count(domain + [('socialization_status', '=', 'not_due')])
            }
            
            # Statistik dokumen
            document_stats = {
                'with_document': SOP.search_count(domain + [('document_url', '!=', False)]),
                'without_document': SOP.search_count(domain + ['|', ('document_url', '=', False), ('document_url', '=', '')])
            }
            
            # Return semua statistik
            return {
                'status': 'success',
                'data': {
                    'total_sops': total_sops,
                    'by_state': stats_by_state,
                    'by_department': stats_by_department,
                    'by_role': stats_by_role,
                    'socialization': socialization_stats,
                    'document': document_stats
                }
            }
        
        except Exception as e:
            _logger.error(f"Error di get_sop_statistics: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/socialization-schedule', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_socialization_schedule(self, **kw):
        """Mendapatkan jadwal sosialisasi SOP"""
        try:
            # Filter parameters
            start_date = kw.get('start_date')
            end_date = kw.get('end_date')
            
            if not start_date or not end_date:
                # Default ke rentang 30 hari
                today = fields.Date.today()
                start_date = today.strftime('%Y-%m-%d')
                end_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Domain untuk SOP dengan jadwal sosialisasi
            domain = [
                ('active', '=', True),
                ('socialization_target_date', '>=', start_date),
                ('socialization_target_date', '<=', end_date),
                ('socialization_state', 'in', ['not_started', 'scheduled', 'in_progress'])
            ]
            
            # Dapatkan SOPs
            sops = request.env['pitcar.sop'].sudo().search(domain, order='socialization_target_date')
            
            # Format hasil
            schedule_items = []
            for sop in sops:
                schedule_items.append({
                    'id': sop.id,
                    'code': sop.code,
                    'name': sop.name,
                    'department': sop.department,
                    'department_label': dict(sop._fields['department'].selection).get(sop.department, ''),
                    'role': sop.role,
                    'role_label': dict(sop._fields['role'].selection).get(sop.role, ''),
                    'socialization_state': sop.socialization_state,
                    'socialization_state_label': dict(sop._fields['socialization_state'].selection).get(sop.socialization_state, ''),
                    'socialization_target_date': sop.socialization_target_date.strftime('%Y-%m-%d') if sop.socialization_target_date else None,
                    'socialization_date': sop.socialization_date.strftime('%Y-%m-%d') if sop.socialization_date else None,
                    'document_url': sop.document_url or '',
                    'notes': sop.notes or ''
                })
            
            return {
                'status': 'success',
                'data': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'items': schedule_items
                }
            }
        
        except Exception as e:
            _logger.error(f"Error di get_socialization_schedule: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/export', type='http', auth='user', methods=['GET'], csrf=False)
    def export_sop_list(self, **kw):
        """Export daftar SOP ke CSV"""
        try:
            # Domain dasar
            domain = [('active', '=', True)]
            
            # Filter parameters
            department = kw.get('department')
            role = kw.get('role')
            state = kw.get('state')
            
            if department:
                domain.append(('department', '=', department))
            
            if role:
                domain.append(('role', '=', role))
            
            if state:
                domain.append(('state', '=', state))
            
            # Dapatkan SOP
            sops = request.env['pitcar.sop'].sudo().search(domain, order='code, name')
            
            if not sops:
                return Response("Tidak ada data SOP yang ditemukan", content_type='text/plain')
            
            # Buat file CSV
            output = StringIO()
            writer = csv.writer(output)
            
            # Header baris
            header = [
                'Kode', 'Nama', 'Departemen', 'Posisi', 'Aktivitas', 
                'Tanggal Mulai', 'Tanggal Selesai', 'Status', 'Status Review',
                'Status Revisi', 'Target Waktu Sosialisasi', 'Tanggal Sosialisasi', 
                'Status Sosialisasi', 'Dokumen URL', 'Keterangan'
            ]
            writer.writerow(header)
            
            # Department dan role mapping
            dept_mapping = dict(request.env['pitcar.sop']._fields['department'].selection)
            role_mapping = dict(request.env['pitcar.sop']._fields['role'].selection)
            state_mapping = dict(request.env['pitcar.sop']._fields['state'].selection)
            review_mapping = dict(request.env['pitcar.sop']._fields['review_state'].selection)
            revision_mapping = dict(request.env['pitcar.sop']._fields['revision_state'].selection)
            socialization_mapping = dict(request.env['pitcar.sop']._fields['socialization_state'].selection)
            
            # Baris data
            for sop in sops:
                row = [
                    sop.code,
                    sop.name,
                    dept_mapping.get(sop.department, ''),
                    role_mapping.get(sop.role, ''),
                    dict(sop._fields['activity_type'].selection).get(sop.activity_type, ''),
                    sop.date_start.strftime('%Y-%m-%d') if sop.date_start else '',
                    sop.date_end.strftime('%Y-%m-%d') if sop.date_end else '',
                    state_mapping.get(sop.state, ''),
                    review_mapping.get(sop.review_state, ''),
                    revision_mapping.get(sop.revision_state, ''),
                    sop.socialization_target_date.strftime('%Y-%m-%d') if sop.socialization_target_date else '',
                    sop.socialization_date.strftime('%Y-%m-%d') if sop.socialization_date else '',
                    socialization_mapping.get(sop.socialization_state, ''),
                    sop.document_url or '',
                    sop.notes or ''
                ]
                writer.writerow(row)
            
            # Set file name
            filename = f"SOP_List_{fields.Date.today().strftime('%Y%m%d')}.csv"
            
            # Return CSV response
            output_str = output.getvalue()
            output.close()
            
            headers = [
                ('Content-Type', 'text/csv'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(output_str)))
            ]
            
            return Response(output_str, headers=headers)
        
        except Exception as e:
            _logger.error(f"Error di export_sop_list: {str(e)}")
            return Response(f"Error: {str(e)}", content_type='text/plain')


    @http.route('/web/sop/employees', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_employees_by_role(self, **kw):
        """Dapatkan daftar karyawan berdasarkan peran untuk sampling"""
        try:
            role = kw.get('role')
            if not role:
                return {'status': 'error', 'message': 'Parameter peran wajib diisi'}
                
            domain = self._get_employee_domain(role)
            
            # Penanganan khusus untuk model khusus
            if role == 'sa':
                # Service Advisor menggunakan model khusus
                employees = request.env['pitcar.service.advisor'].sudo().search([])
                rows = [{
                    'id': sa.id,
                    'name': sa.name
                } for sa in employees]
            elif role == 'mechanic':
                # Mechanic menggunakan model khusus
                employees = request.env['pitcar.mechanic.new'].sudo().search([])
                rows = [{
                    'id': mech.id,
                    'name': mech.name
                } for mech in employees]
            else:
                # Peran lain menggunakan model hr.employee dengan domain
                employees = request.env['hr.employee'].sudo().search(domain)
                rows = [{
                    'id': emp.id,
                    'name': emp.name,
                    'job': emp.job_id.name if emp.job_id else None
                } for emp in employees]
                
            return {
                'status': 'success',
                'data': {
                    'role': role,
                    'employees': rows
                }
            }
        
        except Exception as e:
            _logger.error(f"Error dalam get_employees_by_role: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/sop/master/detail', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sop_detail(self, **kw):
        """Mendapatkan detail SOP berdasarkan ID"""
        try:
            sop_id = kw.get('id')
            if not sop_id:
                return {'status': 'error', 'message': 'ID SOP diperlukan'}
            
            sop = request.env['pitcar.sop'].sudo().browse(int(sop_id))
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}
            
            # Format hasil untuk respons
            result = {
                'id': sop.id,
                'code': sop.code,
                'name': sop.name,
                'description': sop.description or '',
                'department': sop.department,
                'department_label': dict(sop._fields['department'].selection).get(sop.department, ''),
                'role': sop.role,
                'role_label': dict(sop._fields['role'].selection).get(sop.role, ''),
                'sampling_type': sop.sampling_type,
                'sampling_type_label': dict(sop._fields['sampling_type'].selection).get(sop.sampling_type, ''),
                'activity_type': sop.activity_type,
                'activity_type_label': dict(sop._fields['activity_type'].selection).get(sop.activity_type, ''),
                'date_start': sop.date_start.strftime('%Y-%m-%d') if sop.date_start else '',
                'date_end': sop.date_end.strftime('%Y-%m-%d') if sop.date_end else '',
                'state': sop.state,
                'state_label': dict(sop._fields['state'].selection).get(sop.state, ''),
                'review_state': sop.review_state,
                'review_state_label': dict(sop._fields['review_state'].selection).get(sop.review_state, ''),
                'revision_state': sop.revision_state,
                'revision_state_label': dict(sop._fields['revision_state'].selection).get(sop.revision_state, ''),
                'document_url': sop.document_url or '',
                'socialization_state': sop.socialization_state,
                'socialization_state_label': dict(sop._fields['socialization_state'].selection).get(sop.socialization_state, ''),
                'socialization_date': sop.socialization_date.strftime('%Y-%m-%d') if sop.socialization_date else '',
                'socialization_target_date': sop.socialization_target_date.strftime('%Y-%m-%d') if sop.socialization_target_date else '',
                'socialization_status': sop.socialization_status,
                'socialization_status_label': dict(sop._fields['socialization_status'].selection).get(sop.socialization_status, ''),
                'notes': sop.notes or '',
                'days_to_complete': sop.days_to_complete or 0,
                'is_sa': sop.is_sa,
                'is_lead_role': sop.is_lead_role,
                'sequence': sop.sequence,
                'active': sop.active
            }
            
            return {'status': 'success', 'data': result}
        
        except Exception as e:
            _logger.error(f"Error di get_sop_detail: {str(e)}")
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