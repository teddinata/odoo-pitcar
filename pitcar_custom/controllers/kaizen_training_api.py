# controllers/kaizen_training_api.py
from odoo import http, fields
from odoo.http import request, Response
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
    
    @http.route('/web/v2/kpi/kaizen', type='json', auth='user', methods=['POST'], csrf=False)
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
                    'name': 'Jumlah dokumen SOP yang terbentuk dan tersosialisasi sesuai target',
                    'type': 'sop_completion',
                    'weight': 20,
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
                    'weight': 10,
                    'target': 80,
                    'measurement': 'Formula khusus: > 4.5 = 120%, 4 s.d 4.5 = 100%, 3 s.d 3.9 = 50%, < 3 = 0%',
                    'include_in_calculation': True
                },
                {
                    'no': 5,
                    'name': '% permasalahan teknis yang tidak dapat diselesaikan kepala mekanik dibawah kaizen man',
                    'type': 'technical_issues',
                    'weight': 15,
                    'target': 90,
                    'measurement': '% masalah teknis yang dibantu / total masalah teknis',
                    'include_in_calculation': True
                },
                {
                    'no': 6,
                    'name': '% keberhasilan project development yang di-assign kepada kaizen-man tepat pada waktunya',
                    'type': 'project_timeliness',
                    'weight': 15,
                    'target': 100,
                    'measurement': '% project tepat waktu / total project',
                    'include_in_calculation': True
                }
            ]
            
            # Hitung skor KPI
            kpi_scores = []
            
            # Nilai target 
            monthly_training_target = 5  # Target jumlah pelatihan per bulan
            monthly_sop_creation_target = 10  # Target pembuatan SOP per bulan
            monthly_sop_sampling_target = 180  # Target sampling SOP per bulan
            
            # Loop melalui template KPI dan isi dengan data aktual
            for kpi in kpi_template:
                actual = 0
                
                # KPI #1: Penyelesaian pembuatan SOP
                # if kpi['type'] == 'sop_completion':
                #     # Cari project dengan tipe 'creation' (pembuatan)
                #     sop_creation_domain = [
                #         ('project_type', '=', 'creation'),
                #         ('date_start', '>=', start_date.strftime('%Y-%m-%d')),
                #         ('date_end', '<=', end_date.strftime('%Y-%m-%d')),
                #         # Filter untuk project yang dimiliki/diassign ke karyawan Kaizen
                #         '|',
                #         ('project_manager_id', '=', int(employee_id)),
                #         ('team_ids', 'in', [int(employee_id)])
                #     ]
                    
                #     sop_projects = request.env['team.project'].sudo().search(sop_creation_domain)
                #     total_sop_projects = len(sop_projects)
                    
                #     # Jika tidak ada project pembuatan SOP, otomatis nilai 100%
                #     if total_sop_projects == 0:
                #         actual = 100
                #         kpi['measurement'] = "Tidak ada proyek pembuatan SOP pada periode ini (nilai 100%)"
                #     else:
                #         # Hitung berapa yang selesai tepat waktu (tidak overdue)
                #         completed_on_time = 0
                #         for project in sop_projects:
                #             if project.state == 'completed' and (not project.date_end or (
                #                     project.actual_date_end and project.date_end and 
                #                     project.actual_date_end <= fields.Datetime.from_string(project.date_end))):
                #                 completed_on_time += 1
                        
                #         # Hitung persentase penyelesaian tepat waktu
                #         actual = (completed_on_time / total_sop_projects) * 100 if total_sop_projects > 0 else 100
                        
                #         kpi['measurement'] = f"SOP terbentuk: {total_sop_projects}, selesai tepat waktu: {completed_on_time} ({actual:.1f}%)"

                # KPI #1: Penyelesaian pembuatan SOP berdasarkan target sosialisasi
                if kpi['type'] == 'sop_completion':
                    # Dapatkan semua SOP yang memiliki target sosialisasi dalam periode ini
                    sop_domain = [
                        ('active', '=', True),
                        ('socialization_target_date', '>=', start_date.strftime('%Y-%m-%d')),
                        ('socialization_target_date', '<=', end_date.strftime('%Y-%m-%d'))
                    ]
                    
                    sops = request.env['pitcar.sop'].sudo().search(sop_domain)
                    total_sops = len(sops)
                    
                    # Jika tidak ada SOP dengan target sosialisasi pada periode ini, otomatis nilai 100%
                    if total_sops == 0:
                        actual = 100
                        kpi['measurement'] = "Tidak ada SOP dengan target sosialisasi pada periode ini (nilai 100%)"
                    else:
                        # Hitung berapa SOP yang berhasil disosialisasikan tepat waktu
                        on_time_socialization = 0
                        for sop in sops:
                            # SOP dianggap tepat waktu jika:
                            # 1. Status sosialisasi adalah 'done' (selesai)
                            # 2. Tanggal sosialisasi tidak melebihi tanggal target sosialisasi
                            if (sop.socialization_state == 'done' and 
                                sop.socialization_date and 
                                sop.socialization_target_date and 
                                sop.socialization_date <= sop.socialization_target_date):
                                on_time_socialization += 1
                        
                        # Hitung persentase ketepatan waktu sosialisasi
                        actual = (on_time_socialization / total_sops) * 100 if total_sops > 0 else 100
                        
                        kpi['measurement'] = f"SOP dengan target sosialisasi: {total_sops}, " \
                                            f"sosialisasi tepat waktu: {on_time_socialization} ({actual:.1f}%)"
                
                # KPI #2: Sampling SOP
                elif kpi['type'] == 'sop_sampling':
                    # Cari semua sampling SOP oleh tim Kaizen dalam periode ini
                    # Perhatikan: Kita hanya filter berdasarkan tanggal dan tipe sampling (kaizen)
                    # tanpa melakukan filter berdasarkan controller_id untuk menghitung total samplings
                    
                    # Log untuk debugging
                    _logger.info(f"Mencari sampling untuk periode: {start_date.strftime('%Y-%m-%d')} s/d {end_date.strftime('%Y-%m-%d')}")
                    
                    # Query untuk mendapatkan semua sampling oleh tim Kaizen dalam periode ini
                    all_sampling_domain = [
                        ('date', '>=', start_date.strftime('%Y-%m-%d')),
                        ('date', '<=', end_date.strftime('%Y-%m-%d')),
                        ('sampling_type', '=', 'kaizen')  # Filter untuk sampling oleh tim Kaizen
                    ]
                    
                    all_sop_samplings = request.env['pitcar.sop.sampling'].sudo().search(all_sampling_domain)
                    total_samplings = len(all_sop_samplings)
                    
                    # Log jumlah sampling yang ditemukan
                    _logger.info(f"Total sampling oleh tim Kaizen: {total_samplings}")
                    
                    # Hitung berapa SOP yang lulus sampling (dari semua sampling tim Kaizen)
                    passed_samplings = len(all_sop_samplings.filtered(lambda s: s.result == 'pass'))
                    
                    # Jika karyawan ini adalah seorang controller, kita juga ingin mengetahui 
                    # berapa sampling yang dilakukan oleh karyawan ini
                    employee_sampling_domain = [
                        ('date', '>=', start_date.strftime('%Y-%m-%d')),
                        ('date', '<=', end_date.strftime('%Y-%m-%d')),
                        ('sampling_type', '=', 'kaizen'),
                        ('controller_id', '=', int(employee_id))
                    ]
                    
                    employee_samplings = request.env['pitcar.sop.sampling'].sudo().search(employee_sampling_domain)
                    employee_sampling_count = len(employee_samplings)
                    
                    # Log jumlah sampling oleh karyawan ini
                    _logger.info(f"Sampling oleh karyawan ini: {employee_sampling_count}")
                    
                    # Hitung persentase pencapaian tim Kaizen terhadap target
                    sampling_completion = (total_samplings / monthly_sop_sampling_target * 100) if monthly_sop_sampling_target > 0 else 0
                    sampling_quality = (passed_samplings / total_samplings * 100) if total_samplings > 0 else 0
                    
                    # Combined score: 50% based on sampling count, 50% based on quality
                    actual = min(100, (sampling_completion * 0.5) + (sampling_quality * 0.5))
                    
                    # Tampilkan informasi jumlah sampling yang dilakukan oleh karyawan ini
                    # jika karyawan ini adalah controller
                    if employee_sampling_count > 0:
                        kpi['measurement'] = f"Sampling Tim Kaizen: {total_samplings} dari target {monthly_sop_sampling_target} " \
                                            f"(kontribusi: {employee_sampling_count}), " \
                                            f"lulus: {passed_samplings} ({actual:.1f}%)"
                    else:
                        kpi['measurement'] = f"Sampling Tim Kaizen: {total_samplings} dari target {monthly_sop_sampling_target}, " \
                                            f"lulus: {passed_samplings} ({actual:.1f}%)"
                
                # KPI #3: Penyelesaian program pelatihan (existing code)
                elif kpi['type'] == 'training_completion':
                    total_trainings = len(trainings)
                    actual = (total_trainings / monthly_training_target * 100) if monthly_training_target > 0 else 0
                    kpi['measurement'] = f"Program training: {total_trainings} dari target {monthly_training_target} ({actual:.1f}%)"
                
                # KPI #4: Rating kepuasan pelatihan (existing code)
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
                
                # KPI #5: Penyelesaian masalah teknis (dari mentor request)
                elif kpi['type'] == 'technical_issues':
                    # Cari mentor request dalam periode ini
                    mentor_request_domain = [
                        ('request_datetime', '>=', start_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                        ('request_datetime', '<=', end_date_utc.strftime('%Y-%m-%d %H:%M:%S')),
                        ('mentor_id', '=', int(employee_id)),  # Request yang mentor-nya adalah karyawan ini
                    ]
                    
                    mentor_requests = request.env['pitcar.mentor.request'].sudo().search(mentor_request_domain)
                    total_requests = len(mentor_requests)
                    
                    # Hitung berapa request yang terselesaikan (solved)
                    solved_requests = len(mentor_requests.filtered(lambda r: r.state == 'solved'))
                    
                    # Hitung persentase penyelesaian
                    if total_requests > 0:
                        actual = (solved_requests / total_requests) * 100
                    else:
                        actual = 100  # Jika tidak ada request, dianggap 100% selesai
                    
                    kpi['measurement'] = f"Masalah terselesaikan: {solved_requests} dari {total_requests} ({actual:.1f}%)"
                
                # KPI #6: Ketepatan waktu project development
                elif kpi['type'] == 'project_timeliness':
                    # Cari project development yang dimiliki/diassign ke karyawan Kaizen
                    project_domain = [
                        ('project_type', '=', 'development'),  # Filter untuk project pengembangan
                        ('date_start', '>=', start_date.strftime('%Y-%m-%d')),
                        ('date_end', '<=', end_date.strftime('%Y-%m-%d')),
                        '|',
                        ('project_manager_id', '=', int(employee_id)),
                        ('team_ids', 'in', [int(employee_id)]),
                        ('state', 'in', ['completed', 'cancelled'])  # Hanya project yang sudah selesai atau dibatalkan
                    ]
                    
                    projects = request.env['team.project'].sudo().search(project_domain)
                    total_projects = len(projects)
                    
                    # Hitung project yang selesai tepat waktu
                    on_time_projects = 0
                    for project in projects:
                        if project.state == 'completed':
                            # Periksa jika ada tanggal akhir aktual dan jika itu tidak melewati deadline
                            if hasattr(project, 'actual_date_end') and project.actual_date_end:
                                if project.actual_date_end <= fields.Datetime.from_string(project.date_end):
                                    on_time_projects += 1
                            # Jika tidak ada actual_date_end, gunakan state dan date_end sebagai patokan
                            elif project.date_end:
                                current_date = fields.Datetime.now()
                                if current_date <= fields.Datetime.from_string(project.date_end):
                                    on_time_projects += 1
                    
                    # Hitung persentase ketepatan waktu
                    if total_projects > 0:
                        actual = (on_time_projects / total_projects) * 100
                    else:
                        actual = 100  # Jika tidak ada project, dianggap 100% tepat waktu
                    
                    kpi['measurement'] = f"Project tepat waktu: {on_time_projects} dari {total_projects} ({actual:.1f}%)"
                
                # Hitung skor tertimbang
                weighted_score = actual * (kpi['weight'] / 100)
                achievement = weighted_score
                
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
        
    @http.route('/web/v2/kpi/kaizen/export_pdf', type='http', auth='user', methods=['POST'], csrf=False)
    def export_kaizen_kpi_pdf(self, **kw):
        """Export KPI data untuk Tim Kaizen ke format PDF"""
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
            kaizen_data = []
            processed_employee_ids = []  # Lacak karyawan yang sudah diproses

            # Dapatkan semua karyawan Tim Kaizen
            kaizen_employees = request.env['hr.employee'].sudo().search([
                '|',
                '|',
                ('job_title', 'ilike', 'Kaizen'),
                ('job_title', 'ilike', 'Trainer'),
                ('department_id.name', 'ilike', 'Kaizen')
            ])
            
            # Debug logging
            _logger.info(f"Ditemukan {len(kaizen_employees)} karyawan Tim Kaizen untuk laporan KPI PDF")
            
            # Proses setiap karyawan Kaizen
            for employee in kaizen_employees:
                # Dapatkan jabatan
                job_title = employee.job_title or "Kaizen Team"
                department = employee.department_id.name if employee.department_id else "Kaizen Department"
                
                # Dapatkan data KPI dengan memanggil endpoint KPI langsung
                kpi_response = self.get_kaizen_kpi(employee_id=employee.id, month=month, year=year)
                
                if kpi_response.get('status') == 'success' and 'data' in kpi_response:
                    employee_data = kpi_response['data']
                    kaizen_data.append(employee_data)
                    _logger.info(f"Menambahkan karyawan ke laporan: {employee.name}, Posisi: {job_title}")
                else:
                    _logger.warning(f"Tidak dapat mendapatkan data KPI untuk {employee.name}: {kpi_response.get('message', 'Kesalahan tidak diketahui')}")
            
            # Debug logging
            _logger.info(f"Total karyawan dalam laporan PDF: {len(kaizen_data)}")
            
            # Persiapkan data untuk laporan QWeb
            report_data = {
                'period': period,
                'kaizen_members': kaizen_data,
                'current_date': fields.Date.today().strftime('%d-%m-%Y')
            }
            
            # Coba render PDF menggunakan laporan QWeb
            try:
                # Pertama periksa apakah template ada
                template_id = request.env['ir.ui.view'].sudo().search([
                    ('key', '=', 'pitcar_custom.report_kaizen_kpi')
                ], limit=1)
                
                if not template_id:
                    _logger.error("Template QWeb 'pitcar_custom.report_kaizen_kpi' tidak ditemukan")
                    return Response("Error: Template QWeb 'pitcar_custom.report_kaizen_kpi' tidak ditemukan", status=404)
                
                # Render PDF menggunakan laporan QWeb
                html = request.env['ir.qweb']._render('pitcar_custom.report_kaizen_kpi', report_data)
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
                filename = f"Kaizen_KPI_{month}_{year}.pdf"
                
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
            _logger.error(f"Error mengekspor KPI Kaizen ke PDF: {str(e)}", exc_info=True)
            return Response(f"Error: {str(e)}", status=500)

    # controllers/kaizen_training_api.py - Tambahkan endpoint berikut

    @http.route('/web/v2/kaizen/trainings/public-feedback', type='json', auth='public', methods=['POST'], csrf=False)
    def get_public_training_feedback(self, **kw):
        """API publik untuk mendapatkan data pelatihan bagi peserta yang memberikan feedback."""
        try:
            # Ambil parameter dari request
            params = kw
            if 'params' in kw and isinstance(kw['params'], dict):
                params = kw['params']
            
            operation = params.get('operation', 'get_training')
            training_id = params.get('training_id')
            token = params.get('token', '')
            
            if not training_id or not token:
                return {'status': 'error', 'message': 'Missing required parameters'}
            
            # Validasi token (dalam implementasi nyata, gunakan metode yang lebih aman)
            # Contoh sederhana: token adalah base64 dari "training-{id}-feedback"
            expected_token = base64.b64encode(f"training-{training_id}-feedback".encode()).decode()
            
            if token != expected_token:
                return {'status': 'error', 'message': 'Invalid token'}
            
            if operation == 'get_training':
                # Ambil data pelatihan untuk ditampilkan di form feedback publik
                training = request.env['kaizen.training.program'].sudo().browse(int(training_id))
                
                if not training.exists():
                    return {'status': 'error', 'message': 'Training not found'}
                
                # Hanya kirim data yang diperlukan untuk form feedback
                training_data = {
                    'id': training.id,
                    'name': training.name,
                    'state': training.state,
                    'date_start': self._format_datetime_jakarta(training.date_start),
                    'date_end': self._format_datetime_jakarta(training.date_end),
                    'instructor': {
                        'id': training.instructor_id.id,
                        'name': training.instructor_id.name
                    },
                    'attendees': [
                        {
                            'id': attendee.id,
                            'name': attendee.name,
                            'department': attendee.department_id.name if attendee.department_id else None
                        }
                        for attendee in training.attendee_ids
                    ],
                    'ratings': [
                        {
                            'id': rating.id,
                            'attendee_id': rating.attendee_id.id
                        }
                        for rating in training.rating_ids
                    ]
                }
                
                return {'status': 'success', 'data': training_data}
            
            elif operation == 'get_training_summary':
                # Ambil data ringkasan pelatihan untuk halaman summary publik
                training = request.env['kaizen.training.program'].sudo().browse(int(training_id))
                
                if not training.exists():
                    return {'status': 'error', 'message': 'Training not found'}
                
                # Siapkan data detail rating
                ratings_data = []
                for rating in training.rating_ids:
                    rating_data = {
                        'id': rating.id,
                        'rating_value': rating.rating_value,
                        'content_quality_rating': rating.content_quality_rating,
                        'instructor_rating': rating.instructor_rating,
                        'material_rating': rating.material_rating,
                        'organization_rating': rating.organization_rating
                    }
                    ratings_data.append(rating_data)
                
                # Kirim data yang diperlukan untuk halaman summary
                summary_data = {
                    'id': training.id,
                    'name': training.name,
                    'date_end': self._format_datetime_jakarta(training.date_end),
                    'ratings': ratings_data
                }
                
                return {'status': 'success', 'data': summary_data}
            
            else:
                return {'status': 'error', 'message': f'Unknown operation: {operation}'}
        
        except Exception as e:
            _logger.error(f"Error in get_public_training_feedback: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # Tambahan untuk rating API - validasi token saat mengirim rating dari form publik
    @http.route('/web/v2/kaizen/training/ratings', type='json', auth='public', methods=['POST'], csrf=False)
    def manage_ratings(self, **kw):
        """Mengelola operasi CRUD untuk rating pelatihan."""
        # Ambil parameter dari request
        params = kw
        if 'params' in kw and isinstance(kw['params'], dict):
            params = kw['params']
        
        # Ambil operation dengan nilai default 'create'
        operation = params.get('operation', 'create')
        
        # Cek apakah request berasal dari form publik (ditandai dengan token)
        token = params.get('token', '')
        is_public_request = bool(token)
        
        # Jika ini request publik, validasi token
        if is_public_request:
            training_id = params.get('training_id')
            if not training_id or not token:
                return {'status': 'error', 'message': 'Missing required parameters'}
            
            # Validasi token
            expected_token = base64.b64encode(f"training-{training_id}-feedback".encode()).decode()
            if token != expected_token:
                return {'status': 'error', 'message': 'Invalid token'}
        
        # Untuk request publik yang valid atau request internal, lanjutkan dengan logika yang sudah ada
        try:
            # Lanjutkan dengan kode yang sudah ada...
            if operation == 'create':
                # Validasi field yang diperlukan
                required_fields = ['training_id', 'attendee_id', 'rater_id', 'rating_value']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}
                
                # Jika ini adalah request publik, pastikan attendee_id dan rater_id sama
                if is_public_request and kw.get('attendee_id') != kw.get('rater_id'):
                    return {'status': 'error', 'message': 'Invalid rater_id for public feedback'}
                
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
                
                # Cek apakah peserta ini sudah memberikan rating
                existing_rating = request.env['kaizen.training.rating'].sudo().search([
                    ('training_id', '=', int(kw['training_id'])),
                    ('attendee_id', '=', int(kw['attendee_id']))
                ])
                
                if existing_rating:
                    return {'status': 'error', 'message': 'Feedback sudah diberikan sebelumnya'}
                
                rating = request.env['kaizen.training.rating'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_rating_data(rating)}
            
            # Jika request publik, hanya izinkan operasi create
            if is_public_request and operation != 'create':
                return {'status': 'error', 'message': 'Operation not allowed'}
            
            # Berikut adalah operasi yang hanya diizinkan untuk pengguna internal
            elif operation == 'read':
                if not kw.get('rating_id'):
                    return {'status': 'error', 'message': 'Missing rating_id parameter'}
                
                rating = request.env['kaizen.training.rating'].sudo().browse(int(kw['rating_id']))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating not found'}
                
                return {'status': 'success', 'data': self._prepare_rating_data(rating)}
            
            elif operation == 'update':
                if not kw.get('rating_id'):
                    return {'status': 'error', 'message': 'Missing rating_id parameter'}
                
                rating = request.env['kaizen.training.rating'].sudo().browse(int(kw['rating_id']))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating not found'}
                
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
                    return {'status': 'error', 'message': 'Missing rating_id parameter'}
                
                rating = request.env['kaizen.training.rating'].sudo().browse(int(kw['rating_id']))
                if not rating.exists():
                    return {'status': 'error', 'message': 'Rating not found'}
                
                rating.unlink()
                return {'status': 'success', 'message': 'Rating berhasil dihapus'}
            
            elif operation == 'list_by_training':
                if not kw.get('training_id'):
                    return {'status': 'error', 'message': 'Missing training_id parameter'}
                
                ratings = request.env['kaizen.training.rating'].sudo().search([
                    ('training_id', '=', int(kw['training_id']))
                ])
                
                return {
                    'status': 'success',
                    'data': [self._prepare_rating_data(rating) for rating in ratings]
                }
            
            elif operation == 'list_by_attendee':
                if not kw.get('attendee_id'):
                    return {'status': 'error', 'message': 'Missing attendee_id parameter'}
                
                ratings = request.env['kaizen.training.rating'].sudo().search([
                    ('attendee_id', '=', int(kw['attendee_id']))
                ])
                
                return {
                    'status': 'success',
                    'data': [self._prepare_rating_data(rating) for rating in ratings]
                }
            
            else:
                return {'status': 'error', 'message': f'Unknown operation: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error in manage_ratings: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # Tambahkan endpoint untuk mengirim email pengingat feedback ke peserta
    @http.route('/web/v2/kaizen/training/send-feedback-reminders', type='json', auth='user', methods=['POST'], csrf=False)
    def send_feedback_reminders(self, **kw):
        """Kirim email pengingat feedback ke semua peserta yang belum memberikan feedback."""
        try:
            training_id = kw.get('training_id')
            if not training_id:
                return {'status': 'error', 'message': 'Missing training_id parameter'}
            
            training = request.env['kaizen.training.program'].sudo().browse(int(training_id))
            if not training.exists():
                return {'status': 'error', 'message': 'Training not found'}
            
            # Get attendees who haven't provided feedback yet
            attendees_with_rating = training.rating_ids.mapped('attendee_id')
            attendees_without_rating = training.attendee_ids.filtered(lambda a: a not in attendees_with_rating)
            
            if not attendees_without_rating:
                return {'status': 'success', 'message': 'Semua peserta sudah memberikan feedback'}
            
            # Generate feedback token
            feedback_token = base64.b64encode(f"training-{training_id}-feedback".encode()).decode()
            
            # Get base URL from config parameter or use default
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
            feedback_url = f"{base_url}/feedback/{training_id}?token={feedback_token}"
            
            # Prepare email template
            mail_template = request.env.ref('module_name.email_template_feedback_reminder', raise_if_not_found=False)
            if not mail_template:
                return {'status': 'error', 'message': 'Email template not found'}
            
            # Send emails
            sent_count = 0
            for attendee in attendees_without_rating:
                if not attendee.work_email:
                    continue
                    
                # Send email
                try:
                    mail_template.with_context(
                        attendee_name=attendee.name,
                        training_name=training.name,
                        feedback_url=feedback_url
                    ).send_mail(
                        attendee.id,
                        force_send=True
                    )
                    sent_count += 1
                except Exception as mail_error:
                    _logger.error(f"Error sending email to {attendee.name}: {str(mail_error)}")
            
            return {
                'status': 'success', 
                'message': f'Email pengingat berhasil dikirim ke {sent_count} peserta',
                'data': {
                    'total_attendees': len(training.attendee_ids),
                    'attendees_with_rating': len(attendees_with_rating),
                    'attendees_without_rating': len(attendees_without_rating),
                    'emails_sent': sent_count
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in send_feedback_reminders: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
            # Lanjutkan dengan kode yang sudah ada...