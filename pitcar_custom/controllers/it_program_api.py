# controllers/it_kpi_api.py
from odoo import http, fields
from odoo.http import request, Response
import json
import logging
import pytz
from datetime import datetime, timedelta
import base64

_logger = logging.getLogger(__name__)

class ITSystemAPI(http.Controller):
    
    def _format_datetime(self, dt):
        """Format datetime dengan penanganan error yang tepat."""
        if not dt:
            return False
        
        try:
            # Untuk tipe Date (bukan Datetime)
            if hasattr(dt, 'day') and not hasattr(dt, 'hour'):
                return fields.Date.to_string(dt)
                    
            # Jika dt adalah string, konversi ke objek datetime
            if isinstance(dt, str):
                try:
                    if 'T' in dt or ' ' in dt:  # Ini adalah string datetime
                        dt = fields.Datetime.from_string(dt)
                    else:  # Ini adalah string date
                        return dt  # Kembalikan string date langsung
                except Exception as e:
                    _logger.error(f"Error mengkonversi string date/time '{dt}': {e}")
                    return dt  # Kembalikan string asli jika konversi gagal
            
            # Konversi ke string
            if hasattr(dt, 'hour'):  # Ini adalah datetime, bukan date
                try:
                    return fields.Datetime.to_string(dt)
                except Exception as e:
                    _logger.error(f"Error mengkonversi datetime '{dt}': {e}")
                    return str(dt)
            else:
                # Ini adalah objek date
                return fields.Date.to_string(dt) if hasattr(dt, 'day') else str(dt)
                
        except Exception as e:
            _logger.error(f"Error tak terduga di _format_datetime: {e}")
            # Kembalikan nilai yang aman
            return str(dt) if dt else False
    
    def _prepare_system_data(self, system):
        """Siapkan data sistem untuk respon API."""
        return {
            'id': system.id,
            'name': system.name,
            'code': system.code,
            'description': system.description,
            'creation_date': self._format_datetime(system.creation_date),
            'launch_date': self._format_datetime(system.launch_date),
            'version': system.version,
            'state': system.state,
            'documentation_complete': system.documentation_complete,
            'documentation_url': system.documentation_url,
            'socialization_complete': system.socialization_complete,
            'socialization_date': self._format_datetime(system.socialization_date),
            'error_count': system.error_count,
            'error_free_days': system.error_free_days,
            'average_rating': round(system.average_rating, 1),
            'feature_count': system.feature_count,
            'create_date': self._format_datetime(system.create_date),
        }
    
    def _prepare_feature_data(self, feature):
        """Siapkan data fitur untuk respon API."""
        return {
            'id': feature.id,
            'name': feature.name,
            'description': feature.description,
            'state': feature.state,
            'system_id': feature.system_id.id,
            'system_name': feature.system_id.name,
            'has_documentation': feature.has_documentation,
            'documentation_url': feature.documentation_url,
            'parent_id': feature.parent_id.id if feature.parent_id else False,
            'child_count': len(feature.child_ids),
            'responsible': {
                'id': feature.responsible_id.id,
                'name': feature.responsible_id.name
            } if feature.responsible_id else False,
            'sequence': feature.sequence
        }
    
    def _prepare_rating_data(self, rating):
        """Siapkan data rating untuk respon API."""
        return {
            'id': rating.id,
            'system_id': rating.system_id.id,
            'system_name': rating.system_id.name,
            'rater': {
                'id': rating.rater_id.id,
                'name': rating.rater_id.name,
                'department': rating.department_id.name if rating.department_id else False
            },
            'rating_date': self._format_datetime(rating.rating_date),
            'rating_value': rating.rating_value,
            'usability_rating': rating.usability_rating,
            'performance_rating': rating.performance_rating,
            'reliability_rating': rating.reliability_rating,
            'feedback': rating.feedback
        }
    
    def _prepare_error_data(self, error):
        """Siapkan data error untuk respon API."""
        return {
            'id': error.id,
            'name': error.name,
            'system_id': error.system_id.id,
            'system_name': error.system_id.name,
            'reported_by': {
                'id': error.reported_by_id.id,
                'name': error.reported_by_id.name
            } if error.reported_by_id else False,
            'reported_date': self._format_datetime(error.reported_date),
            'severity': error.severity,
            'description': error.description,
            'steps_to_reproduce': error.steps_to_reproduce,
            'state': error.state,
            'assigned_to': {
                'id': error.assigned_to_id.id,
                'name': error.assigned_to_id.name
            } if error.assigned_to_id else False,
            'resolution_date': self._format_datetime(error.resolution_date),
            'resolution': error.resolution,
            'resolution_time': round(error.resolution_time, 2) if error.resolution_time else 0
        }
    
    @http.route('/web/v2/it/systems', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_systems(self, **kw):
        """Mengelola operasi CRUD untuk sistem IT."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['name']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Field yang diperlukan tidak lengkap'}
                
                # Buat sistem IT
                values = {
                    'name': kw['name'],
                    'description': kw.get('description'),
                    'version': kw.get('version', '1.0'),
                    'state': kw.get('state', 'development'),
                    'documentation_complete': kw.get('documentation_complete', False),
                    'documentation_url': kw.get('documentation_url'),
                    'socialization_complete': kw.get('socialization_complete', False)
                }
                
                if kw.get('launch_date'):
                    values['launch_date'] = kw['launch_date']
                    
                if kw.get('creation_date'):
                    values['creation_date'] = kw['creation_date']
                
                system = request.env['it.system'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_system_data(system)}
            
            elif operation == 'read':
                system_id = kw.get('system_id')
                if not system_id:
                    return {'status': 'error', 'message': 'Parameter system_id tidak ada'}
                
                system = request.env['it.system'].sudo().browse(int(system_id))
                if not system.exists():
                    return {'status': 'error', 'message': 'Sistem IT tidak ditemukan'}
                
                include_details = kw.get('include_details', False)
                if isinstance(include_details, str):
                    include_details = include_details.lower() in ('true', '1', 'yes')
                
                system_data = self._prepare_system_data(system)
                
                if include_details:
                    # Tambahkan fitur
                    system_data['features'] = [
                        self._prepare_feature_data(feature) 
                        for feature in system.feature_ids
                    ]
                    
                    # Tambahkan rating
                    system_data['ratings'] = [
                        self._prepare_rating_data(rating) 
                        for rating in system.rating_ids
                    ]
                    
                    # Tambahkan error
                    system_data['errors'] = [
                        self._prepare_error_data(error) 
                        for error in system.error_report_ids
                    ]
                    
                    # Tambahkan info project jika ada
                    if system.project_id:
                        system_data['project'] = {
                            'id': system.project_id.id,
                            'name': system.project_id.name,
                            'state': system.project_id.state,
                            'progress': system.project_id.progress,
                            'date_start': self._format_datetime(system.project_id.date_start),
                            'date_end': self._format_datetime(system.project_id.date_end),
                            'actual_date_end': self._format_datetime(system.project_id.actual_date_end) if hasattr(system.project_id, 'actual_date_end') else False,
                            'is_on_time': system.project_id.is_on_time if hasattr(system.project_id, 'is_on_time') else False,
                        }
                
                return {'status': 'success', 'data': system_data}
            
            elif operation == 'update':
                system_id = kw.get('system_id')
                if not system_id:
                    return {'status': 'error', 'message': 'Parameter system_id tidak ada'}
                
                system = request.env['it.system'].sudo().browse(int(system_id))
                if not system.exists():
                    return {'status': 'error', 'message': 'Sistem IT tidak ditemukan'}
                
                update_values = {}
                updatable_fields = [
                    'name', 'description', 'version', 'state', 
                    'documentation_complete', 'documentation_url',
                    'socialization_complete', 'socialization_date', 'launch_date'
                ]
                
                for field in updatable_fields:
                    if field in kw:
                        if field in ['documentation_complete', 'socialization_complete']:
                            val = kw[field]
                            if isinstance(val, str):
                                val = val.lower() in ('true', '1', 'yes')
                            update_values[field] = val
                        else:
                            update_values[field] = kw[field]
                
                system.write(update_values)
                return {'status': 'success', 'data': self._prepare_system_data(system)}
            
            elif operation == 'delete':
                system_id = kw.get('system_id')
                if not system_id:
                    return {'status': 'error', 'message': 'Parameter system_id tidak ada'}
                
                system = request.env['it.system'].sudo().browse(int(system_id))
                if not system.exists():
                    return {'status': 'error', 'message': 'Sistem IT tidak ditemukan'}
                
                system.unlink()
                return {'status': 'success', 'message': 'Sistem IT berhasil dihapus'}
            
            elif operation == 'list':
                domain = []
                
                # Terapkan filter
                if kw.get('state'):
                    states = kw['state'].split(',')
                    domain.append(('state', 'in', states))
                
                if kw.get('search'):
                    domain.append('|')
                    domain.append(('name', 'ilike', kw['search']))
                    domain.append(('code', 'ilike', kw['search']))
                
                # Pagination
                page = int(kw.get('page', 1))
                limit = int(kw.get('limit', 10))
                offset = (page - 1) * limit
                
                # Sorting
                sort_field = kw.get('sort_field', 'create_date')
                sort_order = kw.get('sort_order', 'desc')
                order = f"{sort_field} {sort_order}"
                
                # Ambil data
                systems = request.env['it.system'].sudo().search(
                    domain, limit=limit, offset=offset, order=order
                )
                total = request.env['it.system'].sudo().search_count(domain)
                
                # Hitung total halaman
                total_pages = (total + limit - 1) // limit if limit > 0 else 1
                
                return {
                    'status': 'success',
                    'data': [self._prepare_system_data(system) for system in systems],
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total,
                        'total_pages': total_pages
                    }
                }
            
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_systems: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/it/features', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_features(self, **kw):
        """Mengelola operasi CRUD untuk fitur sistem IT."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['system_id', 'name']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Field yang diperlukan tidak lengkap'}
                
                # Buat fitur
                values = {
                    'system_id': int(kw['system_id']),
                    'name': kw['name'],
                    'description': kw.get('description'),
                    'state': kw.get('state', 'planned'),
                    'has_documentation': kw.get('has_documentation', False),
                    'documentation_url': kw.get('documentation_url')
                }
                
                if kw.get('parent_id'):
                    values['parent_id'] = int(kw['parent_id'])
                
                if kw.get('responsible_id'):
                    values['responsible_id'] = int(kw['responsible_id'])
                
                if kw.get('sequence'):
                    values['sequence'] = int(kw['sequence'])
                
                feature = request.env['it.system.feature'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_feature_data(feature)}
            
            elif operation == 'read':
                feature_id = kw.get('feature_id')
                if not feature_id:
                    return {'status': 'error', 'message': 'Parameter feature_id tidak ada'}
                
                feature = request.env['it.system.feature'].sudo().browse(int(feature_id))
                if not feature.exists():
                    return {'status': 'error', 'message': 'Fitur tidak ditemukan'}
                
                include_children = kw.get('include_children', False)
                if isinstance(include_children, str):
                    include_children = include_children.lower() in ('true', '1', 'yes')
                
                feature_data = self._prepare_feature_data(feature)
                
                if include_children and feature.child_ids:
                    feature_data['children'] = [
                        self._prepare_feature_data(child) for child in feature.child_ids
                    ]
                
                return {'status': 'success', 'data': feature_data}
            
            elif operation == 'update':
                feature_id = kw.get('feature_id')
                if not feature_id:
                    return {'status': 'error', 'message': 'Parameter feature_id tidak ada'}
                
                feature = request.env['it.system.feature'].sudo().browse(int(feature_id))
                if not feature.exists():
                    return {'status': 'error', 'message': 'Fitur tidak ditemukan'}
                
                update_values = {}
                updatable_fields = [
                    'name', 'description', 'state', 'has_documentation', 
                    'documentation_url', 'parent_id', 'responsible_id', 'sequence'
                ]
                
                for field in updatable_fields:
                    if field in kw:
                        if field in ['parent_id', 'responsible_id']:
                            update_values[field] = int(kw[field]) if kw[field] else False
                        elif field == 'has_documentation':
                            val = kw[field]
                            if isinstance(val, str):
                                val = val.lower() in ('true', '1', 'yes')
                            update_values[field] = val
                        elif field == 'sequence':
                            update_values[field] = int(kw[field])
                        else:
                            update_values[field] = kw[field]
                
                feature.write(update_values)
                return {'status': 'success', 'data': self._prepare_feature_data(feature)}
            
            elif operation == 'delete':
                feature_id = kw.get('feature_id')
                if not feature_id:
                    return {'status': 'error', 'message': 'Parameter feature_id tidak ada'}
                
                feature = request.env['it.system.feature'].sudo().browse(int(feature_id))
                if not feature.exists():
                    return {'status': 'error', 'message': 'Fitur tidak ditemukan'}
                
                feature.unlink()
                return {'status': 'success', 'message': 'Fitur berhasil dihapus'}
            
            elif operation == 'list':
                system_id = kw.get('system_id')
                if not system_id:
                    return {'status': 'error', 'message': 'Parameter system_id tidak ada'}
                
                parent_id = kw.get('parent_id', False)
                if parent_id:
                    parent_id = int(parent_id)
                
                domain = [('system_id', '=', int(system_id))]
                
                # Filter berdasarkan parent
                if parent_id:
                    domain.append(('parent_id', '=', parent_id))
                elif parent_id is False and kw.get('top_level_only', False):
                    domain.append(('parent_id', '=', False))
                
                # Filter berdasarkan state
                if kw.get('state'):
                    states = kw['state'].split(',')
                    domain.append(('state', 'in', states))
                
                # Sorting
                order = kw.get('order', 'sequence, name')
                
                features = request.env['it.system.feature'].sudo().search(domain, order=order)
                
                return {
                    'status': 'success',
                    'data': [self._prepare_feature_data(feature) for feature in features]
                }
            
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_features: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/it/ratings', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_ratings(self, **kw):
        """Mengelola operasi CRUD untuk rating sistem IT."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['system_id', 'rater_id', 'rating_value']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Field yang diperlukan tidak lengkap'}
                
                # Buat rating
                values = {
                    'system_id': int(kw['system_id']),
                    'rater_id': int(kw['rater_id']),
                    'rating_value': float(kw['rating_value']),
                    'usability_rating': kw.get('usability_rating'),
                    'performance_rating': kw.get('performance_rating'),
                    'reliability_rating': kw.get('reliability_rating'),
                    'feedback': kw.get('feedback')
                }
                
                # Cek apakah rater sudah memberikan rating sebelumnya
                existing_rating = request.env['it.system.rating'].sudo().search([
                    ('system_id', '=', int(kw['system_id'])),
                    ('rater_id', '=', int(kw['rater_id']))
                ])
                
                if existing_rating:
                    return {'status': 'error', 'message': 'User ini sudah memberikan rating untuk sistem ini'}
                
                rating = request.env['it.system.rating'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_rating_data(rating)}
            
            elif operation == 'read':
                rating_id = kw.get('rating_id')
                if not rating_id:
                    return {'status': 'error', 'message': 'Parameter rating_id tidak ada'}
                
                rating = request.env['it.system.rating'].sudo().browse(int(rating_id))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating tidak ditemukan'}
                
                return {'status': 'success', 'data': self._prepare_rating_data(rating)}
            
            elif operation == 'update':
                rating_id = kw.get('rating_id')
                if not rating_id:
                    return {'status': 'error', 'message': 'Parameter rating_id tidak ada'}
                
                rating = request.env['it.system.rating'].sudo().browse(int(rating_id))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating tidak ditemukan'}
                
                # Update nilai
                update_values = {}
                updatable_fields = [
                    'rating_value', 'usability_rating', 'performance_rating', 
                    'reliability_rating', 'feedback'
                ]
                
                for field in updatable_fields:
                    if field in kw:
                        if field == 'rating_value':
                            update_values[field] = float(kw[field])
                        else:
                            update_values[field] = kw[field]
                
                rating.write(update_values)
                return {'status': 'success', 'data': self._prepare_rating_data(rating)}
            
            elif operation == 'delete':
                rating_id = kw.get('rating_id')
                if not rating_id:
                    return {'status': 'error', 'message': 'Parameter rating_id tidak ada'}
                
                rating = request.env['it.system.rating'].sudo().browse(int(rating_id))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating tidak ditemukan'}
                
                rating.unlink()
                return {'status': 'success', 'message': 'Rating berhasil dihapus'}
            
            elif operation == 'list_by_system':
                system_id = kw.get('system_id')
                if not system_id:
                    return {'status': 'error', 'message': 'Parameter system_id tidak ada'}
                
                ratings = request.env['it.system.rating'].sudo().search([
                    ('system_id', '=', int(system_id))
                ], order='rating_date desc')
                
                return {
                    'status': 'success',
                    'data': [self._prepare_rating_data(rating) for rating in ratings]
                }
            
            elif operation == 'list_by_rater':
                rater_id = kw.get('rater_id')
                if not rater_id:
                    return {'status': 'error', 'message': 'Parameter rater_id tidak ada'}
                
                ratings = request.env['it.system.rating'].sudo().search([
                    ('rater_id', '=', int(rater_id))
                ], order='rating_date desc')
                
                return {
                    'status': 'success',
                    'data': [self._prepare_rating_data(rating) for rating in ratings]
                }
            
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_ratings: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/it/errors', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_errors(self, **kw):
        """Mengelola operasi CRUD untuk laporan error sistem IT."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['system_id', 'name', 'description']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Field yang diperlukan tidak lengkap'}
                
                # Buat laporan error
                values = {
                    'system_id': int(kw['system_id']),
                    'name': kw['name'],
                    'description': kw['description'],
                    'severity': kw.get('severity', 'medium'),
                    'steps_to_reproduce': kw.get('steps_to_reproduce'),
                    'state': kw.get('state', 'new')
                }
                
                if kw.get('reported_by_id'):
                    values['reported_by_id'] = int(kw['reported_by_id'])
                else:
                    # Default ke user saat ini jika ada employee_id
                    if request.env.user.employee_id:
                        values['reported_by_id'] = request.env.user.employee_id.id
                
                error = request.env['it.error.report'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_error_data(error)}
            
            elif operation == 'read':
                error_id = kw.get('error_id')
                if not error_id:
                    return {'status': 'error', 'message': 'Parameter error_id tidak ada'}
                
                error = request.env['it.error.report'].sudo().browse(int(error_id))
                if not error.exists():
                    return {'status': 'error', 'message': 'Laporan error tidak ditemukan'}
                
                return {'status': 'success', 'data': self._prepare_error_data(error)}
            
            elif operation == 'update':
                error_id = kw.get('error_id')
                if not error_id:
                    return {'status': 'error', 'message': 'Parameter error_id tidak ada'}
                
                error = request.env['it.error.report'].sudo().browse(int(error_id))
                if not error.exists():
                    return {'status': 'error', 'message': 'Laporan error tidak ditemukan'}
                
                # Update nilai
                update_values = {}
                updatable_fields = [
                    'name', 'description', 'severity', 'steps_to_reproduce', 
                    'state', 'assigned_to_id', 'resolution'
                ]
                
                for field in updatable_fields:
                    if field in kw:
                        if field == 'assigned_to_id':
                            update_values[field] = int(kw[field]) if kw[field] else False
                        else:
                            update_values[field] = kw[field]
                
                # Set resolution_date jika state berubah ke resolved atau closed
                old_state = error.state
                new_state = update_values.get('state', old_state)
                
                if new_state in ['resolved', 'closed'] and old_state not in ['resolved', 'closed']:
                    update_values['resolution_date'] = fields.Datetime.now()
                
                error.write(update_values)
                return {'status': 'success', 'data': self._prepare_error_data(error)}
            
            elif operation == 'delete':
                error_id = kw.get('error_id')
                if not error_id:
                    return {'status': 'error', 'message': 'Parameter error_id tidak ada'}
                
                error = request.env['it.error.report'].sudo().browse(int(error_id))
                if not error.exists():
                    return {'status': 'error', 'message': 'Laporan error tidak ditemukan'}
                
                error.unlink()
                return {'status': 'success', 'message': 'Laporan error berhasil dihapus'}
            
            elif operation == 'list_by_system':
                system_id = kw.get('system_id')
                if not system_id:
                    return {'status': 'error', 'message': 'Parameter system_id tidak ada'}
                
                # Terapkan filter tambahan jika ada
                domain = [('system_id', '=', int(system_id))]
                
                if kw.get('state'):
                    states = kw['state'].split(',')
                    domain.append(('state', 'in', states))
                
                if kw.get('severity'):
                    severities = kw['severity'].split(',')
                    domain.append(('severity', 'in', severities))
                
                # Pagination
                page = int(kw.get('page', 1))
                limit = int(kw.get('limit', 10))
                offset = (page - 1) * limit
                
                # Sorting
                order = kw.get('order', 'reported_date desc')
                
                errors = request.env['it.error.report'].sudo().search(
                    domain, limit=limit, offset=offset, order=order
                )
                total = request.env['it.error.report'].sudo().search_count(domain)
                
                # Hitung total halaman
                total_pages = (total + limit - 1) // limit if limit > 0 else 1
                
                return {
                    'status': 'success',
                    'data': [self._prepare_error_data(error) for error in errors],
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total,
                        'total_pages': total_pages
                    }
                }
            
            elif operation == 'list_assigned':
                assigned_to_id = kw.get('assigned_to_id')
                if not assigned_to_id:
                    return {'status': 'error', 'message': 'Parameter assigned_to_id tidak ada'}
                
                domain = [('assigned_to_id', '=', int(assigned_to_id))]
                
                if kw.get('state'):
                    states = kw['state'].split(',')
                    domain.append(('state', 'in', states))
                
                errors = request.env['it.error.report'].sudo().search(
                    domain, order='reported_date desc'
                )
                
                return {
                    'status': 'success',
                    'data': [self._prepare_error_data(error) for error in errors]
                }
            
            elif operation == 'change_state':
                error_id = kw.get('error_id')
                new_state = kw.get('state')
                
                if not error_id or not new_state:
                    return {'status': 'error', 'message': 'Parameter error_id dan state diperlukan'}
                
                error = request.env['it.error.report'].sudo().browse(int(error_id))
                if not error.exists():
                    return {'status': 'error', 'message': 'Laporan error tidak ditemukan'}
                
                # Validasi state
                valid_states = ['new', 'in_progress', 'resolved', 'closed', 'reopened']
                if new_state not in valid_states:
                    return {'status': 'error', 'message': f'State tidak valid. Harus salah satu dari: {", ".join(valid_states)}'}
                
                # Update state dan resolution_date jika diperlukan
                update_vals = {'state': new_state}
                
                if new_state in ['resolved', 'closed'] and error.state not in ['resolved', 'closed']:
                    update_vals['resolution_date'] = fields.Datetime.now()
                
                if new_state == 'reopened':
                    update_vals['resolution_date'] = False
                
                error.write(update_vals)
                return {'status': 'success', 'data': self._prepare_error_data(error)}
            
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_errors: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kpi/it', type='json', auth='user', methods=['POST'], csrf=False)
    def get_it_kpi(self, **kw):
        """Mendapatkan data KPI untuk Tim IT berdasarkan aktivitas project dan sistem."""
        try:
            # Ekstrak parameter
            employee_id = kw.get('employee_id')
            if not employee_id:
                return {'status': 'error', 'message': 'Employee ID diperlukan'}
            
            # Dapatkan dan validasi bulan/tahun
            current_date = datetime.now()
            month = int(kw.get('month', current_date.month))
            year = int(kw.get('year', current_date.year))
            
            # Validasi rentang
            if not (1 <= month <= 12):
                return {'status': 'error', 'message': 'Bulan harus antara 1 dan 12'}
            if year < 2000 or year > 2100:
                return {'status': 'error', 'message': 'Tahun tidak valid'}
            
            # Dapatkan karyawan
            employee = request.env['hr.employee'].sudo().browse(int(employee_id))
            if not employee.exists():
                return {'status': 'error', 'message': 'Karyawan tidak ditemukan'}
            
            # Definisikan timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Hitung rentang tanggal dalam timezone lokal
            start_date = datetime(year, month, 1)
            
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(days=1)
            
            start_date = start_date.replace(hour=0, minute=0, second=0)
            end_date = end_date.replace(hour=23, minute=59, second=59)
            
            # Konversi ke UTC untuk query database
            start_date_utc = tz.localize(start_date).astimezone(pytz.UTC)
            end_date_utc = tz.localize(end_date).astimezone(pytz.UTC)
            
            # Definisikan template KPI untuk Tim IT
            kpi_template = [
                {
                    'no': 1,
                    'name': '% jumlah dari keberhasilan inisiasi yang dilakukan sesuai rencana setiap bulan',
                    'type': 'project_completion',
                    'weight': 20,
                    'target': 80,
                    'measurement': 'Dari Project',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': 'Rating kepuasan survey layanan IT memberikan nilai 4 dari 5',
                    'type': 'service_rating',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Dari Rating',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Ketepatan waktu project development yang di-assign sesuai deadline',
                    'type': 'project_timeliness',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Dari Project',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': '100% sistem yang dibentuk didokumentasi dan disosialisakan untuk tata cara penggunaannya',
                    'type': 'system_documentation',
                    'weight': 20,
                    'target': 100,
                    'measurement': 'Jumlah sosialisasi / jumlah sistem yang dibentuk',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': 'Sistem yang dibentuk berjalan tanpa error setelah 1 bulan',
                    'type': 'system_reliability',
                    'weight': 20,
                    'target': 80,
                    'measurement': 'Dari IT Report System',
                    'include_in_calculation': True
                }
            ]
            
            # Hitung skor KPI
            kpi_scores = []
            
            # Nilai target 
            monthly_project_target = 5  # Target jumlah proyek per bulan
            
            # Loop melalui template KPI dan isi dengan data aktual
            for kpi in kpi_template:
                actual = 0
                
                # KPI #1: Penyelesaian inisiasi proyek
                if kpi['type'] == 'project_completion':
                    # Cari proyek IT development yang berakhir dalam periode ini
                    project_domain = [
                        ('department_id.name', 'ilike', 'IT'),
                        ('project_type', '=', 'development'),
                        ('date_end', '>=', start_date.strftime('%Y-%m-%d')),
                        ('date_end', '<=', end_date.strftime('%Y-%m-%d')),
                        '|',
                        ('project_manager_id', '=', int(employee_id)),
                        ('team_ids', 'in', [int(employee_id)])
                    ]
                    
                    all_projects = request.env['team.project'].sudo().search(project_domain)
                    completed_projects = all_projects.filtered(lambda p: p.state == 'completed')
                    
                    total_projects = len(all_projects)
                    completed_count = len(completed_projects)
                    
                    if total_projects > 0:
                        actual = (completed_count / total_projects) * 100
                    else:
                        actual = 100  # Jika tidak ada proyek, dianggap 100% selesai
                    
                    kpi['measurement'] = f"Proyek selesai: {completed_count} dari {total_projects} ({actual:.1f}%)"
                
                # KPI #2: Rating layanan IT
                elif kpi['type'] == 'service_rating':
                    # Ambil semua rating sistem dalam periode ini
                    rating_domain = [
                        ('rating_date', '>=', start_date.strftime('%Y-%m-%d')),
                        ('rating_date', '<=', end_date.strftime('%Y-%m-%d'))
                    ]
                    
                    ratings = request.env['it.system.rating'].sudo().search(rating_domain)
                    
                    # Hitung rating rata-rata
                    if ratings:
                        avg_rating = sum(rating.rating_value for rating in ratings) / len(ratings)
                        
                        # Formula khusus untuk rating
                        if avg_rating >= 4.5:
                            actual = 120  # > 4.5 = 120%
                        elif avg_rating >= 4.0:
                            actual = 100  # 4.0-4.4 = 100%
                        elif avg_rating >= 3.0:
                            actual = 50   # 3.0-3.9 = 50%
                        else:
                            actual = 0    # < 3.0 = 0%
                        
                        kpi['measurement'] = f"Rating rata-rata: {avg_rating:.1f}/5.0 ({actual:.1f}%)"
                    else:
                        actual = 0
                        kpi['measurement'] = "Belum ada rating dalam periode ini"
                
                # KPI #3: Ketepatan waktu project IT development
                elif kpi['type'] == 'project_timeliness':
                    # Cari proyek IT development yang selesai dalam periode ini
                    project_domain = [
                        ('department_id.name', 'ilike', 'IT'),
                        ('project_type', '=', 'development'),
                        ('state', '=', 'completed'),
                        '|',
                        ('actual_date_end', '>=', start_date.strftime('%Y-%m-%d')),
                        ('actual_date_end', '<=', end_date.strftime('%Y-%m-%d')),
                        '|',
                        ('project_manager_id', '=', int(employee_id)),
                        ('team_ids', 'in', [int(employee_id)])
                    ]
                    
                    completed_projects = request.env['team.project'].sudo().search(project_domain)
                    
                    # Hitung proyek yang selesai tepat waktu
                    on_time_projects = completed_projects.filtered(lambda p: hasattr(p, 'is_on_time') and p.is_on_time)
                    
                    total_completed = len(completed_projects)
                    on_time_count = len(on_time_projects)
                    
                    if total_completed > 0:
                        actual = (on_time_count / total_completed) * 100
                    else:
                        actual = 100  # Jika tidak ada proyek selesai, dianggap 100% tepat waktu
                    
                    kpi['measurement'] = f"Proyek tepat waktu: {on_time_count} dari {total_completed} ({actual:.1f}%)"
                
                # KPI #4: Dokumentasi dan sosialisasi sistem
                elif kpi['type'] == 'system_documentation':
                    # Cari sistem yang dibuat dalam periode ini
                    system_domain = [
                        ('creation_date', '>=', start_date.strftime('%Y-%m-%d')),
                        ('creation_date', '<=', end_date.strftime('%Y-%m-%d'))
                    ]
                    
                    new_systems = request.env['it.system'].sudo().search(system_domain)
                    total_systems = len(new_systems)
                    
                    # Sistem yang terdokumentasi dan tersosialisasi
                    documented_systems = new_systems.filtered(lambda s: s.documentation_complete)
                    socialized_systems = new_systems.filtered(lambda s: s.socialization_complete)
                    fully_compliant_systems = new_systems.filtered(
                        lambda s: s.documentation_complete and s.socialization_complete
                    )
                    
                    if total_systems > 0:
                        actual = (len(fully_compliant_systems) / total_systems) * 100
                    else:
                        actual = 100  # Jika tidak ada sistem baru, dianggap 100% compliant
                    
                    kpi['measurement'] = f"Sistem terdokumentasi & tersosialisasi: {len(fully_compliant_systems)} " \
                                       f"dari {total_systems} ({actual:.1f}%)"
                
                # KPI #5: Keandalan sistem (tanpa error)
                elif kpi['type'] == 'system_reliability':
                    # Cari sistem yang diluncurkan lebih dari 1 bulan yang lalu
                    prev_month_end = start_date - timedelta(days=1)
                    prev_month_start = prev_month_end.replace(day=1)
                    
                    # Ambil sistem yang diluncurkan pada bulan sebelumnya
                    system_domain = [
                        ('launch_date', '>=', prev_month_start.strftime('%Y-%m-%d')),
                        ('launch_date', '<=', prev_month_end.strftime('%Y-%m-%d')),
                        ('state', 'in', ['production', 'maintenance'])  # Hanya sistem yang aktif
                    ]
                    
                    launched_systems = request.env['it.system'].sudo().search(system_domain)
                    total_launched = len(launched_systems)
                    
                    if total_launched > 0:
                        # Cari sistem tanpa error dalam periode saat ini
                        error_free_systems = []
                        for system in launched_systems:
                            error_count = request.env['it.error.report'].sudo().search_count([
                                ('system_id', '=', system.id),
                                ('reported_date', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                                ('reported_date', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                                ('severity', 'in', ['critical', 'high'])  # Hanya error berat
                            ])
                            if error_count == 0:
                                error_free_systems.append(system.id)
                        
                        error_free_count = len(error_free_systems)
                        actual = (error_free_count / total_launched) * 100
                        
                        kpi['measurement'] = f"Sistem tanpa error: {error_free_count} dari {total_launched} ({actual:.1f}%)"
                    else:
                        actual = 100  # Jika tidak ada sistem diluncurkan, dianggap 100% reliable
                        kpi['measurement'] = "Tidak ada sistem baru yang diluncurkan pada bulan sebelumnya"

                # Hitung skor tertimbang
                weighted_score = (actual / kpi['target']) * kpi['weight']
                if actual > kpi['target']:  # Cap pada 100% pencapaian
                    weighted_score = kpi['weight']
                
                # Tambahkan ke skor KPI
                kpi_scores.append({
                    'no': kpi['no'],
                    'name': kpi['name'],
                    'type': kpi['type'],
                    'weight': kpi['weight'],
                    'target': kpi['target'],
                    'measurement': kpi['measurement'],
                    'actual': actual,
                    'achievement': min(100, (actual / kpi['target']) * 100) if kpi['target'] > 0 else 0,
                    'weighted_score': weighted_score
                })
            
            # Hitung skor total
            total_score = sum(kpi['weighted_score'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            
            # Tentukan peringkat kinerja
            performance_status = 'Tercapai' if total_score >= 89 else 'Di Bawah Target'
            
            # Format periode untuk respon
            month_names = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 
                        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
            month_display = month_names[month-1]
            
            # Bangun respon
            response = {
                'status': 'success',
                'data': {
                    'employee': {
                        'id': employee.id,
                        'name': employee.name,
                        'position': employee.job_title or "IT Staff",
                        'department': employee.department_id.name if employee.department_id else "IT Department"
                    },
                    'period': {
                        'month': month,
                        'year': year,
                        'display': f"{month_display} {year}"
                    },
                    'kpi_scores': kpi_scores,
                    'summary': {
                        'total_weight': 100,
                        'target': 89,
                        'total_score': round(total_score, 2),
                        'achievement_status': performance_status
                    }
                }
            }
            
            return response
            
        except Exception as e:
            _logger.error(f"Error di get_it_kpi: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kpi/it/export_pdf', type='http', auth='user', methods=['POST'], csrf=False)
    def export_it_kpi_pdf(self, **kw):
        """Export KPI data untuk Tim IT ke format PDF"""
        try:
            # Dapatkan dan validasi bulan/tahun
            current_date = datetime.now()
            month = int(kw.get('month', current_date.month))
            year = int(kw.get('year', current_date.year))

            # Validasi rentang
            if not (1 <= month <= 12):
                return Response('Bulan harus antara 1 dan 12', status=400)
            if year < 2000 or year > 2100:
                return Response('Tahun tidak valid', status=400)
                
            # Definisikan timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Hitung rentang tanggal dalam timezone lokal
            local_start = datetime(year, month, 1)
            if month == 12:
                local_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                local_end = datetime(year, month + 1, 1) - timedelta(days=1)
            
            local_start = local_start.replace(hour=0, minute=0, second=0)
            local_end = local_end.replace(hour=23, minute=59, second=59)
            
            start_date = tz.localize(local_start)
            end_date = tz.localize(local_end)
            
            start_date_utc = start_date.astimezone(pytz.UTC)
            end_date_utc = end_date.astimezone(pytz.UTC)

            # Format periode untuk tampilan
            month_names = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 
                        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
            month_display = month_names[month-1]
            period = f"{month_display} {year}"

            # Persiapkan data untuk laporan PDF
            it_data = []

            # Dapatkan semua karyawan Tim IT
            it_employees = request.env['hr.employee'].sudo().search([
                '|',
                '|',
                ('job_title', 'ilike', 'IT'),
                ('job_title', 'ilike', 'Sistem'),
                ('department_id.name', 'ilike', 'IT')
            ])
            
            # Debug logging
            _logger.info(f"Ditemukan {len(it_employees)} karyawan Tim IT untuk laporan KPI PDF")
            
            # Proses setiap karyawan IT
            for employee in it_employees:
                # Dapatkan data KPI dengan memanggil endpoint KPI langsung
                kpi_response = self.get_it_kpi(employee_id=employee.id, month=month, year=year)
                
                if kpi_response.get('status') == 'success' and 'data' in kpi_response:
                    employee_data = kpi_response['data']
                    it_data.append(employee_data)
                    _logger.info(f"Menambahkan karyawan ke laporan: {employee.name}, Posisi: {employee.job_title}")
                else:
                    _logger.warning(f"Tidak dapat mendapatkan data KPI untuk {employee.name}: {kpi_response.get('message', 'Kesalahan tidak diketahui')}")
            
            # Persiapkan data untuk laporan QWeb
            report_data = {
                'period': period,
                'it_members': it_data,
                'current_date': fields.Date.today().strftime('%d-%m-%Y')
            }
            
            # Coba render PDF menggunakan laporan QWeb
            try:
                # Pertama periksa apakah template ada
                template_id = request.env['ir.ui.view'].sudo().search([
                    ('key', '=', 'pitcar_custom.report_it_kpi')
                ], limit=1)
                
                if not template_id:
                    _logger.error("Template QWeb 'pitcar_custom.report_it_kpi' tidak ditemukan")
                    return Response("Error: Template QWeb 'pitcar_custom.report_it_kpi' tidak ditemukan", status=404)
                
                # Render PDF menggunakan laporan QWeb
                html = request.env['ir.qweb']._render('pitcar_custom.report_it_kpi', report_data)
                pdf_content = request.env['ir.actions.report']._run_wkhtmltopdf(
                    [html],
                    header=b'', footer=b'',
                    landscape=True,
                    specific_paperformat_args={
                        'data-report-margin-top': 10,
                        'data-report-margin-bottom': 10,
                        'data-report-margin-left': 5,
                        'data-report-margin-right': 5,
                    }
                )

                # Persiapkan nama file
                filename = f"IT_KPI_{month}_{year}.pdf"
                
                # Kembalikan respon PDF
                return Response(
                    pdf_content,
                    headers={
                        'Content-Type': 'application/pdf',
                        'Content-Disposition': f'attachment; filename="{filename}"',
                        'Content-Length': len(pdf_content),
                    },
                    status=200
                )
            except Exception as template_error:
                _logger.error(f"Error rendering template QWeb: {str(template_error)}", exc_info=True)
                return Response(f"Error rendering template laporan: {str(template_error)}", status=500)
        
        except Exception as e:
            _logger.error(f"Error mengekspor KPI IT ke PDF: {str(e)}", exc_info=True)
            return Response(f"Error: {str(e)}", status=500)

    @http.route('/web/v2/it/statistics', type='json', auth='user', methods=['POST'], csrf=False)
    def get_it_statistics(self, **kw):
        """Mendapatkan statistik IT berdasarkan periode."""
        try:
            # Set periode default ke bulan/tahun saat ini
            current_date = datetime.now()
            month = int(kw.get('month', current_date.month))
            year = int(kw.get('year', current_date.year))
            
            # Definisikan timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Hitung rentang tanggal dalam timezone lokal
            start_date = datetime(year, month, 1)
            
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(days=1)
            
            start_date = start_date.replace(hour=0, minute=0, second=0)
            end_date = end_date.replace(hour=23, minute=59, second=59)
            
            # Konversi ke UTC untuk query database
            start_date_utc = tz.localize(start_date).astimezone(pytz.UTC)
            end_date_utc = tz.localize(end_date).astimezone(pytz.UTC)
            
            # Filter untuk proyek dalam periode yang ditentukan
            project_domain = [
                ('department_id.name', 'ilike', 'IT'),
                ('project_type', '=', 'development'),
                ('date_start', '>=', start_date.strftime('%Y-%m-%d')),
                ('date_end', '<=', end_date.strftime('%Y-%m-%d')),
            ]
            
            # Query proyek
            projects = request.env['team.project'].sudo().search(project_domain)
            
            # Filter untuk sistem dalam periode yang ditentukan
            system_domain = [
                ('creation_date', '>=', start_date.strftime('%Y-%m-%d')),
                ('creation_date', '<=', end_date.strftime('%Y-%m-%d')),
            ]
            
            # Query sistem
            systems = request.env['it.system'].sudo().search(system_domain)
            
            # Filter untuk error dalam periode yang ditentukan
            error_domain = [
                ('reported_date', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('reported_date', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
            ]
            
            # Query error
            errors = request.env['it.error.report'].sudo().search(error_domain)
            
            # Filter untuk rating dalam periode yang ditentukan
            rating_domain = [
                ('rating_date', '>=', start_date.strftime('%Y-%m-%d')),
                ('rating_date', '<=', end_date.strftime('%Y-%m-%d')),
            ]
            
            # Query rating
            ratings = request.env['it.system.rating'].sudo().search(rating_domain)
            
            # Siapkan statistik
            total_projects = len(projects)
            total_systems = len(systems)
            total_errors = len(errors)
            total_ratings = len(ratings)
            
            # Proyek yang selesai
            completed_projects = len(projects.filtered(lambda p: p.state == 'completed'))
            
            # Proyek yang tepat waktu (jika field is_on_time tersedia)
            on_time_projects = len(projects.filtered(lambda p: p.state == 'completed' and hasattr(p, 'is_on_time') and p.is_on_time))
            
            # Sistem yang terdokumentasi dan tersosialisasi
            documented_systems = len(systems.filtered(lambda s: s.documentation_complete))
            socialized_systems = len(systems.filtered(lambda s: s.socialization_complete))
            fully_compliant_systems = len(systems.filtered(lambda s: s.documentation_complete and s.socialization_complete))
            
            # Distribusi error berdasarkan severity
            critical_errors = len(errors.filtered(lambda e: e.severity == 'critical'))
            high_errors = len(errors.filtered(lambda e: e.severity == 'high'))
            medium_errors = len(errors.filtered(lambda e: e.severity == 'medium'))
            low_errors = len(errors.filtered(lambda e: e.severity == 'low'))
            
            # Error yang terselesaikan
            resolved_errors = len(errors.filtered(lambda e: e.state in ['resolved', 'closed']))
            
            # Rata-rata rating
            avg_rating = sum(rating.rating_value for rating in ratings) / len(ratings) if ratings else 0.0
            
            # Format bulan untuk tampilan
            month_names = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 
                        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
            month_display = month_names[month-1]
            
            # Siapkan respon
            response = {
                'period': {
                    'month': month,
                    'year': year,
                    'display': f"{month_display} {year}"
                },
                'statistics': {
                    'projects': {
                        'total': total_projects,
                        'completed': completed_projects,
                        'completion_rate': (completed_projects / total_projects * 100) if total_projects else 0.0,
                        'on_time': on_time_projects,
                        'on_time_rate': (on_time_projects / completed_projects * 100) if completed_projects else 0.0
                    },
                    'systems': {
                        'total': total_systems,
                        'documented': documented_systems,
                        'documentation_rate': (documented_systems / total_systems * 100) if total_systems else 0.0,
                        'socialized': socialized_systems,
                        'socialization_rate': (socialized_systems / total_systems * 100) if total_systems else 0.0,
                        'fully_compliant': fully_compliant_systems,
                        'compliance_rate': (fully_compliant_systems / total_systems * 100) if total_systems else 0.0
                    },
                    'errors': {
                        'total': total_errors,
                        'by_severity': {
                            'critical': critical_errors,
                            'high': high_errors,
                            'medium': medium_errors,
                            'low': low_errors
                        },
                        'resolved': resolved_errors,
                        'resolution_rate': (resolved_errors / total_errors * 100) if total_errors else 0.0
                    },
                    'ratings': {
                        'total': total_ratings,
                        'average': round(avg_rating, 1),
                        'distribution': {
                            '5': len([r for r in ratings if r.rating_value >= 4.5]),
                            '4': len([r for r in ratings if 3.5 <= r.rating_value < 4.5]),
                            '3': len([r for r in ratings if 2.5 <= r.rating_value < 3.5]),
                            '2': len([r for r in ratings if 1.5 <= r.rating_value < 2.5]),
                            '1': len([r for r in ratings if r.rating_value < 1.5])
                        }
                    }
                }
            }
            
            return {'status': 'success', 'data': response}
            
        except Exception as e:
            _logger.error(f"Error di get_it_statistics: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    @http.route('/web/v2/it/dashboard', type='json', auth='user', methods=['POST'], csrf=False)
    def get_it_dashboard(self, **kw):
        """Mendapatkan data dashboard untuk sistem IT."""
        try:
            # Data untuk dashboard dibagi menjadi beberapa bagian:
            # 1. Overview: Jumlah sistem, proyek, error, rating rata-rata
            # 2. Sistem: Distribusi sistem berdasarkan status
            # 3. Proyek: Status proyek, proyek yang akan datang
            # 4. Error: Distribusi error, error yang perlu ditangani
            # 5. Rating: Trend rating dalam 6 bulan terakhir
            
            # --- 1. Overview ---
            total_systems = request.env['it.system'].sudo().search_count([])
            total_projects = request.env['team.project'].sudo().search_count([
                ('department_id.name', 'ilike', 'IT'),
                ('project_type', '=', 'development')
            ])
            total_errors = request.env['it.error.report'].sudo().search_count([])
            
            # Hitung rating rata-rata
            ratings = request.env['it.system.rating'].sudo().search([])
            avg_rating = sum(r.rating_value for r in ratings) / len(ratings) if ratings else 0.0
            
            # --- 2. Sistem berdasarkan status ---
            system_by_state = {}
            system_states = ['development', 'testing', 'production', 'maintenance', 'retired']
            for state in system_states:
                count = request.env['it.system'].sudo().search_count([('state', '=', state)])
                system_by_state[state] = count
            
            # --- 3. Proyek berdasarkan status ---
            project_by_state = {}
            project_states = ['draft', 'planning', 'in_progress', 'on_hold', 'completed', 'cancelled']
            for state in project_states:
                count = request.env['team.project'].sudo().search_count([
                    ('department_id.name', 'ilike', 'IT'),
                    ('project_type', '=', 'development'),
                    ('state', '=', state)
                ])
                project_by_state[state] = count
            
            # Proyek yang akan datang (deadline dalam 30 hari ke depan)
            now = fields.Date.today()
            upcoming_deadline = now + timedelta(days=30)
            upcoming_projects = request.env['team.project'].sudo().search([
                ('department_id.name', 'ilike', 'IT'),
                ('project_type', '=', 'development'),
                ('state', 'in', ['draft', 'planning', 'in_progress']),
                ('date_end', '>=', now.strftime('%Y-%m-%d')),
                ('date_end', '<=', upcoming_deadline.strftime('%Y-%m-%d'))
            ], order='date_end asc', limit=5)
            
            upcoming_projects_data = []
            for project in upcoming_projects:
                days_left = (fields.Date.from_string(project.date_end) - now).days
                upcoming_projects_data.append({
                    'id': project.id,
                    'name': project.name,
                    'state': project.state,
                    'deadline': self._format_datetime(project.date_end),
                    'days_left': days_left,
                    'progress': project.progress,
                    'project_manager': project.project_manager_id.name
                })
            
            # --- 4. Error berdasarkan status dan severity ---
            error_by_state = {}
            error_states = ['new', 'in_progress', 'resolved', 'closed', 'reopened']
            for state in error_states:
                count = request.env['it.error.report'].sudo().search_count([('state', '=', state)])
                error_by_state[state] = count
            
            error_by_severity = {}
            error_severities = ['critical', 'high', 'medium', 'low']
            for severity in error_severities:
                count = request.env['it.error.report'].sudo().search_count([('severity', '=', severity)])
                error_by_severity[severity] = count
            
            # Error yang perlu ditangani segera (critical & high yang belum resolved)
            critical_errors = request.env['it.error.report'].sudo().search([
                ('severity', 'in', ['critical', 'high']),
                ('state', 'in', ['new', 'in_progress', 'reopened'])
            ], order='reported_date desc', limit=5)
            
            critical_errors_data = []
            for error in critical_errors:
                reported_date = fields.Datetime.from_string(error.reported_date)
                days_ago = (datetime.now() - reported_date).days
                critical_errors_data.append({
                    'id': error.id,
                    'name': error.name,
                    'system': error.system_id.name,
                    'severity': error.severity,
                    'state': error.state,
                    'reported_date': self._format_datetime(error.reported_date),
                    'days_ago': days_ago,
                    'assigned_to': error.assigned_to_id.name if error.assigned_to_id else False
                })
            
            # --- 5. Trend rating 6 bulan terakhir ---
            rating_trend = []
            current_date = datetime.now()
            for i in range(5, -1, -1):  # 5 bulan ke belakang sampai bulan ini
                month = (current_date.month - i) % 12 or 12  # Pastikan bulan valid (1-12)
                year = current_date.year - ((current_date.month - i - 1) // 12)  # Kurangi tahun jika bulan < 0
                
                month_start = datetime(year, month, 1)
                if month == 12:
                    month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = datetime(year, month + 1, 1) - timedelta(days=1)
                
                month_ratings = request.env['it.system.rating'].sudo().search([
                    ('rating_date', '>=', month_start.strftime('%Y-%m-%d')),
                    ('rating_date', '<=', month_end.strftime('%Y-%m-%d'))
                ])
                
                avg_month_rating = sum(r.rating_value for r in month_ratings) / len(month_ratings) if month_ratings else 0
                
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                month_label = f"{month_names[month-1]} {year}"
                
                rating_trend.append({
                    'month': month_label,
                    'average_rating': round(avg_month_rating, 1),
                    'count': len(month_ratings)
                })
            
            # Siapkan respon
            response = {
                'overview': {
                    'total_systems': total_systems,
                    'total_projects': total_projects,
                    'total_errors': total_errors,
                    'average_rating': round(avg_rating, 1)
                },
                'systems': {
                    'by_state': system_by_state
                },
                'projects': {
                    'by_state': project_by_state,
                    'upcoming': upcoming_projects_data
                },
                'errors': {
                    'by_state': error_by_state,
                    'by_severity': error_by_severity,
                    'critical': critical_errors_data
                },
                'ratings': {
                    'trend': rating_trend
                }
            }
            
            return {'status': 'success', 'data': response}
            
        except Exception as e:
            _logger.error(f"Error di get_it_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/it/projects', type='json', auth='user', methods=['POST'], csrf=False)
    def list_it_projects(self, **kw):
        """Mendapatkan daftar proyek IT dengan filter dan pagination."""
        try:
            domain = [
                ('department_id.name', 'ilike', 'IT'),
                ('project_type', '=', 'development')
            ]
            
            # Terapkan filter
            if kw.get('state'):
                states = kw['state'].split(',')
                domain.append(('state', 'in', states))
            
            if kw.get('project_manager_id'):
                domain.append(('project_manager_id', '=', int(kw['project_manager_id'])))
            
            # Filter untuk proyek yang memiliki Tim IT
            if kw.get('team_member_id'):
                domain.append(('team_ids', 'in', [int(kw['team_member_id'])]))
            
            # Filter pencarian
            if kw.get('search'):
                domain.append('|')
                domain.append(('name', 'ilike', kw['search']))
                domain.append(('code', 'ilike', kw['search']))
            
            # Filter rentang tanggal
            if kw.get('date_start') and kw.get('date_end'):
                domain.append('|')
                domain.append('&')
                domain.append(('date_start', '<=', kw['date_end']))
                domain.append(('date_end', '>=', kw['date_start']))
                domain.append('&')
                domain.append(('date_start', '<=', kw['date_end']))
                domain.append(('date_end', '=', False))
            elif kw.get('date_start'):
                domain.append(('date_end', '>=', kw['date_start']))
            elif kw.get('date_end'):
                domain.append(('date_start', '<=', kw['date_end']))
            
            # Pagination
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 10))
            offset = (page - 1) * limit
            
            # Sorting
            sort_field = kw.get('sort_field', 'date_start')
            sort_order = kw.get('sort_order', 'desc')
            order = f"{sort_field} {sort_order}"
            
            # Ambil data
            projects = request.env['team.project'].sudo().search(
                domain, limit=limit, offset=offset, order=order
            )
            total = request.env['team.project'].sudo().search_count(domain)
            
            # Hitung total halaman
            total_pages = (total + limit - 1) // limit if limit > 0 else 1
            
            # Siapkan data proyek untuk respon
            project_data = []
            for project in projects:
                project_info = {
                    'id': project.id,
                    'name': project.name,
                    'code': project.code,
                    'state': project.state,
                    'date_start': self._format_datetime(project.date_start),
                    'date_end': self._format_datetime(project.date_end),
                    'actual_date_end': self._format_datetime(project.actual_date_end) if hasattr(project, 'actual_date_end') else False,
                    'is_on_time': project.is_on_time if hasattr(project, 'is_on_time') else False,
                    'progress': project.progress,
                    'project_manager': {
                        'id': project.project_manager_id.id,
                        'name': project.project_manager_id.name
                    },
                    'team_count': len(project.team_ids),
                    'task_count': len(project.task_ids),
                    'create_date': self._format_datetime(project.create_date)
                }
                
                # Cek jika ada sistem IT terkait
                related_system = request.env['it.system'].sudo().search([
                    ('project_id', '=', project.id)
                ], limit=1)
                
                if related_system:
                    project_info['related_system'] = {
                        'id': related_system.id,
                        'name': related_system.name,
                        'state': related_system.state
                    }
                
                project_data.append(project_info)
            
            return {
                'status': 'success',
                'data': project_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'total_pages': total_pages
                }
            }
            
        except Exception as e:
            _logger.error(f"Error di list_it_projects: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/it/attachments', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_attachments(self, **kw):
        """Mengelola attachment untuk sistem atau fitur."""
        try:
            operation = kw.get('operation', 'list')
            model = kw.get('model')  # 'it.system' atau 'it.system.feature'
            record_id = kw.get('record_id')
            
            if not model or not record_id:
                return {'status': 'error', 'message': 'Parameter model dan record_id diperlukan'}
            
            record = request.env[model].sudo().browse(int(record_id))
            if not record.exists():
                return {'status': 'error', 'message': f'Record {model} dengan ID {record_id} tidak ditemukan'}
            
            if operation == 'list':
                # Buat query untuk mendapatkan semua attachment untuk record tersebut
                if model == 'it.system':
                    attachments = record.document_attachment_ids
                elif model == 'it.system.feature':
                    attachments = record.document_attachment_ids
                else:
                    return {'status': 'error', 'message': f'Model {model} tidak didukung'}
                
                attachment_data = []
                for attachment in attachments:
                    attachment_data.append({
                        'id': attachment.id,
                        'name': attachment.name,
                        'mimetype': attachment.mimetype,
                        'file_size': attachment.file_size,
                        'url': f'/web/content/{attachment.id}?download=true',
                        'create_date': self._format_datetime(attachment.create_date)
                    })
                
                return {'status': 'success', 'data': attachment_data}
            
            elif operation == 'add':
                attachment_id = kw.get('attachment_id')
                if not attachment_id:
                    return {'status': 'error', 'message': 'Parameter attachment_id diperlukan'}
                    
                attachment = request.env['ir.attachment'].sudo().browse(int(attachment_id))
                if not attachment.exists():
                    return {'status': 'error', 'message': 'Attachment tidak ditemukan'}
                
                if model == 'it.system':
                    record.write({'document_attachment_ids': [(4, attachment.id)]})
                elif model == 'it.system.feature':
                    record.write({'document_attachment_ids': [(4, attachment.id)]})
                
                return {'status': 'success', 'message': 'Attachment berhasil ditambahkan'}
                
            elif operation == 'remove':
                attachment_id = kw.get('attachment_id')
                if not attachment_id:
                    return {'status': 'error', 'message': 'Parameter attachment_id diperlukan'}
                    
                attachment = request.env['ir.attachment'].sudo().browse(int(attachment_id))
                if not attachment.exists():
                    return {'status': 'error', 'message': 'Attachment tidak ditemukan'}
                
                if model == 'it.system':
                    record.write({'document_attachment_ids': [(3, attachment.id)]})
                elif model == 'it.system.feature':
                    record.write({'document_attachment_ids': [(3, attachment.id)]})
                
                return {'status': 'success', 'message': 'Attachment berhasil dihapus dari record'}
                
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_attachments: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/it/upload_attachment', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_attachment(self, **kw):
        """Upload attachment untuk sistem atau fitur."""
        try:
            model = kw.get('model')  # 'it.system' atau 'it.system.feature'
            record_id = kw.get('record_id')
            description = kw.get('description', '')
            
            if not model or not record_id:
                return Response(json.dumps({
                    'status': 'error', 
                    'message': 'Parameter model dan record_id diperlukan'
                }), mimetype='application/json', status=400)
            
            # Validasi record
            record = request.env[model].sudo().browse(int(record_id))
            if not record.exists():
                return Response(json.dumps({
                    'status': 'error', 
                    'message': f'Record {model} dengan ID {record_id} tidak ditemukan'
                }), mimetype='application/json', status=404)
            
            # Dapatkan file
            if 'file' not in request.httprequest.files:
                return Response(json.dumps({
                    'status': 'error', 
                    'message': 'File tidak ditemukan dalam request'
                }), mimetype='application/json', status=400)
            
            file = request.httprequest.files['file']
            file_data = file.read()
            filename = file.filename
            
            # Create attachment
            attachment_vals = {
                'name': filename,
                'datas': base64.b64encode(file_data),
                'res_model': model,
                'res_id': int(record_id),
                'description': description,
                'type': 'binary'
            }
            
            attachment = request.env['ir.attachment'].sudo().create(attachment_vals)
            
            # Hubungkan attachment dengan record
            if model == 'it.system':
                record.write({'document_attachment_ids': [(4, attachment.id)]})
            elif model == 'it.system.feature':
                record.write({'document_attachment_ids': [(4, attachment.id)]})
            
            # Response
            return Response(json.dumps({
                'status': 'success',
                'data': {
                    'id': attachment.id,
                    'name': attachment.name,
                    'mimetype': attachment.mimetype,
                    'file_size': attachment.file_size,
                    'url': f'/web/content/{attachment.id}?download=true',
                    'create_date': self._format_datetime(attachment.create_date)
                }
            }), mimetype='application/json')
            
        except Exception as e:
            _logger.error(f"Error upload attachment: {str(e)}")
            return Response(json.dumps({
                'status': 'error',
                'message': str(e)
            }), mimetype='application/json', status=500)
        
    @http.route('/web/v2/it/maintenance', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_maintenance(self, **kw):
        """Mengelola operasi CRUD untuk maintenance log sistem IT."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['name', 'system_id', 'maintenance_type', 'scheduled_date', 
                                'scheduled_time_start', 'scheduled_time_end', 'responsible_id', 'description']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Field yang diperlukan tidak lengkap'}
                
                # Konversi nilai
                values = {
                    'name': kw['name'],
                    'system_id': int(kw['system_id']),
                    'maintenance_type': kw['maintenance_type'],
                    'scheduled_date': kw['scheduled_date'],
                    'scheduled_time_start': float(kw['scheduled_time_start']),
                    'scheduled_time_end': float(kw['scheduled_time_end']),
                    'responsible_id': int(kw['responsible_id']),
                    'description': kw['description'],
                    'status': kw.get('status', 'scheduled')
                }
                
                # Optional fields
                if kw.get('version_after'):
                    values['version_after'] = kw['version_after']
                    
                if kw.get('team_ids'):
                    if isinstance(kw['team_ids'], list):
                        values['team_ids'] = [(6, 0, [int(id) for id in kw['team_ids']])]
                        
                if kw.get('affected_features'):
                    if isinstance(kw['affected_features'], list):
                        values['affected_features'] = [(6, 0, [int(id) for id in kw['affected_features']])]
                        
                if kw.get('tag_ids'):
                    if isinstance(kw['tag_ids'], list):
                        values['tag_ids'] = [(6, 0, [int(id) for id in kw['tag_ids']])]
                
                # Create record
                maintenance = request.env['it.system.maintenance'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_maintenance_data(maintenance)}
            
            elif operation == 'read':
                maintenance_id = kw.get('maintenance_id')
                if not maintenance_id:
                    return {'status': 'error', 'message': 'Parameter maintenance_id tidak ada'}
                
                maintenance = request.env['it.system.maintenance'].sudo().browse(int(maintenance_id))
                if not maintenance.exists():
                    return {'status': 'error', 'message': 'Maintenance log tidak ditemukan'}
                
                return {'status': 'success', 'data': self._prepare_maintenance_data(maintenance)}
            
            elif operation == 'update':
                maintenance_id = kw.get('maintenance_id')
                if not maintenance_id:
                    return {'status': 'error', 'message': 'Parameter maintenance_id tidak ada'}
                
                maintenance = request.env['it.system.maintenance'].sudo().browse(int(maintenance_id))
                if not maintenance.exists():
                    return {'status': 'error', 'message': 'Maintenance log tidak ditemukan'}
                
                # Update values
                update_values = {}
                updatable_fields = [
                    'name', 'maintenance_type', 'scheduled_date', 'scheduled_time_start', 
                    'scheduled_time_end', 'responsible_id', 'description', 'status',
                    'version_after', 'notes', 'changelog', 'is_successful'
                ]
                
                for field in updatable_fields:
                    if field in kw:
                        if field in ['responsible_id']:
                            update_values[field] = int(kw[field])
                        elif field in ['scheduled_time_start', 'scheduled_time_end']:
                            update_values[field] = float(kw[field])
                        elif field in ['is_successful']:
                            update_values[field] = bool(kw[field])
                        else:
                            update_values[field] = kw[field]
                
                # Many2many fields
                if kw.get('team_ids'):
                    if isinstance(kw['team_ids'], list):
                        update_values['team_ids'] = [(6, 0, [int(id) for id in kw['team_ids']])]
                        
                if kw.get('affected_features'):
                    if isinstance(kw['affected_features'], list):
                        update_values['affected_features'] = [(6, 0, [int(id) for id in kw['affected_features']])]
                        
                if kw.get('tag_ids'):
                    if isinstance(kw['tag_ids'], list):
                        update_values['tag_ids'] = [(6, 0, [int(id) for id in kw['tag_ids']])]
                
                # Update record
                maintenance.write(update_values)
                return {'status': 'success', 'data': self._prepare_maintenance_data(maintenance)}
            
            elif operation == 'delete':
                maintenance_id = kw.get('maintenance_id')
                if not maintenance_id:
                    return {'status': 'error', 'message': 'Parameter maintenance_id tidak ada'}
                
                maintenance = request.env['it.system.maintenance'].sudo().browse(int(maintenance_id))
                if not maintenance.exists():
                    return {'status': 'error', 'message': 'Maintenance log tidak ditemukan'}
                
                maintenance.unlink()
                return {'status': 'success', 'message': 'Maintenance log berhasil dihapus'}
            
            elif operation == 'list':
                domain = []
                
                # Terapkan filter
                if kw.get('system_id'):
                    domain.append(('system_id', '=', int(kw['system_id'])))
                    
                if kw.get('status'):
                    statuses = kw['status'].split(',')
                    domain.append(('status', 'in', statuses))
                    
                if kw.get('maintenance_type'):
                    types = kw['maintenance_type'].split(',')
                    domain.append(('maintenance_type', 'in', types))
                    
                if kw.get('date_start'):
                    domain.append(('scheduled_date', '>=', kw['date_start']))
                    
                if kw.get('date_end'):
                    domain.append(('scheduled_date', '<=', kw['date_end']))
                    
                if kw.get('responsible_id'):
                    domain.append(('responsible_id', '=', int(kw['responsible_id'])))
                
                # Pagination
                page = int(kw.get('page', 1))
                limit = int(kw.get('limit', 10))
                offset = (page - 1) * limit
                
                # Sorting
                order = kw.get('order', 'scheduled_date desc, id desc')
                
                # Ambil data
                maintenance_logs = request.env['it.system.maintenance'].sudo().search(
                    domain, limit=limit, offset=offset, order=order
                )
                total = request.env['it.system.maintenance'].sudo().search_count(domain)
                
                # Siapkan response
                result = {
                    'status': 'success',
                    'data': [self._prepare_maintenance_data(log) for log in maintenance_logs],
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total,
                        'total_pages': (total + limit - 1) // limit if limit else 1
                    }
                }
                
                return result
                
            elif operation == 'change_status':
                maintenance_id = kw.get('maintenance_id')
                new_status = kw.get('status')
                
                if not maintenance_id or not new_status:
                    return {'status': 'error', 'message': 'Parameter maintenance_id dan status diperlukan'}
                
                maintenance = request.env['it.system.maintenance'].sudo().browse(int(maintenance_id))
                if not maintenance.exists():
                    return {'status': 'error', 'message': 'Maintenance log tidak ditemukan'}
                
                # Validasi status
                valid_statuses = ['scheduled', 'in_progress', 'completed', 'cancelled']
                if new_status not in valid_statuses:
                    return {'status': 'error', 'message': f'Status tidak valid. Harus salah satu dari: {", ".join(valid_statuses)}'}
                
                # Update status
                if new_status == 'in_progress':
                    maintenance.action_start()
                elif new_status == 'completed':
                    maintenance.action_complete()
                elif new_status == 'cancelled':
                    maintenance.action_cancel()
                else:
                    maintenance.write({'status': new_status})
                
                return {'status': 'success', 'data': self._prepare_maintenance_data(maintenance)}
                
            elif operation == 'get_tags':
                # Ambil semua tags
                tags = request.env['it.maintenance.tag'].sudo().search([])
                tags_data = [{'id': tag.id, 'name': tag.name, 'color': tag.color} for tag in tags]
                return {'status': 'success', 'data': tags_data}
            
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_maintenance: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    def _prepare_maintenance_data(self, maintenance):
        """Siapkan data maintenance untuk respon API."""
        # Convert float time to string format (HH:MM)
        def float_to_time(float_time):
            hours = int(float_time)
            minutes = int((float_time - hours) * 60)
            return f"{hours:02d}:{minutes:02d}"
        
        # Base data
        data = {
            'id': maintenance.id,
            'name': maintenance.name,
            'system_id': maintenance.system_id.id,
            'system_name': maintenance.system_id.name,
            'maintenance_type': maintenance.maintenance_type,
            'scheduled_date': self._format_datetime(maintenance.scheduled_date),
            'scheduled_time_start': float_to_time(maintenance.scheduled_time_start),
            'scheduled_time_end': float_to_time(maintenance.scheduled_time_end),
            'status': maintenance.status,
            'description': maintenance.description,
            'responsible_id': maintenance.responsible_id.id,
            'responsible_name': maintenance.responsible_id.name,
            'version_before': maintenance.version_before,
            'version_after': maintenance.version_after or '',
            'notes': maintenance.notes or '',
            'changelog': maintenance.changelog or '',
            'is_successful': maintenance.is_successful,
            'actual_downtime': maintenance.actual_downtime,
            'downtime_exceeded': maintenance.downtime_exceeded
        }
        
        # Add team members
        data['team_members'] = []
        for employee in maintenance.team_ids:
            data['team_members'].append({
                'id': employee.id,
                'name': employee.name
            })
        
        # Add affected features
        data['affected_features'] = []
        for feature in maintenance.affected_features:
            data['affected_features'].append({
                'id': feature.id,
                'name': feature.name
            })
        
        # Add tags
        data['tags'] = []
        for tag in maintenance.tag_ids:
            data['tags'].append({
                'id': tag.id,
                'name': tag.name,
                'color': tag.color
            })
        
        # Add actual times if present
        if maintenance.actual_start_time:
            data['actual_start_time'] = self._format_datetime(maintenance.actual_start_time)
        if maintenance.actual_end_time:
            data['actual_end_time'] = self._format_datetime(maintenance.actual_end_time)
        
        return data
    
    @http.route('/web/v2/it/version_history', type='json', auth='user', methods=['POST'], csrf=False)
    def get_version_history(self, **kw):
        """Mendapatkan riwayat versi sistem IT."""
        try:
            system_id = kw.get('system_id')
            if not system_id:
                return {'status': 'error', 'message': 'Parameter system_id diperlukan'}
            
            # Get version history
            history = request.env['it.system.version.history'].sudo().search([
                ('system_id', '=', int(system_id))
            ], order='change_date desc')
            
            # Prepare response
            history_data = []
            for record in history:
                history_data.append({
                    'id': record.id,
                    'previous_version': record.previous_version,
                    'new_version': record.new_version,
                    'change_date': self._format_datetime(record.change_date),
                    'changed_by': record.changed_by_id.name,
                    'maintenance_id': record.maintenance_id.id if record.maintenance_id else None,
                    'maintenance_name': record.maintenance_id.name if record.maintenance_id else None,
                    'changelog': record.changelog or ''
                })
            
            return {'status': 'success', 'data': history_data}
            
        except Exception as e:
            _logger.error(f"Error di get_version_history: {str(e)}")
            return {'status': 'error', 'message': str(e)}