# controllers/team_project_api.py
from odoo import http, fields
from odoo.http import request
import json
import logging
import pytz
import datetime  # Import the full datetime module

_logger = logging.getLogger(__name__)

class TeamProjectAPI(http.Controller):
    def _format_datetime_jakarta(self, dt):
        """Convert UTC datetime/date to Jakarta timezone (UTC+7)"""
        if not dt:
            return False
        
        # If it's a Date field (not Datetime)
        if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
            return fields.Date.to_string(dt)
                
        # If dt is a string, convert to datetime object
        if isinstance(dt, str):
            if 'T' in dt or ' ' in dt:  # It's a datetime string
                dt = fields.Datetime.from_string(dt)
            else:  # It's a date string
                return dt  # Just return the date string
        
        # Define Jakarta timezone
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        
        # Convert to Jakarta timezone (only for datetime objects)
        try:
            dt_utc = pytz.utc.localize(dt) if not dt.tzinfo else dt
            dt_jakarta = dt_utc.astimezone(jakarta_tz)
            return fields.Datetime.to_string(dt_jakarta)
        except AttributeError:
            # If we get here, it means dt doesn't have tzinfo attribute
            # So it's likely a date object that slipped through our checks
            return fields.Date.to_string(dt) if hasattr(dt, 'day') else str(dt)
    
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
                for field in ['name', 'date_start', 'date_end', 'description', 'state', 'priority']:
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

    @http.route('/web/v2/team/projects/list', type='json', auth='user', methods=['POST'], csrf=False)
    def get_projects(self, **kw):
        """Mengambil daftar proyek dengan filter."""
        try:
            domain = []
            if kw.get('department_id'):
                domain.append(('department_id', '=', int(kw['department_id'])))
            if kw.get('state'):
                domain.append(('state', '=', kw['state']))
            if kw.get('date_start'):
                domain.append(('date_start', '>=', kw['date_start']))
            if kw.get('date_end'):
                domain.append(('date_end', '<=', kw['date_end']))
            limit = kw.get('limit', 10)
            offset = kw.get('offset', 0)

            projects = request.env['team.project'].sudo().search(domain, limit=limit, offset=offset)
            total = request.env['team.project'].sudo().search_count(domain)

            return {
                'status': 'success',
                'data': [self._prepare_project_data(project) for project in projects],
                'total': total,
                'limit': limit,
                'offset': offset
            }
        except Exception as e:
            _logger.error(f"Error in get_projects: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/team/tasks', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_tasks(self, **kw):
        """Mengelola operasi CRUD untuk tugas tim."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                required_fields = ['name', 'project_id', 'assigned_to']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                assigned_to = kw['assigned_to'] if isinstance(kw['assigned_to'], list) else json.loads(kw['assigned_to'])
                values = {
                    'name': kw['name'],
                    'project_id': int(kw['project_id']),
                    'assigned_to': [(6, 0, assigned_to)],
                    'planned_date_start': kw.get('planned_date_start'),
                    'planned_date_end': kw.get('planned_date_end'),
                    'planned_hours': float(kw.get('planned_hours', 0.0)),
                    'description': kw.get('description'),
                    'state': kw.get('state', 'draft'),
                }
                if kw.get('reviewer_id'):
                    values['reviewer_id'] = int(kw['reviewer_id'])
                if kw.get('type_id'):
                    values['type_id'] = int(kw['type_id'])

                task = request.env['team.project.task'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_task_data(task)}

            elif operation == 'update':
                task_id = kw.get('task_id')
                if not task_id:
                    return {'status': 'error', 'message': 'Missing task_id'}
                task = request.env['team.project.task'].sudo().browse(int(task_id))
                if not task.exists():
                    return {'status': 'error', 'message': 'Task not found'}

                update_values = {}
                for field in ['name', 'planned_date_start', 'planned_date_end', 
                            'planned_hours', 'description', 'state', 'progress']:
                    if field in kw:
                        update_values[field] = kw[field] if field != 'planned_hours' else float(kw[field])
                if kw.get('assigned_to'):
                    assigned_to = kw['assigned_to'] if isinstance(kw['assigned_to'], list) else json.loads(kw['assigned_to'])
                    update_values['assigned_to'] = [(6, 0, assigned_to)]
                if kw.get('reviewer_id'):
                    update_values['reviewer_id'] = int(kw['reviewer_id'])
                if kw.get('type_id'):
                    update_values['type_id'] = int(kw['type_id'])

                task.write(update_values)
                return {'status': 'success', 'data': self._prepare_task_data(task), 'message': 'Task updated'}

            elif operation == 'delete':
                task_id = kw.get('task_id')
                if not task_id:
                    return {'status': 'error', 'message': 'Missing task_id'}
                task = request.env['team.project.task'].sudo().browse(int(task_id))
                if not task.exists():
                    return {'status': 'error', 'message': 'Task not found'}
                task.unlink()
                return {'status': 'success', 'message': 'Task deleted'}

        except Exception as e:
            _logger.error(f"Error in manage_tasks: {str(e)}")
            return {'status': 'error', 'message': str(e)}

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
                'message_type': 'regular'
            }
            
            message = request.env['team.project.message'].sudo().create(values)
            
            # Proses mentions jika ada
            if kw.get('mentions'):
                for user_id in kw['mentions']:
                    # Buat notifikasi untuk setiap user yang di-mention
                    request.env['pitcar.notification'].sudo().create_or_update_notification(
                        model='team.project.message',
                        res_id=message.id,
                        type='mention',
                        title=f"You were mentioned by {request.env.user.name}",
                        message=f"You were mentioned in a message: '{kw['content'][:100]}...'",
                        user_id=user_id,
                        data={
                            'message_id': message.id, 
                            'group_id': values['group_id'],
                            'action': 'view_group_chat'
                        }
                    )
            
            return {'status': 'success', 'data': self._prepare_message_data(message)}
        except Exception as e:
            _logger.error(f"Error in send_chat_message: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # Helper Methods
    def _prepare_project_data(self, project):
        """Menyiapkan data proyek untuk respons API."""
        return {
            'id': project.id,
            'name': project.name,
            'code': project.code,
            'department': {'id': project.department_id.id, 'name': project.department_id.name},
            'dates': {
                'start': fields.Date.to_string(project.date_start),
                'end': fields.Date.to_string(project.date_end)
            },
            'team': {
                'manager': {'id': project.project_manager_id.id, 'name': project.project_manager_id.name},
                'members': [{'id': m.id, 'name': m.name} for m in project.team_ids]
            },
            'group_id': project.group_id.id if project.group_id else False,
            'state': project.state,
            'progress': project.progress,
            'priority': project.priority,
            'task_count': len(project.task_ids)
        }

    def _prepare_task_data(self, task):
        """Menyiapkan data tugas untuk respons API."""
        return {
            'id': task.id,
            'name': task.name,
            'project': {'id': task.project_id.id, 'name': task.project_id.name},
            'type': {'id': task.type_id.id, 'name': task.type_id.name} if task.type_id else None,
            'assigned_to': [{'id': a.id, 'name': a.name} for a in task.assigned_to],
            'reviewer': {'id': task.reviewer_id.id, 'name': task.reviewer_id.name} if task.reviewer_id else None,
            'dates': {
                'planned_start': self._format_datetime_jakarta(task.planned_date_start) if task.planned_date_start else False,
                'planned_end': self._format_datetime_jakarta(task.planned_date_end) if task.planned_date_end else False,
                'actual_start': self._format_datetime_jakarta(task.actual_date_start) if task.actual_date_start else False,
                'actual_end': self._format_datetime_jakarta(task.actual_date_end) if task.actual_date_end else False
            },
            'hours': {
                'planned': task.planned_hours,
                'actual': task.actual_hours
            },
            'state': task.state,
            'progress': task.progress,
            'description': task.description,
            'checklist_progress': task.checklist_progress
        }

    def _prepare_message_data(self, message):
        """Menyiapkan data pesan untuk respons API."""
        return {
            'id': message.id,
            'group_id': message.group_id.id,
            'author': {'id': message.author_id.id, 'name': message.author_id.name},
            'content': message.content,
            'date': self._format_datetime_jakarta(message.date),
            'project_id': message.project_id.id if message.project_id else None,
            'is_pinned': message.is_pinned
        }
    
    # controllers/team_project_api.py (Lanjutan)

    @http.route('/web/v2/team/meetings', type='json', auth='user', methods=['POST'], csrf=False)
    def manage_meetings(self, **kw):
        """Mengelola operasi CRUD untuk rapat tim."""
        try:
            operation = kw.get('operation', 'create')

            if operation == 'create':
                required_fields = ['name', 'start_datetime', 'end_datetime', 'organizer_id']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'start_datetime': kw['start_datetime'],
                    'end_datetime': kw['end_datetime'],
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
                required_fields = ['name', 'date', 'activity_type']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'date': kw['date'],
                    'activity_type': kw['activity_type'],
                    'creator_id': kw.get('creator_id', request.env.user.employee_id.id),
                    'project_id': int(kw['project_id']) if kw.get('project_id') else False,
                    'hours_spent': float(kw.get('hours_spent', 0.0)),
                    'description': kw.get('description'),
                    'state': kw.get('state', 'planned'),
                }

                bau = request.env['team.project.bau'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_bau_data(bau)}

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
                    'employee_id': int(kw.get('employee_id', request.env.user.employee_id.id)),
                    'date': kw.get('date', fields.Date.context_today(request)),
                    'hours': float(kw['hours']),
                    'description': kw.get('description'),
                }

                timesheet = request.env['team.project.timesheet'].sudo().create(values)
                return {'status': 'success', 'data': self._prepare_timesheet_data(timesheet)}

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
        """Menyiapkan data aktivitas BAU untuk respons API."""
        return {
            'id': bau.id,
            'name': bau.name,
            'project': {'id': bau.project_id.id, 'name': bau.project_id.name} if bau.project_id else None,
            'creator': {'id': bau.creator_id.id, 'name': bau.creator_id.name},
            'date': self._format_datetime_jakarta(bau.date),
            'activity_type': bau.activity_type,
            'hours_spent': bau.hours_spent,
            'description': bau.description,
            'state': bau.state,
            'verification': {
                'verified_by': {'id': bau.verified_by.id, 'name': bau.verified_by.name} if bau.verified_by else None,
                'date': self._format_datetime_jakarta(bau.verification_date) if bau.verification_date else False
            }
        }
    
    def _prepare_checklist_data(self, checklist):
        """Menyiapkan data checklist untuk respons API."""
        return {
            'id': checklist.id,
            'name': checklist.name,
            'task': {'id': checklist.task_id.id, 'name': checklist.task_id.name},
            'sequence': checklist.sequence,
            'assigned_to': {'id': checklist.assigned_to.id, 'name': checklist.assigned_to.name} if checklist.assigned_to else None,
            'deadline': fields.Date.to_string(checklist.deadline) if checklist.deadline else False,
            'is_done': checklist.is_done,
            'notes': checklist.notes
        }
    
    def _prepare_timesheet_data(self, timesheet):
        """Menyiapkan data timesheet untuk respons API."""
        return {
            'id': timesheet.id,
            'task': {'id': timesheet.task_id.id, 'name': timesheet.task_id.name},
            'project': {'id': timesheet.project_id.id, 'name': timesheet.project_id.name},
            'employee': {'id': timesheet.employee_id.id, 'name': timesheet.employee_id.name},
            'date': self._format_datetime_jakarta(timesheet.date),
            'hours': timesheet.hours,
            'description': timesheet.description
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
            
            # Ambil pesan-pesan dari grup
            domain = [('group_id', '=', int(group_id))]
            messages = request.env['team.project.message'].sudo().search(
                domain, limit=limit, offset=offset, order='date desc'
            )
            
            return {
                'status': 'success',
                'data': [self._prepare_message_data(message) for message in messages],
                'total': request.env['team.project.message'].sudo().search_count(domain)
            }
        except Exception as e:
            _logger.error(f"Error in get_group_messages: {str(e)}")
            return {'status': 'error', 'message': str(e)}