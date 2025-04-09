# controllers/team_project_api.py
from odoo import http, fields
from odoo.http import request
import json
import logging
import pytz
import datetime  
from datetime import datetime, timedelta
import base64
import os
import werkzeug
from werkzeug.utils import secure_filename

_logger = logging.getLogger(__name__)

class TeamProjectAPI(http.Controller):
    def _format_datetime_jakarta(self, dt):
        """Menyiapkan format datetime ke timezone Jakarta dengan penanganan error yang tepat."""
        if not dt:
            return False
        
        try:
            # Import datetime langsung di dalam fungsi untuk memastikan ketersediaan
            import datetime
            
            # Untuk tipe Date (bukan Datetime)
            if hasattr(dt, 'day') and not hasattr(dt, 'hour'):
                return fields.Date.to_string(dt)
                    
            # Jika dt adalah string, konversi ke objek datetime
            if isinstance(dt, str):
                try:
                    if 'T' in dt or ' ' in dt:  # Ini datetime string
                        dt = fields.Datetime.from_string(dt)
                    else:  # Ini date string
                        return dt  # Kembalikan date string langsung
                except Exception as e:
                    _logger.error(f"Error converting date/time string '{dt}': {e}")
                    return dt  # Kembalikan string asli jika konversi gagal
            
            # Define Jakarta timezone
            jakarta_tz = pytz.timezone('Asia/Jakarta')
            
            # Convert ke Jakarta timezone (hanya untuk objek datetime)
            if hasattr(dt, 'hour'):  # Ini adalah datetime, bukan date
                try:
                    dt_utc = pytz.utc.localize(dt) if not hasattr(dt, 'tzinfo') or dt.tzinfo is None else dt
                    dt_jakarta = dt_utc.astimezone(jakarta_tz)
                    return fields.Datetime.to_string(dt_jakarta)
                except Exception as e:
                    _logger.error(f"Error converting datetime '{dt}': {e}")
                    return str(dt)
            else:
                # Ini adalah objek date
                return fields.Date.to_string(dt) if hasattr(dt, 'day') else str(dt)
                
        except Exception as e:
            _logger.error(f"Unexpected error in _format_datetime_jakarta: {e}")
            # Return nilai yang aman
            return str(dt) if dt else False
    
    @http.route('/web/v2/team/projects', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_projects(self, **kw):
        """Mengelola operasi CRUD untuk proyek tim."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                required_fields = ['name', 'date_start', 'date_end', 'project_manager_id', 'department_id']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'date_start': kw['date_start'],
                    'date_end': kw['date_end'],
                    'project_manager_id': int(kw['project_manager_id']),
                    'department_id': int(kw['department_id']),
                    'description': kw.get('description'),
                    'state': kw.get('state', 'draft'),
                    'priority': kw.get('priority', '1'),
                    'project_type': kw.get('project_type', 'general'),  # Default ke general jika tidak disebutkan
                }
                if kw.get('team_ids'):
                    team_ids = kw['team_ids'] if isinstance(kw['team_ids'], list) else json.loads(kw['team_ids'])
                    values['team_ids'] = [(6, 0, team_ids)]

                project = request.env['team.project'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_project_data(project)}

            # Di dalam metode manage_projects
            elif operation == 'read':
                project_id = kw.get('project_id')
                if not project_id:
                    return {'status': 'error', 'message': 'Missing project_id'}
                
                project = request.env['team.project'].sudo().browse(int(project_id))
                if not project.exists():
                    return {'status': 'error', 'message': 'Project not found'}
                
                # Parse parameter include_attachments jika ada
                include_attachments = kw.get('include_attachments', False)
                if isinstance(include_attachments, str):
                    include_attachments = include_attachments.lower() in ('true', '1', 'yes')
                
                # Get related tasks
                tasks = []
                for task in project.task_ids:
                    tasks.append(self._prepare_task_data(task))
                
                # Get related meetings
                meetings = []
                for meeting in project.meeting_ids:
                    meetings.append(self._prepare_meeting_data(meeting))
                
                # Get related BAU activities
                bau_activities = []
                for bau in project.bau_ids:
                    bau_activities.append(self._prepare_bau_data(bau))
                
                # Prepare project data with additional related data
                project_data = self._prepare_project_data(project)
                
                # Add attachment information if requested
                if include_attachments and project.attachment_ids:
                    project_data['attachments'] = []
                    for attachment in project.attachment_ids:
                        project_data['attachments'].append({
                            'id': attachment.id,
                            'name': attachment.name,
                            'mimetype': attachment.mimetype,
                            'size': attachment.file_size,
                            'url': f'/web/content/{attachment.id}?download=true',
                            'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False,
                            'create_date': fields.Datetime.to_string(attachment.create_date),
                            'create_uid': {
                                'id': attachment.create_uid.id,
                                'name': attachment.create_uid.name
                            }
                        })
                
                project_data.update({
                    'tasks': tasks,
                    'meetings': meetings,
                    'bau_activities': bau_activities,
                    'stakeholders': [{'id': s.id, 'name': s.name} for s in project.stakeholder_ids]
                })
                
                return {'status': 'success', 'data': project_data}

            elif operation == 'update':
                project_id = kw.get('project_id')
                if not project_id:
                    return {'status': 'error', 'message': 'Missing project_id'}
                project = request.env['team.project'].sudo().browse(int(project_id))
                if not project.exists():
                    return {'status': 'error', 'message': 'Project not found'}

                update_values = {}
                for field in ['name', 'date_start', 'date_end', 'description', 'state', 'priority', 'project_type']:
                    if field in kw:
                        update_values[field] = kw[field]
                if kw.get('project_manager_id'):
                    update_values['project_manager_id'] = int(kw['project_manager_id'])
                if kw.get('team_ids'):
                    team_ids = kw['team_ids'] if isinstance(kw['team_ids'], list) else json.loads(kw['team_ids'])
                    update_values['team_ids'] = [(6, 0, team_ids)]

                project.write(update_values)
                return {'status': 'success', 'data': self._prepare_project_data(project), 'message': 'Project updated'}

            elif operation == 'delete':
                project_id = kw.get('project_id')
                if not project_id:
                    return {'status': 'error', 'message': 'Missing project_id'}
                project = request.env['team.project'].sudo().browse(int(project_id))
                if not project.exists():
                    return {'status': 'error', 'message': 'Project not found'}
                project.unlink()
                return {'status': 'success', 'message': 'Project deleted'}

        except Exception as e:
            _logger.error(f"Error in manage_projects: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/team/project/attachments', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_project_attachments(self, **kw):
        """Mengelola attachment untuk project."""
        try:
            operation = kw.get('operation', 'list')
            project_id = kw.get('project_id')
            
            if not project_id:
                return {'status': 'error', 'message': 'Missing project_id parameter'}
            
            project = request.env['team.project'].sudo().browse(int(project_id))
            if not project.exists():
                return {'status': 'error', 'message': 'Project not found'}
            
            if operation == 'list':
                # Get attachments for the project
                attachments = project.attachment_ids
                attachment_data = []
                
                for attachment in attachments:
                    attachment_data.append({
                        'id': attachment.id,
                        'name': attachment.name,
                        'mimetype': attachment.mimetype,
                        'create_date': fields.Datetime.to_string(attachment.create_date),
                        'create_uid': {
                            'id': attachment.create_uid.id,
                            'name': attachment.create_uid.name
                        },
                        'size': attachment.file_size,
                        'url': f'/web/content/{attachment.id}?download=true',
                        'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False
                    })
                
                return {
                    'status': 'success',
                    'data': attachment_data
                }
            
            elif operation == 'add':
                # Check if attachment data is provided
                if not kw.get('attachment_id'):
                    return {'status': 'error', 'message': 'Missing attachment_id parameter'}
                
                attachment_id = int(kw.get('attachment_id'))
                attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
                
                if not attachment.exists():
                    return {'status': 'error', 'message': 'Attachment not found'}
                
                # Link attachment to project
                project.attachment_ids = [(4, attachment_id)]
                
                return {
                    'status': 'success',
                    'message': f'Attachment "{attachment.name}" added to project successfully'
                }
            
            elif operation == 'remove':
                # Check if attachment data is provided
                if not kw.get('attachment_id'):
                    return {'status': 'error', 'message': 'Missing attachment_id parameter'}
                
                attachment_id = int(kw.get('attachment_id'))
                
                # Remove attachment from project
                project.attachment_ids = [(3, attachment_id)]
                
                return {
                    'status': 'success',
                    'message': 'Attachment removed from project successfully'
                }
            
            else:
                return {'status': 'error', 'message': f'Unknown operation: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error in manage_project_attachments: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/team/project/upload_attachment', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_project_attachment(self, **kw):
        """Upload attachment langsung ke project."""
        try:
            # Validasi parameter
            if not kw.get('project_id'):
                return json.dumps({'status': 'error', 'message': 'Missing project_id parameter'})
            
            project_id = int(kw.get('project_id'))
            project = request.env['team.project'].sudo().browse(project_id)
            
            if not project.exists():
                return json.dumps({'status': 'error', 'message': 'Project not found'})
            
            # Cek file yang diupload
            if 'file' not in http.request.httprequest.files:
                return json.dumps({'status': 'error', 'message': 'No file uploaded'})
            
            # Ambil file
            file = http.request.httprequest.files['file']
            filename = file.filename
            file_content = file.read()
            mimetype = file.content_type
            
            # Validasi ukuran file (maksimal 20 MB)
            max_size = 20 * 1024 * 1024  # 20 MB
            if len(file_content) > max_size:
                return json.dumps({'status': 'error', 'message': 'File size exceeds the limit (20 MB)'})
            
            # Validasi tipe file
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.zip', '.rar']
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension not in allowed_extensions:
                return json.dumps({'status': 'error', 'message': 'File type not allowed'})
            
            # Encode file sebagai base64
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            
            # Buat attachment
            attachment = request.env['ir.attachment'].sudo().create({
                'name': filename,
                'datas': file_base64,
                'res_model': 'team.project',
                'res_id': project_id,
                'type': 'binary',
                'mimetype': mimetype,
            })
            
            # Tambahkan ke project
            project.attachment_ids = [(4, attachment.id)]
            
            return json.dumps({
                'status': 'success',
                'data': {
                    'id': attachment.id,
                    'name': attachment.name,
                    'mimetype': attachment.mimetype,
                    'size': attachment.file_size,
                    'url': f'/web/content/{attachment.id}?download=true'
                }
            })
        
        except Exception as e:
            _logger.error(f"Error during file upload: {str(e)}")
            return json.dumps({'status': 'error', 'message': str(e)})
    
    @http.route('/web/v2/team/projects/list', type='json', auth='user', methods=['POST'], csrf=False)
    def get_projects(self, **kw):
        """Mengambil daftar proyek dengan filter dan pagination yang lebih baik."""
        try:
            domain = []
            
            # Filter departemen
            if kw.get('department_id'):
                domain.append(('department_id', '=', int(kw['department_id'])))
            
            # Filter project_type yang baru ditambahkan
            if kw.get('project_type'):
                domain.append(('project_type', '=', kw['project_type']))
            
            # Filter status
            if kw.get('state'):
                domain.append(('state', '=', kw['state']))
            
            # Filter tanggal - ubah logika untuk menangkap proyek yang overlap dengan rentang
            if kw.get('date_start') and kw.get('date_end'):
                # Proyek yang berakhir setelah date_start dan dimulai sebelum date_end
                # Ini menangkap semua proyek yang overlap dengan rentang tanggal
                domain.append('|')
                domain.append('&')
                domain.append(('date_start', '<=', kw['date_end']))  # Proyek dimulai sebelum atau pada tanggal akhir filter
                domain.append(('date_end', '>=', kw['date_start']))  # Proyek berakhir setelah atau pada tanggal awal filter
                
                # Atau proyek yang belum memiliki tanggal akhir (date_end = False)
                domain.append('&')
                domain.append(('date_start', '<=', kw['date_end']))
                domain.append(('date_end', '=', False))
            
            # Jika hanya date_start yang diisi
            elif kw.get('date_start'):
                domain.append(('date_end', '>=', kw['date_start']))  # Proyek yang berakhir setelah date_start
            
            # Jika hanya date_end yang diisi
            elif kw.get('date_end'):
                domain.append(('date_start', '<=', kw['date_end']))  # Proyek yang dimulai sebelum date_end
            
            # Filter manager proyek jika ada
            if kw.get('project_manager_id'):
                domain.append(('project_manager_id', '=', int(kw['project_manager_id'])))
            
            # Filter prioritas jika ada
            if kw.get('priority'):
                domain.append(('priority', '=', kw['priority']))
            
            # Filter pencarian (search)
            if kw.get('search'):
                domain.append('|')
                domain.append(('name', 'ilike', kw['search']))
                domain.append(('code', 'ilike', kw['search']))
            
            # Pagination yang lebih baik
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 10))
            offset = (page - 1) * limit
            
            # Sorting
            sort_field = kw.get('sort_field', 'date_start')
            sort_order = kw.get('sort_order', 'desc')
            order = f"{sort_field} {sort_order}"
            
            # Tambahkan logging untuk debugging
            _logger.info(f"Project filter domain: {domain}")
            
            # Cari proyek dengan domain filter
            projects = request.env['team.project'].sudo().search(domain, limit=limit, offset=offset, order=order)
            total = request.env['team.project'].sudo().search_count(domain)
            
            # Hitung total pages untuk membantu frontend
            total_pages = (total + limit - 1) // limit if limit > 0 else 1
            
            # Log jumlah hasil
            _logger.info(f"Found {len(projects)} projects matching the filter criteria")
            
            return {
                'status': 'success',
                'data': [self._prepare_project_data(project) for project in projects],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'total_pages': total_pages
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_projects: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/tasks', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_tasks(self, **kw):
        """Mengelola operasi CRUD untuk tugas tim."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'list':
                # Build domain filter
                domain = []
                
                # Tangani setiap parameter dengan aman
                try:
                    if kw.get('project_id'):
                        domain.append(('project_id', '=', int(kw['project_id'])))
                    if kw.get('department_id'):
                        domain.append(('department_id', '=', int(kw['department_id'])))
                    if kw.get('type_id'):
                        domain.append(('type_id', '=', int(kw['type_id'])))
                    if kw.get('assigned_to'):
                        # Pastikan assigned_to diproses dengan benar
                        assigned_to = kw['assigned_to']
                        # Jika string, coba parse sebagai JSON jika berisi array
                        if isinstance(assigned_to, str) and assigned_to.startswith('['):
                            try:
                                assigned_to = json.loads(assigned_to)
                            except Exception:
                                assigned_to = [int(assigned_to)]
                        # Jika bukan list, konversi ke list
                        if not isinstance(assigned_to, list):
                            assigned_to = [int(assigned_to)]
                        domain.append(('assigned_to', 'in', assigned_to))
                    # Filter status
                    if kw.get('state'):
                        domain.append(('state', '=', kw['state']))
                    
                    # Filter tipe task
                    if kw.get('type_id'):
                        domain.append(('type_id', '=', int(kw['type_id'])))
                    
                    # Filter prioritas
                    if kw.get('priority'):
                        domain.append(('priority', '=', kw['priority']))
                    
                    # Filter rentang tanggal due date
                    if kw.get('due_date_from'):
                        domain.append(('planned_date_end', '>=', kw['due_date_from']))
                    if kw.get('due_date_to'):
                        domain.append(('planned_date_end', '<=', kw['due_date_to']))
                    
                    # Filter task overdue
                    if kw.get('is_overdue') == 'true':
                        today = fields.Date.today()
                        domain.append(('planned_date_end', '<', today))
                        domain.append(('state', 'not in', ['done', 'cancelled']))
                    
                    # Filter progress
                    if kw.get('progress_min'):
                        domain.append(('progress', '>=', float(kw['progress_min'])))
                    if kw.get('progress_max'):
                        domain.append(('progress', '<=', float(kw['progress_max'])))
                    
                    # Filter berdasarkan tag/label (jika model memiliki field tag_ids)
                    if kw.get('tag_ids'):
                        tag_ids = kw['tag_ids'] if isinstance(kw['tag_ids'], list) else json.loads(kw['tag_ids'])
                        domain.append(('tag_ids', 'in', tag_ids))
                    
                    # Filter "my tasks" - tasks untuk user saat ini
                    if kw.get('my_tasks') == 'true':
                        domain.append(('assigned_to', 'in', [request.env.user.employee_id.id]))
                    
                    # Filter task baru/diupdate dalam X hari terakhir
                    if kw.get('recent_days'):
                        days = int(kw['recent_days'])
                        date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                        domain.append('|')
                        domain.append(('create_date', '>=', date_limit))
                        domain.append(('write_date', '>=', date_limit))
                    
                    # Filter dependency
                    if kw.get('has_dependencies') == 'true':
                        domain.append(('depends_on_ids', '!=', False))
                    elif kw.get('has_dependencies') == 'false':
                        domain.append(('depends_on_ids', '=', False))
                    
                    # Filter blocked
                    if kw.get('is_blocked') == 'true':
                        domain.append(('blocked_by_id', '!=', False))
                    elif kw.get('is_blocked') == 'false':
                        domain.append(('blocked_by_id', '=', False))
                        
                    # Filter nama task (search)
                    if kw.get('search'):
                        domain.append('|')
                        domain.append(('name', 'ilike', kw['search']))
                        domain.append(('description', 'ilike', kw['search']))

                    
                    # Get tasks based on domain filters
                    tasks = request.env['team.project.task'].sudo().search(domain)
                    
                    # Buat task data dengan error handling
                    task_data = []
                    for task in tasks:
                        try:
                            task_data.append(self._prepare_task_data(task))
                        except Exception as e:
                            _logger.error(f"Error preparing task data: {str(e)}")
                            # Skip task yang error atau tambahkan data minimal
                            continue
                            
                    # Return formatted task data
                    return {
                        'status': 'success',
                        'data': task_data
                    }
                except Exception as e:
                    _logger.error(f"Error in list operation: {str(e)}")
                    return {'status': 'error', 'message': str(e)}

            elif operation == 'read':
                try:
                    task_id = kw.get('task_id')
                    if not task_id:
                        return {'status': 'error', 'message': 'Missing task_id'}
                    
                    task = request.env['team.project.task'].sudo().browse(int(task_id))
                    if not task.exists():
                        return {'status': 'error', 'message': 'Task not found'}
                    
                    # Parse parameter include_attachments jika ada
                    include_attachments = kw.get('include_attachments', False)
                    if isinstance(include_attachments, str):
                        include_attachments = include_attachments.lower() in ('true', '1', 'yes')
                    
                    # Prepare task data dengan parameter include_attachments
                    task_data = self._prepare_task_data(task, include_attachments)
                    
                    # Get checklist items if available
                    if hasattr(task, 'checklist_ids'):
                        # Get checklist items
                        checklist_items = []
                        for item in task.checklist_ids:
                            if hasattr(self, '_prepare_checklist_data'):
                                try:
                                    checklist_items.append(self._prepare_checklist_data(item))
                                except Exception as e:
                                    _logger.error(f"Error preparing checklist data: {e}")
                        
                        # Add to task data
                        task_data['checklists'] = checklist_items
                    
                    # Get timesheets if available
                    if hasattr(task, 'timesheet_ids'):
                        # Get timesheets
                        timesheets = []
                        for timesheet in task.timesheet_ids:
                            if hasattr(self, '_prepare_timesheet_data'):
                                try:
                                    timesheets.append(self._prepare_timesheet_data(timesheet))
                                except Exception as e:
                                    _logger.error(f"Error preparing timesheet data: {e}")
                        
                        # Add to task data
                        task_data['timesheets'] = timesheets
                    
                    return {'status': 'success', 'data': task_data}
                except Exception as e:
                    _logger.error(f"Error reading task: {str(e)}")
                    return {'status': 'error', 'message': f"Error reading task: {str(e)}"}

            elif operation == 'create':
                try:
                    required_fields = ['name', 'project_id', 'assigned_to']
                    if not all(kw.get(field) for field in required_fields):
                        return {'status': 'error', 'message': 'Missing required fields'}

                    # Initialize values dictionary
                    values = {
                        'name': kw['name'],
                        'project_id': int(kw['project_id']),
                        'description': kw.get('description', ''),
                        'state': kw.get('state', 'draft'),
                        'priority': kw.get('priority', '1'),
                    }

                    # Handle assigned_to conversion
                    if kw.get('assigned_to'):
                        assigned_to = kw['assigned_to']
                        # If assigned_to is a string, try to convert it to a list
                        if isinstance(assigned_to, str):
                            try:
                                assigned_to = json.loads(assigned_to)
                            except (ValueError, json.JSONDecodeError):
                                assigned_to = [int(assigned_to)] if assigned_to.isdigit() else []
                        # Ensure assigned_to is a list
                        if not isinstance(assigned_to, list):
                            assigned_to = [assigned_to]
                        values['assigned_to'] = [(6, 0, assigned_to)]

                    # Add other optional fields
                    if kw.get('planned_date_start'):
                        values['planned_date_start'] = kw['planned_date_start']
                    if kw.get('planned_date_end'):
                        values['planned_date_end'] = kw['planned_date_end']
                    if kw.get('planned_hours'):
                        values['planned_hours'] = float(kw.get('planned_hours', 0.0))
                    if kw.get('progress'):
                        values['progress'] = float(kw.get('progress', 0.0))

                    # Create the task with the values
                    task = request.env['team.project.task'].sudo().create(values)
                    return {'status': 'success', 'data': self._prepare_task_data(task)}
                except Exception as e:
                    _logger.error(f"Error creating task: {str(e)}")
                    return {'status': 'error', 'message': f"Error creating task: {str(e)}"}

            elif operation == 'update':
                try:
                    task_id = kw.get('task_id')
                    if not task_id:
                        return {'status': 'error', 'message': 'Missing task_id'}
                        
                    task = request.env['team.project.task'].sudo().browse(int(task_id))
                    if not task.exists():
                        return {'status': 'error', 'message': 'Task not found'}

                    # Initialize update values dictionary
                    update_values = {}

                    # Properti auto_timesheet untuk perubahan status 
                    auto_timesheet = kw.get('auto_timesheet', True)
                    
                    # Tambahkan ke values task
                    if auto_timesheet is not None:
                        update_values['auto_timesheet'] = auto_timesheet
                    
                    # Handle scalar fields
                    scalar_fields = ['name', 'description', 'state', 'progress', 'priority']
                    for field in scalar_fields:
                        if field in kw:
                            # Convert progress to float if needed
                            if field == 'progress' and kw[field] is not None:
                                update_values[field] = float(kw[field])
                            else:
                                update_values[field] = kw[field]
                    
                    # Handle date fields
                    date_fields = ['planned_date_start', 'planned_date_end']
                    for field in date_fields:
                        if field in kw and kw[field]:
                            update_values[field] = kw[field]
                    
                    # Handle numeric fields
                    if 'planned_hours' in kw and kw['planned_hours'] is not None:
                        try:
                            update_values['planned_hours'] = float(kw['planned_hours'])
                        except (ValueError, TypeError):
                            _logger.warning(f"Invalid planned_hours value: {kw['planned_hours']}")
                    
                    # Handle the assigned_to many2many relationship
                    if kw.get('assigned_to'):
                        try:
                            # Ensure assigned_to is a list
                            if isinstance(kw['assigned_to'], list):
                                assigned_to = kw['assigned_to']
                            else:
                                # Try to parse JSON if it's a string
                                try:
                                    assigned_to = json.loads(kw['assigned_to'])
                                except (ValueError, json.JSONDecodeError):
                                    # If not JSON, convert to list
                                    assigned_to = [int(kw['assigned_to'])]
                            
                            # Ensure all items are integers
                            assigned_to = [int(id) for id in assigned_to if id]
                            if assigned_to:
                                update_values['assigned_to'] = [(6, 0, assigned_to)]
                        except Exception as e:
                            _logger.error(f"Error processing assigned_to: {str(e)}")
                    
                    # Handle single relations
                    relation_fields = [('reviewer_id', 'reviewer_id'), ('type_id', 'type_id')]
                    for param_name, field_name in relation_fields:
                        if kw.get(param_name):
                            try:
                                update_values[field_name] = int(kw[param_name])
                            except (ValueError, TypeError):
                                _logger.warning(f"Invalid {param_name} value: {kw[param_name]}")
                    
                    # Apply updates
                    _logger.info(f"Updating task {task_id} with values: {update_values}")
                    task.write(update_values)

                    # Return the updated task data with timesheet info
                    response_data = self._prepare_task_data(task)
                    
                    # Tambahkan informasi timesheet terbaru jika ada
                    if 'state' in update_values and auto_timesheet:
                        recent_timesheet = request.env['team.project.timesheet'].sudo().search([
                            ('task_id', '=', task.id)
                        ], limit=1, order='create_date desc')
                        
                        if recent_timesheet:
                            response_data['recent_timesheet'] = {
                                'id': recent_timesheet.id,
                                'hours': recent_timesheet.hours,
                                'date': fields.Date.to_string(recent_timesheet.date)
                            }
                    
                    # Return the updated task data
                    return {'status': 'success', 'data': self._prepare_task_data(task), 'message': 'Task updated'}
                except Exception as e:
                    import traceback
                    _logger.error(f"Error updating task: {str(e)}\n{traceback.format_exc()}")
                    return {'status': 'error', 'message': f"Error updating task: {str(e)}"}

            elif operation == 'delete':
                try:
                    task_id = kw.get('task_id')
                    if not task_id:
                        return {'status': 'error', 'message': 'Missing task_id'}
                    task = request.env['team.project.task'].sudo().browse(int(task_id))
                    if not task.exists():
                        return {'status': 'error', 'message': 'Task not found'}
                    task.unlink()
                    return {'status': 'success', 'message': 'Task deleted'}
                except Exception as e:
                    _logger.error(f"Error deleting task: {str(e)}")
                    return {'status': 'error', 'message': f"Error deleting task: {str(e)}"}
            
            else:
                return {'status': 'error', 'message': f'Unknown operation: {operation}'}

        except Exception as e:
            _logger.error(f"Error in manage_tasks: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/team/upload_temporary_attachment', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_temporary_attachment(self, **kw):
        """Upload attachment sementara yang bisa dikaitkan dengan pesan."""
        try:
            # Cek file yang diupload
            if 'file' not in http.request.httprequest.files:
                return json.dumps({'status': 'error', 'message': 'No file uploaded'})
            
            # Ambil file
            file = http.request.httprequest.files['file']
            filename = file.filename
            file_content = file.read()
            mimetype = file.content_type
            
            # Validasi ukuran file (maksimal 20 MB)
            max_size = 20 * 1024 * 1024  # 20 MB
            if len(file_content) > max_size:
                return json.dumps({'status': 'error', 'message': 'File size exceeds the limit (20 MB)'})
            
            # Validasi tipe file
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.zip', '.rar']
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension not in allowed_extensions:
                return json.dumps({'status': 'error', 'message': 'File type not allowed'})
            
            # Encode file sebagai base64
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            
            # Buat attachment sementara (belum terkait dengan model spesifik)
            attachment = request.env['ir.attachment'].sudo().create({
                'name': filename,
                'datas': file_base64,
                'type': 'binary',
                'mimetype': mimetype,
            })
            
            # Return hasil
            return json.dumps({
                'status': 'success',
                'data': {
                    'id': attachment.id,
                    'name': attachment.name,
                    'mimetype': attachment.mimetype,
                    'size': attachment.file_size,
                    'url': f'/web/content/{attachment.id}?download=true',
                    'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False
                },
                'message': 'File uploaded successfully'
            })
        
        except Exception as e:
            _logger.error(f"Error during temporary file upload: {str(e)}")
            return json.dumps({'status': 'error', 'message': str(e)})

    @http.route('/web/v2/team/chat/send', type='json', auth='user', methods=['POST'], csrf=False)
    def send_chat_message(self, **kw):
        try:
            required_fields = ['group_id', 'content']
            if not all(kw.get(field) for field in required_fields):
                return {'status': 'error', 'message': 'Missing required fields'}

            values = {
                'group_id': int(kw['group_id']),
                'author_id': request.env.user.employee_id.id,
                'content': kw['content'],
                'project_id': int(kw['project_id']) if kw.get('project_id') else False,
                'message_type': kw.get('message_type', 'regular')
            }
            
            message = request.env['team.project.message'].sudo().create(values)
            
            # Proses attachment yang mungkin telah diupload sebelumnya
            if kw.get('attachment_ids'):
                attachment_ids = kw['attachment_ids'] if isinstance(kw['attachment_ids'], list) else json.loads(kw['attachment_ids'])
                
                # Validasi bahwa setiap attachment ada dan belum terkait dengan model lain
                for attachment_id in attachment_ids:
                    attachment = request.env['ir.attachment'].sudo().browse(int(attachment_id))
                    if attachment.exists() and (not attachment.res_id or not attachment.res_model):
                        # Update attachment untuk mengaitkannya dengan pesan
                        attachment.write({
                            'res_model': 'team.project.message',
                            'res_id': message.id
                        })
                        # Tambahkan ke pesan
                        message.write({
                            'attachment_ids': [(4, attachment.id)]
                        })
            
            # Proses mentions jika ada
            if kw.get('mentions'):
                for user_id in kw['mentions']:
                    # Hindari self-mention (kunci untuk mengatasi masalah utama)
                    if int(user_id) == request.env.user.id:
                        continue
                        
                    user = request.env['res.users'].sudo().browse(int(user_id))
                    if user.exists() and user.employee_id:
                        # Pastikan recipient_id adalah employee dari user yang di-mention
                        # Pastikan sender_id adalah employee dari user yang sedang login
                        request.env['team.project.notification'].sudo().create_project_notification(
                            model='team.project.message',
                            res_id=message.id,
                            type='mention',
                            title=f"Anda disebut oleh {request.env.user.employee_id.name}",
                            message=f"Anda disebut dalam pesan: '{kw['content'][:100]}...'",
                            project_id=values.get('project_id', False),
                            sender_id=request.env.user.employee_id.id,
                            recipient_id=user.employee_id.id,
                            category='mention',
                            data={
                                'message_id': message.id, 
                                'group_id': values['group_id'],
                                'action': 'view_group_chat'
                            }
                        )
            
            message_data = self._prepare_message_data(message)
            
            # Tambahkan data attachment ke respons
            if message.attachment_ids:
                message_data['attachments'] = []
                for attachment in message.attachment_ids:
                    message_data['attachments'].append({
                        'id': attachment.id,
                        'name': attachment.name,
                        'mimetype': attachment.mimetype,
                        'size': attachment.file_size,
                        'url': f'/web/content/{attachment.id}?download=true',
                        'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False,
                        'create_date': fields.Datetime.to_string(attachment.create_date),
                        'create_uid': {
                            'id': attachment.create_uid.id,
                            'name': attachment.create_uid.name
                        }
                    })
            
            return {'status': 'success', 'data': message_data}
        except Exception as e:
            _logger.error(f"Error in send_chat_message: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # Helper Methods
    def _prepare_project_data(self, project):
        """Menyiapkan data proyek untuk respons API dengan informasi pelacakan waktu penyelesaian."""
        project_data = {
            'id': project.id,
            'name': project.name,
            'code': project.code,
            'department': {'id': project.department_id.id, 'name': project.department_id.name},
            'project_type': project.project_type,
            'dates': {
                'start': fields.Date.to_string(project.date_start),
                'end': fields.Date.to_string(project.date_end),
                'actual_end': fields.Date.to_string(project.actual_date_end) if project.actual_date_end else False
            },
            'team': {
                'manager': {'id': project.project_manager_id.id, 'name': project.project_manager_id.name},
                'members': [{'id': m.id, 'name': m.name} for m in project.team_ids]
            },
            'group_id': project.group_id.id if project.group_id else False,
            'state': project.state,
            'progress': project.progress,
            'priority': project.priority,
            'description': project.description,
            'task_count': len(project.task_ids),
            'attachment_count': project.attachment_count,
            'completion': {
                'is_on_time': project.is_on_time,
                'days_delayed': project.days_delayed
            }
        }
        
        return project_data

    def _prepare_task_data(self, task, include_attachments=False):
        """Menyiapkan data tugas untuk respons API dengan error handling."""
        try:
            # Initialize an empty dictionary for task data
            task_data = {
                'id': task.id,
                'name': task.name,
                'priority': task.priority
            }
            
            # Add project info if available
            if hasattr(task, 'project_id') and task.project_id:
                task_data['project'] = {
                    'id': task.project_id.id,
                    'name': task.project_id.name
                }
            else:
                task_data['project'] = None
            
            # Add type info if available
            if hasattr(task, 'type_id') and task.type_id:
                task_data['type'] = {
                    'id': task.type_id.id,
                    'name': task.type_id.name
                }
            else:
                task_data['type'] = None
            
            # Add assigned_to info if available
            task_data['assigned_to'] = []
            if hasattr(task, 'assigned_to') and task.assigned_to:
                for person in task.assigned_to:
                    task_data['assigned_to'].append({
                        'id': person.id,
                        'name': person.name
                    })
            
            # Add reviewer info if available
            task_data['reviewer'] = None
            if hasattr(task, 'reviewer_id') and task.reviewer_id:
                task_data['reviewer'] = {
                    'id': task.reviewer_id.id,
                    'name': task.reviewer_id.name
                }
            
            # Add dates info
            task_data['dates'] = {
                'planned_start': self._format_datetime_jakarta(task.planned_date_start) if hasattr(task, 'planned_date_start') and task.planned_date_start else False,
                'planned_end': self._format_datetime_jakarta(task.planned_date_end) if hasattr(task, 'planned_date_end') and task.planned_date_end else False,
                'actual_start': self._format_datetime_jakarta(task.actual_date_start) if hasattr(task, 'actual_date_start') and task.actual_date_start else False,
                'actual_end': self._format_datetime_jakarta(task.actual_date_end) if hasattr(task, 'actual_date_end') and task.actual_date_end else False
            }
            
            # Add hours info
            task_data['hours'] = {
                'planned': task.planned_hours if hasattr(task, 'planned_hours') else 0,
                'actual': task.actual_hours if hasattr(task, 'actual_hours') else 0
            }
            
            # Add other fields
            task_data['state'] = task.state if hasattr(task, 'state') else 'draft'
            task_data['progress'] = task.progress if hasattr(task, 'progress') else 0
            task_data['description'] = task.description if hasattr(task, 'description') else ''
            task_data['checklist_progress'] = task.checklist_progress if hasattr(task, 'checklist_progress') else 0
            
            # Tambahkan data attachment jika diminta
            if include_attachments and hasattr(task, 'attachment_ids'):
                task_data['attachment_count'] = len(task.attachment_ids)
                
                # Jika diminta detail attachment
                task_data['attachments'] = []
                for attachment in task.attachment_ids:
                    task_data['attachments'].append({
                        'id': attachment.id,
                        'name': attachment.name,
                        'mimetype': attachment.mimetype if hasattr(attachment, 'mimetype') else 'application/octet-stream',
                        'size': attachment.file_size if hasattr(attachment, 'file_size') else 0,
                        'url': f'/web/content/{attachment.id}?download=true',
                        'is_image': attachment.mimetype.startswith('image/') if hasattr(attachment, 'mimetype') and attachment.mimetype else False,
                        'create_date': fields.Datetime.to_string(attachment.create_date),
                        'create_uid': {
                            'id': attachment.create_uid.id,
                            'name': attachment.create_uid.name
                        }
                    })
            
            # Kembali seluruh data tugas
            return task_data
        
        except Exception as e:
            import traceback
            _logger.error(f"Error in _prepare_task_data: {str(e)}\n{traceback.format_exc()}")
            # Return minimal data untuk menghindari kegagalan total
            return {
                'id': task.id,
                'name': task.name or "Unknown",
                'error': str(e)
            }

    def _prepare_message_data(self, message):
        """Menyiapkan data pesan untuk respons API."""
        message_data = {
            'id': message.id,
            'group_id': message.group_id.id,
            'author': {'id': message.author_id.id, 'name': message.author_id.name},
            'content': message.content,
            'date': self._format_datetime_jakarta(message.date),
            'project_id': message.project_id.id if message.project_id else None,
            'is_pinned': message.is_pinned,
            'attachment_count': message.attachment_count if hasattr(message, 'attachment_count') else len(message.attachment_ids)
        }
        
        return message_data
    
    # controllers/team_project_api.py (Lanjutan)

    @http.route('/web/v2/team/upload_attachment', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_attachment(self, **kw):
        """Upload attachment untuk task atau pesan."""
        try:
            # Validasi parameter
            if not kw.get('model') or not kw.get('res_id'):
                return json.dumps({'status': 'error', 'message': 'Missing required parameters (model, res_id)'})
            
            model_name = kw.get('model')
            res_id = int(kw.get('res_id'))
            
            # Validasi model yang diizinkan
            allowed_models = ['team.project.task', 'team.project.message', 'team.project']
            if model_name not in allowed_models:
                return json.dumps({'status': 'error', 'message': 'Invalid model. Allowed models: team.project.task, team.project.message, team.project'})
            
            # Cek file yang diupload
            if 'file' not in http.request.httprequest.files:
                return json.dumps({'status': 'error', 'message': 'No file uploaded'})
            
            # Ambil file
            file = http.request.httprequest.files['file']
            filename = file.filename
            file_content = file.read()
            mimetype = file.content_type
            
            # Validasi ukuran file (maksimal 20 MB)
            max_size = 20 * 1024 * 1024  # 20 MB
            if len(file_content) > max_size:
                return json.dumps({'status': 'error', 'message': 'File size exceeds the limit (20 MB)'})
            
            # Validasi tipe file
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.zip', '.rar']
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension not in allowed_extensions:
                return json.dumps({'status': 'error', 'message': 'File type not allowed'})
            
            # Validasi record ada
            record = request.env[model_name].sudo().browse(res_id)
            if not record.exists():
                return json.dumps({'status': 'error', 'message': f'{model_name} with ID {res_id} not found'})
            
            # Encode file sebagai base64
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            
            # Buat attachment
            attachment = request.env['ir.attachment'].sudo().create({
                'name': filename,
                'datas': file_base64,
                'res_model': model_name,
                'res_id': res_id,
                'type': 'binary',
                'mimetype': mimetype,
            })
            
            # Return hasil
            return json.dumps({
                'status': 'success',
                'data': {
                    'id': attachment.id,
                    'name': attachment.name,
                    'mimetype': attachment.mimetype,
                    'size': attachment.file_size,
                    'url': f'/web/content/{attachment.id}?download=true',
                    'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False,
                    'create_date': fields.Datetime.to_string(attachment.create_date),
                    'create_uid': {
                        'id': attachment.create_uid.id,
                        'name': attachment.create_uid.name
                    }
                },
                'message': 'File uploaded successfully'
            })
        
        except Exception as e:
            _logger.error(f"Error during file upload: {str(e)}")
            return json.dumps({'status': 'error', 'message': str(e)})

    @http.route('/web/v2/team/get_attachments', type='json', auth='user', methods=['POST'], csrf=False)
    def get_attachments(self, **kw):
        """Mengambil daftar attachment untuk task atau pesan."""
        try:
            # Validasi parameter
            if not kw.get('model') or not kw.get('res_id'):
                return {'status': 'error', 'message': 'Missing required parameters (model, res_id)'}
            
            model_name = kw.get('model')
            res_id = int(kw.get('res_id'))
            
            # Validasi model yang diizinkan
            allowed_models = ['team.project.task', 'team.project.message', 'team.project']
            if model_name not in allowed_models:
                return {'status': 'error', 'message': 'Invalid model. Allowed models: team.project.task, team.project.message, team.project'}
            
            # Validasi record ada
            record = request.env[model_name].sudo().browse(res_id)
            if not record.exists():
                return {'status': 'error', 'message': f'{model_name} with ID {res_id} not found'}
            
            # Cari attachment
            attachments = request.env['ir.attachment'].sudo().search([
                ('res_model', '=', model_name),
                ('res_id', '=', res_id)
            ], order='create_date DESC')
            
            # Format data attachment
            attachment_data = []
            for attachment in attachments:
                attachment_data.append({
                    'id': attachment.id,
                    'name': attachment.name,
                    'mimetype': attachment.mimetype,
                    'create_date': fields.Datetime.to_string(attachment.create_date),
                    'create_uid': {
                        'id': attachment.create_uid.id,
                        'name': attachment.create_uid.name
                    },
                    'size': attachment.file_size,
                    'url': f'/web/content/{attachment.id}?download=true',
                    'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False
                })
            
            return {
                'status': 'success',
                'data': attachment_data
            }
        
        except Exception as e:
            _logger.error(f"Error in get_attachments: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/delete_attachment', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_attachment(self, **kw):
        """Menghapus attachment."""
        try:
            # Validasi parameter
            if not kw.get('attachment_id'):
                return {'status': 'error', 'message': 'Missing attachment_id parameter'}
            
            attachment_id = int(kw.get('attachment_id'))
            
            # Cari attachment
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if not attachment.exists():
                return {'status': 'error', 'message': 'Attachment not found'}
            
            # Validasi model
            allowed_models = ['team.project.task', 'team.project.message', 'team.project']
            if attachment.res_model not in allowed_models:
                return {'status': 'error', 'message': 'Cannot delete attachment from this model'}
            
            # Hapus attachment
            attachment_name = attachment.name  # Simpan nama untuk respons
            attachment.unlink()
            
            return {
                'status': 'success',
                'message': f'Attachment "{attachment_name}" deleted successfully'
            }
        
        except Exception as e:
            _logger.error(f"Error in delete_attachment: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/meetings', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_meetings(self, **kw):
        """Mengelola operasi CRUD untuk rapat tim."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                required_fields = ['name', 'start_datetime', 'end_datetime', 'organizer_id']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                # Handle timezone for datetime fields (assuming frontend sends local Jakarta time)
                start_dt = fields.Datetime.from_string(kw['start_datetime'])
                end_dt = fields.Datetime.from_string(kw['end_datetime'])
                
                # Assume times from frontend are in Jakarta time (+7)
                jakarta_tz = pytz.timezone('Asia/Jakarta')
                
                # Localize to Jakarta timezone
                start_jakarta = jakarta_tz.localize(start_dt)
                end_jakarta = jakarta_tz.localize(end_dt)
                
                # Convert to UTC for storage
                start_utc = start_jakarta.astimezone(pytz.UTC)
                end_utc = end_jakarta.astimezone(pytz.UTC)

                values = {
                    'name': kw['name'],
                    'start_datetime': fields.Datetime.to_string(start_utc),
                    'end_datetime': fields.Datetime.to_string(end_utc),
                    'organizer_id': int(kw['organizer_id']),
                    'project_id': int(kw['project_id']) if kw.get('project_id') else False,
                    'location': kw.get('location'),
                    'virtual_location': kw.get('virtual_location'),
                    'agenda': kw.get('agenda'),
                    'notes': kw.get('notes'),
                    'state': kw.get('state', 'planned'),
                }
                
                if kw.get('attendee_ids'):
                    attendee_ids = kw['attendee_ids'] if isinstance(kw['attendee_ids'], list) else json.loads(kw['attendee_ids'])
                    values['attendee_ids'] = [(6, 0, attendee_ids)]

                meeting = request.env['team.project.meeting'].sudo().create(values)
                
                # Opsional: Otomatis kirim notifikasi ke peserta
                if kw.get('notify_attendees', False):
                    meeting.action_notify_attendees()
                    
                return {'status': 'success', 'data': self._prepare_meeting_data(meeting)}

            elif operation == 'update':
                meeting_id = kw.get('meeting_id')
                if not meeting_id:
                    return {'status': 'error', 'message': 'Missing meeting_id'}
                meeting = request.env['team.project.meeting'].sudo().browse(int(meeting_id))
                if not meeting.exists():
                    return {'status': 'error', 'message': 'Meeting not found'}

                update_values = {}
                for field in ['name', 'start_datetime', 'end_datetime', 'location', 'virtual_location', 'agenda', 'notes', 'state']:
                    if field in kw:
                        update_values[field] = kw[field]
                
                if kw.get('organizer_id'):
                    update_values['organizer_id'] = int(kw['organizer_id'])
                if kw.get('project_id'):
                    update_values['project_id'] = int(kw['project_id'])
                if kw.get('attendee_ids'):
                    attendee_ids = kw['attendee_ids'] if isinstance(kw['attendee_ids'], list) else json.loads(kw['attendee_ids'])
                    update_values['attendee_ids'] = [(6, 0, attendee_ids)]

                meeting.write(update_values)
                return {'status': 'success', 'data': self._prepare_meeting_data(meeting), 'message': 'Meeting updated'}

            elif operation == 'delete':
                meeting_id = kw.get('meeting_id')
                if not meeting_id:
                    return {'status': 'error', 'message': 'Missing meeting_id'}
                meeting = request.env['team.project.meeting'].sudo().browse(int(meeting_id))
                if not meeting.exists():
                    return {'status': 'error', 'message': 'Meeting not found'}
                meeting.unlink()
                return {'status': 'success', 'message': 'Meeting deleted'}

        except Exception as e:
            _logger.error(f"Error in manage_meetings: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/team/meetings/actions', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_meeting_actions(self, **kw):
        """Mengelola item aksi dari rapat."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                required_fields = ['name', 'meeting_id', 'assigned_to']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'meeting_id': int(kw['meeting_id']),
                    'assigned_to': int(kw['assigned_to']),
                    'due_date': kw.get('due_date'),
                    'notes': kw.get('notes'),
                    'state': kw.get('state', 'todo'),
                }

                action = request.env['team.project.meeting.action'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_meeting_action_data(action)}

            elif operation == 'update':
                action_id = kw.get('action_id')
                if not action_id:
                    return {'status': 'error', 'message': 'Missing action_id'}
                action = request.env['team.project.meeting.action'].sudo().browse(int(action_id))
                if not action.exists():
                    return {'status': 'error', 'message': 'Meeting action not found'}

                update_values = {}
                for field in ['name', 'due_date', 'notes', 'state']:
                    if field in kw:
                        update_values[field] = kw[field]
                
                if kw.get('assigned_to'):
                    update_values['assigned_to'] = int(kw['assigned_to'])

                action.write(update_values)
                return {'status': 'success', 'data': self._prepare_meeting_action_data(action), 'message': 'Meeting action updated'}

            elif operation == 'delete':
                action_id = kw.get('action_id')
                if not action_id:
                    return {'status': 'error', 'message': 'Missing action_id'}
                action = request.env['team.project.meeting.action'].sudo().browse(int(action_id))
                if not action.exists():
                    return {'status': 'error', 'message': 'Meeting action not found'}
                action.unlink()
                return {'status': 'success', 'message': 'Meeting action deleted'}

        except Exception as e:
            _logger.error(f"Error in manage_meeting_actions: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/bau', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_bau_activities(self, **kw):
        """Mengelola aktivitas BAU (Business As Usual)."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                required_fields = ['name', 'date', 'activity_type', 'time_start', 'time_end']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                # Convert time from string format (HH:MM) to float format (hours.fraction)
                time_start = self._convert_time_to_float(kw['time_start'])
                time_end = self._convert_time_to_float(kw['time_end'])
                
                # Validate time values
                if not self._validate_time_values(time_start, time_end):
                    return {'status': 'error', 'message': 'Invalid time values or time range'}

                values = {
                    'name': kw['name'],
                    'date': kw['date'],
                    'activity_type': kw['activity_type'],
                    'creator_id': kw.get('creator_id', request.env.user.employee_id.id),
                    'project_id': int(kw['project_id']) if kw.get('project_id') else False,
                    'time_start': time_start,
                    'time_end': time_end,
                    'description': kw.get('description'),
                    'state': kw.get('state', 'planned'),
                }

                # Let the model compute hours_spent based on time_start and time_end
                # If hours_spent is explicitly provided, use it
                if kw.get('hours_spent'):
                    values['hours_spent'] = float(kw.get('hours_spent', 0.0))

                bau = request.env['team.project.bau'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_bau_data(bau)}
            
            elif operation == 'get':
                domain = []
                if kw.get('creator_id'):
                    domain.append(('creator_id', '=', int(kw['creator_id'])))
                if kw.get('project_id'):
                    domain.append(('project_id', '=', int(kw['project_id'])))
                if kw.get('date_from'):
                    domain.append(('date', '>=', kw['date_from']))
                if kw.get('date_to'):
                    domain.append(('date', '<=', kw['date_to']))
                if kw.get('activity_type'):
                    domain.append(('activity_type', '=', kw['activity_type']))
                if kw.get('state'):
                    domain.append(('state', '=', kw['state']))

                bau_activities = request.env['team.project.bau'].sudo().search(domain)
                return {
                    'status': 'success',
                    'data': [self._prepare_bau_data(bau) for bau in bau_activities]
                }

            elif operation == 'update':
                bau_id = kw.get('bau_id')
                if not bau_id:
                    return {'status': 'error', 'message': 'Missing bau_id'}
                bau = request.env['team.project.bau'].sudo().browse(int(bau_id))
                if not bau.exists():
                    return {'status': 'error', 'message': 'BAU activity not found'}

                update_values = {}
                for field in ['name', 'date', 'activity_type', 'description', 'state']:
                    if field in kw:
                        update_values[field] = kw[field]
                
                # Handle time fields
                if kw.get('time_start'):
                    update_values['time_start'] = self._convert_time_to_float(kw['time_start'])
                if kw.get('time_end'):
                    update_values['time_end'] = self._convert_time_to_float(kw['time_end'])
                
                # If both times are updated, verify them
                if 'time_start' in update_values and 'time_end' in update_values:
                    if not self._validate_time_values(update_values['time_start'], update_values['time_end']):
                        return {'status': 'error', 'message': 'Invalid time values or time range'}
                
                if kw.get('hours_spent'):
                    update_values['hours_spent'] = float(kw['hours_spent'])
                if kw.get('project_id'):
                    update_values['project_id'] = int(kw['project_id'])
                if kw.get('creator_id'):
                    update_values['creator_id'] = int(kw['creator_id'])

                bau.write(update_values)
                return {'status': 'success', 'data': self._prepare_bau_data(bau), 'message': 'BAU activity updated'}

            elif operation == 'delete':
                bau_id = kw.get('bau_id')
                if not bau_id:
                    return {'status': 'error', 'message': 'Missing bau_id'}
                bau = request.env['team.project.bau'].sudo().browse(int(bau_id))
                if not bau.exists():
                    return {'status': 'error', 'message': 'BAU activity not found'}
                bau.unlink()
                return {'status': 'success', 'message': 'BAU activity deleted'}

        except Exception as e:
            _logger.error(f"Error in manage_bau_activities: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _convert_time_to_float(self, time_str):
        """Convert time string (HH:MM) to float (hours.fraction)"""
        try:
            if isinstance(time_str, float) or isinstance(time_str, int):
                return float(time_str)
                
            # Handle already float-like strings
            if isinstance(time_str, str) and not ':' in time_str:
                return float(time_str)
                
            # Parse time in HH:MM format
            hours, minutes = map(int, time_str.split(':'))
            return hours + (minutes / 60.0)
        except Exception as e:
            _logger.error(f"Error converting time: {str(e)}")
            return 0.0

    def _validate_time_values(self, time_start, time_end):
        """Validate time values"""
        try:
            # Check time ranges
            if time_start < 0 or time_start >= 24:
                return False
            if time_end < 0 or time_end >= 24:
                return False
                
            # Allow overnight spans (end time < start time)
            # But limit unrealistic spans (over 16 hours)
            if time_end < time_start and (time_start - time_end) > 16:
                return False
                
            return True
        except Exception as e:
            _logger.error(f"Error validating time values: {str(e)}")
            return False


    def _format_time_float_to_string(self, time_float):
        """Convert float time (hours.fraction) to string format (HH:MM)"""
        try:
            if time_float is False or time_float is None:
                return "00:00"
                
            hours = int(time_float)
            minutes = int((time_float - hours) * 60)
            return f"{hours:02d}:{minutes:02d}"
        except Exception as e:
            _logger.error(f"Error formatting time: {str(e)}")
            return "00:00"

        
    @http.route('/web/v2/team/bau/report', type='json', auth='user', methods=['POST'], csrf=False)
    def team_bau_report(self, **kw):
        """Generate BAU activity reports and analytics"""
        try:
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            
            domain = []
            if date_from:
                domain.append(('date', '>=', date_from))
            if date_to:
                domain.append(('date', '<=', date_to))
                
            # Get all BAU activities within date range
            bau_activities = request.env['team.project.bau'].sudo().search(domain)
            
            # Calculate summary data
            total_hours = sum(bau_activities.mapped('hours_spent'))
            date_set = set(bau_activities.mapped('date'))
            total_bau_days = len(date_set)
            
            # Group activities by creator
            creators_data = []
            creators = {}
            
            for activity in bau_activities:
                creator_id = activity.creator_id.id
                if creator_id not in creators:
                    creators[creator_id] = {
                        'creator_id': creator_id,
                        'creator_name': activity.creator_id.name,
                        'activities': []
                    }
                creators[creator_id]['activities'].append(self._prepare_bau_data(activity))
            
            for creator_id, data in creators.items():
                creators_data.append(data)
            
            # Group activities by day
            daily_data = []
            days = {}
            
            for activity in bau_activities:
                date_str = fields.Date.to_string(activity.date)
                if date_str not in days:
                    days[date_str] = {
                        'date': date_str,
                        'activities': []
                    }
                days[date_str]['activities'].append(self._prepare_bau_data(activity))
            
            for date_str, data in sorted(days.items()):
                daily_data.append(data)
            
            # Calculate estimated project hours
            # Assuming 8-hour workday and subtracting BAU hours
            total_work_hours = total_bau_days * 8  # 8 hours per workday
            project_hours = max(0, total_work_hours - total_hours)
            
            return {
                'status': 'success',
                'data': {
                    'summary': {
                        'total_hours': total_hours,
                        'total_bau_days': total_bau_days,
                        'project_hours': project_hours,
                        'bau_vs_project_ratio': f"{total_hours}:{project_hours}"
                    },
                    'creators': creators_data,
                    'daily_data': daily_data
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in team_bau_report: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/bau/calendar', type='json', auth='user', methods=['POST'], csrf=False)
    def get_bau_calendar(self, **kw):
        """Get BAU activities for calendar view."""
        try:
            # Validasi input
            if not kw.get('date_from') or not kw.get('date_to'):
                return {'status': 'error', 'message': 'Date range is required'}
                
            # Build domain for filtering
            domain = [
                ('date', '>=', kw['date_from']),
                ('date', '<=', kw['date_to'])
            ]
            
            # Filter by creator (untuk view pribadi atau filter spesifik anggota tim)
            if kw.get('creator_id'):
                domain.append(('creator_id', '=', int(kw['creator_id'])))
            
            # Filter by project
            if kw.get('project_id'):
                domain.append(('project_id', '=', int(kw['project_id'])))

            # Di endpoint get_bau_calendar
            # Setelah filter project_id, tambahkan filter department_id
            if kw.get('department_id'):
                # Filter berdasarkan departemen proyek
                # Pertama, dapatkan proyek dari departemen tersebut
                project_ids = request.env['team.project'].sudo().search([
                    ('department_id', '=', int(kw['department_id']))
                ]).ids
                
                if project_ids:
                    domain.append(('project_id', 'in', project_ids))
                else:
                    # Jika tidak ada proyek dalam departemen, kembalikan hasil kosong
                    return {
                        'status': 'success',
                        'data': []
                    }
            
            # Get BAU activities
            bau_activities = request.env['team.project.bau'].sudo().search(domain, order='date ASC, time_start ASC')
            
            # Tambahkan informasi department ke setiap project yang terlibat
            calendar_data = []
            for day in self._group_activities_by_date(bau_activities):
                # Untuk setiap aktivitas, tambahkan department_id pada creator
                for activity in day['activities']:
                    if activity.get('creator'):
                        # Ambil data employee dari creator
                        employee = request.env['hr.employee'].sudo().browse(activity['creator']['id'])
                        # Tambahkan department_id ke creator
                        if employee.department_id:
                            activity['creator']['department_id'] = employee.department_id.id
                            activity['creator']['department_name'] = employee.department_id.name
                
                calendar_data.append(day)
            
            return {
                'status': 'success',
                'data': calendar_data
            }
        
        except Exception as e:
            _logger.error(f"Error in get_bau_calendar: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    # Implementasikan helper method untuk mengelompokkan aktivitas berdasarkan tanggal
    def _group_activities_by_date(self, activities):
        """Group activities by date for calendar view."""
        calendar_data = {}
        
        for bau in activities:
            date_key = str(bau.date)
            if date_key not in calendar_data:
                calendar_data[date_key] = {
                    'date': date_key,
                    'activities': [],
                    'total_hours': 0,
                    'target_achieved': False
                }
                
            # Add activity data
            activity_data = self._prepare_bau_data(bau)
            calendar_data[date_key]['activities'].append(activity_data)
            calendar_data[date_key]['total_hours'] += bau.hours_spent
            
        # Convert dictionary to list
        return list(calendar_data.values())
    
    @http.route('/web/v2/team/departments', type='json', auth='user', methods=['POST'], csrf=False)
    def get_departments(self, **kw):
        """Get list of departments for dropdown."""
        try:
            departments = request.env['hr.department'].sudo().search_read(
                [], ['id', 'name'], order='name'
            )
            
            return {
                'status': 'success',
                'data': departments
            }
        except Exception as e:
            _logger.error(f"Error in get_departments: {str(e)}")
            return {'status': 'error', 'message': str(e)}


    @http.route('/web/v2/team/bau/batch', type='json', auth='user', methods=['POST'], csrf=False)
    def create_batch_bau_activities(self, **kw):
        """Create BAU activities in batch for a date range."""
        try:
            # Get params
            params = kw.get('params', {})
            activity = params.get('activity', {})
            date_from = params.get('date_from')
            date_to = params.get('date_to')
            exclude_weekends = params.get('exclude_weekends', True)
            
            # Validate required params
            if not all([activity, date_from, date_to]):
                return {'status': 'error', 'message': 'Missing required parameters'}
            
            # Validate activity parameters
            required_fields = ['name', 'activity_type', 'time_start', 'time_end']
            if not all(activity.get(field) for field in required_fields):
                return {'status': 'error', 'message': 'Activity is missing required fields'}
            
            # Convert time values
            time_start = self._convert_time_to_float(activity['time_start'])
            time_end = self._convert_time_to_float(activity['time_end'])
            
            # Validate time values
            if not self._validate_time_values(time_start, time_end):
                return {'status': 'error', 'message': 'Invalid time values or time range'}
            
            # Generate date range
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                if date_from_obj > date_to_obj:
                    return {'status': 'error', 'message': 'Start date must be before end date'}
                    
                # Generate all dates in range
                date_range = []
                current_date = date_from_obj
                while current_date <= date_to_obj:
                    # Skip weekends if requested
                    if exclude_weekends and current_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                        current_date += timedelta(days=1)
                        continue
                        
                    date_range.append(current_date)
                    current_date += timedelta(days=1)
            except Exception as e:
                _logger.error(f"Error generating date range: {str(e)}")
                return {'status': 'error', 'message': f"Error with date format: {str(e)}"}
            
            # Create activities for each date
            created_activities = []
            errors = []
            
            for date in date_range:
                date_str = date.strftime('%Y-%m-%d')
                try:
                    # Prepare values
                    values = {
                        'name': activity['name'],
                        'activity_type': activity['activity_type'],
                        'date': date_str,
                        'time_start': time_start,
                        'time_end': time_end,
                        'creator_id': activity.get('creator_id', request.env.user.employee_id.id),
                        'description': activity.get('description', ''),
                        'state': 'planned',
                    }
                    
                    # Add project_id if provided
                    if activity.get('project_id'):
                        values['project_id'] = activity['project_id']
                    
                    # Add hours_spent if provided, otherwise let the model compute it
                    if activity.get('hours_spent'):
                        values['hours_spent'] = float(activity['hours_spent'])
                    
                    # Create activity
                    bau = request.env['team.project.bau'].sudo().create(values)
                    created_activities.append(self._prepare_bau_data(bau))
                except Exception as e:
                    _logger.error(f"Error creating BAU activity for date {date_str}: {str(e)}")
                    errors.append({'date': date_str, 'error': str(e)})
            
            # Return result
            if not created_activities and errors:
                return {'status': 'error', 'message': 'Failed to create any activities', 'data': {'errors': errors}}
            
            if errors:
                return {
                    'status': 'partial_success',
                    'message': f'Created {len(created_activities)} activities with {len(errors)} errors',
                    'data': {
                        'created': created_activities,
                        'errors': errors
                    }
                }
            
            return {
                'status': 'success',
                'message': f'Successfully created {len(created_activities)} activities',
                'data': {
                    'created': created_activities
                }
            }
        except Exception as e:
            _logger.error(f"Error in create_batch_bau_activities: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/bau/verify', type='json', auth='user', methods=['POST'], csrf=False)
    def verify_bau_activity(self, **kw):
        """Verify a BAU activity (mark as done or not done)."""
        try:
            # Get params
            bau_id = kw.get('bau_id')
            state = kw.get('state')
            verification_reason = kw.get('verification_reason')
            hours_spent = kw.get('hours_spent')
            time_start = kw.get('time_start')
            time_end = kw.get('time_end')
            
            # Validate required params
            if not bau_id:
                return {'status': 'error', 'message': 'Missing bau_id parameter'}
            
            if state not in ['done', 'not_done']:
                return {'status': 'error', 'message': 'Invalid state parameter (must be "done" or "not_done")'}
            
            # Get BAU activity
            bau = request.env['team.project.bau'].sudo().browse(int(bau_id))
            if not bau.exists():
                return {'status': 'error', 'message': 'BAU activity not found'}
            
            # Check if activity can be verified
            today = fields.Date.today()
            activity_date = bau.date
            
            # Can only verify activities from today or yesterday
            delta_days = (today - activity_date).days
            if delta_days > 1:
                return {'status': 'error', 'message': 'Cannot verify activities older than 1 day'}
            
            # If verifying H+1 activity, require a reason
            requires_reason = delta_days == 1
            if requires_reason and not verification_reason:
                return {'status': 'error', 'message': 'Verification reason required for H+1 activities'}
            
            # Update values
            values = {
                'state': state,
                'verified_by': request.env.user.employee_id.id,
                'verification_date': fields.Datetime.now(),
            }
            
            # Update time fields if provided
            if time_start:
                values['time_start'] = self._convert_time_to_float(time_start)
            
            if time_end:
                values['time_end'] = self._convert_time_to_float(time_end)
            
            # If both time_start and time_end are provided, validate them
            if time_start and time_end:
                if not self._validate_time_values(values['time_start'], values['time_end']):
                    return {'status': 'error', 'message': 'Invalid time values or time range'}
            
            # Add hours_spent if explicitly provided
            if hours_spent is not None:
                values['hours_spent'] = float(hours_spent)
                
            # Add verification reason if provided
            if verification_reason:
                values['verification_reason'] = verification_reason
            
            # Update BAU activity
            bau.write(values)
            
            return {
                'status': 'success',
                'message': f'Activity successfully verified as "{state}"',
                'data': self._prepare_bau_data(bau)
            }
        except Exception as e:
            _logger.error(f"Error in verify_bau_activity: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/task/checklists', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_task_checklists(self, **kw):
        """Mengelola checklist item untuk tugas."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                required_fields = ['name', 'task_id']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'task_id': int(kw['task_id']),
                    'sequence': int(kw.get('sequence', 10)),
                    'assigned_to': int(kw['assigned_to']) if kw.get('assigned_to') else False,
                    'deadline': kw.get('deadline'),
                    'notes': kw.get('notes'),
                    'is_done': kw.get('is_done', False),
                }

                checklist = request.env['team.project.task.checklist'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_checklist_data(checklist)}

            elif operation == 'update':
                checklist_id = kw.get('checklist_id')
                if not checklist_id:
                    return {'status': 'error', 'message': 'Missing checklist_id'}
                checklist = request.env['team.project.task.checklist'].sudo().browse(int(checklist_id))
                if not checklist.exists():
                    return {'status': 'error', 'message': 'Checklist item not found'}

                update_values = {}
                for field in ['name', 'sequence', 'deadline', 'notes', 'is_done']:
                    if field in kw:
                        update_values[field] = kw[field]
                
                if kw.get('assigned_to'):
                    update_values['assigned_to'] = int(kw['assigned_to'])

                checklist.write(update_values)
                
                # Refresh task progress after updating checklist
                checklist.task_id._compute_checklist_progress()
                
                return {'status': 'success', 'data': self._prepare_checklist_data(checklist), 'message': 'Checklist item updated'}

            elif operation == 'delete':
                checklist_id = kw.get('checklist_id')
                if not checklist_id:
                    return {'status': 'error', 'message': 'Missing checklist_id'}
                checklist = request.env['team.project.task.checklist'].sudo().browse(int(checklist_id))
                if not checklist.exists():
                    return {'status': 'error', 'message': 'Checklist item not found'}
                task_id = checklist.task_id.id
                checklist.unlink()
                
                # Refresh task progress after deleting checklist
                task = request.env['team.project.task'].sudo().browse(task_id)
                if task.exists():
                    task._compute_checklist_progress()
                
                return {'status': 'success', 'message': 'Checklist item deleted'}

        except Exception as e:
            _logger.error(f"Error in manage_task_checklists: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/task/timesheets', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_timesheets(self, **kw):
        """Mengelola timesheet untuk tugas."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                required_fields = ['task_id', 'hours']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'task_id': int(kw['task_id']),
                    'hours': float(kw['hours']),
                }
                
                # Handle employee_id safely
                if kw.get('employee_id'):
                    values['employee_id'] = int(kw['employee_id'])
                else:
                    # Use current user's employee record without relying on context
                    current_user = request.env['res.users'].sudo().browse(request.uid)
                    if current_user.employee_id:
                        values['employee_id'] = current_user.employee_id.id
                    else:
                        return {'status': 'error', 'message': 'No employee record found for current user'}
                
                # Handle date safely
                if kw.get('date'):
                    values['date'] = kw['date']
                else:
                    # Use current date without relying on context_today
                    from datetime import date
                    values['date'] = date.today().strftime('%Y-%m-%d')
                
                # Add description if provided
                if kw.get('description'):
                    values['description'] = kw['description']

                # Create the timesheet record
                timesheet = request.env['team.project.timesheet'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_timesheet_data(timesheet)}

            # Di dalam metode manage_timesheets di TeamProjectAPI
            elif operation == 'list':
                domain = []
                
                # Optional filtering by task
                if kw.get('task_id'):
                    domain.append(('task_id', '=', int(kw['task_id'])))
                
                # Other optional filters
                if kw.get('date_from'):
                    domain.append(('date', '>=', kw['date_from']))
                if kw.get('date_to'):
                    domain.append(('date', '<=', kw['date_to']))
                if kw.get('project_id'):
                    domain.append(('project_id', '=', int(kw['project_id'])))
                if kw.get('task_name'):
                    # Search tasks by name first, then filter timesheets by those task IDs
                    tasks = request.env['team.project.task'].sudo().search([
                        ('name', 'ilike', kw['task_name'])
                    ])
                    if tasks:
                        domain.append(('task_id', 'in', tasks.ids))
                    else:
                        # No matching tasks, return empty result
                        return {
                            'status': 'success',
                            'data': [],
                            'total': 0,
                            'stats': {
                                'total_hours': 0,
                                'weekly_hours': 0,
                                'team_members_count': 0,
                                'tasks_count': 0
                            }
                        }
                
                # Pagination
                page = int(kw.get('page', 1))
                limit = int(kw.get('limit', 10))
                offset = (page - 1) * limit
                
                # Get total count for pagination
                total_count = request.env['team.project.timesheet'].sudo().search_count(domain)
                
                # Get paginated timesheets
                timesheets = request.env['team.project.timesheet'].sudo().search(
                    domain, limit=limit, offset=offset, order='date desc'
                )
                
                # Calculate stats
                from datetime import date, timedelta
                
                # Weekly hours (current week)
                today = date.today()
                start_of_week = today - timedelta(days=today.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                
                weekly_timesheets = request.env['team.project.timesheet'].sudo().search([
                    ('date', '>=', start_of_week.strftime('%Y-%m-%d')),
                    ('date', '<=', end_of_week.strftime('%Y-%m-%d'))
                ] + domain)
                
                weekly_hours = sum(weekly_timesheets.mapped('hours'))
                
                # Total hours for all filtered timesheets
                all_timesheets = request.env['team.project.timesheet'].sudo().search(domain)
                total_hours = sum(all_timesheets.mapped('hours'))
                
                # Unique team members and tasks
                team_members_count = len(set(all_timesheets.mapped('employee_id.id')))
                tasks_count = len(set(all_timesheets.mapped('task_id.id')))
                
                return {
                    'status': 'success',
                    'data': [self._prepare_timesheet_data(timesheet) for timesheet in timesheets],
                    'total': total_count,
                    'stats': {
                        'total_hours': total_hours,
                        'weekly_hours': weekly_hours,
                        'team_members_count': team_members_count,
                        'tasks_count': tasks_count
                    }
                }

            elif operation == 'update':
                timesheet_id = kw.get('timesheet_id')
                if not timesheet_id:
                    return {'status': 'error', 'message': 'Missing timesheet_id'}
                timesheet = request.env['team.project.timesheet'].sudo().browse(int(timesheet_id))
                if not timesheet.exists():
                    return {'status': 'error', 'message': 'Timesheet not found'}

                update_values = {}
                for field in ['date', 'description']:
                    if field in kw:
                        update_values[field] = kw[field]
                
                if kw.get('hours'):
                    update_values['hours'] = float(kw['hours'])
                if kw.get('employee_id'):
                    update_values['employee_id'] = int(kw['employee_id'])

                timesheet.write(update_values)
                return {'status': 'success', 'data': self._prepare_timesheet_data(timesheet), 'message': 'Timesheet updated'}

            elif operation == 'delete':
                timesheet_id = kw.get('timesheet_id')
                if not timesheet_id:
                    return {'status': 'error', 'message': 'Missing timesheet_id'}
                timesheet = request.env['team.project.timesheet'].sudo().browse(int(timesheet_id))
                if not timesheet.exists():
                    return {'status': 'error', 'message': 'Timesheet not found'}
                timesheet.unlink()
                return {'status': 'success', 'message': 'Timesheet deleted'}

        except Exception as e:
            _logger.error(f"Error in manage_timesheets: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # Additional Helper Methods
    def _prepare_meeting_data(self, meeting):
        """Menyiapkan data rapat untuk respons API."""
        return {
            'id': meeting.id,
            'name': meeting.name,
            'project': {'id': meeting.project_id.id, 'name': meeting.project_id.name} if meeting.project_id else None,
            'organizer': {'id': meeting.organizer_id.id, 'name': meeting.organizer_id.name},
            'attendees': [{'id': a.id, 'name': a.name} for a in meeting.attendee_ids],
            'dates': {
                'start': self._format_datetime_jakarta(meeting.start_datetime),
                'end': self._format_datetime_jakarta(meeting.end_datetime),
                'duration': meeting.duration
            },
            'location': meeting.location,
            'virtual_location': meeting.virtual_location,
            'agenda': meeting.agenda,
            'notes': meeting.notes,
            'state': meeting.state,
            'action_items_count': len(meeting.action_items)
        }
    
    def _prepare_meeting_action_data(self, action):
        """Menyiapkan data item aksi rapat untuk respons API."""
        return {
            'id': action.id,
            'name': action.name,
            'meeting': {'id': action.meeting_id.id, 'name': action.meeting_id.name},
            'assigned_to': {'id': action.assigned_to.id, 'name': action.assigned_to.name},
            'due_date': self._format_datetime_jakarta(action.due_date) if action.due_date else False,
            'state': action.state,
            'notes': action.notes
        }
    
    def _prepare_bau_data(self, bau):
        """
        Prepare BAU data for API response.
        Includes time fields to match ContentManagementAPI format.
        """
        if not bau:
            return {}
            
        # Format time values
        time_start_str = self._format_time_float_to_string(bau.time_start if hasattr(bau, 'time_start') else False)
        time_end_str = self._format_time_float_to_string(bau.time_end if hasattr(bau, 'time_end') else False)
        
        # Prepare project info
        project_data = False
        if bau.project_id:
            project_data = {
                'id': bau.project_id.id,
                'name': bau.project_id.name
            }
        
        # Prepare verification info
        verified_by_data = False
        if bau.verified_by:
            verified_by_data = {
                'id': bau.verified_by.id,
                'name': bau.verified_by.name
            }
        
        # Prepare time info
        time_data = {
            'start': time_start_str,
            'end': time_end_str,
            'duration': bau.hours_spent
        }
        
        return {
            'id': bau.id,
            'name': bau.name,
            'project': project_data,
            'creator': {
                'id': bau.creator_id.id,
                'name': bau.creator_id.name,
                'position': bau.creator_id.job_id.name if hasattr(bau.creator_id, 'job_id') and bau.creator_id.job_id else ''
            },
            'date': bau.date,
            'activity_type': bau.activity_type,
            'hours_spent': bau.hours_spent,
            'description': bau.description,
            'state': bau.state,
            'verification': {
                'verified_by': verified_by_data,
                'date': bau.verification_date if hasattr(bau, 'verification_date') else False
            },
            'time': time_data,
            'impact_on_delivery': bau.impact_on_delivery if hasattr(bau, 'impact_on_delivery') else ''
        }
    
    def _prepare_checklist_data(self, checklist):
        """Menyiapkan data checklist untuk respons API."""
        return {
            'id': checklist.id,
            'name': checklist.name,
            'task': {'id': checklist.task_id.id, 'name': checklist.task_id.name} if checklist.task_id else None,
            'sequence': checklist.sequence if hasattr(checklist, 'sequence') else 0,
            'assigned_to': {'id': checklist.assigned_to.id, 'name': checklist.assigned_to.name} if hasattr(checklist, 'assigned_to') and checklist.assigned_to else None,
            'deadline': fields.Date.to_string(checklist.deadline) if hasattr(checklist, 'deadline') and checklist.deadline else False,
            'is_done': checklist.is_done if hasattr(checklist, 'is_done') else False,
            'notes': checklist.notes if hasattr(checklist, 'notes') else ''
        }
        
    def _prepare_timesheet_data(self, timesheet):
        """Menyiapkan data timesheet untuk respons API."""
        return {
            'id': timesheet.id,
            'task': {'id': timesheet.task_id.id, 'name': timesheet.task_id.name} if timesheet.task_id else None,
            'project': {'id': timesheet.project_id.id, 'name': timesheet.project_id.name} if hasattr(timesheet, 'project_id') and timesheet.project_id else None,
            'employee': {'id': timesheet.employee_id.id, 'name': timesheet.employee_id.name} if timesheet.employee_id else None,
            'date': self._format_datetime_jakarta(timesheet.date) if timesheet.date else False,
            'hours': timesheet.hours if hasattr(timesheet, 'hours') else 0.0,
            'description': timesheet.description if hasattr(timesheet, 'description') else ''
        }
    
    @http.route('/web/v2/team/task-types', type='json', auth='user', methods=['POST'], csrf=False)
    def get_task_types(self, **kw):
        """Get task types for team projects."""
        try:
            task_types = request.env['team.project.task.type'].sudo().search_read(
                [], ['id', 'name', 'description', 'color', 'default_planned_hours']
            )
            
            return {
                'status': 'success',
                'data': task_types
            }
        except Exception as e:
            _logger.error(f"Error in get_task_types: {str(e)}")
            return {'status': 'error', 'message': str(e)}
            
    @http.route('/web/v2/team/tasks/departments', type='json', auth='user', methods=['POST'], csrf=False)
    def get_departments_with_tasks(self, **kw):
        """Get departments that have tasks."""
        try:
            # Get all departments that have tasks
            query = """
                SELECT DISTINCT d.id, d.name, COUNT(t.id) as task_count
                FROM hr_department d
                JOIN team_project p ON p.department_id = d.id
                JOIN team_project_task t ON t.project_id = p.id
                GROUP BY d.id, d.name
                ORDER BY d.name
            """
            request.env.cr.execute(query)
            departments = request.env.cr.dictfetchall()
            
            return {
                'status': 'success',
                'data': departments
            }
        except Exception as e:
            _logger.error(f"Error in get_departments_with_tasks: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/team/messages', type='json', auth='user', methods=['POST'], csrf=False)
    def get_group_messages(self, **kw):
        """Mengambil pesan-pesan dari grup kolaborasi."""
        try:
            group_id = kw.get('group_id')
            if not group_id:
                return {'status': 'error', 'message': 'Missing group_id'}
                    
            # Limit dan offset opsional untuk pagination
            limit = int(kw.get('limit', 50))
            offset = int(kw.get('offset', 0))
            
            # Flag untuk menyertakan attachment
            include_attachments = kw.get('include_attachments', True)
            
            # Ambil pesan-pesan dari grup
            domain = [('group_id', '=', int(group_id))]
            messages = request.env['team.project.message'].sudo().search(
                domain, limit=limit, offset=offset, order='date desc'
            )
            
            # Siapkan data pesan dengan attachment
            message_data = []
            for message in messages:
                msg_data = self._prepare_message_data(message)
                
                # Tambahkan data attachment jika diminta
                if include_attachments and message.attachment_ids:
                    msg_data['attachments'] = []
                    for attachment in message.attachment_ids:
                        msg_data['attachments'].append({
                            'id': attachment.id,
                            'name': attachment.name,
                            'mimetype': attachment.mimetype,
                            'size': attachment.file_size,
                            'url': f'/web/content/{attachment.id}?download=true',
                            'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False,
                            'create_date': fields.Datetime.to_string(attachment.create_date),
                            'create_uid': {
                                'id': attachment.create_uid.id,
                                'name': attachment.create_uid.name
                            }
                        })
                
                message_data.append(msg_data)
            
            return {
                'status': 'success',
                'data': message_data,
                'total': request.env['team.project.message'].sudo().search_count(domain)
            }
        except Exception as e:
            _logger.error(f"Error in get_group_messages: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # DASHBOARD
    # Add these endpoints to your TeamProjectAPI class in controllers/team_project_api.py
    @http.route('/web/v2/team/task/timesheets/list', type='json', auth='user', methods=['POST'], csrf=False)
    def list_timesheets(self, **kw):
        """Get a list of timesheets with filtering and pagination support."""
        try:
            # Build domain filter
            domain = []
            
            # Handle project filter
            if kw.get('project_id'):
                domain.append(('project_id', '=', int(kw['project_id'])))
            
            # Handle task name filter (via search on related task)
            if kw.get('task_name'):
                task_name = kw['task_name']
                # Search for tasks with this name
                task_ids = request.env['team.project.task'].sudo().search([
                    ('name', 'ilike', task_name)
                ]).ids
                if task_ids:
                    domain.append(('task_id', 'in', task_ids))
                else:
                    # If no tasks match, return empty result
                    return {
                        'status': 'success',
                        'data': [],
                        'total': 0,
                        'stats': self._get_timesheet_stats(domain)
                    }
            
            # Handle date range filters
            if kw.get('date_from'):
                domain.append(('date', '>=', kw['date_from']))
            if kw.get('date_to'):
                domain.append(('date', '<=', kw['date_to']))
            
            # Handle employee filter
            if kw.get('employee_id'):
                domain.append(('employee_id', '=', int(kw['employee_id'])))
            
            # Pagination parameters
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 10))
            offset = (page - 1) * limit

            # Get total count for pagination
            total_count = request.env['team.project.timesheet'].sudo().search_count(domain)
            
            # Get timesheet entries
            timesheets = request.env['team.project.timesheet'].sudo().search(
                domain, limit=limit, offset=offset, order='date desc, id desc'
            )
            
            # Format the data for frontend
            timesheet_data = [self._prepare_timesheet_data(timesheet) for timesheet in timesheets]
            
            # Get statistics for display
            stats = self._get_timesheet_stats(domain)
            
            return {
                'status': 'success',
                'data': timesheet_data,
                'total': total_count,
                'stats': stats
            }
            
        except Exception as e:
            _logger.error(f"Error in list_timesheets: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_timesheet_stats(self, domain):
        """Calculate timesheet statistics based on the given domain."""
        try:
            # Get all timesheets matching domain for statistics
            all_timesheets = request.env['team.project.timesheet'].sudo().search(domain)
            
            # Total hours
            total_hours = sum(all_timesheets.mapped('hours'))
            
            # Get current week timesheets
            today = fields.Date.today()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            weekly_domain = domain + [
                ('date', '>=', week_start),
                ('date', '<=', week_end)
            ]
            weekly_timesheets = request.env['team.project.timesheet'].sudo().search(weekly_domain)
            weekly_hours = sum(weekly_timesheets.mapped('hours'))
            
            # Count unique team members
            team_members_count = len(set(all_timesheets.mapped('employee_id.id')))
            
            # Count unique tasks
            tasks_count = len(set(all_timesheets.mapped('task_id.id')))
            
            return {
                'total_hours': round(total_hours, 1),
                'weekly_hours': round(weekly_hours, 1),
                'team_members_count': team_members_count,
                'tasks_count': tasks_count
            }
        except Exception as e:
            _logger.error(f"Error calculating timesheet stats: {str(e)}")
            return {
                'total_hours': 0,
                'weekly_hours': 0,
                'team_members_count': 0,
                'tasks_count': 0
            }

    @http.route('/web/v2/team/task/timesheets/export', type='json', auth='user', methods=['POST'], csrf=False)
    def export_timesheets(self, **kw):
        """Export timesheets to CSV format."""
        try:
            # Build domain filter (similar to list_timesheets)
            domain = []
            
            if kw.get('project_id'):
                domain.append(('project_id', '=', int(kw['project_id'])))
                
            if kw.get('task_name'):
                task_name = kw['task_name']
                task_ids = request.env['team.project.task'].sudo().search([
                    ('name', 'ilike', task_name)
                ]).ids
                if task_ids:
                    domain.append(('task_id', 'in', task_ids))
            
            if kw.get('date_from'):
                domain.append(('date', '>=', kw['date_from']))
            if kw.get('date_to'):
                domain.append(('date', '<=', kw['date_to']))
            
            if kw.get('employee_id'):
                domain.append(('employee_id', '=', int(kw['employee_id'])))
            
            # Get all matching timesheet entries without pagination
            timesheets = request.env['team.project.timesheet'].sudo().search(domain, order='date desc, id desc')
            
            # Generate CSV data
            csv_data = "Date,Task,Project,Employee,Hours,Description\n"
            
            for ts in timesheets:
                # Format date
                date_str = fields.Date.to_string(ts.date)
                
                # Get related data
                task_name = ts.task_id.name.replace(',', ' ') if ts.task_id.name else '-'
                project_name = ts.project_id.name.replace(',', ' ') if ts.project_id.name else '-'
                employee_name = ts.employee_id.name.replace(',', ' ') if ts.employee_id.name else '-'
                
                # Format description (escape commas and newlines)
                description = (ts.description or '-').replace(',', ' ').replace('\n', ' ').replace('\r', ' ')
                
                # Add row to CSV
                csv_data += f"{date_str},{task_name},{project_name},{employee_name},{ts.hours},{description}\n"
                
            return {
                'status': 'success',
                'data': csv_data
            }
            
        except Exception as e:
            _logger.error(f"Error in export_timesheets: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/reports/timesheet', type='json', auth='user', methods=['POST'], csrf=False)
    def generate_timesheet_report(self, **kw):
        """Generate timesheet reports with different aggregation options."""
        try:
            # Get report parameters
            report_type = kw.get('report_type', 'employee')  # Default: by employee
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            employee_id = kw.get('employee_id') and int(kw['employee_id'])
            project_id = kw.get('project_id') and int(kw['project_id'])
            
            if not date_from or not date_to:
                return {'status': 'error', 'message': 'Date range is required for report generation'}
            
            # Build base domain
            domain = [
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ]
            
            if employee_id:
                domain.append(('employee_id', '=', employee_id))
            
            if project_id:
                domain.append(('project_id', '=', project_id))
            
            # Get all matching timesheet entries
            timesheets = request.env['team.project.timesheet'].sudo().search(domain)
            
            # Generate report based on type
            report_data = []
            
            if report_type == 'employee':
                # Group by employee
                employee_data = {}
                
                for ts in timesheets:
                    employee_id = ts.employee_id.id
                    if employee_id not in employee_data:
                        employee_data[employee_id] = {
                            'name': ts.employee_id.name,
                            'hours': 0,
                            'percentage': 0,
                            'taskCount': 0,
                            'tasks': set()
                        }
                    
                    employee_data[employee_id]['hours'] += ts.hours
                    employee_data[employee_id]['tasks'].add(ts.task_id.id)
                
                # Calculate percentages and task counts
                total_hours = sum(data['hours'] for data in employee_data.values())
                
                for emp_id, data in employee_data.items():
                    data['taskCount'] = len(data['tasks'])
                    data['percentage'] = (data['hours'] / total_hours * 100) if total_hours else 0
                    del data['tasks']  # Remove temporary set
                    report_data.append(data)
                    
            elif report_type == 'project':
                # Group by project
                project_data = {}
                
                for ts in timesheets:
                    project_id = ts.project_id.id
                    if project_id not in project_data:
                        project_data[project_id] = {
                            'name': ts.project_id.name,
                            'hours': 0,
                            'percentage': 0,
                            'employeeCount': 0,
                            'employees': set()
                        }
                    
                    project_data[project_id]['hours'] += ts.hours
                    project_data[project_id]['employees'].add(ts.employee_id.id)
                
                # Calculate percentages and employee counts
                total_hours = sum(data['hours'] for data in project_data.values())
                
                for proj_id, data in project_data.items():
                    data['employeeCount'] = len(data['employees'])
                    data['percentage'] = (data['hours'] / total_hours * 100) if total_hours else 0
                    del data['employees']  # Remove temporary set
                    report_data.append(data)
                    
            elif report_type == 'task':
                # Group by task
                for ts in timesheets:
                    report_data.append({
                        'name': ts.task_id.name,
                        'project': ts.project_id.name,
                        'employee': ts.employee_id.name,
                        'hours': ts.hours
                    })
                    
            elif report_type == 'date':
                # Group by date
                date_data = {}
                
                for ts in timesheets:
                    date_str = fields.Date.to_string(ts.date)
                    if date_str not in date_data:
                        date_data[date_str] = {
                            'date': date_str,
                            'hours': 0,
                            'taskCount': 0,
                            'employeeCount': 0,
                            'tasks': set(),
                            'employees': set()
                        }
                    
                    date_data[date_str]['hours'] += ts.hours
                    date_data[date_str]['tasks'].add(ts.task_id.id)
                    date_data[date_str]['employees'].add(ts.employee_id.id)
                
                # Calculate task and employee counts
                for date_str, data in date_data.items():
                    data['taskCount'] = len(data['tasks'])
                    data['employeeCount'] = len(data['employees'])
                    del data['tasks']
                    del data['employees']
                    report_data.append(data)
            
            return {
                'status': 'success',
                'data': report_data
            }
            
        except Exception as e:
            _logger.error(f"Error in generate_timesheet_report: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/session/get_employees', type='json', auth='user', methods=['POST'], csrf=False)
    def get_employees(self, **kw):
        """Get list of employees for dropdown selection and Gantt chart."""
        try:
            # Get filter parameters
            project_id = kw.get('project_id')
            department_id = kw.get('department_id')
            
            domain = []
            
            # Add filters if provided
            if project_id:
                # Get employees from specific project
                project = request.env['team.project'].sudo().browse(int(project_id))
                if project.exists():
                    # Get the employee IDs from this project's team
                    team_ids = project.team_ids.ids
                    if project.project_manager_id:
                        team_ids.append(project.project_manager_id.id)
                    
                    if team_ids:
                        domain.append(('id', 'in', team_ids))
            
            if department_id:
                domain.append(('department_id', '=', int(department_id)))
            
            # Search for employees with given domain
            employees = request.env['hr.employee'].sudo().search(domain)
            
            # Prepare response data with employee details
            employee_data = []
            for employee in employees:
                emp_data = {
                    'id': employee.id,
                    'name': employee.name,
                    'job_title': employee.job_id.name if employee.job_id else '',
                    'department': employee.department_id.name if employee.department_id else '',
                    'email': employee.work_email or '',
                    'phone': employee.work_phone or '',
                }
                
                # Add photo if available
                if employee.image_128:
                    emp_data['avatar'] = f"data:image/png;base64,{employee.image_128.decode('utf-8')}"
                
                employee_data.append(emp_data)
            
            return {
                'status': 'success',
                'data': employee_data
            }
        except Exception as e:
            _logger.error(f"Error in get_employees: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    # Add these functions to your TeamProjectAPI class in controllers/team_project_api.py
    @http.route('/web/v2/team/reports/timesheet/analytics', type='json', auth='user', methods=['POST'], csrf=False)
    def timesheet_analytics(self, **kw):
        """Generate analytics data for timesheet dashboards."""
        try:
            # Get parameters
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            employee_id = kw.get('employee_id') and int(kw['employee_id'])
            project_id = kw.get('project_id') and int(kw['project_id'])
            
            if not date_from or not date_to:
                return {'status': 'error', 'message': 'Date range is required for analytics'}
                
            # Build base domain
            domain = [
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ]
            
            if employee_id:
                domain.append(('employee_id', '=', employee_id))
            if project_id:
                domain.append(('project_id', '=', project_id))
                
            # Get daily distribution data
            daily_distribution = self._get_daily_distribution(domain)
            
            # Get productivity metrics
            productivity_metrics = self._get_productivity_metrics(domain)
            
            # Get summary distribution data
            summary_distribution = self._get_summary_distribution(domain)
            
            return {
                'status': 'success',
                'data': {
                    'daily_distribution': daily_distribution,
                    'productivity_metrics': productivity_metrics,
                    'summary_distribution': summary_distribution
                }
            }
        
        except Exception as e:
            _logger.error(f"Error in timesheet_analytics: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_daily_distribution(self, domain):
        """Get daily distribution of hours for the week days."""
        try:
            # Create a dictionary to store hours by day of week
            days_of_week = {
                0: {'label': 'Mon', 'hours': 0},
                1: {'label': 'Tue', 'hours': 0},
                2: {'label': 'Wed', 'hours': 0},
                3: {'label': 'Thu', 'hours': 0},
                4: {'label': 'Fri', 'hours': 0},
                5: {'label': 'Sat', 'hours': 0},
                6: {'label': 'Sun', 'hours': 0}
            }
            
            # Get timesheets matching domain
            timesheets = request.env['team.project.timesheet'].sudo().search(domain)
            
            # Group hours by day of week
            for ts in timesheets:
                # Convert date to day of week (0=Monday, 6=Sunday)
                day_of_week = fields.Date.from_string(ts.date).weekday()
                days_of_week[day_of_week]['hours'] += ts.hours
            
            # Convert to list format for frontend
            result = [days_of_week[i] for i in range(7)]
            
            # Calculate max hours for percentage calculation
            max_hours = max([day['hours'] for day in result]) if result else 0
            
            # Add height percentage for chart visualization
            for day in result:
                day['heightPercentage'] = (day['hours'] / max_hours * 100) if max_hours > 0 else 0
            
            return result
        
        except Exception as e:
            _logger.error(f"Error in _get_daily_distribution: {str(e)}")
            return []

    def _get_productivity_metrics(self, domain):
        """Calculate productivity metrics based on tasks and timesheets."""
        try:
            # Get all timesheets matching domain
            timesheets = request.env['team.project.timesheet'].sudo().search(domain)
            
            # Get unique tasks from timesheets
            task_ids = list(set(timesheets.mapped('task_id.id')))
            
            if not task_ids:
                return {
                    'completionRate': 0,
                    'utilization': 0,
                    'efficiency': 0
                }
            
            # Get tasks to check completion status
            tasks = request.env['team.project.task'].sudo().browse(task_ids)
            
            # Calculate completion rate
            total_tasks = len(tasks)
            completed_tasks = len(tasks.filtered(lambda t: t.state == 'done'))
            completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Calculate utilization
            # Sum of logged hours / Sum of planned hours (capped at 100%)
            total_logged_hours = sum(timesheets.mapped('hours'))
            total_planned_hours = sum(tasks.mapped('planned_hours'))
            utilization = min(100, (total_logged_hours / total_planned_hours * 100)) if total_planned_hours > 0 else 0
            
            # Calculate efficiency
            # This could be a complex metric, but we'll use a simple formula:
            # Average task progress / Average expected progress based on logged hours vs planned hours
            avg_progress = sum(tasks.mapped('progress')) / total_tasks if total_tasks > 0 else 0
            expected_progress = min(100, (total_logged_hours / total_planned_hours * 100)) if total_planned_hours > 0 else 0
            
            # If expected_progress is 0 (no planned hours), use a default value
            if expected_progress == 0:
                efficiency = avg_progress  # Just use average progress
            else:
                # Compare actual progress to expected progress, capped at 120%
                efficiency = min(120, (avg_progress / expected_progress * 100))
            
            return {
                'completionRate': round(completion_rate),
                'utilization': round(utilization),
                'efficiency': round(efficiency)
            }
        
        except Exception as e:
            _logger.error(f"Error in _get_productivity_metrics: {str(e)}")
            return {
                'completionRate': 0,
                'utilization': 0,
                'efficiency': 0
            }

    def _get_summary_distribution(self, domain):
        """Get summary of time distribution based on report type context."""
        try:
            # Get context from parameters, default to project
            context_type = domain.get('context_type', 'project')
            
            # Get all timesheets
            timesheets = request.env['team.project.timesheet'].sudo().search(domain)
            
            if not timesheets:
                return []
                
            result = []
            
            if context_type == 'project':
                # Group by project
                project_data = {}
                
                for ts in timesheets:
                    project_id = ts.project_id.id
                    if project_id not in project_data:
                        project_data[project_id] = {
                            'name': ts.project_id.name or 'Undefined',
                            'hours': 0
                        }
                    project_data[project_id]['hours'] += ts.hours
                
                result = list(project_data.values())
                
            elif context_type == 'employee':
                # Group by employee
                employee_data = {}
                
                for ts in timesheets:
                    employee_id = ts.employee_id.id
                    if employee_id not in employee_data:
                        employee_data[employee_id] = {
                            'name': ts.employee_id.name or 'Undefined',
                            'hours': 0
                        }
                    employee_data[employee_id]['hours'] += ts.hours
                
                result = list(employee_data.values())
                
            elif context_type == 'task':
                # Group by task type
                type_data = {}
                
                for ts in timesheets:
                    # Use task type if available, otherwise "Undefined"
                    type_name = ts.task_id.type_id.name if ts.task_id.type_id else 'Undefined'
                    type_key = type_name  # Using name as key
                    
                    if type_key not in type_data:
                        type_data[type_key] = {
                            'name': type_name,
                            'hours': 0
                        }
                    type_data[type_key]['hours'] += ts.hours
                
                result = list(type_data.values())
                
            else:  # 'date' or any other fallback
                # Group by week
                week_data = {}
                
                for ts in timesheets:
                    # Get ISO week number
                    date_obj = fields.Date.from_string(ts.date)
                    year, week_num, _ = date_obj.isocalendar()
                    week_key = f"Week {week_num}"
                    
                    if week_key not in week_data:
                        week_data[week_key] = {
                            'name': week_key,
                            'hours': 0
                        }
                    week_data[week_key]['hours'] += ts.hours
                
                result = list(week_data.values())
            
            # Calculate total hours for percentage
            total_hours = sum(item['hours'] for item in result)
            
            # Add percentage to each item
            for item in result:
                item['percentage'] = (item['hours'] / total_hours * 100) if total_hours > 0 else 0
            
            # Sort by hours in descending order
            result.sort(key=lambda x: x['hours'], reverse=True)
            
            return result
        
        except Exception as e:
            _logger.error(f"Error in _get_summary_distribution: {str(e)}")
            return []
    
    # Add these endpoints to your TeamProjectAPI class in controllers/team_project_api.py
    @http.route('/web/v2/team/dashboard/summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_summary(self, **kw):
        """Get project dashboard summary statistics with completion tracking information."""
        try:
            # Get optional department filter
            department_id = kw.get('department_id') and int(kw['department_id'])
            
            # Build domain for projects
            project_domain = []
            if department_id:
                project_domain.append(('department_id', '=', department_id))
                
            # Get projects based on domain
            projects = request.env['team.project'].sudo().search(project_domain)
            
            # Calculate summary statistics
            total_projects = len(projects)
            active_projects = len(projects.filtered(lambda p: p.state == 'in_progress'))
            completed_projects = len(projects.filtered(lambda p: p.state == 'completed'))
            
            # Get completion statistics
            on_time_completed = len(projects.filtered(lambda p: p.state == 'completed' and p.is_on_time))
            delayed_completed = len(projects.filtered(lambda p: p.state == 'completed' and not p.is_on_time))
            
            # Calculate on-time completion rate
            on_time_completion_rate = (on_time_completed / completed_projects * 100) if completed_projects else 0
            
            # Calculate average delay for delayed projects
            delayed_projects = projects.filtered(lambda p: p.state == 'completed' and not p.is_on_time)
            avg_delay_days = sum(delayed_projects.mapped('days_delayed')) / len(delayed_projects) if delayed_projects else 0
            
            # Get total planned hours vs actual hours
            total_planned_hours = sum(projects.mapped('planned_hours'))
            total_actual_hours = sum(projects.mapped('actual_hours'))
            hours_efficiency = (total_planned_hours / total_actual_hours) * 100 if total_actual_hours else 0
            
            # Get task statistics
            tasks = request.env['team.project.task'].sudo().search([('project_id', 'in', projects.ids)])
            total_tasks = len(tasks)
            completed_tasks = len(tasks.filtered(lambda t: t.state == 'done'))
            
            task_completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks else 0
            
            # Get upcoming deadlines
            today = fields.Date.today()
            upcoming_deadline = today + timedelta(days=14)  # Next 14 days
            
            upcoming_tasks = request.env['team.project.task'].sudo().search([
                ('project_id', 'in', projects.ids),
                ('state', 'not in', ['done', 'cancelled']),
                ('planned_date_end', '>=', today),
                ('planned_date_end', '<=', upcoming_deadline)
            ], limit=5, order='planned_date_end')
            
            upcoming_tasks_data = [self._prepare_task_data(task) for task in upcoming_tasks]
            
            # Get project progress data for visualization
            project_progress_data = []
            for project in projects:
                if project.state not in ['cancelled', 'draft']:
                    project_progress_data.append({
                        'id': project.id,
                        'name': project.name,
                        'progress': project.progress,
                        'state': project.state,
                        'tasks_count': len(project.task_ids),
                        'tasks_completed': len(project.task_ids.filtered(lambda t: t.state == 'done')),
                        'is_on_time': project.is_on_time if project.state == 'completed' else None,
                        'days_delayed': project.days_delayed if project.state == 'completed' and not project.is_on_time else 0,
                        'actual_end_date': fields.Date.to_string(project.actual_date_end) if project.actual_date_end else None
                    })
                    
            # Sort by progress for visualization
            project_progress_data.sort(key=lambda p: p['progress'])
            
            # Get delayed projects for detailed reporting
            delayed_projects_data = []
            for project in delayed_projects:
                delayed_projects_data.append({
                    'id': project.id,
                    'name': project.name,
                    'planned_end_date': fields.Date.to_string(project.date_end),
                    'actual_end_date': fields.Date.to_string(project.actual_date_end),
                    'days_delayed': project.days_delayed,
                    'progress': project.progress
                })
                
            # Sort by delay days (highest first)
            delayed_projects_data.sort(key=lambda p: p['days_delayed'], reverse=True)
            
            return {
                'status': 'success',
                'data': {
                    'summary': {
                        'total_projects': total_projects,
                        'active_projects': active_projects,
                        'completed_projects': completed_projects,
                        'on_time_completed': on_time_completed,
                        'delayed_completed': delayed_completed,
                        'on_time_completion_rate': round(on_time_completion_rate, 1),
                        'avg_delay_days': round(avg_delay_days, 1),
                        'total_tasks': total_tasks,
                        'completed_tasks': completed_tasks,
                        'task_completion_rate': round(task_completion_rate, 1),
                        'total_planned_hours': round(total_planned_hours, 1),
                        'total_actual_hours': round(total_actual_hours, 1),
                        'hours_efficiency': round(hours_efficiency, 1)
                    },
                    'upcoming_tasks': upcoming_tasks_data,
                    'project_progress': project_progress_data[:10],  # Limit to top 10 projects
                    'delayed_projects': delayed_projects_data
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_dashboard_summary: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/dashboard/activity', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_activity(self, **kw):
        """Get recent activity for dashboard."""
        try:
            # Get optional filters
            department_id = kw.get('department_id') and int(kw['department_id'])
            limit = int(kw.get('limit', 10))
            
            # Build domain for projects
            project_domain = []
            if department_id:
                project_domain.append(('department_id', '=', department_id))
                
            # Get projects based on domain
            projects = request.env['team.project'].sudo().search(project_domain)
            project_ids = projects.ids
            
            # Recent completed tasks
            recent_tasks = request.env['team.project.task'].sudo().search([
                ('project_id', 'in', project_ids),
                ('state', '=', 'done'),
                ('actual_date_end', '!=', False)
            ], limit=limit, order='actual_date_end desc')
            
            # Recent timesheet entries
            recent_timesheets = request.env['team.project.timesheet'].sudo().search([
                ('project_id', 'in', project_ids)
            ], limit=limit, order='create_date desc')
            
            # Recent meetings
            recent_meetings = request.env['team.project.meeting'].sudo().search([
                ('project_id', 'in', project_ids),
                ('state', 'in', ['done', 'in_progress'])
            ], limit=limit, order='start_datetime desc')
            
            # Format activity data
            activity_data = []
            
            # Add tasks to activity
            for task in recent_tasks:
                activity_data.append({
                    'type': 'task',
                    'id': task.id,
                    'title': task.name,
                    'project': {
                        'id': task.project_id.id,
                        'name': task.project_id.name
                    },
                    'user': {
                        'id': task.assigned_to[0].id if task.assigned_to else False,
                        'name': task.assigned_to[0].name if task.assigned_to else 'Unassigned'
                    },
                    'date': self._format_datetime_jakarta(task.actual_date_end),
                    'description': f"Task completed"
                })
                
            # Add timesheets to activity
            for timesheet in recent_timesheets:
                activity_data.append({
                    'type': 'timesheet',
                    'id': timesheet.id,
                    'title': timesheet.task_id.name or 'Time Entry',
                    'project': {
                        'id': timesheet.project_id.id,
                        'name': timesheet.project_id.name
                    },
                    'user': {
                        'id': timesheet.employee_id.id,
                        'name': timesheet.employee_id.name
                    },
                    'date': self._format_datetime_jakarta(timesheet.create_date),
                    'description': f"{timesheet.hours} hours logged" + (f": {timesheet.description}" if timesheet.description else "")
                })
                
            # Add meetings to activity
            for meeting in recent_meetings:
                activity_data.append({
                    'type': 'meeting',
                    'id': meeting.id,
                    'title': meeting.name,
                    'project': {
                        'id': meeting.project_id.id,
                        'name': meeting.project_id.name
                    },
                    'user': {
                        'id': meeting.organizer_id.id,
                        'name': meeting.organizer_id.name
                    },
                    'date': self._format_datetime_jakarta(meeting.start_datetime),
                    'description': f"Meeting {meeting.state}"
                })
                
            # Sort all activity by date (newest first)
            activity_data.sort(key=lambda x: x['date'], reverse=True)
            
            return {
                'status': 'success',
                'data': activity_data[:limit]  # Limit to requested number
            }
        except Exception as e:
            _logger.error(f"Error in get_dashboard_activity: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/dashboard/workload', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_workload(self, **kw):
        """Get team workload statistics for dashboard."""
        try:
            # Get optional department filter
            department_id = kw.get('department_id') and int(kw['department_id'])
            
            # Build domain for projects
            project_domain = [('state', '=', 'in_progress')]
            if department_id:
                project_domain.append(('department_id', '=', department_id))
                
            # Get active projects
            active_projects = request.env['team.project'].sudo().search(project_domain)
            
            # Get all team members from active projects
            team_members = request.env['hr.employee']
            for project in active_projects:
                team_members |= project.team_ids
                team_members |= project.project_manager_id
                
            # Remove duplicates
            team_members = team_members.sorted(key=lambda e: e.name)
            
            # Calculate workload for each team member
            workload_data = []
            
            for employee in team_members:
                # Count assigned tasks
                assigned_tasks = request.env['team.project.task'].sudo().search([
                    ('project_id', 'in', active_projects.ids),
                    ('assigned_to', 'in', [employee.id]),
                    ('state', 'not in', ['done', 'cancelled'])
                ])
                
                # Get last 7 days timesheets
                today = fields.Date.today()
                week_start = today - timedelta(days=7)
                
                recent_timesheets = request.env['team.project.timesheet'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('date', '>=', week_start),
                    ('date', '<=', today)
                ])
                
                # Calculate hours per day
                hours_logged = sum(recent_timesheets.mapped('hours'))
                days_worked = len(set(recent_timesheets.mapped('date')))
                hours_per_day = hours_logged / max(days_worked, 1)
                
                # Calculate workload score (0-100%)
                # Consider: task count, priority, and hours per day
                task_count = len(assigned_tasks)
                high_priority_count = len(assigned_tasks.filtered(lambda t: t.priority in ['2', '3']))
                
                # Base workload on task count (0-40%)
                task_factor = min(40, task_count * 10)
                
                # Add high priority impact (0-30%)
                priority_factor = min(30, high_priority_count * 15)
                
                # Add hours impact (0-30%)
                hours_factor = min(30, hours_per_day * 5)  # 6 hours/day = 30%
                
                # Calculate total workload score
                workload_score = task_factor + priority_factor + hours_factor
                
                # Determine workload level
                if workload_score < 30:
                    workload_level = 'low'
                elif workload_score < 70:
                    workload_level = 'medium'
                else:
                    workload_level = 'high'
                    
                # Add to results
                workload_data.append({
                    'employee': {
                        'id': employee.id,
                        'name': employee.name
                    },
                    'assigned_tasks': task_count,
                    'high_priority_tasks': high_priority_count,
                    'recent_hours': round(hours_logged, 1),
                    'hours_per_day': round(hours_per_day, 1),
                    'workload_score': workload_score,
                    'workload_level': workload_level,
                    'projects': [{
                        'id': task.project_id.id,
                        'name': task.project_id.name
                    } for task in assigned_tasks]
                })
                
            return {
                'status': 'success',
                'data': workload_data
            }
        except Exception as e:
            _logger.error(f"Error in get_dashboard_workload: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/dashboard/timeline', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_timeline(self, **kw):
        """Get project timeline data for Gantt chart."""
        try:
            # Get optional department filter
            department_id = kw.get('department_id') and int(kw['department_id'])
            
            # Build domain for projects
            project_domain = [('state', 'not in', ['cancelled'])]
            if department_id:
                project_domain.append(('department_id', '=', department_id))
                
            # Get projects and their tasks
            projects = request.env['team.project'].sudo().search(project_domain, order='date_start')
            
            timeline_data = []
            
            # Add project timeline data
            for project in projects:
                # Get tasks with planned dates
                tasks_with_dates = project.task_ids.filtered(
                    lambda t: t.planned_date_start and t.planned_date_end and t.state not in ['cancelled']
                )
                
                project_data = {
                    'id': project.id,
                    'project_id': f"project_{project.id}",
                    'name': project.name,
                    'type': 'project',
                    'start': fields.Date.to_string(project.date_start),
                    'end': fields.Date.to_string(project.date_end),
                    'progress': project.progress,
                    'dependencies': [],
                    'style': {
                        'base': {
                            'fill': self._get_state_color(project.state),
                            'stroke': '#000000'
                        }
                    },
                    'children': []
                }
                
                # Add tasks to the project
                for task in tasks_with_dates:
                    task_data = {
                        'id': task.id,
                        'task_id': f"task_{task.id}",
                        'name': task.name,
                        'type': 'task',
                        'start': fields.Datetime.to_string(task.planned_date_start),
                        'end': fields.Datetime.to_string(task.planned_date_end),
                        'progress': task.progress,
                        'dependencies': [],
                        'style': {
                            'base': {
                                'fill': self._get_state_color(task.state),
                                'stroke': '#555555'
                            }
                        }
                    }
                    
                    # Add task dependencies
                    for dep in task.depends_on_ids:
                        if dep in tasks_with_dates:
                            task_data['dependencies'].append(f"task_{dep.id}")
                    
                    project_data['children'].append(task_data)
                    
                timeline_data.append(project_data)
                
            return {
                'status': 'success',
                'data': timeline_data
            }
        except Exception as e:
            _logger.error(f"Error in get_dashboard_timeline: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_state_color(self, state):
        """Get color for state visualization."""
        colors = {
            # Project states
            'draft': '#E0E0E0',
            'planning': '#FFD700',
            'in_progress': '#4CAF50',
            'on_hold': '#FFA500',
            'completed': '#2196F3',
            'cancelled': '#F44336',
            
            # Task states
            'planned': '#FFD700',
            'review': '#9C27B0',
            'done': '#2196F3'
        }
        return colors.get(state, '#E0E0E0')  # Default to light gray
    # Add these endpoints to your TeamProjectAPI class in controllers/team_project_api.py

    @http.route('/web/v2/team/dashboard/department-stats', type='json', auth='user', methods=['POST'], csrf=False)
    def get_department_stats(self, **kw):
        """Get project statistics grouped by department for dashboard visualization."""
        try:
            # Get all departments that have projects
            departments = request.env['hr.department'].sudo().search([])
            departments_with_projects = departments.filtered(lambda d: d.id in request.env['team.project'].sudo().mapped('department_id.id'))
            
            department_stats = []
            
            for department in departments_with_projects:
                # Get projects for this department
                projects = request.env['team.project'].sudo().search([('department_id', '=', department.id)])
                
                if not projects:
                    continue
                    
                total_projects = len(projects)
                active_projects = len(projects.filtered(lambda p: p.state == 'in_progress'))
                completed_projects = len(projects.filtered(lambda p: p.state == 'completed'))
                
                # Get total tasks and completed tasks
                all_tasks = request.env['team.project.task'].sudo().search([('project_id', 'in', projects.ids)])
                total_tasks = len(all_tasks)
                completed_tasks = len(all_tasks.filtered(lambda t: t.state == 'done'))
                
                # Calculate task completion rate
                task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks else 0
                
                # Calculate average project progress
                avg_progress = sum(projects.mapped('progress')) / total_projects if total_projects else 0
                
                department_stats.append({
                    'department': {
                        'id': department.id,
                        'name': department.name
                    },
                    'total_projects': total_projects,
                    'active_projects': active_projects,
                    'completed_projects': completed_projects,
                    'total_tasks': total_tasks,
                    'completed_tasks': completed_tasks,
                    'task_completion_rate': round(task_completion_rate, 1),
                    'avg_progress': round(avg_progress, 1)
                })
                
            return {
                'status': 'success',
                'data': department_stats
            }
        except Exception as e:
            _logger.error(f"Error in get_department_stats: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/dashboard/project-milestones', type='json', auth='user', methods=['POST'], csrf=False)
    def get_project_milestones(self, **kw):
        """Get important project milestones for dashboard timeline."""
        try:
            # Get optional filters
            department_id = kw.get('department_id') and int(kw['department_id'])
            days_ahead = int(kw.get('days_ahead', 30))
            
            # Calculate date range
            today = fields.Date.today()
            end_date = today + timedelta(days=days_ahead)
            
            # Build domain for projects
            project_domain = [
                ('state', 'not in', ['cancelled', 'completed']),
                ('date_end', '>=', today),
                ('date_end', '<=', end_date)
            ]
            
            if department_id:
                project_domain.append(('department_id', '=', department_id))
                
            # Get projects with end dates in the upcoming period
            projects = request.env['team.project'].sudo().search(project_domain, order='date_end')
            
            # Get tasks with due dates in the upcoming period
            task_domain = [
                ('state', 'not in', ['done', 'cancelled']),
                ('planned_date_end', '>=', today),
                ('planned_date_end', '<=', end_date)
            ]
            
            if department_id:
                # Get projects first then filter tasks
                project_ids = request.env['team.project'].sudo().search([
                    ('department_id', '=', department_id)
                ]).ids
                task_domain.append(('project_id', 'in', project_ids))
                
            tasks = request.env['team.project.task'].sudo().search(task_domain, order='planned_date_end')
            
            # Get meetings in the upcoming period
            meeting_domain = [
                ('start_datetime', '>=', fields.Datetime.now()),
                ('start_datetime', '<=', fields.Datetime.to_string(
                    fields.Datetime.from_string(fields.Datetime.now()) + timedelta(days=days_ahead)
                ))
            ]
            
            if department_id:
                # Get department projects first
                project_ids = request.env['team.project'].sudo().search([
                    ('department_id', '=', department_id)
                ]).ids
                meeting_domain.append(('project_id', 'in', project_ids))
                
            meetings = request.env['team.project.meeting'].sudo().search(meeting_domain, order='start_datetime')
            
            # Prepare milestone data
            milestones = []
            
            # Add project end dates
            for project in projects:
                days_to_deadline = (project.date_end - today).days
                
                milestones.append({
                    'type': 'project_deadline',
                    'id': project.id,
                    'title': f"Project deadline: {project.name}",
                    'date': fields.Date.to_string(project.date_end),
                    'days_remaining': days_to_deadline,
                    'status': 'warning' if days_to_deadline <= 7 else 'info',
                    'project': {
                        'id': project.id,
                        'name': project.name
                    },
                    'progress': project.progress
                })
                
            # Add task due dates
            for task in tasks:
                # Get due date from planned_date_end
                due_date = fields.Datetime.from_string(task.planned_date_end).date()
                days_to_deadline = (due_date - today).days
                
                milestones.append({
                    'type': 'task_deadline',
                    'id': task.id,
                    'title': f"Task due: {task.name}",
                    'date': fields.Date.to_string(due_date),
                    'days_remaining': days_to_deadline,
                    'status': 'danger' if days_to_deadline <= 2 else ('warning' if days_to_deadline <= 7 else 'info'),
                    'project': {
                        'id': task.project_id.id,
                        'name': task.project_id.name
                    },
                    'assigned_to': [{'id': emp.id, 'name': emp.name} for emp in task.assigned_to],
                    'progress': task.progress
                })
                
            # Add upcoming meetings
            for meeting in meetings:
                meeting_date = fields.Datetime.from_string(meeting.start_datetime).date()
                days_to_meeting = (meeting_date - today).days
                
                milestones.append({
                    'type': 'meeting',
                    'id': meeting.id,
                    'title': f"Meeting: {meeting.name}",
                    'date': fields.Date.to_string(meeting_date),
                    'time': fields.Datetime.from_string(meeting.start_datetime).strftime('%H:%M'),
                    'days_remaining': days_to_meeting,
                    'status': 'info',
                    'project': {
                        'id': meeting.project_id.id,
                        'name': meeting.project_id.name
                    },
                    'organizer': {
                        'id': meeting.organizer_id.id,
                        'name': meeting.organizer_id.name
                    }
                })
                
            # Sort by date
            milestones.sort(key=lambda x: x['date'])
            
            return {
                'status': 'success',
                'data': milestones
            }
        except Exception as e:
            _logger.error(f"Error in get_project_milestones: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/dashboard/task-distribution', type='json', auth='user', methods=['POST'], csrf=False)
    def get_task_distribution(self, **kw):
        """Get task distribution data for dashboard visualization."""
        try:
            # Get optional filters
            department_id = kw.get('department_id') and int(kw['department_id'])
            project_id = kw.get('project_id') and int(kw['project_id'])
            
            # Build domain for tasks
            domain = []
            
            if department_id:
                # Get department projects first
                project_ids = request.env['team.project'].sudo().search([
                    ('department_id', '=', department_id)
                ]).ids
                domain.append(('project_id', 'in', project_ids))
            
            if project_id:
                domain.append(('project_id', '=', project_id))
                
            # Get tasks
            tasks = request.env['team.project.task'].sudo().search(domain)
            
            # Distribution by state
            state_distribution = {}
            for task in tasks:
                state = task.state
                if state not in state_distribution:
                    state_distribution[state] = 0
                state_distribution[state] += 1
                
            # Format for chart
            state_labels = {
                'draft': 'Draft',
                'planned': 'Planned',
                'in_progress': 'In Progress',
                'review': 'In Review',
                'done': 'Done',
                'cancelled': 'Cancelled'
            }
            
            state_colors = {
                'draft': '#E0E0E0',
                'planned': '#FFD700',
                'in_progress': '#4CAF50',
                'review': '#9C27B0',
                'done': '#2196F3',
                'cancelled': '#F44336'
            }
            
            state_chart_data = [
                {
                    'label': state_labels.get(state, state),
                    'value': count,
                    'color': state_colors.get(state, '#E0E0E0')
                }
                for state, count in state_distribution.items()
            ]
            
            # Distribution by priority
            priority_distribution = {}
            for task in tasks:
                priority = task.priority
                if priority not in priority_distribution:
                    priority_distribution[priority] = 0
                priority_distribution[priority] += 1
                
            # Format for chart
            priority_labels = {
                '0': 'Low',
                '1': 'Medium',
                '2': 'High',
                '3': 'Critical'
            }
            
            priority_colors = {
                '0': '#2196F3',  # Blue
                '1': '#4CAF50',  # Green
                '2': '#FFA500',  # Orange
                '3': '#F44336'   # Red
            }
            
            priority_chart_data = [
                {
                    'label': priority_labels.get(priority, priority),
                    'value': count,
                    'color': priority_colors.get(priority, '#E0E0E0')
                }
                for priority, count in priority_distribution.items()
            ]
            
            # Get task count per project
            project_task_count = {}
            for task in tasks:
                project_id = task.project_id.id
                if project_id not in project_task_count:
                    project_task_count[project_id] = {
                        'project': {
                            'id': project_id,
                            'name': task.project_id.name
                        },
                        'total': 0,
                        'completed': 0
                    }
                project_task_count[project_id]['total'] += 1
                if task.state == 'done':
                    project_task_count[project_id]['completed'] += 1
                    
            # Format for chart
            project_chart_data = list(project_task_count.values())
            for project in project_chart_data:
                project['completion_rate'] = (project['completed'] / project['total'] * 100) if project['total'] > 0 else 0
                
            # Sort by total task count (descending)
            project_chart_data.sort(key=lambda x: x['total'], reverse=True)
            
            return {
                'status': 'success',
                'data': {
                    'by_state': state_chart_data,
                    'by_priority': priority_chart_data,
                    'by_project': project_chart_data[:10]  # Limit to top 10 projects
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_task_distribution: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    # Add these endpoints to your TeamProjectAPI class in controllers/team_project_api.py

    @http.route('/web/v2/team/dashboard/performance', type='json', auth='user', methods=['POST'], csrf=False)
    def get_project_performance(self, **kw):
        """Get project performance analytics for dashboard."""
        try:
            # Get optional filters
            project_id = kw.get('project_id') and int(kw['project_id'])
            department_id = kw.get('department_id') and int(kw['department_id'])
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            
            # Build domain
            project_domain = []
            if project_id:
                project_domain.append(('id', '=', project_id))
            if department_id:
                project_domain.append(('department_id', '=', department_id))
                
            # Get projects
            projects = request.env['team.project'].sudo().search(project_domain)
            
            if not projects:
                return {
                    'status': 'success',
                    'data': {
                        'efficiency': 0,
                        'on_time_completion': 0,
                        'budget_utilization': 0,
                        'team_allocation': 0,
                        'timeline': [],
                        'project_scores': []
                    }
                }
                
            # Calculate project performance metrics
            
            # 1. Time Efficiency (actual hours vs planned hours)
            all_planned_hours = sum(projects.mapped('planned_hours'))
            all_actual_hours = sum(projects.mapped('actual_hours'))
            time_efficiency = (all_planned_hours / all_actual_hours * 100) if all_actual_hours > 0 else 0
            
            # 2. On-time Task Completion
            all_tasks = request.env['team.project.task'].sudo().search([
                ('project_id', 'in', projects.ids),
                ('state', '=', 'done')
            ])
            
            on_time_tasks = 0
            for task in all_tasks:
                if task.planned_date_end and task.actual_date_end:
                    planned_end = fields.Datetime.from_string(task.planned_date_end)
                    actual_end = fields.Datetime.from_string(task.actual_date_end)
                    if actual_end <= planned_end:
                        on_time_tasks += 1
                        
            on_time_completion = (on_time_tasks / len(all_tasks) * 100) if all_tasks else 0
            
            # 3. Budget Utilization (mock data - assuming 100 is optimal)
            # In a real scenario, this would be calculated from budget tracking
            budget_utilization = 85  # Mock value
            
            # 4. Team Allocation (% of team members actively contributing)
            all_team_members = set()
            contributing_members = set()
            
            for project in projects:
                team_members = project.team_ids.ids + [project.project_manager_id.id]
                all_team_members.update(team_members)
                
                # Check timesheet entries
                for member_id in team_members:
                    timesheet_count = request.env['team.project.timesheet'].sudo().search_count([
                        ('employee_id', '=', member_id),
                        ('project_id', '=', project.id)
                    ])
                    
                    if timesheet_count > 0:
                        contributing_members.add(member_id)
                        
            team_allocation = (len(contributing_members) / len(all_team_members) * 100) if all_team_members else 0
            
            # 5. Project Timeline Progression
            timeline_data = []
            for project in projects:
                # Calculate total days in project
                total_days = (project.date_end - project.date_start).days
                if total_days <= 0:
                    continue
                    
                # Calculate days elapsed
                today = fields.Date.today()
                if today < project.date_start:
                    days_elapsed = 0
                elif today > project.date_end:
                    days_elapsed = total_days
                else:
                    days_elapsed = (today - project.date_start).days
                    
                # Calculate expected progress based on timeline
                time_progress = (days_elapsed / total_days * 100) if total_days > 0 else 0
                
                # Project progress from model
                actual_progress = project.progress
                
                # Add to timeline data
                timeline_data.append({
                    'project': {
                        'id': project.id,
                        'name': project.name
                    },
                    'time_progress': round(time_progress, 1),
                    'actual_progress': round(actual_progress, 1),
                    'variance': round(actual_progress - time_progress, 1),
                    'on_track': actual_progress >= time_progress
                })
                
            # 6. Calculate individual project performance scores
            project_scores = []
            for project in projects:
                # Check tasks
                project_tasks = request.env['team.project.task'].sudo().search([
                    ('project_id', '=', project.id)
                ])
                
                completed_tasks = len(project_tasks.filtered(lambda t: t.state == 'done'))
                total_tasks = len(project_tasks)
                task_completion = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
                
                # Time management score
                project_planned_hours = project.planned_hours or 0.1  # Avoid division by zero
                project_actual_hours = project.actual_hours or 0
                time_management = min(100, (project_planned_hours / project_actual_hours * 100)) if project_actual_hours > 0 else 100
                
                # On-time task completion
                on_time_project_tasks = 0
                for task in project_tasks.filtered(lambda t: t.state == 'done'):
                    if task.planned_date_end and task.actual_date_end:
                        planned_end = fields.Datetime.from_string(task.planned_date_end)
                        actual_end = fields.Datetime.from_string(task.actual_date_end)
                        if actual_end <= planned_end:
                            on_time_project_tasks += 1
                            
                on_time_delivery = (on_time_project_tasks / completed_tasks * 100) if completed_tasks > 0 else 0
                
                # Calculate overall performance score (weighted average)
                performance_score = (
                    task_completion * 0.4 +
                    time_management * 0.3 +
                    on_time_delivery * 0.3
                )
                
                project_scores.append({
                    'project': {
                        'id': project.id,
                        'name': project.name
                    },
                    'progress': round(project.progress, 1),
                    'task_completion': round(task_completion, 1),
                    'time_management': round(time_management, 1),
                    'on_time_delivery': round(on_time_delivery, 1),
                    'performance_score': round(performance_score, 1)
                })
                
            # Sort projects by performance score (descending)
            project_scores.sort(key=lambda x: x['performance_score'], reverse=True)
            
            return {
                'status': 'success',
                'data': {
                    'efficiency': round(time_efficiency, 1),
                    'on_time_completion': round(on_time_completion, 1),
                    'budget_utilization': round(budget_utilization, 1),
                    'team_allocation': round(team_allocation, 1),
                    'timeline': timeline_data,
                    'project_scores': project_scores
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_project_performance: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/dashboard/team-performance', type='json', auth='user', methods=['POST'], csrf=False)
    def get_team_performance(self, **kw):
        """Get team member performance analytics for dashboard."""
        try:
            # Get optional filters
            department_id = kw.get('department_id') and int(kw['department_id'])
            project_id = kw.get('project_id') and int(kw['project_id'])
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            
            # Build domain for timesheets
            timesheet_domain = []
            
            if project_id:
                timesheet_domain.append(('project_id', '=', project_id))
            elif department_id:
                # Get projects from department
                project_ids = request.env['team.project'].sudo().search([
                    ('department_id', '=', department_id)
                ]).ids
                
                if project_ids:
                    timesheet_domain.append(('project_id', 'in', project_ids))
                    
            # Date filters
            if date_from:
                timesheet_domain.append(('date', '>=', date_from))
            if date_to:
                timesheet_domain.append(('date', '<=', date_to))
                
            # Get timesheets
            timesheets = request.env['team.project.timesheet'].sudo().search(timesheet_domain)
            
            if not timesheets:
                return {
                    'status': 'success',
                    'data': {
                        'team_members': [],
                        'productivity_trend': [],
                        'skill_distribution': []
                    }
                }
                
            # Get employees from timesheets
            employee_ids = timesheets.mapped('employee_id.id')
            employees = request.env['hr.employee'].sudo().browse(employee_ids)
            
            # Calculate performance metrics for each team member
            team_member_data = []
            
            for employee in employees:
                employee_timesheets = timesheets.filtered(lambda t: t.employee_id.id == employee.id)
                
                if not employee_timesheets:
                    continue
                    
                # Get tasks for this employee
                task_ids = employee_timesheets.mapped('task_id.id')
                employee_tasks = request.env['team.project.task'].sudo().browse(task_ids)
                
                # Calculate metrics
                total_hours = sum(employee_timesheets.mapped('hours'))
                completed_tasks = len(employee_tasks.filtered(lambda t: t.state == 'done'))
                total_tasks = len(employee_tasks)
                task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
                
                # On-time task completion
                on_time_tasks = 0
                for task in employee_tasks.filtered(lambda t: t.state == 'done'):
                    if task.planned_date_end and task.actual_date_end:
                        planned_end = fields.Datetime.from_string(task.planned_date_end)
                        actual_end = fields.Datetime.from_string(task.actual_date_end)
                        if actual_end <= planned_end:
                            on_time_tasks += 1
                            
                on_time_rate = (on_time_tasks / completed_tasks * 100) if completed_tasks > 0 else 0
                
                # Calculate unique projects
                project_ids = employee_timesheets.mapped('project_id.id')
                
                # Calculate productivity (hours per task)
                productivity = (total_hours / total_tasks) if total_tasks > 0 else 0
                
                # Calculate performance score
                performance_score = (
                    task_completion_rate * 0.5 +
                    on_time_rate * 0.5
                )
                
                team_member_data.append({
                    'employee': {
                        'id': employee.id,
                        'name': employee.name
                    },
                    'total_hours': round(total_hours, 1),
                    'completed_tasks': completed_tasks,
                    'total_tasks': total_tasks,
                    'task_completion_rate': round(task_completion_rate, 1),
                    'on_time_rate': round(on_time_rate, 1),
                    'productivity': round(productivity, 2),
                    'project_count': len(project_ids),
                    'performance_score': round(performance_score, 1)
                })
                
            # Sort by performance score (descending)
            team_member_data.sort(key=lambda x: x['performance_score'], reverse=True)
            
            # Generate productivity trend (mock data)
            # In a real implementation, this would be calculated from historical data
            productivity_trend = [
                {'date': '2023-01-01', 'productivity': 85},
                {'date': '2023-02-01', 'productivity': 87},
                {'date': '2023-03-01', 'productivity': 82},
                {'date': '2023-04-01', 'productivity': 90},
                {'date': '2023-05-01', 'productivity': 92},
                {'date': '2023-06-01', 'productivity': 88}
            ]
            
            # Generate skill distribution (mock data)
            # In a real implementation, this would come from employee skills model
            skill_distribution = [
                {'skill': 'Project Management', 'count': 8},
                {'skill': 'Development', 'count': 12},
                {'skill': 'Design', 'count': 6},
                {'skill': 'Testing', 'count': 5},
                {'skill': 'Documentation', 'count': 4}
            ]
            
            return {
                'status': 'success',
                'data': {
                    'team_members': team_member_data,
                    'productivity_trend': productivity_trend,
                    'skill_distribution': skill_distribution
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_team_performance: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/dashboard/resource-allocation', type='json', auth='user', methods=['POST'], csrf=False)
    def get_resource_allocation(self, **kw):
        """Get resource allocation data for dashboard visualization."""
        try:
            # Get optional filters
            department_id = kw.get('department_id') and int(kw['department_id'])
            date_from = kw.get('date_from', fields.Date.to_string(fields.Date.today()))
            date_to = kw.get('date_to', fields.Date.to_string(fields.Date.today() + timedelta(days=30)))
            
            # Build domain for active projects
            project_domain = [('state', '=', 'in_progress')]
            if department_id:
                project_domain.append(('department_id', '=', department_id))
                
            # Get active projects
            active_projects = request.env['team.project'].sudo().search(project_domain)
            
            if not active_projects:
                return {
                    'status': 'success',
                    'data': {
                        'allocation_by_project': [],
                        'allocation_by_employee': [],
                        'project_resources': []
                    }
                }
                
            # Get all timesheets within date range for these projects
            timesheet_domain = [
                ('project_id', 'in', active_projects.ids),
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ]
            
            timesheets = request.env['team.project.timesheet'].sudo().search(timesheet_domain)
            
            # 1. Allocation by project
            project_allocation = {}
            
            for timesheet in timesheets:
                project_id = timesheet.project_id.id
                if project_id not in project_allocation:
                    project_allocation[project_id] = {
                        'project': {
                            'id': project_id,
                            'name': timesheet.project_id.name
                        },
                        'total_hours': 0,
                        'employee_count': set()
                    }
                    
                project_allocation[project_id]['total_hours'] += timesheet.hours
                project_allocation[project_id]['employee_count'].add(timesheet.employee_id.id)
                
            # Format output and calculate percentages
            allocation_by_project = []
            total_hours = sum(data['total_hours'] for data in project_allocation.values())
            
            for project_id, data in project_allocation.items():
                allocation_percentage = (data['total_hours'] / total_hours * 100) if total_hours > 0 else 0
                allocation_by_project.append({
                    'project': data['project'],
                    'hours': round(data['total_hours'], 1),
                    'percentage': round(allocation_percentage, 1),
                    'employee_count': len(data['employee_count'])
                })
                
            # Sort by hours (descending)
            allocation_by_project.sort(key=lambda x: x['hours'], reverse=True)
            
            # 2. Allocation by employee
            employee_allocation = {}
            
            for timesheet in timesheets:
                employee_id = timesheet.employee_id.id
                if employee_id not in employee_allocation:
                    employee_allocation[employee_id] = {
                        'employee': {
                            'id': employee_id,
                            'name': timesheet.employee_id.name
                        },
                        'total_hours': 0,
                        'projects': set(),
                        'project_allocation': {}
                    }
                    
                employee_allocation[employee_id]['total_hours'] += timesheet.hours
                employee_allocation[employee_id]['projects'].add(timesheet.project_id.id)
                
                # Track allocation per project
                project_id = timesheet.project_id.id
                if project_id not in employee_allocation[employee_id]['project_allocation']:
                    employee_allocation[employee_id]['project_allocation'][project_id] = {
                        'project': {
                            'id': project_id,
                            'name': timesheet.project_id.name
                        },
                        'hours': 0
                    }
                    
                employee_allocation[employee_id]['project_allocation'][project_id]['hours'] += timesheet.hours
                
            # Format output and calculate percentages
            allocation_by_employee = []
            
            for employee_id, data in employee_allocation.items():
                # Calculate project percentages
                project_allocation = []
                for project_data in data['project_allocation'].values():
                    percentage = (project_data['hours'] / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                    project_allocation.append({
                        'project': project_data['project'],
                        'hours': round(project_data['hours'], 1),
                        'percentage': round(percentage, 1)
                    })
                    
                # Sort project allocation by hours
                project_allocation.sort(key=lambda x: x['hours'], reverse=True)
                
                allocation_by_employee.append({
                    'employee': data['employee'],
                    'total_hours': round(data['total_hours'], 1),
                    'project_count': len(data['projects']),
                    'project_allocation': project_allocation
                })
                
            # Sort by total hours (descending)
            allocation_by_employee.sort(key=lambda x: x['total_hours'], reverse=True)
            
            # 3. Project resources overview
            project_resources = []
            
            for project in active_projects:
                # Get team members assigned to this project
                team_members = project.team_ids | project.project_manager_id
                
                # Get tasks for this project
                project_tasks = request.env['team.project.task'].sudo().search([
                    ('project_id', '=', project.id),
                    ('state', 'not in', ['cancelled', 'done'])
                ])
                
                # Get resource allocation
                team_allocation = {}
                for task in project_tasks:
                    for assignee in task.assigned_to:
                        if assignee.id not in team_allocation:
                            team_allocation[assignee.id] = {
                                'employee': {
                                    'id': assignee.id,
                                    'name': assignee.name
                                },
                                'task_count': 0
                            }
                        team_allocation[assignee.id]['task_count'] += 1
                        
                # Calculate allocation percentages
                assignee_data = list(team_allocation.values())
                total_task_assignments = sum(data['task_count'] for data in assignee_data)
                
                for data in assignee_data:
                    data['allocation_percentage'] = (data['task_count'] / total_task_assignments * 100) if total_task_assignments > 0 else 0
                    
                # Sort by task count (descending)
                assignee_data.sort(key=lambda x: x['task_count'], reverse=True)
                
                project_resources.append({
                    'project': {
                        'id': project.id,
                        'name': project.name
                    },
                    'team_size': len(team_members),
                    'active_tasks': len(project_tasks),
                    'team_allocation': assignee_data
                })
                
            return {
                'status': 'success',
                'data': {
                    'allocation_by_project': allocation_by_project,
                    'allocation_by_employee': allocation_by_employee,
                    'project_resources': project_resources
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_resource_allocation: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/team/reports/on-time-completion', type='json', auth='user', methods=['POST'], csrf=False)
    def get_on_time_completion_report(self, **kw):
        """Generate a report on project on-time completion performance."""
        try:
            # Get optional filters
            department_id = kw.get('department_id') and int(kw['department_id'])
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            
            # Build domain for projects
            project_domain = [('state', '=', 'completed')]
            
            if department_id:
                project_domain.append(('department_id', '=', department_id))
                
            if date_from:
                project_domain.append(('actual_date_end', '>=', date_from))
            if date_to:
                project_domain.append(('actual_date_end', '<=', date_to))
                
            # Get completed projects
            completed_projects = request.env['team.project'].sudo().search(project_domain)
            
            if not completed_projects:
                return {
                    'status': 'success',
                    'data': {
                        'summary': {
                            'total_projects': 0,
                            'on_time_projects': 0,
                            'delayed_projects': 0,
                            'on_time_rate': 0,
                            'avg_delay_days': 0
                        },
                        'by_department': [],
                        'by_project_type': [],
                        'by_project_manager': [],
                        'detailed_projects': []
                    }
                }
                
            # Calculate summary statistics
            total_projects = len(completed_projects)
            on_time_projects = len(completed_projects.filtered(lambda p: p.is_on_time))
            delayed_projects = len(completed_projects.filtered(lambda p: not p.is_on_time))
            
            on_time_rate = (on_time_projects / total_projects * 100) if total_projects else 0
            
            # Calculate average delay for delayed projects
            delayed_project_records = completed_projects.filtered(lambda p: not p.is_on_time)
            avg_delay_days = sum(delayed_project_records.mapped('days_delayed')) / len(delayed_project_records) if delayed_project_records else 0
            
            # Group by department
            department_stats = {}
            for project in completed_projects:
                dept_id = project.department_id.id
                dept_name = project.department_id.name
                
                if dept_id not in department_stats:
                    department_stats[dept_id] = {
                        'id': dept_id,
                        'name': dept_name,
                        'total': 0,
                        'on_time': 0,
                        'delayed': 0,
                        'rate': 0
                    }
                    
                department_stats[dept_id]['total'] += 1
                if project.is_on_time:
                    department_stats[dept_id]['on_time'] += 1
                else:
                    department_stats[dept_id]['delayed'] += 1
                    
            # Calculate on-time rate for each department
            for dept_id, stats in department_stats.items():
                stats['rate'] = (stats['on_time'] / stats['total'] * 100) if stats['total'] else 0
                
            # Group by project type
            type_stats = {}
            for project in completed_projects:
                project_type = project.project_type
                
                if project_type not in type_stats:
                    type_stats[project_type] = {
                        'type': project_type,
                        'total': 0,
                        'on_time': 0,
                        'delayed': 0,
                        'rate': 0
                    }
                    
                type_stats[project_type]['total'] += 1
                if project.is_on_time:
                    type_stats[project_type]['on_time'] += 1
                else:
                    type_stats[project_type]['delayed'] += 1
                    
            # Calculate on-time rate for each project type
            for project_type, stats in type_stats.items():
                stats['rate'] = (stats['on_time'] / stats['total'] * 100) if stats['total'] else 0
                
            # Group by project manager
            manager_stats = {}
            for project in completed_projects:
                manager_id = project.project_manager_id.id
                manager_name = project.project_manager_id.name
                
                if manager_id not in manager_stats:
                    manager_stats[manager_id] = {
                        'id': manager_id,
                        'name': manager_name,
                        'total': 0,
                        'on_time': 0,
                        'delayed': 0,
                        'rate': 0
                    }
                    
                manager_stats[manager_id]['total'] += 1
                if project.is_on_time:
                    manager_stats[manager_id]['on_time'] += 1
                else:
                    manager_stats[manager_id]['delayed'] += 1
                    
            # Calculate on-time rate for each project manager
            for manager_id, stats in manager_stats.items():
                stats['rate'] = (stats['on_time'] / stats['total'] * 100) if stats['total'] else 0
                
            # Prepare detailed project data
            detailed_projects = []
            for project in completed_projects:
                detailed_projects.append({
                    'id': project.id,
                    'name': project.name,
                    'project_type': project.project_type,
                    'department': project.department_id.name,
                    'manager': project.project_manager_id.name,
                    'planned_end_date': fields.Date.to_string(project.date_end),
                    'actual_end_date': fields.Date.to_string(project.actual_date_end),
                    'is_on_time': project.is_on_time,
                    'days_delayed': project.days_delayed if not project.is_on_time else 0,
                    'progress': project.progress
                })
                
            # Sort by completion date (most recent first)
            detailed_projects.sort(key=lambda p: p['actual_end_date'], reverse=True)
            
            return {
                'status': 'success',
                'data': {
                    'summary': {
                        'total_projects': total_projects,
                        'on_time_projects': on_time_projects,
                        'delayed_projects': delayed_projects,
                        'on_time_rate': round(on_time_rate, 1),
                        'avg_delay_days': round(avg_delay_days, 1)
                    },
                    'by_department': list(department_stats.values()),
                    'by_project_type': list(type_stats.values()),
                    'by_project_manager': list(manager_stats.values()),
                    'detailed_projects': detailed_projects
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_on_time_completion_report: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/team/notification/categories', type='json', auth='user', methods=['POST'], csrf=False)
    def get_notification_categories(self, **kw):
        try:
            # Dapatkan semua kategori yang tersedia di sistem
            categories = request.env['team.project.notification'].sudo()._fields['notification_category'].selection
            
            # Format hasil
            category_list = []
            for value, label in categories:
                category_list.append({
                    'value': value,
                    'label': label
                })
                
            # Kelompokkan kategori berdasarkan tipe
            grouped_categories = {
                'project': ['task_assigned', 'task_updated', 'task_completed', 'task_overdue', 'project_update', 'deadline_approaching'],
                'chat': ['mention', 'new_message', 'comment_added'],
                'meeting': ['meeting_scheduled', 'meeting_reminder']
            }
            
            return {
                'status': 'success',
                'data': {
                    'categories': category_list,
                    'grouped': grouped_categories
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_notification_categories: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # Tambahkan ke file controllers/team_project_api.py
    @http.route('/web/v2/team/notifications', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_notifications(self, **kw):
        try:
            operation = kw.get('operation', 'list')

            if operation == 'list':
                # Get employee_id for current user
                employee_id = request.env.user.employee_id.id
                
                domain = [('recipient_id', '=', employee_id)]
                
                # Key change: Make this parameter explicit and default to False
                unread_only = kw.get('unread_only', False)
                if unread_only:
                    domain.append(('is_read', '=', False))
                
                # Tambahkan filter kategori jika ada
                if kw.get('category'):
                    domain.append(('notification_category', '=', kw['category']))
                    
                # Pagination
                limit = int(kw.get('limit', 20))
                offset = int(kw.get('offset', 0))
                
                # Sorting - tambahkan opsi sorting
                sort_field = kw.get('sort_field', 'request_time')
                sort_order = kw.get('sort_order', 'desc')
                order = f"{sort_field} {sort_order}"
                
                # Get notifications
                notifications = request.env['team.project.notification'].sudo().search(
                    domain, limit=limit, offset=offset, order=order
                )
                
                # Format data
                notifications_data = []
                for notif in notifications:
                    # Parse JSON data
                    data = {}
                    if notif.data:
                        try:
                            data = json.loads(notif.data)
                        except:
                            data = {'error': 'Invalid JSON data'}
                    
                    notifications_data.append({
                        'id': notif.id,
                        'title': notif.title,
                        'message': notif.message,
                        'date': self._format_datetime_jakarta(notif.request_time),
                        'category': notif.notification_category,
                        'is_read': notif.is_read,
                        'priority': notif.priority,
                        'model': notif.model,
                        'res_id': notif.res_id,
                        'data': data,
                        'sender': {
                            'id': notif.sender_id.id,
                            'name': notif.sender_id.name
                        } if notif.sender_id else None,
                        'project': {
                            'id': notif.project_id.id,
                            'name': notif.project_id.name
                        } if notif.project_id else None
                    })
                
                return {
                    'status': 'success',
                    'data': notifications_data,
                    'total': request.env['team.project.notification'].sudo().search_count(domain)
                }
                
            elif operation == 'mark_read':
                notification_id = kw.get('notification_id')
                if not notification_id:
                    return {'status': 'error', 'message': 'Missing notification_id'}
                    
                notification = request.env['team.project.notification'].sudo().browse(int(notification_id))
                if not notification.exists():
                    return {'status': 'error', 'message': 'Notification not found'}
                    
                notification.write({'is_read': True})
                return {'status': 'success', 'message': 'Notification marked as read'}
                
            elif operation == 'mark_all_read':
                # Mark all notifications as read for current user
                employee_id = request.env.user.employee_id.id
                domain = [('recipient_id', '=', employee_id), ('is_read', '=', False)]
                
                if kw.get('project_id'):
                    domain.append(('project_id', '=', int(kw['project_id'])))
                if kw.get('category'):
                    domain.append(('notification_category', '=', kw['category']))
                    
                notifications = request.env['team.project.notification'].sudo().search(domain)
                notifications.write({'is_read': True})
                
                return {
                    'status': 'success', 
                    'message': f'{len(notifications)} notifications marked as read'
                }
                
            elif operation == 'get_unread_count':
                # Mendapatkan jumlah notifikasi yang belum dibaca
                employee_id = request.env.user.employee_id.id
                domain = [('recipient_id', '=', employee_id), ('is_read', '=', False)]
                
                count = request.env['team.project.notification'].sudo().search_count(domain)
                
                return {
                    'status': 'success',
                    'count': count
                }
                
            else:
                return {'status': 'error', 'message': f'Unknown operation: {operation}'}
                
        except Exception as e:
            _logger.error(f"Error in manage_notifications: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    