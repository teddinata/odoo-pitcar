# controllers/content_api.py
from odoo import http, fields
from odoo.http import request
import logging
import json
from datetime import datetime
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

class ContentManagementAPI(http.Controller):
    @http.route('/web/v2/content/projects', type='json', auth='user', methods=['POST'], csrf=False)
    def content_projects(self, **kw):
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                required_fields = ['name', 'date_start', 'date_end', 'project_manager_id']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'date_start': kw['date_start'],
                    'date_end': kw['date_end'],
                    'project_manager_id': int(kw['project_manager_id']),
                    'description': kw.get('description', ''),
                    'planned_video_count': int(kw.get('planned_video_count', 0)),
                    'planned_design_count': int(kw.get('planned_design_count', 0)),
                }

                if kw.get('team_ids'):
                    # Pastikan team_ids adalah list
                    team_ids = kw['team_ids'] if isinstance(kw['team_ids'], list) else json.loads(kw['team_ids'])
                    values['team_ids'] = [(6, 0, team_ids)]

                try:
                    project = request.env['content.project'].sudo().create(values)
                    return {
                        'status': 'success',
                        'data': self._prepare_project_data(project)
                    }
                except Exception as create_error:
                    return {
                        'status': 'error',
                        'message': f'Error creating project: {str(create_error)}'
                    }

        except Exception as e:
            _logger.error('Error in content_projects: %s', str(e))
            return {
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }
        
    @http.route('/web/v2/content/projects/list', type='json', auth='user', methods=['POST'], csrf=False)
    def get_projects(self, **kw):
        """Get list of projects with optional filters"""
        try:
            domain = []
            
            # Add filters if provided
            if kw.get('state'):
                domain.append(('state', '=', kw['state']))
            if kw.get('project_manager_id'):
                domain.append(('project_manager_id', '=', int(kw['project_manager_id'])))
            if kw.get('date_start'):
                domain.append(('date_start', '>=', kw['date_start']))
            if kw.get('date_end'):
                domain.append(('date_end', '<=', kw['date_end']))
                
            # Get projects
            projects = request.env['content.project'].sudo().search(domain)
            
            return {
                'status': 'success',
                'data': [self._prepare_project_data(project) for project in projects]
            }
            
        except Exception as e:
            _logger.error('Error in get_projects: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error fetching projects: {str(e)}'
            }

    @http.route('/web/v2/content/projects/<int:project_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_project_detail(self, project_id, **kw):
        """Get detailed information of a specific project"""
        try:
            project = request.env['content.project'].sudo().browse(project_id)
            if not project.exists():
                return {
                    'status': 'error',
                    'message': 'Project not found'
                }
                
            return {
                'status': 'success',
                'data': self._prepare_project_data(project)
            }
            
        except Exception as e:
            _logger.error('Error in get_project_detail: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error fetching project details: {str(e)}'
            }

    @http.route('/web/v2/content/tasks', type='json', auth='user', methods=['POST'], csrf=False)
    def content_tasks(self, **kw):
        """Handle content task operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                return self._create_task(kw)
            elif operation == 'update_status':
                return self._update_task_status(kw)
            elif operation == 'update':
                return self._update_task(kw)
            elif operation == 'get':
                return self._get_tasks(kw)
            else:
                return {'status': 'error', 'message': 'Invalid operation'}
                
        except Exception as e:
            _logger.error('Error in content_tasks: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error processing task: {str(e)}'
            }

    def _create_task(self, data):
        """Helper method to create task"""
        required_fields = ['name', 'project_id', 'content_type', 'assigned_to']
        if not all(data.get(field) for field in required_fields):
            return {'status': 'error', 'message': 'Missing required fields'}

        try:
            # Pastikan assigned_to adalah list
            assigned_to = data.get('assigned_to')
            if not isinstance(assigned_to, list):
                assigned_to = [assigned_to]

            values = {
                'name': data['name'],
                'project_id': int(data['project_id']),
                'content_type': data['content_type'],
                'assigned_to': [(6, 0, assigned_to)],  # Format Many2many untuk Odoo
                'state': 'draft',
                'progress': 0.0
            }

            # Tambahkan optional fields
            if data.get('reviewer_id'):
                values['reviewer_id'] = int(data['reviewer_id'])
            if data.get('planned_date_start'):
                values['planned_date_start'] = data['planned_date_start']
            if data.get('planned_date_end'):
                values['planned_date_end'] = data['planned_date_end']
            if data.get('planned_hours'):
                values['planned_hours'] = float(data['planned_hours'])
            if data.get('description'):
                values['description'] = data['description']

            task = request.env['content.task'].sudo().create(values)
            return {
                'status': 'success',
                'data': self._prepare_task_data(task)
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error creating task: {str(e)}'
            }

    def _update_task_status(self, data):
        """Helper method to update task status"""
        if not data.get('task_id') or not data.get('new_status'):
            return {'status': 'error', 'message': 'Missing task_id or new_status'}

        try:
            task = request.env['content.task'].sudo().browse(int(data['task_id']))
            if not task.exists():
                return {'status': 'error', 'message': 'Task not found'}

            update_values = {'state': data['new_status']}

            # Handle revision status
            if data['new_status'] == 'revision':
                if data.get('is_drag', False):
                    # Jika dari drag, return early dengan status need_revision_form
                    return {
                        'status': 'need_revision_form',
                        'data': self._prepare_task_data(task)
                    }
                
                # Jika dengan feedback, create revision
                if not data.get('feedback'):
                    return {'status': 'error', 'message': 'Feedback is required for revision'}
                
                # Create revision record
                revision = request.env['content.revision'].sudo().create({
                    'task_id': task.id,
                    'revision_number': task.revision_count + 1,
                    'requested_by': request.env.user.employee_id.id,
                    'feedback': data['feedback'],
                    'revision_points': data.get('revision_points'),
                    'deadline': data.get('deadline')
                })
                
                # Update task progress and state
                update_values.update({
                    'progress': max(task.progress - 20, 0),
                    'state': 'revision'
                })

                # Create activity log message
                task.message_post(
                    body=f"Task set to revision #{task.revision_count + 1}\n" + 
                        f"Feedback: {data['feedback']}\n" +
                        (f"Points: {data['revision_points']}\n" if data.get('revision_points') else "") +
                        (f"Deadline: {data['deadline']}" if data.get('deadline') else ""),
                    message_type='notification'
                )
    
            if data['new_status'] == 'in_progress' and not task.actual_date_start:
                update_values['actual_date_start'] = fields.Datetime.now()
                update_values['progress'] = 30.0
            elif data['new_status'] == 'review' and not task.actual_date_end:
                update_values['actual_date_end'] = fields.Datetime.now()
                update_values['progress'] = 70.0
            elif data['new_status'] == 'done' and not task.actual_date_end:
                update_values['actual_date_end'] = fields.Datetime.now()
                update_values['progress'] = 100.0

            task.write(update_values)
            return {
                'status': 'success',
                'data': self._prepare_task_data(task)
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error updating task status: {str(e)}'
            }
    
    def _update_task(self, data):
        """Helper method to update task"""
        if not data.get('task_id'):
            return {'status': 'error', 'message': 'Missing task_id'}

        try:
            task = request.env['content.task'].sudo().browse(int(data['task_id']))
            if not task.exists():
                return {'status': 'error', 'message': 'Task not found'}

            update_values = {}
            if data.get('name'):
                update_values['name'] = data['name']
            if data.get('content_type'):
                update_values['content_type'] = data['content_type']
            if data.get('assigned_to'):
                # Pastikan assigned_to adalah list
                assigned_to = data['assigned_to'] if isinstance(data['assigned_to'], list) else json.loads(data['assigned_to'])
                update_values['assigned_to'] = [(6, 0, assigned_to)]
            if data.get('reviewer_id'):
                update_values['reviewer_id'] = int(data['reviewer_id'])
            if data.get('planned_date_start'):
                update_values['planned_date_start'] = data['planned_date_start']
            if data.get('planned_date_end'):
                update_values['planned_date_end'] = data['planned_date_end']
            if data.get('planned_hours'):
                update_values['planned_hours'] = float(data['planned_hours'])
            if data.get('description'):
                update_values['description'] = data['description']
            # update progress
            if data.get('progress'):
                update_values['progress'] = float(data['progress'])

            task.write(update_values)
            return {
                'status': 'success',
                'data': self._prepare_task_data(task)
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error updating task: {str(e)}'
            }

    def _get_tasks(self, data):
        """Helper method to get tasks"""
        try:
            domain = []
            
            if data.get('project_id'):
                domain.append(('project_id', '=', int(data['project_id'])))
            if data.get('assigned_to'):
                domain.append(('assigned_to', '=', int(data['assigned_to'])))
            if data.get('state'):
                domain.append(('state', '=', data['state']))
            if data.get('content_type'):
                domain.append(('content_type', '=', data['content_type']))

            tasks = request.env['content.task'].sudo().search(domain)
            return {
                'status': 'success',
                'data': [self._prepare_task_data(task) for task in tasks]
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error fetching tasks: {str(e)}'
            }

    @http.route('/web/v2/content/tasks/request_revision', type='json', auth='user', methods=['POST'])
    def request_task_revision(self, **kw):
        try:
            if not kw.get('task_id') or not kw.get('feedback'):
                return {'status': 'error', 'message': 'Missing required fields'}

            task = request.env['content.task'].sudo().browse(int(kw['task_id']))
            if not task.exists():
                return {'status': 'error', 'message': 'Task not found'}

            # Create revision record
            revision_values = {
                'task_id': task.id,
                'revision_number': task.revision_count + 1,
                'requested_by': request.env.user.employee_id.id,
                'feedback': kw['feedback'],
                'revision_points': kw.get('revision_points'),
                'deadline': kw.get('deadline')
            }
            
            revision = request.env['content.revision'].sudo().create(revision_values)

            # Update task status
            task.write({
                'state': 'revision',
                'progress': max(task.progress - 20, 0)  # Kurangi progress
            })

            return {
                'status': 'success',
                'data': self._prepare_task_data(task)
            }

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/content/bau', type='json', auth='user', methods=['POST'], csrf=False)
    def content_bau(self, **kw):
        """Handle BAU activity operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                required_fields = ['name', 'creator_id', 'date', 'activity_type', 'hours_spent']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'creator_id': int(kw['creator_id']),
                    'date': kw['date'],
                    'activity_type': kw['activity_type'],
                    'hours_spent': float(kw['hours_spent']),
                    'project_id': int(kw['project_id']) if kw.get('project_id') else False,
                    'description': kw.get('description', ''),
                    'impact_on_delivery': kw.get('impact_on_delivery', '')
                }

                bau = request.env['content.bau'].sudo().create(values)
                return {
                    'status': 'success',
                    'data': self._prepare_bau_data(bau)
                }

            elif operation == 'get':
                domain = []
                if kw.get('creator_id'):
                    domain.append(('creator_id', '=', int(kw['creator_id'])))
                if kw.get('date_from'):
                    domain.append(('date', '>=', kw['date_from']))
                if kw.get('date_to'):
                    domain.append(('date', '<=', kw['date_to']))

                bau_activities = request.env['content.bau'].sudo().search(domain)
                return {
                    'status': 'success',
                    'data': [self._prepare_bau_data(bau) for bau in bau_activities]
                }
          
        except Exception as e:
          _logger.error('Error: %s', e)
          return {'status': 'error', 'message': 'An error occurred'}

    def _prepare_project_data(self, project):
        """Helper method to prepare project data"""
        return {
            'id': project.id,
            'name': project.name,
            'code': project.code,
            'dates': {
                'start': project.date_start,
                'end': project.date_end
            },
            'team': {
                'manager': {
                    'id': project.project_manager_id.id,
                    'name': project.project_manager_id.name,
                    'position': project.project_manager_id.job_id.name,
                },
                'members': [{
                    'id': member.id,
                    'name': member.name,
                    'position': member.job_id.name,
                } for member in project.team_ids]
            },
            'content_plan': {
                'video_count': project.planned_video_count,
                'design_count': project.planned_design_count
            },
            'progress': project.progress,
            'state': project.state,
            'tasks': [{
                'id': task.id,
                'name': task.name,
                'type': task.content_type,
                'state': task.state,
                'progress': task.progress,
                'revision_count': task.revision_count
            } for task in project.task_ids]
        }

    def _prepare_task_data(self, task):
        """Helper method to prepare task data"""
        return {
            'id': task.id,
            'name': task.name,
            'project': {
                'id': task.project_id.id,
                'name': task.project_id.name
            },
            'content_type': task.content_type,
            'assigned_to': [{
                'id': member.id,
                'name': member.name,
                'position': member.job_id.name,
            } for member in task.assigned_to],
            'reviewer': {
                'id': task.reviewer_id.id,
                'name': task.reviewer_id.name,
                'position': task.reviewer_id.job_id.name,
            } if task.reviewer_id else None,
            'dates': {
                'planned_start': task.planned_date_start,
                'planned_end': task.planned_date_end,
                'actual_start': task.actual_date_start,
                'actual_end': task.actual_date_end
            },
            'hours': {
                'planned': task.planned_hours,
                'actual': task.actual_hours
            },
            'revisions': {
                'count': task.revision_count,
                'excessive': task.has_excessive_revisions,
                'history': [{
                    'number': rev.revision_number,
                    'requested_by': rev.requested_by.name,
                    'date': rev.date_requested,
                    'notes': rev.description
                } for rev in task.revision_ids]
            },
            'activity_logs': [{
                'id': log.id,
                'date': log.date,
                'author': {
                    'id': log.author_id.id,
                    'name': log.author_id.name,
                    'position': log.author_id.job_id.name,
                } if log.author_id else None,
                'message': log.body,
                'tracking_values': [{
                    'field': tracking.field_desc,
                    'old_value': tracking.old_value_char,
                    'new_value': tracking.new_value_char
                } for tracking in log.tracking_value_ids] if log.tracking_value_ids else []
            } for log in logs],
            'progress': task.progress,
            'state': task.state
        }

    def _prepare_bau_data(self, bau):
        """Helper method to prepare BAU data"""
        return {
            'id': bau.id,
            'name': bau.name,
            'creator': {
                'id': bau.creator_id.id,
                'name': bau.creator_id.name,
                'position': bau.creator_id.job_id.name,
            },
            'date': bau.date,
            'activity_type': bau.activity_type,
            'hours_spent': bau.hours_spent,
            'project': {
                'id': bau.project_id.id,
                'name': bau.project_id.name
            } if bau.project_id else None,
            'description': bau.description,
            'impact_on_delivery': bau.impact_on_delivery
        }

    @http.route('/web/v2/content/tasks/logs', type='json', auth='user', methods=['POST'], csrf=False)
    def get_task_logs(self, **kw):
        """Get task change logs"""
        try:
            if not kw.get('task_id'):
                return {'status': 'error', 'message': 'Missing task_id'}
                
            task = request.env['content.task'].sudo().browse(int(kw['task_id']))
            if not task.exists():
                return {'status': 'error', 'message': 'Task not found'}
                
            # Get message/log history for this task
            logs = request.env['mail.message'].sudo().search([
                ('model', '=', 'content.task'),
                ('res_id', '=', task.id),
                ('message_type', 'in', ['comment', 'notification'])
            ], order='date desc')
            
            return {
                'status': 'success',
                'data': [self._prepare_log_data(log) for log in logs]
            }
            
        except Exception as e:
            _logger.error('Error getting task logs: %s', str(e))
            return {
                'status': 'error', 
                'message': f'Error getting task logs: {str(e)}'
            }

    @http.route('/web/v2/content/projects/logs', type='json', auth='user', methods=['POST'], csrf=False)
    def get_project_logs(self, **kw):
        """Get project change logs"""
        try:
            if not kw.get('project_id'):
                return {'status': 'error', 'message': 'Missing project_id'}
                
            project = request.env['content.project'].sudo().browse(int(kw['project_id']))
            if not project.exists():
                return {'status': 'error', 'message': 'Project not found'}
                
            # Get message/log history for this project
            logs = request.env['mail.message'].sudo().search([
                ('model', '=', 'content.project'),
                ('res_id', '=', project.id),
                ('message_type', 'in', ['comment', 'notification'])
            ], order='date desc')
            
            return {
                'status': 'success',
                'data': [self._prepare_log_data(log) for log in logs]
            }
            
        except Exception as e:
            _logger.error('Error getting project logs: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error getting project logs: {str(e)}'
            }

    def _prepare_log_data(self, log):
        """Helper method to prepare log data"""
        return {
            'id': log.id,
            'date': log.date,
            'author': {
                'id': log.author_id.id,
                'name': log.author_id.name,
                'position': log.author_id.job_id.name,
            } if log.author_id else None,
            'message': log.body,
            'tracking_values': [{
                'field': tracking.field_desc,
                'old_value': tracking.old_value_char,
                'new_value': tracking.new_value_char
            } for tracking in log.tracking_value_ids] if log.tracking_value_ids else []
        }