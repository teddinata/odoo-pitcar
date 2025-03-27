# controllers/kaizen_training_api.py
from odoo import http, fields
from odoo.http import request
import json
import logging
import pytz
import datetime
from datetime import datetime, timedelta
import base64

_logger = logging.getLogger(__name__)

class KaizenTrainingAPI(http.Controller):
    def _format_datetime_jakarta(self, dt):
        """Format datetime ke timezone Jakarta dengan penanganan error yang tepat."""
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
            
            # Define Jakarta timezone
            jakarta_tz = pytz.timezone('Asia/Jakarta')
            
            # Konversi ke timezone Jakarta (hanya untuk objek datetime)
            if hasattr(dt, 'hour'):  # Ini adalah datetime, bukan date
                try:
                    dt_utc = pytz.utc.localize(dt) if not hasattr(dt, 'tzinfo') or dt.tzinfo is None else dt
                    dt_jakarta = dt_utc.astimezone(jakarta_tz)
                    return fields.Datetime.to_string(dt_jakarta)
                except Exception as e:
                    _logger.error(f"Error mengkonversi datetime '{dt}': {e}")
                    return str(dt)
            else:
                # Ini adalah objek date
                return fields.Date.to_string(dt) if hasattr(dt, 'day') else str(dt)
                
        except Exception as e:
            _logger.error(f"Error tak terduga di _format_datetime_jakarta: {e}")
            # Kembalikan nilai yang aman
            return str(dt) if dt else False
    
    def _prepare_training_data(self, training):
        """Siapkan data pelatihan untuk respon API."""
        return {
            'id': training.id,
            'name': training.name,
            'code': training.code,
            'description': training.description,
            'date_start': self._format_datetime_jakarta(training.date_start),
            'date_end': self._format_datetime_jakarta(training.date_end),
            'creator': {
                'id': training.creator_id.id,
                'name': training.creator_id.name
            },
            'instructor': {
                'id': training.instructor_id.id,
                'name': training.instructor_id.name
            },
            'verifier': {
                'id': training.verifier_id.id,
                'name': training.verifier_id.name
            },
            'state': training.state,
            'target_participants': training.target_participants,
            'attendee_count': training.attendee_count,
            'location': training.location,
            'average_rating': round(training.average_rating, 1),
            'success_rate': round(training.success_rate, 2),
            'attendance_taken': training.attendance_taken,
            'attendance_date': self._format_datetime_jakarta(training.attendance_date) if training.attendance_date else False,
            'create_date': self._format_datetime_jakarta(training.create_date),
        }
    
    def _prepare_attendee_data(self, employee):
        """Siapkan data peserta untuk respon API."""
        return {
            'id': employee.id,
            'name': employee.name,
            'department': {
                'id': employee.department_id.id if employee.department_id else False,
                'name': employee.department_id.name if employee.department_id else False
            },
            'job_title': employee.job_title,
            'work_email': employee.work_email,
            'mobile_phone': employee.mobile_phone,
        }
    
    def _prepare_rating_data(self, rating):
        """Siapkan data rating untuk respon API."""
        return {
            'id': rating.id,
            'training_id': rating.training_id.id,
            'attendee': {
                'id': rating.attendee_id.id,
                'name': rating.attendee_id.name
            },
            'rater': {
                'id': rating.rater_id.id,
                'name': rating.rater_id.name
            },
            'rating_date': self._format_datetime_jakarta(rating.rating_date),
            'rating_value': rating.rating_value,
            'content_quality_rating': rating.content_quality_rating,
            'instructor_rating': rating.instructor_rating,
            'material_rating': rating.material_rating,
            'organization_rating': rating.organization_rating,
            'notes': rating.notes
        }

    def _prepare_material_data(self, material):
        """Siapkan data materi untuk respon API."""
        return {
            'id': material.id,
            'name': material.name,
            'description': material.description,
            'material_type': material.material_type,
            'is_mandatory': material.is_mandatory,
            'attachments': [{
                'id': att.id,
                'name': att.name,
                'mimetype': att.mimetype,
                'url': f'/web/content/{att.id}?download=true'
            } for att in material.attachment_ids]
        }
    
    @http.route('/web/v2/kaizen/trainings', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_trainings(self, **kw):
        """Mengelola operasi CRUD untuk program pelatihan Kaizen."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['name', 'date_start', 'date_end', 'creator_id', 'instructor_id', 'verifier_id', 'target_participants']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Field yang diperlukan tidak lengkap'}

                # Buat program pelatihan
                values = {
                    'name': kw['name'],
                    'description': kw.get('description'),
                    'date_start': kw['date_start'],
                    'date_end': kw['date_end'],
                    'creator_id': int(kw['creator_id']),
                    'instructor_id': int(kw['instructor_id']),
                    'verifier_id': int(kw['verifier_id']),
                    'target_participants': int(kw['target_participants']),
                    'location': kw.get('location'),
                    'state': kw.get('state', 'draft')
                }

                # Tambahkan peserta jika disediakan
                if kw.get('attendee_ids'):
                    attendee_ids = kw['attendee_ids']
                    if isinstance(attendee_ids, str):
                        try:
                            attendee_ids = json.loads(attendee_ids)
                        except Exception:
                            return {'status': 'error', 'message': 'Format attendee_ids tidak valid'}
                    values['attendee_ids'] = [(6, 0, [int(id) for id in attendee_ids])]

                training = request.env['kaizen.training.program'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_training_data(training)}

            elif operation == 'read':
                training_id = kw.get('training_id')
                if not training_id:
                    return {'status': 'error', 'message': 'Parameter training_id tidak ada'}
                
                training = request.env['kaizen.training.program'].sudo().browse(int(training_id))
                if not training.exists():
                    return {'status': 'error', 'message': 'Program pelatihan tidak ditemukan'}
                
                include_details = kw.get('include_details', False)
                if isinstance(include_details, str):
                    include_details = include_details.lower() in ('true', '1', 'yes')
                
                # Siapkan data respon
                training_data = self._prepare_training_data(training)
                
                # Sertakan informasi detail jika diminta
                if include_details:
                    # Tambahkan peserta
                    training_data['attendees'] = [
                        self._prepare_attendee_data(attendee) 
                        for attendee in training.attendee_ids
                    ]
                    
                    # Tambahkan rating
                    training_data['ratings'] = [
                        self._prepare_rating_data(rating) 
                        for rating in training.rating_ids
                    ]
                    
                    # Tambahkan materi
                    training_data['materials'] = [
                        self._prepare_material_data(material) 
                        for material in training.training_material_ids
                    ]
                
                return {'status': 'success', 'data': training_data}

            elif operation == 'update':
                training_id = kw.get('training_id')
                if not training_id:
                    return {'status': 'error', 'message': 'Parameter training_id tidak ada'}
                
                training = request.env['kaizen.training.program'].sudo().browse(int(training_id))
                if not training.exists():
                    return {'status': 'error', 'message': 'Program pelatihan tidak ditemukan'}
                
                # Update nilai
                update_values = {}
                updatable_fields = [
                    'name', 'description', 'date_start', 'date_end', 
                    'instructor_id', 'verifier_id', 'target_participants', 
                    'location', 'state'
                ]
                
                for field in updatable_fields:
                    if field in kw:
                        if field in ['instructor_id', 'verifier_id']:
                            update_values[field] = int(kw[field])
                        elif field == 'target_participants':
                            update_values[field] = int(kw[field])
                        else:
                            update_values[field] = kw[field]
                
                # Update peserta jika disediakan
                if kw.get('attendee_ids'):
                    attendee_ids = kw['attendee_ids']
                    if isinstance(attendee_ids, str):
                        try:
                            attendee_ids = json.loads(attendee_ids)
                        except Exception:
                            return {'status': 'error', 'message': 'Format attendee_ids tidak valid'}
                    update_values['attendee_ids'] = [(6, 0, [int(id) for id in attendee_ids])]
                
                training.write(update_values)
                return {'status': 'success', 'data': self._prepare_training_data(training)}

            elif operation == 'delete':
                training_id = kw.get('training_id')
                if not training_id:
                    return {'status': 'error', 'message': 'Parameter training_id tidak ada'}
                
                training = request.env['kaizen.training.program'].sudo().browse(int(training_id))
                if not training.exists():
                    return {'status': 'error', 'message': 'Program pelatihan tidak ditemukan'}
                
                training.unlink()
                return {'status': 'success', 'message': 'Program pelatihan berhasil dihapus'}

            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}

        except Exception as e:
            _logger.error(f"Error di manage_trainings: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kaizen/trainings/list', type='json', auth='user', methods=['POST'], csrf=False)
    def list_trainings(self, **kw):
        """Mendapatkan daftar program pelatihan Kaizen dengan filter dan pagination."""
        try:
            domain = []
            
            # Terapkan filter
            if kw.get('creator_id'):
                domain.append(('creator_id', '=', int(kw['creator_id'])))
            
            if kw.get('instructor_id'):
                domain.append(('instructor_id', '=', int(kw['instructor_id'])))
            
            if kw.get('verifier_id'):
                domain.append(('verifier_id', '=', int(kw['verifier_id'])))
            
            if kw.get('state'):
                states = kw['state'].split(',')
                domain.append(('state', 'in', states))
            
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
            
            # Filter pencarian
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
            trainings = request.env['kaizen.training.program'].sudo().search(
                domain, limit=limit, offset=offset, order=order
            )
            total = request.env['kaizen.training.program'].sudo().search_count(domain)
            
            # Hitung total halaman
            total_pages = (total + limit - 1) // limit if limit > 0 else 1
            
            return {
                'status': 'success',
                'data': [self._prepare_training_data(training) for training in trainings],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'total_pages': total_pages
                }
            }
            
        except Exception as e:
            _logger.error(f"Error di list_trainings: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kaizen/training/attendees', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_attendees(self, **kw):
        """Mengelola peserta pelatihan."""
        try:
            operation = kw.get('operation', 'list')
            
            if not kw.get('training_id'):
                return {'status': 'error', 'message': 'Parameter training_id diperlukan'}
            
            training_id = int(kw['training_id'])
            training = request.env['kaizen.training.program'].sudo().browse(training_id)
            if not training.exists():
                return {'status': 'error', 'message': 'Program pelatihan tidak ditemukan'}
            
            if operation == 'list':
                # Ambil semua peserta
                attendees = training.attendee_ids
                
                return {
                    'status': 'success',
                    'data': [self._prepare_attendee_data(attendee) for attendee in attendees]
                }
            
            elif operation == 'add':
                # Validasi field yang diperlukan
                if not kw.get('employee_ids'):
                    return {'status': 'error', 'message': 'Parameter employee_ids diperlukan'}
                
                # Parse employee IDs
                employee_ids = kw['employee_ids']
                if isinstance(employee_ids, str):
                    try:
                        employee_ids = json.loads(employee_ids)
                    except Exception:
                        return {'status': 'error', 'message': 'Format employee_ids tidak valid'}
                
                # Tambahkan karyawan ke pelatihan
                employee_ids = [int(id) for id in employee_ids]
                current_attendees = training.attendee_ids.ids
                
                # Gabungkan peserta yang ada dengan yang baru
                all_attendees = list(set(current_attendees + employee_ids))
                
                training.write({'attendee_ids': [(6, 0, all_attendees)]})
                
                return {
                    'status': 'success',
                    'message': f'Berhasil menambahkan {len(employee_ids)} peserta',
                    'data': [self._prepare_attendee_data(attendee) for attendee in training.attendee_ids]
                }
            
            elif operation == 'remove':
                # Validasi field yang diperlukan
                if not kw.get('employee_id'):
                    return {'status': 'error', 'message': 'Parameter employee_id diperlukan'}
                
                employee_id = int(kw['employee_id'])
                
                # Hapus karyawan dari pelatihan
                training.write({'attendee_ids': [(3, employee_id)]})
                
                return {
                    'status': 'success',
                    'message': 'Peserta berhasil dihapus',
                    'data': [self._prepare_attendee_data(attendee) for attendee in training.attendee_ids]
                }
            
            elif operation == 'replace':
                # Validasi field yang diperlukan
                if not kw.get('employee_ids'):
                    return {'status': 'error', 'message': 'Parameter employee_ids diperlukan'}
                
                # Parse employee IDs
                employee_ids = kw['employee_ids']
                if isinstance(employee_ids, str):
                    try:
                        employee_ids = json.loads(employee_ids)
                    except Exception:
                        return {'status': 'error', 'message': 'Format employee_ids tidak valid'}
                
                # Ganti semua peserta
                employee_ids = [int(id) for id in employee_ids]
                training.write({'attendee_ids': [(6, 0, employee_ids)]})
                
                return {
                    'status': 'success',
                    'message': 'Daftar peserta berhasil diperbarui',
                    'data': [self._prepare_attendee_data(attendee) for attendee in training.attendee_ids]
                }
            
            elif operation == 'take_attendance':
                # Tandai absensi sebagai telah diambil
                training.write({
                    'attendance_taken': True,
                    'attendance_date': fields.Date.today()
                })
                
                return {
                    'status': 'success',
                    'message': 'Absensi berhasil diambil',
                    'data': {
                        'attendance_taken': True,
                        'attendance_date': self._format_datetime_jakarta(fields.Date.today())
                    }
                }
            
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_attendees: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kaizen/training/ratings', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_ratings(self, **kw):
        """Mengelola operasi CRUD untuk rating pelatihan."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['training_id', 'attendee_id', 'rater_id', 'rating_value']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Field yang diperlukan tidak lengkap'}
                
                # Buat rating
                values = {
                    'training_id': int(kw['training_id']),
                    'attendee_id': int(kw['attendee_id']),
                    'rater_id': int(kw['rater_id']),
                    'rating_value': float(kw['rating_value']),
                    'content_quality_rating': kw.get('content_quality_rating'),
                    'instructor_rating': kw.get('instructor_rating'),
                    'material_rating': kw.get('material_rating'),
                    'organization_rating': kw.get('organization_rating'),
                    'notes': kw.get('notes')
                }
                
                rating = request.env['kaizen.training.rating'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_rating_data(rating)}
            
            elif operation == 'read':
                if not kw.get('rating_id'):
                    return {'status': 'error', 'message': 'Parameter rating_id tidak ada'}
                
                rating = request.env['kaizen.training.rating'].sudo().browse(int(kw['rating_id']))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating tidak ditemukan'}
                
                return {'status': 'success', 'data': self._prepare_rating_data(rating)}
            
            elif operation == 'update':
                if not kw.get('rating_id'):
                    return {'status': 'error', 'message': 'Parameter rating_id tidak ada'}
                
                rating = request.env['kaizen.training.rating'].sudo().browse(int(kw['rating_id']))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating tidak ditemukan'}
                
                # Update nilai
                update_values = {}
                updatable_fields = [
                    'rating_value', 'content_quality_rating', 'instructor_rating', 
                    'material_rating', 'organization_rating', 'notes'
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
                if not kw.get('rating_id'):
                    return {'status': 'error', 'message': 'Parameter rating_id tidak ada'}
                
                rating = request.env['kaizen.training.rating'].sudo().browse(int(kw['rating_id']))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating tidak ditemukan'}
                
                rating.unlink()
                return {'status': 'success', 'message': 'Rating berhasil dihapus'}
            
            elif operation == 'list_by_training':
                if not kw.get('training_id'):
                    return {'status': 'error', 'message': 'Parameter training_id tidak ada'}
                
                ratings = request.env['kaizen.training.rating'].sudo().search([
                    ('training_id', '=', int(kw['training_id']))
                ])
                
                return {
                    'status': 'success',
                    'data': [self._prepare_rating_data(rating) for rating in ratings]
                }
            
            elif operation == 'list_by_attendee':
                if not kw.get('attendee_id'):
                    return {'status': 'error', 'message': 'Parameter attendee_id tidak ada'}
                
                ratings = request.env['kaizen.training.rating'].sudo().search([
                    ('attendee_id', '=', int(kw['attendee_id']))
                ])
                
                return {
                    'status': 'success',
                    'data': [self._prepare_rating_data(rating) for rating in ratings]
                }
            
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_ratings: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kaizen/training/materials', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_materials(self, **kw):
        """Mengelola operasi CRUD untuk materi pelatihan."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['training_id', 'name', 'material_type']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Field yang diperlukan tidak lengkap'}
                
                # Buat materi
                values = {
                    'training_id': int(kw['training_id']),
                    'name': kw['name'],
                    'description': kw.get('description'),
                    'material_type': kw['material_type'],
                    'is_mandatory': kw.get('is_mandatory', True)
                }
                
                if kw.get('sequence'):
                    values['sequence'] = int(kw['sequence'])
                
                # Buat record materi
                material = request.env['kaizen.training.material'].sudo().create(values)
                
                # Tangani attachment IDs jika disediakan
                if kw.get('attachment_ids'):
                    attachment_ids = kw['attachment_ids']
                    if isinstance(attachment_ids, str):
                        try:
                            attachment_ids = json.loads(attachment_ids)
                        except:
                            return {'status': 'error', 'message': 'Format attachment_ids tidak valid'}
                    
                    material.write({'attachment_ids': [(6, 0, [int(id) for id in attachment_ids])]})
                
                return {'status': 'success', 'data': self._prepare_material_data(material)}
            
            elif operation == 'read':
                if not kw.get('material_id'):
                    return {'status': 'error', 'message': 'Parameter material_id tidak ada'}
                
                material = request.env['kaizen.training.material'].sudo().browse(int(kw['material_id']))
                if not material.exists():
                    return {'status': 'error', 'message': 'Materi pelatihan tidak ditemukan'}
                
                return {'status': 'success', 'data': self._prepare_material_data(material)}
            
            elif operation == 'update':
                if not kw.get('material_id'):
                    return {'status': 'error', 'message': 'Parameter material_id tidak ada'}
                
                material = request.env['kaizen.training.material'].sudo().browse(int(kw['material_id']))
                if not material.exists():
                    return {'status': 'error', 'message': 'Materi pelatihan tidak ditemukan'}
                
                # Update nilai
                update_values = {}
                updatable_fields = ['name', 'description', 'material_type', 'is_mandatory', 'sequence']
                
                for field in updatable_fields:
                    if field in kw:
                        if field in ['sequence']:
                            update_values[field] = int(kw[field])
                        elif field in ['is_mandatory']:
                            is_mandatory = kw[field]
                            if isinstance(is_mandatory, str):
                                is_mandatory = is_mandatory.lower() in ('true', '1', 'yes')
                            update_values[field] = is_mandatory
                        else:
                            update_values[field] = kw[field]
                
                # Tangani attachment IDs jika disediakan
                if kw.get('attachment_ids'):
                    attachment_ids = kw['attachment_ids']
                    if isinstance(attachment_ids, str):
                        try:
                            attachment_ids = json.loads(attachment_ids)
                        except:
                            return {'status': 'error', 'message': 'Format attachment_ids tidak valid'}
                    
                    update_values['attachment_ids'] = [(6, 0, [int(id) for id in attachment_ids])]
                
                material.write(update_values)
                return {'status': 'success', 'data': self._prepare_material_data(material)}
            
            elif operation == 'delete':
                if not kw.get('material_id'):
                    return {'status': 'error', 'message': 'Parameter material_id tidak ada'}
                
                material = request.env['kaizen.training.material'].sudo().browse(int(kw['material_id']))
                if not material.exists():
                    return {'status': 'error', 'message': 'Materi pelatihan tidak ditemukan'}
                
                material.unlink()
                return {'status': 'success', 'message': 'Materi pelatihan berhasil dihapus'}
            
            elif operation == 'list':
                if not kw.get('training_id'):
                    return {'status': 'error', 'message': 'Parameter training_id tidak ada'}
                
                materials = request.env['kaizen.training.material'].sudo().search([
                    ('training_id', '=', int(kw['training_id']))
                ], order='sequence')
                
                return {
                    'status': 'success',
                    'data': [self._prepare_material_data(material) for material in materials]
                }
            
            else:
                return {'status': 'error', 'message': f'Operasi tidak dikenal: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error di manage_materials: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kaizen/training/summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_training_summary(self, **kw):
        """Mendapatkan ringkasan program pelatihan dengan metrik KPI."""
        try:
            if not kw.get('training_id'):
                return {'status': 'error', 'message': 'Parameter training_id tidak ada'}
            
            training_id = int(kw['training_id'])
            training = request.env['kaizen.training.program'].sudo().browse(training_id)
            if not training.exists():
                return {'status': 'error', 'message': 'Program pelatihan tidak ditemukan'}
            
            # Siapkan data ringkasan dasar
            summary = {
                'training': self._prepare_training_data(training),
                'metrics': {}
            }
            
            # Hitung metrik
            total_attendees = len(training.attendee_ids)
            
            # Hitung metrik rating
            ratings = training.rating_ids.mapped('rating_value')
            avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
            
            # Hitung distribusi rating
            rating_distribution = {
                '5': len([r for r in ratings if 4.5 <= r <= 5.0]),
                '4': len([r for r in ratings if 3.5 <= r < 4.5]),
                '3': len([r for r in ratings if 2.5 <= r < 3.5]),
                '2': len([r for r in ratings if 1.5 <= r < 2.5]),
                '1': len([r for r in ratings if 0.0 <= r < 1.5])
            }
            
            # Tambahkan metrik ke ringkasan
            summary['metrics'] = {
                'target_participants': training.target_participants,
                'total_attendees': total_attendees,
                'attendance_rate': (total_attendees / training.target_participants * 100) if training.target_participants else 0.0,
                'average_rating': avg_rating,
                'rating_distribution': rating_distribution,
                'ratings_count': len(ratings),
                'ratings_percentage': (len(ratings) / total_attendees * 100) if total_attendees else 0.0
            }
            
            # Siapkan data tambahan untuk perhitungan KPI
            if training.average_rating >= 4.5:
                rating_achievement = 120  # > 4.5 = 120%
            elif training.average_rating >= 4.0:
                rating_achievement = 100  # 4.0-4.4 = 100%
            elif training.average_rating >= 3.0:
                rating_achievement = 50   # 3.0-3.9 = 50%
            else:
                rating_achievement = 0    # < 3.0 = 0%
            
            # Tambahkan metrik spesifik KPI
            summary['kpi'] = {
                'rating_achievement': rating_achievement,
                'target_achievement': (total_attendees / training.target_participants * 100) if training.target_participants else 0.0
            }
            
            return {'status': 'success', 'data': summary}
            
        except Exception as e:
            _logger.error(f"Error di get_training_summary: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kaizen/training/statistics', type='json', auth='user', methods=['POST'], csrf=False)
    def get_training_statistics(self, **kw):
        """Mendapatkan statistik pelatihan keseluruhan untuk tim Kaizen."""
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
            
            # Filter untuk pelatihan dalam periode yang ditentukan
            domain = [
                ('date_start', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_end', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
            ]
            
            # Tambahkan filter creator jika ditentukan
            if kw.get('creator_id'):
                domain.append(('creator_id', '=', int(kw['creator_id'])))
            
            # Query pelatihan
            trainings = request.env['kaizen.training.program'].sudo().search(domain)
            
            # Siapkan statistik
            total_trainings = len(trainings)
            total_attendees = sum(len(training.attendee_ids) for training in trainings)
            total_target_participants = sum(training.target_participants for training in trainings)
            completed_trainings = len(trainings.filtered(lambda t: t.state == 'completed'))
            
            # Hitung rata-rata rating
            all_ratings = []
            for training in trainings:
                all_ratings.extend(training.rating_ids.mapped('rating_value'))
            
            avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 0.0
            
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
                    'total_trainings': total_trainings,
                    'completed_trainings': completed_trainings,
                    'completion_rate': (completed_trainings / total_trainings * 100) if total_trainings else 0.0,
                    'total_attendees': total_attendees,
                    'total_target_participants': total_target_participants,
                    'participants_achievement': (total_attendees / total_target_participants * 100) if total_target_participants else 0.0,
                    'average_rating': avg_rating,
                    'total_ratings': len(all_ratings)
                }
            }
            
            return {'status': 'success', 'data': response}
            
        except Exception as e:
            _logger.error(f"Error di get_training_statistics: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/kaizen/kpi', type='json', auth='user', methods=['POST'], csrf=False)
    def get_kaizen_kpi(self, **kw):
        """Mendapatkan data KPI untuk Tim Kaizen berdasarkan aktivitas pelatihan."""
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
            
            # Dapatkan data pelatihan untuk karyawan ini (sebagai pembuat atau instruktur)
            domain = [
                '|',
                ('creator_id', '=', int(employee_id)),
                ('instructor_id', '=', int(employee_id)),
                ('date_start', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_end', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
            ]
            
            trainings = request.env['kaizen.training.program'].sudo().search(domain)
            
            # Dapatkan posisi pekerjaan
            job_title = employee.job_title if employee.job_title else "Unknown"
            department = employee.department_id.name if employee.department_id else "Unknown Department"
            
            # Definisikan template KPI untuk Tim Kaizen
            kpi_template = [
                {
                    'no': 1,
                    'name': 'Jumlah dokumen SOP yang terbentuk sesuai target',
                    'type': 'sop_completion',
                    'weight': 10,
                    'target': 90,
                    'measurement': 'SOP terbentuk / target SOP',
                    'include_in_calculation': True
                },
                {
                    'no': 2,
                    'name': '% dokumentasi sampling SOP sesuai ekspektasi target sampling',
                    'type': 'sop_sampling',
                    'weight': 20,
                    'target': 90,
                    'measurement': '% SOP sesuai target / total sampling SOP',
                    'include_in_calculation': True
                },
                {
                    'no': 3,
                    'name': 'Jumlah program pengembangan kemampuan otomotif sesuai dengan target yang diumumkan',
                    'type': 'training_completion',
                    'weight': 20,
                    'target': 90,
                    'measurement': 'Jumlah aktual program / target program',
                    'include_in_calculation': True
                },
                {
                    'no': 4,
                    'name': 'Rating kepuasan training memberikan nilai 4 dari 5',
                    'type': 'training_satisfaction',
                    'weight': 20,
                    'target': 80,
                    'measurement': 'Formula khusus: > 4.5 = 120%, 4 s.d 4.5 = 100%, 3 s.d 3.9 = 50%, < 3 = 0%',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': '% permasalahan teknis yang tidak dapat diselesaikan kepala mekanik dibawah kaizen man',
                    'type': 'technical_issues',
                    'weight': 20,
                    'target': 90,
                    'measurement': '% masalah teknis yang dibantu / total masalah teknis',
                    'include_in_calculation': True
                },
                {
                    'no': 6,
                    'name': '% keberhasilan project development yang di-assign kepada kaizen-man tepat pada waktunya',
                    'type': 'project_timeliness',
                    'weight': 10,
                    'target': 100,
                    'measurement': '% project tepat waktu / total project',
                    'include_in_calculation': True
                }
            ]
            
            # Hitung skor KPI
            kpi_scores = []
            
            # Nilai target 
            monthly_training_target = 5  # Target jumlah pelatihan per bulan
            
            # Loop melalui template KPI dan isi dengan data aktual
            for kpi in kpi_template:
                actual = 0
                
                # KPI #3: Penyelesaian program pelatihan
                if kpi['type'] == 'training_completion':
                    total_trainings = len(trainings)
                    actual = (total_trainings / monthly_training_target * 100) if monthly_training_target > 0 else 0
                    kpi['measurement'] = f"Program training: {total_trainings} dari target {monthly_training_target} ({actual:.1f}%)"
                
                # KPI #4: Rating kepuasan pelatihan
                elif kpi['type'] == 'training_satisfaction':
                    # Dapatkan semua rating di semua pelatihan
                    all_ratings = []
                    for training in trainings:
                        all_ratings.extend(training.rating_ids.mapped('rating_value'))
                    
                    avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 0
                    
                    # Terapkan formula khusus
                    if avg_rating >= 4.5:
                        actual = 120  # > 4.5 = 120%
                    elif avg_rating >= 4.0:
                        actual = 100  # 4.0-4.4 = 100%
                    elif avg_rating >= 3.0:
                        actual = 50   # 3.0-3.9 = 50%
                    else:
                        actual = 0    # < 3.0 = 0%
                    
                    kpi['measurement'] = f"Rating rata-rata: {avg_rating:.1f} dari 5.0 (Pencapaian: {actual:.1f}%)"
                
                # Untuk KPI lainnya (nilai placeholder contoh untuk demonstrasi)
                else:
                    # Ini perlu diimplementasikan berdasarkan logika bisnis aktual
                    if kpi['type'] == 'sop_completion':
                        actual = 85  # Contoh placeholder
                    elif kpi['type'] == 'sop_sampling':
                        actual = 90  # Contoh placeholder
                    elif kpi['type'] == 'technical_issues':
                        actual = 95  # Contoh placeholder
                    elif kpi['type'] == 'project_timeliness':
                        actual = 100  # Contoh placeholder
                
                # Hitung skor tertimbang
                weighted_score = actual * (kpi['weight'] / 100)
                achievement = actual
                
                # Tambahkan ke skor KPI
                kpi_scores.append({
                    'no': kpi['no'],
                    'name': kpi['name'],
                    'type': kpi['type'],
                    'weight': kpi['weight'],
                    'target': kpi['target'],
                    'measurement': kpi['measurement'],
                    'actual': actual,
                    'achievement': achievement,
                    'weighted_score': weighted_score
                })
            
            # Hitung skor total
            total_score = sum(kpi['weighted_score'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            
            # Hitung bobot total
            total_weight = sum(kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True))
            
            # Hitung target rata-rata
            avg_target = sum(kpi['target'] * kpi['weight'] for kpi in kpi_scores if kpi.get('include_in_calculation', True)) / total_weight if total_weight else 0
            
            # Tentukan peringkat kinerja
            performance_status = 'Tercapai' if total_score >= avg_target else 'Di Bawah Target'
            
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
                        'position': job_title,
                        'department': department
                    },
                    'period': {
                        'month': month,
                        'year': year,
                        'display': f"{month_display} {year}"
                    },
                    'kpi_scores': kpi_scores,
                    'summary': {
                        'total_weight': total_weight,
                        'target': avg_target,
                        'total_score': round(total_score, 2),
                        'achievement_status': performance_status
                    }
                }
            }
            
            return response
            
        except Exception as e:
            _logger.error(f"Error di get_kaizen_kpi: {str(e)}")
            return {'status': 'error', 'message': str(e)}