# controllers/content_api.py
from odoo import http, fields
from odoo.http import request
import logging
import json
from datetime import datetime, timedelta
from odoo.exceptions import AccessError, ValidationError
from collections import defaultdict

_logger = logging.getLogger(__name__)

class ContentManagementAPI(http.Controller):
    @http.route('/web/v2/content/projects', type='json', auth='user', methods=['POST'], csrf=False)
    def content_projects(self, **kw):
        try:
            operation = kw.get('operation', 'create')

            if operation == 'delete':
                return self._delete_project(kw)
            elif operation == 'update':
                return self._update_project(kw)
            
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
    
    def _update_project(self, data):
        """Helper method to update project"""
        try:
            if not data.get('project_id'):
                return {'status': 'error', 'message': 'Project ID is required'}

            project = request.env['content.project'].sudo().browse(int(data['project_id']))
            if not project.exists():
                return {'status': 'error', 'message': 'Project not found'}

            update_values = {}
            
            # Update basic fields if provided
            if data.get('name'):
                update_values['name'] = data['name']
            if data.get('description') is not None:  # Allow empty description
                update_values['description'] = data['description']
            if data.get('date_start'):
                update_values['date_start'] = data['date_start']
            if data.get('date_end'):
                update_values['date_end'] = data['date_end']
            if data.get('project_manager_id'):
                update_values['project_manager_id'] = int(data['project_manager_id'])
            if data.get('planned_video_count') is not None:
                update_values['planned_video_count'] = int(data['planned_video_count'])
            if data.get('planned_design_count') is not None:
                update_values['planned_design_count'] = int(data['planned_design_count'])
            if data.get('state'):
                update_values['state'] = data['state']

            # Handle team_ids update if provided
            if data.get('team_ids'):
                team_ids = data['team_ids'] if isinstance(data['team_ids'], list) else json.loads(data['team_ids'])
                update_values['team_ids'] = [(6, 0, team_ids)]

            # Create activity log
            changes = [f"{field} updated to {value}" for field, value in update_values.items()]
            if changes:
                project.message_post(
                    body=f"Project updated by {request.env.user.name}:\n" + "\n".join(changes),
                    message_type='notification'
                )

            # Update the project
            project.write(update_values)

            return {
                'status': 'success',
                'data': self._prepare_project_data(project),
                'message': 'Project updated successfully'
            }

        except Exception as e:
            _logger.error('Error updating project: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error updating project: {str(e)}'
            }

    def _delete_project(self, data):
        """Helper method to delete project with optional force delete"""
        try:
            if not data.get('project_id'):
                return {
                    'jsonrpc': '2.0',
                    'result': {'status': 'error', 'message': 'Project ID is required'},
                    'id': data.get('id')
                }

            project = request.env['content.project'].sudo().browse(int(data['project_id']))
            if not project.exists():
                return {
                    'jsonrpc': '2.0',
                    'result': {'status': 'error', 'message': 'Project not found'},
                    'id': data.get('id')
                }

            # Cek apakah force delete diaktifkan
            force_delete = data.get('force', False)

            if project.task_ids and not force_delete:
                return {
                    'jsonrpc': '2.0',
                    'result': {
                        'status': 'error',
                        'message': 'Cannot delete project with existing tasks. Please delete or move tasks first.'
                    },
                    'id': data.get('id')
                }

            # Jika force delete diaktifkan, hapus semua task dan revision terkait
            if force_delete and project.task_ids:
                for task in project.task_ids:
                    # Hapus semua revision terkait task
                    if task.revision_ids:
                        task.revision_ids.unlink()
                    # Hapus task itu sendiri
                    task.unlink()

            # Catat log sebelum penghapusan project
            project.message_post(
                body=f"Project '{project.name}' was deleted by {request.env.user.name}" + 
                    (" (force delete)" if force_delete else ""),
                message_type='notification'
            )

            # Hapus project
            project.unlink()

            return {
                'jsonrpc': '2.0',
                'result': {
                    'status': 'success',
                    'message': 'Project deleted successfully' + (' (force delete)' if force_delete else '')
                },
                'id': data.get('id')
            }

        except Exception as e:
            _logger.error('Error deleting project: %s', str(e))
            return {
                'jsonrpc': '2.0',
                'result': {'status': 'error', 'message': f'Error deleting project: {str(e)}'},
                'id': data.get('id')
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
            elif operation == 'delete':
                return self._delete_task(kw)
            
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
        
    def _delete_task(self, data):
        """Helper method to delete task"""
        try:
            if not data.get('task_id'):
                return {'status': 'error', 'message': 'Task ID is required'}

            task = request.env['content.task'].sudo().browse(int(data['task_id']))
            if not task.exists():
                return {'status': 'error', 'message': 'Task not found'}

            # Check if task can be deleted (e.g., not in certain states)
            if task.state in ['completed']:
                return {
                    'status': 'error', 
                    'message': 'Cannot delete a completed task. Please archive it instead.'
                }

            # Create activity log before deletion
            task.message_post(
                body=f"Task '{task.name}' was deleted by {request.env.user.name}",
                message_type='notification'
            )

            # Delete the task
            task.unlink()

            return {
                'status': 'success',
                'message': 'Task deleted successfully'
            }

        except Exception as e:
            _logger.error('Error deleting task: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error deleting task: {str(e)}'
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
                required_fields = ['name', 'creator_id', 'date', 'activity_type']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'creator_id': int(kw['creator_id']),
                    'date': kw['date'],
                    'activity_type': kw['activity_type'],
                    'hours_spent': float(kw.get('hours_spent', 0.0)),  # Opsional
                    'project_id': int(kw['project_id']) if kw.get('project_id') else False,
                    'description': kw.get('description', ''),
                    'impact_on_delivery': kw.get('impact_on_delivery', ''),
                    'state': kw.get('state', 'planned'),  # Default ke planned
                }

                bau = request.env['content.bau'].sudo().create(values)
                return {
                    'status': 'success',
                    'data': self._prepare_bau_data(bau)
                }

            elif operation == 'update':
                if not kw.get('bau_id'):
                    return {'status': 'error', 'message': 'Missing BAU ID'}
                    
                bau = request.env['content.bau'].sudo().browse(int(kw['bau_id']))
                if not bau.exists():
                    return {'status': 'error', 'message': 'BAU activity not found'}
                    
                update_values = {}
                if kw.get('name'):
                    update_values['name'] = kw['name']
                if kw.get('activity_type'):
                    update_values['activity_type'] = kw['activity_type']
                if kw.get('hours_spent') is not None:
                    update_values['hours_spent'] = float(kw['hours_spent'])
                if kw.get('date'):
                    update_values['date'] = kw['date']
                if kw.get('description') is not None:
                    update_values['description'] = kw['description']
                if kw.get('impact_on_delivery') is not None:
                    update_values['impact_on_delivery'] = kw['impact_on_delivery']
                if kw.get('state'):
                    update_values['state'] = kw['state']  # Update status menjadi done/not_done
                    
                bau.write(update_values)
                return {
                    'status': 'success',
                    'data': self._prepare_bau_data(bau),
                    'message': 'BAU activity updated successfully'
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
                
            elif operation == 'delete':
                if not kw.get('bau_id'):
                    return {'status': 'error', 'message': 'Missing BAU ID'}
                    
                try:
                    bau = request.env['content.bau'].sudo().browse(int(kw['bau_id']))
                    if not bau.exists():
                        return {'status': 'error', 'message': 'BAU activity not found'}
                        
                    # Simpan nama untuk pesan konfirmasi
                    bau_name = bau.name
                    
                    # Hapus BAU record
                    bau.unlink()
                    return {
                        'status': 'success',
                        'message': f'BAU activity "{bau_name}" deleted successfully'
                    }
                    
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Error deleting BAU activity: {str(e)}'
                    }
          
        except Exception as e:
          _logger.error('Error: %s', e)
          return {'status': 'error', 'message': 'An error occurred'}

    def _prepare_project_data(self, project):
        """Helper method to prepare project data"""
        tasks_data = []
        for task in project.task_ids:
            task_data = {
                'id': task.id,
                'name': task.name,
                'type': task.content_type,  # Tetap gunakan 'type' untuk kompatibilitas
                'content_type': task.content_type,  # Tambahkan juga 'content_type'
                'state': task.state,
                'progress': task.progress,
                'revision_count': task.revision_count,
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
                'assigned_to': [{
                    'id': member.id,
                    'name': member.name,
                    'position': member.job_id.name if member.job_id else ''
                } for member in task.assigned_to],
                'reviewer': {
                    'id': task.reviewer_id.id,
                    'name': task.reviewer_id.name,
                    'position': task.reviewer_id.job_id.name if task.reviewer_id.job_id else ''
                } if task.reviewer_id else None,
                'description': task.description
            }
            tasks_data.append(task_data)
        
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
            'tasks': tasks_data
        }

    def _prepare_task_data(self, task):
        """Helper method to prepare task data"""
        # Get task logs
        # logs = request.env['mail.message'].sudo().search([
        #     ('model', '=', 'content.task'),
        #     ('res_id', '=', task.id),
        #     ('message_type', 'in', ['comment', 'notification'])
        # ], order='date desc')

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
            # 'activity_logs': [{
            #     'id': log.id,
            #     'date': log.date,
            #     'author': {
            #         'id': log.author_id.id,
            #         'name': log.author_id.name,
            #         'position': log.author_id.job_id.name,
            #     } if log.author_id else None,
            #     'message': log.body,
            #     'tracking_values': [{
            #         'field': tracking.field_desc,
            #         'old_value': tracking.old_value_char,
            #         'new_value': tracking.new_value_char
            #     } for tracking in log.tracking_value_ids] if log.tracking_value_ids else []
            # } for log in logs],
            'progress': task.progress,
            'state': task.state
        }

    def _prepare_bau_data(self, bau):
        return {
            'id': bau.id,
            'name': bau.name,
            'creator': {
                'id': bau.creator_id.id,
                'name': bau.creator_id.name,
                'position': bau.creator_id.job_id.name if bau.creator_id.job_id else '',
            },
            'date': bau.date,
            'activity_type': bau.activity_type,
            'hours_spent': bau.hours_spent,
            'project': {
                'id': bau.project_id.id,
                'name': bau.project_id.name
            } if bau.project_id else None,
            'description': bau.description,
            'impact_on_delivery': bau.impact_on_delivery,
            'state': bau.state,  # Ganti is_target_achieved dengan state
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
                # Remove job_id since it's not available in res.partner
                'email': log.author_id.email,
            } if log.author_id else None,
            'message': log.body,
            'tracking_values': [{
                'field': tracking.field_desc,
                'old_value': tracking.old_value_char,
                'new_value': tracking.new_value_char
            } for tracking in log.tracking_value_ids] if log.tracking_value_ids else []
        }

    @http.route('/web/v2/content/bau/report', type='json', auth='user', methods=['POST'], csrf=False)
    def bau_report(self, **kw):
        try:
            if not kw.get('date_from') or not kw.get('date_to'):
                return {'status': 'error', 'message': 'Date range is required'}
            
            bau_domain = [
                ('date', '>=', kw['date_from']),
                ('date', '<=', kw['date_to'])
            ]
            if kw.get('creator_id'):
                bau_domain.append(('creator_id', '=', int(kw['creator_id'])))
            
            bau_activities = request.env['content.bau'].sudo().search(bau_domain)
            
            creators_data = {}
            daily_data = {}
            
            for bau in bau_activities:
                creator_id = bau.creator_id.id
                if creator_id not in creators_data:
                    creators_data[creator_id] = {
                        'creator_id': creator_id,
                        'creator_name': bau.creator_id.name,
                        'position': bau.creator_id.job_id.name if bau.creator_id.job_id else '',
                        'total_activities': 0,
                        'done_activities': 0,
                        'bau_days': set(),
                        'activities': []
                    }
                
                creators_data[creator_id]['total_activities'] += 1
                if bau.state == 'done':
                    creators_data[creator_id]['done_activities'] += 1
                creators_data[creator_id]['bau_days'].add(bau.date)
                creators_data[creator_id]['activities'].append(self._prepare_bau_data(bau))
                
                date_key = str(bau.date)
                if date_key not in daily_data:
                    daily_data[date_key] = {
                        'date': date_key,
                        'total_activities': 0,
                        'done_activities': 0,
                        'creators': set()
                    }
                
                daily_data[date_key]['total_activities'] += 1
                if bau.state == 'done':
                    daily_data[date_key]['done_activities'] += 1
                daily_data[date_key]['creators'].add(creator_id)
            
            # Hitung realisasi per creator
            for creator_id, data in creators_data.items():
                data['realization_rate'] = round((data['done_activities'] / data['total_activities'] * 100), 2) if data['total_activities'] > 0 else 0
                data['bau_days'] = len(data['bau_days'])
                data['activities'] = sorted(data['activities'], key=lambda x: x['date'], reverse=True)[:5]
            
            processed_daily_data = list(daily_data.values())
            
            total_bau_days = len(daily_data)
            total_activities = sum(data['total_activities'] for data in daily_data.values())
            total_done = sum(data['done_activities'] for data in daily_data.values())
            realization_rate = round((total_done / total_activities * 100), 2) if total_activities > 0 else 0
            
            top_performer = max(creators_data.values(), key=lambda x: x['realization_rate']) if creators_data else None
            
            report_data = {
                'creators': list(creators_data.values()),
                'daily_data': processed_daily_data,
                'summary': {
                    'total_bau_days': total_bau_days,
                    'total_activities': total_activities,
                    'total_done': total_done,
                    'realization_rate': realization_rate,
                    'top_performer': top_performer['creator_name'] if top_performer else None,
                }
            }
            
            return {
                'status': 'success',
                'data': report_data
            }
            
        except Exception as e:
            _logger.error('Error in bau_report: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error generating BAU report: {str(e)}'
            }
        
    @http.route('/web/v2/content/bau/batch', type='json', auth='user', methods=['POST'], csrf=False)
    def batch_bau(self, **kw):
        """Handle batch BAU activities creation with date range support, excluding weekends"""
        try:
            # Validasi input
            if not kw.get('activity') or not isinstance(kw['activity'], dict):
                return {'status': 'error', 'message': 'Activity object is required'}
            if not kw.get('date_from') or not kw.get('date_to'):
                return {'status': 'error', 'message': 'Date range (date_from and date_to) is required'}

            activity = kw['activity']
            date_from = fields.Date.from_string(kw['date_from'])
            date_to = fields.Date.from_string(kw['date_to'])

            # Validasi tanggal
            if date_from > date_to:
                return {'status': 'error', 'message': 'date_from must be before date_to'}
            if date_from < fields.Date.today():
                return {'status': 'error', 'message': 'Cannot plan activities for past dates'}

            # Validasi required fields untuk aktivitas
            required_fields = ['name', 'creator_id', 'activity_type']
            if not all(activity.get(field) for field in required_fields):
                return {'status': 'error', 'message': 'Missing required fields in activity'}

            created_baus = []
            errors = []

            # Buat aktivitas hanya untuk hari kerja
            current_date = date_from
            while current_date <= date_to:
                # 0-4 adalah Senin-Jumat, 5-6 adalah Sabtu-Minggu
                if current_date.weekday() < 6:  # Hanya hari kerja
                    try:
                        values = {
                            'name': activity['name'],
                            'creator_id': int(activity['creator_id']),
                            'date': current_date,
                            'activity_type': activity['activity_type'],
                            'hours_spent': float(activity.get('hours_spent', 0.0)),  # Opsional
                            'project_id': int(activity['project_id']) if activity.get('project_id') else False,
                            'description': activity.get('description', ''),
                            'impact_on_delivery': activity.get('impact_on_delivery', ''),
                            'state': 'planned',  # Selalu planned untuk rencana
                        }

                        bau = request.env['content.bau'].sudo().create(values)
                        created_baus.append(self._prepare_bau_data(bau))

                    except Exception as e:
                        errors.append(f"Error creating activity for {current_date}: {str(e)}")

                current_date += timedelta(days=1)  # Tambah 1 hari

            return {
                'status': 'partial_success' if errors else 'success',
                'data': {
                    'created': created_baus,
                    'errors': errors
                },
                'message': f'Created {len(created_baus)} BAU activities with {len(errors)} errors'
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error processing batch BAU: {str(e)}'
            }
        
    @http.route('/web/v2/content/bau/calendar', type='json', auth='user', methods=['POST'], csrf=False)
    def bau_calendar(self, **kw):
        """Get BAU activities for calendar view"""
        try:
            # Validasi input
            if not kw.get('date_from') or not kw.get('date_to'):
                return {'status': 'error', 'message': 'Date range is required'}
                
            domain = [
                ('date', '>=', kw['date_from']),
                ('date', '<=', kw['date_to'])
            ]
            
            # Optional filter by creator
            if kw.get('creator_id'):
                domain.append(('creator_id', '=', int(kw['creator_id'])))
                
            # Get BAU activities
            bau_activities = request.env['content.bau'].sudo().search(domain)
            
            # Group activities by date for calendar view
            calendar_data = {}
            for bau in bau_activities:
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
                
                # Add time information for week view (mock start/end times)
                # In real implementation, you'd have actual start/end times
                hours = int(bau.hours_spent)
                minutes = int((bau.hours_spent - hours) * 60)
                
                # Mock start at 9 AM and calculate end time
                start_hour = 9
                end_hour = start_hour + hours
                end_minutes = minutes
                
                # Adjust if hours overflow
                if end_hour > 17:  # Cap at 5 PM
                    end_hour = 17
                    end_minutes = 0
                
                activity_data['time'] = {
                    'start': f"{start_hour:02d}:{0:02d}",
                    'end': f"{end_hour:02d}:{end_minutes:02d}",
                    'duration': bau.hours_spent
                }
                
                calendar_data[date_key]['activities'].append(activity_data)
                calendar_data[date_key]['total_hours'] += bau.hours_spent
                
                # Update target achieved status
                target_hours = bau.target_hours if hasattr(bau, 'target_hours') else 2.0
                if bau.hours_spent >= target_hours:
                    calendar_data[date_key]['target_achieved'] = True
            
            return {
                'status': 'success',
                'data': list(calendar_data.values())
            }
            
        except Exception as e:
            _logger.error('Error in bau_calendar: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error getting calendar data: {str(e)}'
            }
        
    @http.route('/web/v2/content/bau/verify', type='json', auth='user', methods=['POST'], csrf=False)
    def verify_bau(self, **kw):
        """Verify BAU activity status (done/not_done) on same day or H+1 with reason"""
        try:
            if not kw.get('bau_id') or not kw.get('state'):
                return {'status': 'error', 'message': 'Missing bau_id or state'}
            
            bau = request.env['content.bau'].sudo().browse(int(kw['bau_id']))
            if not bau.exists():
                return {'status': 'error', 'message': 'BAU activity not found'}
            
            # Cek tanggal saat ini
            current_date = fields.Date.today()  # Misalnya 10 Maret 2025
            activity_date = bau.date
            delta_days = (current_date - activity_date).days
            
            # Validasi tanggal verifikasi (H atau H+1)
            if delta_days < 0:
                return {
                    'status': 'error',
                    'message': f'Maaf, Anda tidak dapat memverifikasi aktivitas yang terjadi di masa depan (tanggal aktivitas: {activity_date}).'
                }
            elif delta_days > 1:
                return {
                    'status': 'error',
                    'message': f'Verifikasi harus dilakukan pada hari yang sama atau H+1 (tanggal aktivitas: {activity_date})'
                }
            elif delta_days == 1:  # H+1
                if not kw.get('verification_reason'):
                    return {
                        'status': 'error',
                        'message': 'Alasan verifikasi diperlukan untuk verifikasi H+1'
                    }
            
            # Validasi state
            new_state = kw['state']
            if new_state not in ['done', 'not_done']:
                return {'status': 'error', 'message': 'State must be "done" or "not_done"'}
            
            # Update status dan verifikasi
            update_values = {
                'state': new_state,
                'verified_by': request.env.user.employee_id.id,
                'verification_date': fields.Datetime.now(),
                'hours_spent': float(kw.get('hours_spent', bau.hours_spent)),  # Opsional
            }
            if delta_days == 1:
                update_values['verification_reason'] = kw['verification_reason']
            
            bau.write(update_values)
            
            # Catat log aktivitas
            log_message = f"Status changed to {new_state} by {request.env.user.name}"
            if delta_days == 1:
                log_message += f"\nReason for H+1 verification: {kw['verification_reason']}"
            bau.message_post(body=log_message)
            
            return {
                'status': 'success',
                'data': self._prepare_bau_data(bau),
                'message': f'BAU activity {bau.name} verified as {new_state}'
            }
            
        except Exception as e:
            _logger.error('Error verifying BAU: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error verifying BAU: {str(e)}'
            }
        
    @http.route('/web/v2/content/dashboard', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kw):
        """
        Get comprehensive dashboard data for monitoring projects, tasks, and BAU activities
        """
        try:
            # Dapatkan filter dari parameter
            date_from = kw.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            date_to = kw.get('date_to', datetime.now().strftime('%Y-%m-%d'))
            filter_creator_id = int(kw['creator_id']) if kw.get('creator_id') else False
            filter_project_id = int(kw['project_id']) if kw.get('project_id') else False
            
            # Buat tanggal untuk query
            date_from_obj = fields.Date.from_string(date_from)
            date_to_obj = fields.Date.from_string(date_to)
            
            # Inisialisasi data dashboard
            dashboard_data = {
                'summary': self._get_dashboard_summary(date_from, date_to, filter_creator_id, filter_project_id),
                'projects': self._get_dashboard_projects(date_from, date_to, filter_project_id),
                'tasks': self._get_dashboard_tasks(date_from, date_to, filter_creator_id, filter_project_id),
                'bau': self._get_dashboard_bau(date_from, date_to, filter_creator_id),
                'team_performance': self._get_team_performance(date_from, date_to, filter_project_id),
                'revisions': self._get_revision_metrics(date_from, date_to, filter_creator_id, filter_project_id),
                'time_tracking': self._get_time_tracking_data(date_from, date_to, filter_creator_id, filter_project_id),
                'trends': self._get_trend_data(date_from, date_to)
            }
            
            return {
                'status': 'success',
                'data': dashboard_data
            }
            
        except Exception as e:
            _logger.error('Error in dashboard data: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error fetching dashboard data: {str(e)}'
            }
    
    def _get_dashboard_summary(self, date_from, date_to, filter_creator_id, filter_project_id):
        """
        Get summary statistics for dashboard
        """
        # Setup domain filters
        project_domain = []
        task_domain = []
        bau_domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ]
        
        if filter_project_id:
            project_domain.append(('id', '=', filter_project_id))
            task_domain.append(('project_id', '=', filter_project_id))
            bau_domain.append(('project_id', '=', filter_project_id))
        
        if filter_creator_id:
            task_domain.append(('assigned_to', 'in', [filter_creator_id]))
            bau_domain.append(('creator_id', '=', filter_creator_id))
        
        # Get projects statistics
        projects = request.env['content.project'].sudo().search(project_domain)
        active_projects = projects.filtered(lambda p: p.state == 'in_progress')
        completed_projects = projects.filtered(lambda p: p.state == 'completed')
        
        # Get tasks statistics
        all_tasks = request.env['content.task'].sudo().search(task_domain)
        pending_tasks = all_tasks.filtered(lambda t: t.state in ['draft', 'in_progress', 'review', 'revision'])
        completed_tasks = all_tasks.filtered(lambda t: t.state == 'done')
        
        # Filter tasks in date range
        tasks_in_period = all_tasks.filtered(
            lambda t: (t.actual_date_start and t.actual_date_start.date() >= fields.Date.from_string(date_from)) or
                    (t.planned_date_start and t.planned_date_start.date() >= fields.Date.from_string(date_from))
        )
        
        # Calculate on-time completion rate
        on_time_tasks = 0
        delayed_tasks = 0
        for task in completed_tasks:
            if task.planned_date_end and task.actual_date_end:
                if task.actual_date_end <= task.planned_date_end:
                    on_time_tasks += 1
                else:
                    delayed_tasks += 1
        
        on_time_rate = (on_time_tasks / len(completed_tasks) * 100) if completed_tasks else 0
        
        # Get BAU statistics
        bau_activities = request.env['content.bau'].sudo().search(bau_domain)
        planned_bau = bau_activities.filtered(lambda b: b.state == 'planned')
        completed_bau = bau_activities.filtered(lambda b: b.state == 'done')
        
        bau_completion_rate = (len(completed_bau) / len(bau_activities) * 100) if bau_activities else 0
        
        # Get time tracking data for tasks
        total_planned = 0
        total_actual = 0
        
        planned_vs_actual = []
        for task in all_tasks.filtered(lambda t: t.state == 'done'):
            if task.planned_hours > 0:
                planned_vs_actual.append({
                    'id': task.id,
                    'name': task.name,
                    'content_type': task.content_type,
                    'planned_hours': task.planned_hours,
                    'actual_hours': task.actual_hours,
                    'variance': task.actual_hours - task.planned_hours,
                    'variance_percent': ((task.actual_hours - task.planned_hours) / task.planned_hours * 100) if task.planned_hours else 0
                })
                total_planned += task.planned_hours
                total_actual += task.actual_hours
        
        # Sort by variance (highest first)
        planned_vs_actual.sort(key=lambda x: abs(x['variance']), reverse=True)
        
        # Time spent by content type
        time_by_type = defaultdict(lambda: {'planned': 0, 'actual': 0, 'tasks': 0})
        
        for task in all_tasks:
            if task.content_type:
                time_by_type[task.content_type]['planned'] += task.planned_hours
                time_by_type[task.content_type]['actual'] += task.actual_hours
                time_by_type[task.content_type]['tasks'] += 1
        
        type_time_data = []
        for type_name, data in time_by_type.items():
            avg_planned = data['planned'] / data['tasks'] if data['tasks'] > 0 else 0
            avg_actual = data['actual'] / data['tasks'] if data['tasks'] > 0 else 0
            
            type_time_data.append({
                'type': type_name,
                'total_planned': round(data['planned'], 1),
                'total_actual': round(data['actual'], 1),
                'avg_planned': round(avg_planned, 1),
                'avg_actual': round(avg_actual, 1),
                'task_count': data['tasks']
            })
        
        # BAU hours by day
        hours_by_day = defaultdict(float)
        for bau in bau_activities:
            day_key = str(bau.date)
            hours_by_day[day_key] += bau.hours_spent
        
        daily_hours = []
        for day, hours in hours_by_day.items():
            daily_hours.append({
                'date': day,
                'hours': round(hours, 1)
            })
        
        # Sort by date
        daily_hours.sort(key=lambda x: x['date'])
        
        # Combine into summary
        summary = {
            'period': {
                'from': date_from,
                'to': date_to
            },
            'projects': {
                'total': len(projects),
                'active': len(active_projects),
                'completed': len(completed_projects),
                'avg_progress': sum(p.progress for p in projects) / len(projects) if projects else 0,
            },
            'tasks': {
                'total': len(all_tasks),
                'pending': len(pending_tasks),
                'completed': len(completed_tasks),
                'completion_rate': (len(completed_tasks) / len(all_tasks) * 100) if all_tasks else 0,
                'on_time_rate': on_time_rate
            },
            'bau': {
                'total': len(bau_activities),
                'planned': len(planned_bau),
                'completed': len(completed_bau),
                'completion_rate': bau_completion_rate
            },
            'time_tracking': {
                'planned_vs_actual': planned_vs_actual[:10],  # Top 10 by variance
                'by_content_type': type_time_data,
                'bau_daily_hours': daily_hours,
                'summary': {
                    'total_planned_hours': round(total_planned, 1),
                    'total_actual_hours': round(total_actual, 1),
                    'variance': round(total_actual - total_planned, 1),
                    'variance_percent': round(((total_actual - total_planned) / total_planned * 100) if total_planned else 0, 1),
                    'total_bau_hours': round(sum(bau.hours_spent for bau in bau_activities), 1)
                }
            }
        }
        
        return summary

    def _get_trend_data(self, date_from, date_to):
        """
        Get trend data for various metrics over time
        """
        # Convert date strings to date objects
        start_date = fields.Date.from_string(date_from)
        end_date = fields.Date.from_string(date_to)
        
        # Calculate date range
        delta = (end_date - start_date).days + 1
        
        # Determine appropriate grouping (daily, weekly, or monthly)
        grouping = 'daily'
        if delta > 60:
            grouping = 'monthly'
        elif delta > 14:
            grouping = 'weekly'
        
        # Initialize data structures based on grouping
        time_periods = []
        if grouping == 'daily':
            current = start_date
            while current <= end_date:
                time_periods.append(str(current))
                current += timedelta(days=1)
        elif grouping == 'weekly':
            # Get start of week
            current = start_date - timedelta(days=start_date.weekday())
            while current <= end_date:
                week_end = current + timedelta(days=6)
                time_periods.append(f"{current} to {week_end}")
                current += timedelta(days=7)
        else:  # monthly
            current = start_date.replace(day=1)
            while current <= end_date:
                # Get last day of month
                if current.month == 12:
                    last_day = current.replace(day=31)
                else:
                    last_day = current.replace(month=current.month+1, day=1) - timedelta(days=1)
                time_periods.append(f"{current.year}-{current.month}")
                
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year+1, month=1)
                else:
                    current = current.replace(month=current.month+1)
        
        # Initialize trend data
        trend_data = {
            'time_periods': time_periods,
            'grouping': grouping,
            'task_completion': [0] * len(time_periods),
            'task_creation': [0] * len(time_periods),
            'bau_completion': [0] * len(time_periods),
            'avg_revision_count': [0] * len(time_periods),
            'project_progress': []  # Will store project progress over time
        }
        
        # Get task data
        tasks = request.env['content.task'].sudo().search([])
        
        for task in tasks:
            # Track task creation and completion
            if task.create_date:
                created_date = task.create_date.date()
                if start_date <= created_date <= end_date:
                    if grouping == 'daily':
                        idx = time_periods.index(str(created_date))
                    elif grouping == 'weekly':
                        # Find the week
                        week_start = created_date - timedelta(days=created_date.weekday())
                        week_end = week_start + timedelta(days=6)
                        week_str = f"{week_start} to {week_end}"
                        if week_str in time_periods:
                            idx = time_periods.index(week_str)
                        else:
                            idx = -1
                    else:  # monthly
                        month_str = f"{created_date.year}-{created_date.month}"
                        if month_str in time_periods:
                            idx = time_periods.index(month_str)
                        else:
                            idx = -1
                    
                    if idx >= 0:
                        trend_data['task_creation'][idx] += 1
            
            if task.state == 'done' and task.actual_date_end:
                completed_date = task.actual_date_end.date()
                if start_date <= completed_date <= end_date:
                    if grouping == 'daily':
                        idx = time_periods.index(str(completed_date))
                    elif grouping == 'weekly':
                        # Find the week
                        week_start = completed_date - timedelta(days=completed_date.weekday())
                        week_end = week_start + timedelta(days=6)
                        week_str = f"{week_start} to {week_end}"
                        if week_str in time_periods:
                            idx = time_periods.index(week_str)
                        else:
                            idx = -1
                    else:  # monthly
                        month_str = f"{completed_date.year}-{completed_date.month}"
                        if month_str in time_periods:
                            idx = time_periods.index(month_str)
                        else:
                            idx = -1
                    
                    if idx >= 0:
                        trend_data['task_completion'][idx] += 1
        
        # Get BAU data
        bau_activities = request.env['content.bau'].sudo().search([
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ])
        
        for bau in bau_activities:
            if bau.state == 'done' and bau.date:
                completed_date = bau.date
                if start_date <= completed_date <= end_date:
                    if grouping == 'daily':
                        idx = time_periods.index(str(completed_date))
                    elif grouping == 'weekly':
                        # Find the week
                        week_start = completed_date - timedelta(days=completed_date.weekday())
                        week_end = week_start + timedelta(days=6)
                        week_str = f"{week_start} to {week_end}"
                        if week_str in time_periods:
                            idx = time_periods.index(week_str)
                        else:
                            idx = -1
                    else:  # monthly
                        month_str = f"{completed_date.year}-{completed_date.month}"
                        if month_str in time_periods:
                            idx = time_periods.index(month_str)
                        else:
                            idx = -1
                    
                    if idx >= 0:
                        trend_data['bau_completion'][idx] += 1
        
        # Get revision data over time
        revisions = request.env['content.revision'].sudo().search([])
        
        # Group revisions by time period
        revisions_by_period = [[] for _ in range(len(time_periods))]
        for revision in revisions:
            if revision.date_requested:
                revision_date = revision.date_requested.date()
                if start_date <= revision_date <= end_date:
                    if grouping == 'daily':
                        idx = time_periods.index(str(revision_date))
                    elif grouping == 'weekly':
                        # Find the week
                        week_start = revision_date - timedelta(days=revision_date.weekday())
                        week_end = week_start + timedelta(days=6)
                        week_str = f"{week_start} to {week_end}"
                        if week_str in time_periods:
                            idx = time_periods.index(week_str)
                        else:
                            idx = -1
                    else:  # monthly
                        month_str = f"{revision_date.year}-{revision_date.month}"
                        if month_str in time_periods:
                            idx = time_periods.index(month_str)
                        else:
                            idx = -1
                    
                    if idx >= 0:
                        revisions_by_period[idx].append(revision)
        
        # Calculate average revision count
        for i, period_revisions in enumerate(revisions_by_period):
            if period_revisions:
                # Count unique tasks with revisions in this period
                unique_tasks = set(r.task_id.id for r in period_revisions if r.task_id)
                if unique_tasks:
                    trend_data['avg_revision_count'][i] = round(len(period_revisions) / len(unique_tasks), 1)
        
        # Get project progress over time for active projects
        active_projects = request.env['content.project'].sudo().search([
            ('state', '=', 'in_progress')
        ])
        
        for project in active_projects:
            # Get task completion dates to estimate progress over time
            completed_tasks = project.task_ids.filtered(lambda t: t.state == 'done' and t.actual_date_end)
            if not completed_tasks:
                continue
                
            # Sort by completion date
            sorted_tasks = sorted(completed_tasks, key=lambda t: t.actual_date_end)
            
            total_tasks = len(project.task_ids)
            if total_tasks == 0:
                continue
                
            # Track progress over time
            project_progress = {
                'id': project.id,
                'name': project.name,
                'progress': []
            }
            
            task_count = 0
            for task in sorted_tasks:
                task_count += 1
                progress = (task_count / total_tasks) * 100
                
                completed_date = task.actual_date_end.date()
                if start_date <= completed_date <= end_date:
                    project_progress['progress'].append({
                        'date': str(completed_date),
                        'progress': round(progress, 1)
                    })
            
            if project_progress['progress']:
                trend_data['project_progress'].append(project_progress)
        
        return trend_data
    
    def _get_dashboard_projects(self, date_from, date_to, filter_project_id):
        """
        Get detailed project data for dashboard
        """
        domain = []
        if filter_project_id:
            domain.append(('id', '=', filter_project_id))
        
        projects = request.env['content.project'].sudo().search(domain)
        
        # Calculate additional metrics for each project
        project_data = []
        for project in projects:
            # Task statistics
            total_tasks = len(project.task_ids)
            completed_tasks = len(project.task_ids.filtered(lambda t: t.state == 'done'))
            
            # Detect potential delays
            delayed_tasks = 0
            for task in project.task_ids:
                if task.state != 'done' and task.planned_date_end and fields.Datetime.now() > task.planned_date_end:
                    delayed_tasks += 1
            
            # Calculate time to completion estimate
            remaining_tasks = total_tasks - completed_tasks
            avg_task_days = 0
            if completed_tasks:
                completed_with_dates = project.task_ids.filtered(lambda t: t.state == 'done' and t.actual_date_start and t.actual_date_end)
                if completed_with_dates:
                    total_days = sum((t.actual_date_end - t.actual_date_start).days + 1 for t in completed_with_dates)
                    avg_task_days = total_days / len(completed_with_dates)
            
            estimated_days_left = remaining_tasks * avg_task_days if avg_task_days else 0
            
            # Calculate if project is at risk
            is_at_risk = False
            if project.state == 'in_progress':
                if delayed_tasks > 0:
                    is_at_risk = True
                elif project.date_end:
                    days_left = (project.date_end - fields.Date.today()).days
                    if estimated_days_left > days_left and days_left > 0:
                        is_at_risk = True
            
            project_item = {
                'id': project.id,
                'name': project.name,
                'code': project.code,
                'dates': {
                    'start': project.date_start,
                    'end': project.date_end,
                    'days_left': (project.date_end - fields.Date.today()).days if project.date_end else 0
                },
                'manager': {
                    'id': project.project_manager_id.id,
                    'name': project.project_manager_id.name
                },
                'content_plan': {
                    'video': project.planned_video_count,
                    'design': project.planned_design_count,
                    'total': project.planned_video_count + project.planned_design_count
                },
                'tasks': {
                    'total': total_tasks,
                    'completed': completed_tasks,
                    'delayed': delayed_tasks,
                    'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks else 0
                },
                'progress': project.progress,
                'state': project.state,
                'risk_assessment': {
                    'is_at_risk': is_at_risk,
                    'estimated_days_left': round(estimated_days_left, 1),
                    'risk_factors': []
                }
            }
            
            # Add risk factors
            risk_factors = []
            if delayed_tasks > 0:
                risk_factors.append(f"{delayed_tasks} delayed tasks")
            if project.date_end and estimated_days_left > (project.date_end - fields.Date.today()).days > 0:
                risk_factors.append("Estimated completion exceeds deadline")
            if project.progress < 40 and (project.date_end - fields.Date.today()).days < 7:
                risk_factors.append("Low progress with approaching deadline")
                
            project_item['risk_assessment']['risk_factors'] = risk_factors
            
            project_data.append(project_item)
        
        # Sort projects by risk (at-risk first) and then by days left
        project_data.sort(key=lambda x: (not x['risk_assessment']['is_at_risk'], x['dates']['days_left']))
        
        return project_data
    
    def _get_dashboard_tasks(self, date_from, date_to, filter_creator_id, filter_project_id):
        """
        Get task analytics for dashboard
        """
        domain = []
        if filter_project_id:
            domain.append(('project_id', '=', filter_project_id))
        if filter_creator_id:
            domain.append(('assigned_to', 'in', [filter_creator_id]))
        
        # Get all tasks within projects (even if outside date range)
        all_tasks = request.env['content.task'].sudo().search(domain)
        
        # Task completion trend
        completed_by_week = defaultdict(int)
        pending_by_status = defaultdict(int)
        
        for task in all_tasks:
            # Count tasks by status
            if task.state != 'done':
                pending_by_status[task.state] += 1
            elif task.actual_date_end:
                # Group completed tasks by week
                week = task.actual_date_end.strftime('%Y-W%W')
                completed_by_week[week] += 1
        
        # Task distribution by type
        task_types = defaultdict(int)
        for task in all_tasks:
            task_types[task.content_type] += 1
        
        # Task duration analysis
        task_durations = []
        for task in all_tasks:
            if task.state == 'done' and task.actual_date_start and task.actual_date_end:
                duration_days = (task.actual_date_end - task.actual_date_start).days
                task_durations.append({
                    'task_id': task.id,
                    'name': task.name,
                    'duration_days': duration_days,
                    'content_type': task.content_type
                })
        
        # Sort by duration (longest first)
        task_durations.sort(key=lambda x: x['duration_days'], reverse=True)
        
        # Recent completed tasks
        recent_completed = []
        for task in all_tasks:
            if task.state == 'done' and task.actual_date_end:
                if fields.Date.from_string(date_from) <= task.actual_date_end.date() <= fields.Date.from_string(date_to):
                    recent_completed.append({
                        'id': task.id,
                        'name': task.name,
                        'project_id': task.project_id.id,
                        'project_name': task.project_id.name,
                        'content_type': task.content_type,
                        'completed_date': task.actual_date_end,
                        'assigned_to': [{
                            'id': member.id,
                            'name': member.name
                        } for member in task.assigned_to]
                    })
        
        # Sort by completion date (most recent first)
        recent_completed.sort(key=lambda x: x['completed_date'], reverse=True)
        
        # Upcoming deadlines
        upcoming_deadlines = []
        for task in all_tasks:
            if task.state != 'done' and task.planned_date_end:
                # Include tasks with deadlines in next 7 days
                days_until_deadline = (task.planned_date_end - fields.Datetime.now()).days
                if 0 <= days_until_deadline <= 7:
                    upcoming_deadlines.append({
                        'id': task.id,
                        'name': task.name,
                        'project_id': task.project_id.id,
                        'project_name': task.project_id.name,
                        'days_left': days_until_deadline,
                        'deadline': task.planned_date_end,
                        'state': task.state,
                        'assigned_to': [{
                            'id': member.id,
                            'name': member.name
                        } for member in task.assigned_to]
                    })
        
        # Sort by days left (urgent first)
        upcoming_deadlines.sort(key=lambda x: x['days_left'])
        
        return {
            'completion_trend': [{'week': week, 'count': count} for week, count in sorted(completed_by_week.items())],
            'pending_by_status': [{'status': status, 'count': count} for status, count in pending_by_status.items()],
            'by_type': [{'type': type, 'count': count} for type, count in task_types.items()],
            'durations': task_durations[:10],  # Top 10 longest tasks
            'recent_completed': recent_completed[:5],  # 5 most recent completions
            'upcoming_deadlines': upcoming_deadlines[:10]  # 10 most urgent deadlines
        }
    
    def _get_dashboard_bau(self, date_from, date_to, filter_creator_id):
        """
        Get BAU analytics for dashboard
        """
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ]
        
        if filter_creator_id:
            domain.append(('creator_id', '=', filter_creator_id))
        
        bau_activities = request.env['content.bau'].sudo().search(domain)
        
        # BAU completion rate by day
        bau_by_day = defaultdict(lambda: {'total': 0, 'completed': 0})
        
        # BAU hours by type
        hours_by_type = defaultdict(float)
        
        # BAU activities by creator
        activities_by_creator = defaultdict(lambda: {'total': 0, 'completed': 0, 'hours': 0.0})
        
        for bau in bau_activities:
            # Group by day
            day_key = str(bau.date)
            bau_by_day[day_key]['total'] += 1
            if bau.state == 'done':
                bau_by_day[day_key]['completed'] += 1
            
            # Sum hours by type
            hours_by_type[bau.activity_type] += bau.hours_spent
            
            # Group by creator
            creator_key = bau.creator_id.id
            creator_name = bau.creator_id.name
            activities_by_creator[creator_key]['name'] = creator_name
            activities_by_creator[creator_key]['total'] += 1
            activities_by_creator[creator_key]['hours'] += bau.hours_spent
            if bau.state == 'done':
                activities_by_creator[creator_key]['completed'] += 1
        
        # Calculate completion rates for each day and creator
        daily_completion = []
        for day, counts in bau_by_day.items():
            completion_rate = (counts['completed'] / counts['total'] * 100) if counts['total'] else 0
            daily_completion.append({
                'date': day,
                'total': counts['total'],
                'completed': counts['completed'],
                'completion_rate': round(completion_rate, 1)
            })
        
        # Sort by date
        daily_completion.sort(key=lambda x: x['date'])
        
        # Format hours by type
        hours_data = [{'type': type, 'hours': hours} for type, hours in hours_by_type.items()]
        
        # Format and calculate for creators
        creator_performance = []
        for creator_id, data in activities_by_creator.items():
            completion_rate = (data['completed'] / data['total'] * 100) if data['total'] else 0
            creator_performance.append({
                'id': creator_id,
                'name': data['name'],
                'total': data['total'],
                'completed': data['completed'],
                'hours': round(data['hours'], 1),
                'completion_rate': round(completion_rate, 1)
            })
        
        # Sort by completion rate (highest first)
        creator_performance.sort(key=lambda x: x['completion_rate'], reverse=True)
        
        return {
            'daily_completion': daily_completion,
            'hours_by_type': hours_data,
            'creator_performance': creator_performance,
            'summary': {
                'total_activities': sum(data['total'] for data in daily_completion),
                'completed_activities': sum(data['completed'] for data in daily_completion),
                'total_hours': sum(data['hours'] for data in hours_data),
                'avg_completion_rate': round(sum(data['completion_rate'] for data in daily_completion) / len(daily_completion), 1) if daily_completion else 0
            }
        }
    
    def _get_team_performance(self, date_from, date_to, filter_project_id):
        """
        Get team performance metrics for dashboard
        """
        # Get all employees involved in projects
        domain = []
        if filter_project_id:
            domain.append(('id', '=', filter_project_id))
        
        projects = request.env['content.project'].sudo().search(domain)
        
        team_members = set()
        for project in projects:
            if project.project_manager_id:
                team_members.add(project.project_manager_id.id)
            team_members.update(member.id for member in project.team_ids)
        
        # Get tasks assigned to each team member
        performance_data = []
        for member_id in team_members:
            employee = request.env['hr.employee'].sudo().browse(member_id)
            if not employee.exists():
                continue
            
            # Tasks assigned to this member
            task_domain = [('assigned_to', 'in', [member_id])]
            if filter_project_id:
                task_domain.append(('project_id', '=', filter_project_id))
            
            tasks = request.env['content.task'].sudo().search(task_domain)
            
            # Calculate metrics
            total_tasks = len(tasks)
            completed_tasks = len(tasks.filtered(lambda t: t.state == 'done'))
            tasks_in_progress = len(tasks.filtered(lambda t: t.state in ['in_progress', 'review', 'revision']))
            
            # On-time completion
            on_time_tasks = 0
            for task in tasks.filtered(lambda t: t.state == 'done'):
                if task.planned_date_end and task.actual_date_end and task.actual_date_end <= task.planned_date_end:
                    on_time_tasks += 1
            
            # Calculate average revision count
            avg_revisions = sum(task.revision_count for task in tasks) / total_tasks if total_tasks else 0
            
            # Projects involved
            project_ids = set(task.project_id.id for task in tasks if task.project_id)
            projects_involved = len(project_ids)
            
            # Get BAU activities for this member
            bau_domain = [
                ('creator_id', '=', member_id), 
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ]
            bau_activities = request.env['content.bau'].sudo().search(bau_domain)
            
            # Calculate BAU metrics
            total_bau = len(bau_activities)
            completed_bau = len(bau_activities.filtered(lambda b: b.state == 'done'))
            total_hours = sum(bau.hours_spent for bau in bau_activities)
            
            # Add to performance data
            performance_data.append({
                'id': employee.id,
                'name': employee.name,
                'position': employee.job_id.name if employee.job_id else '',
                'tasks': {
                    'total': total_tasks,
                    'completed': completed_tasks,
                    'in_progress': tasks_in_progress,
                    'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks else 0,
                    'on_time_rate': (on_time_tasks / completed_tasks * 100) if completed_tasks else 0
                },
                'bau': {
                    'total': total_bau,
                    'completed': completed_bau,
                    'completion_rate': (completed_bau / total_bau * 100) if total_bau else 0,
                    'hours': total_hours
                },
                'revisions': {
                    'avg_per_task': round(avg_revisions, 1)
                },
                'projects_involved': projects_involved
            })
        
        # Sort by task completion rate (highest first)
        performance_data.sort(key=lambda x: x['tasks']['completion_rate'], reverse=True)
        
        return performance_data
    
    def _get_revision_metrics(self, date_from, date_to, filter_creator_id, filter_project_id):
        """
        Get revision analytics for dashboard
        """
        domain = []
        if filter_project_id:
            domain.append(('project_id', '=', filter_project_id))
        
        all_tasks = request.env['content.task'].sudo().search(domain)
        
        # Filter by assigned to if needed
        if filter_creator_id:
            all_tasks = all_tasks.filtered(lambda t: filter_creator_id in t.assigned_to.ids)
        
        # Tasks with high revision counts
        high_revision_tasks = all_tasks.filtered(lambda t: t.revision_count > 0)
        high_revision_tasks = sorted(high_revision_tasks, key=lambda t: t.revision_count, reverse=True)
        
        high_revision_data = []
        for task in high_revision_tasks[:10]:  # Top 10
            high_revision_data.append({
                'id': task.id,
                'name': task.name,
                'project_id': task.project_id.id,
                'project_name': task.project_id.name,
                'revision_count': task.revision_count,
                'state': task.state,
                'assigned_to': [{
                    'id': member.id,
                    'name': member.name
                } for member in task.assigned_to]
            })
        
        # Revision reasons analysis
        revisions = request.env['content.revision'].sudo().search([('task_id', 'in', all_tasks.ids)])
        
        # Count common phrases in feedback
        feedback_keywords = defaultdict(int)
        common_phrases = ["quality", "deadline", "format", "incorrect", "missing", "rework", "clarity", "alignment", "brand"]
        
        for revision in revisions:
            feedback_lower = revision.feedback.lower()
            for phrase in common_phrases:
                if phrase in feedback_lower:
                    feedback_keywords[phrase] += 1
        
        # Count revisions by requestor
        revisions_by_requestor = defaultdict(int)
        for revision in revisions:
            if revision.requested_by:
                requestor_id = revision.requested_by.id
                requestor_name = revision.requested_by.name
                key = f"{requestor_id}:{requestor_name}"
                revisions_by_requestor[key] += 1
        
        # Format for output
        feedback_analysis = [{'keyword': k, 'count': v} for k, v in feedback_keywords.items()]
        feedback_analysis.sort(key=lambda x: x['count'], reverse=True)
        
        requestor_analysis = []
        for key, count in revisions_by_requestor.items():
            id_str, name = key.split(':', 1)
            requestor_analysis.append({
                'id': int(id_str),
                'name': name,
                'count': count
            })
        
        requestor_analysis.sort(key=lambda x: x['count'], reverse=True)
        
        # Average revisions by content type
        revisions_by_type = defaultdict(lambda: {'count': 0, 'tasks': 0})
        for task in all_tasks:
            if task.content_type:
                revisions_by_type[task.content_type]['count'] += task.revision_count
                revisions_by_type[task.content_type]['tasks'] += 1
        
        type_analysis = []
        for type_name, data in revisions_by_type.items():
            avg_revisions = data['count'] / data['tasks'] if data['tasks'] > 0 else 0
            type_analysis.append({
                'type': type_name,
                'avg_revisions': round(avg_revisions, 2),
                'total_revisions': data['count'],
                'total_tasks': data['tasks']
            })
        
        type_analysis.sort(key=lambda x: x['avg_revisions'], reverse=True)
        
        return {
            'high_revision_tasks': high_revision_data,
            'feedback_analysis': feedback_analysis,
            'by_requestor': requestor_analysis,
            'by_content_type': type_analysis,
            'summary': {
                'total_revisions': sum(task.revision_count for task in all_tasks),
                'tasks_with_revisions': len(high_revision_tasks),
                'excessive_revisions_count': len(all_tasks.filtered(lambda t: t.has_excessive_revisions))
            }
        }
    
    def _get_time_tracking_data(self, date_from, date_to, filter_creator_id, filter_project_id):
        """
        Get time tracking analytics for dashboard
        """
        domain = []
        if filter_project_id:
            domain.append(('project_id', '=', filter_project_id))
        
        all_tasks = request.env['content.task'].sudo().search(domain)
        
        # Filter by assigned to if needed
        if filter_creator_id:
            all_tasks = all_tasks.filtered(lambda t: filter_creator_id in t.assigned_to.ids)
        
        # Planned vs. actual hours
        planned_vs_actual = []
        total_planned = 0
        total_actual = 0
        
        for task in all_tasks:
            if task.planned_hours > 0 and task.state == 'done':
                planned_vs_actual.append({
                    'id': task.id,
                    'name': task.name,
                    'content_type': task.content_type,
                    'planned_hours': task.planned_hours,
                    'actual_hours': task.actual_hours,
                    'variance': task.actual_hours - task.planned_hours,
                    'variance_percent': ((task.actual_hours - task.planned_hours) / task.planned_hours * 100) if task.planned_hours else 0
                })
                total_planned += task.planned_hours
                total_actual += task.actual_hours
        
        # Sort by variance (highest first)
        planned_vs_actual.sort(key=lambda x: abs(x['variance']), reverse=True)
        
        # Time spent by content type
        time_by_type = defaultdict(lambda: {'planned': 0, 'actual': 0, 'tasks': 0})
        
        for task in all_tasks:
            if task.content_type:
                time_by_type[task.content_type]['planned'] += task.planned_hours
                time_by_type[task.content_type]['actual'] += task.actual_hours
                time_by_type[task.content_type]['tasks'] += 1
        
        type_time_data = []
        for type_name, data in time_by_type.items():
            avg_planned = data['planned'] / data['tasks'] if data['tasks'] > 0 else 0
            avg_actual = data['actual'] / data['tasks'] if data['tasks'] > 0 else 0
            
            type_time_data.append({
                'type': type_name,
                'total_planned': round(data['planned'], 1),
                'total_actual': round(data['actual'], 1),
                'avg_planned': round(avg_planned, 1),
                'avg_actual': round(avg_actual, 1),
                'task_count': data['tasks']
            })
        
    @http.route('/web/v2/content/dashboard/workload', type='json', auth='user', methods=['POST'], csrf=False)
    def get_workload_analysis(self, **kw):
        """
        Get detailed workload analysis for team members
        """
        try:
            # Dapatkan filter dari parameter
            date_from = kw.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            date_to = kw.get('date_to', datetime.now().strftime('%Y-%m-%d'))
            
            # Get all employees
            employees = request.env['hr.employee'].sudo().search([])
            
            workload_data = []
            for employee in employees:
                # Get tasks assigned to this employee
                task_domain = [
                    ('assigned_to', 'in', [employee.id]),
                    '|',
                    '&', ('planned_date_start', '>=', date_from), ('planned_date_start', '<=', date_to),
                    '&', ('planned_date_end', '>=', date_from), ('planned_date_end', '<=', date_to)
                ]
                
                tasks = request.env['content.task'].sudo().search(task_domain)
                
                if not tasks:
                    continue  # Skip employees without tasks
                    
                # Calculate task distribution by day
                workload_by_day = defaultdict(int)
                
                for task in tasks:
                    if task.planned_date_start and task.planned_date_end:
                        # Calculate duration in days
                        start_date = task.planned_date_start.date()
                        end_date = task.planned_date_end.date()
                        
                        # Ensure dates are within range
                        if start_date < fields.Date.from_string(date_from):
                            start_date = fields.Date.from_string(date_from)
                        if end_date > fields.Date.from_string(date_to):
                            end_date = fields.Date.from_string(date_to)
                        
                        # Distribute workload across days
                        current_date = start_date
                        while current_date <= end_date:
                            workload_by_day[str(current_date)] += 1
                            current_date += timedelta(days=1)
                
                # Get BAU activities
                bau_domain = [
                    ('creator_id', '=', employee.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to)
                ]
                
                bau_activities = request.env['content.bau'].sudo().search(bau_domain)
                
                # Add BAU activities to workload
                for bau in bau_activities:
                    workload_by_day[str(bau.date)] += 1
                
                # Format daily workload
                daily_workload = []
                for day, count in workload_by_day.items():
                    daily_workload.append({
                        'date': day,
                        'count': count
                    })
                
                # Sort by date
                daily_workload.sort(key=lambda x: x['date'])
                
                # Calculate metrics
                total_task_days = sum(day['count'] for day in daily_workload)
                avg_daily_workload = round(total_task_days / len(daily_workload), 1) if daily_workload else 0
                
                # Find peak workload days
                peak_days = sorted(daily_workload, key=lambda x: x['count'], reverse=True)[:5]
                
                # Calculate overall capacity
                capacity_percent = min(avg_daily_workload / 5 * 100, 100)  # Assuming 5 tasks per day is 100% capacity
                
                workload_data.append({
                    'id': employee.id,
                    'name': employee.name,
                    'position': employee.job_id.name if employee.job_id else '',
                    'daily_workload': daily_workload,
                    'peak_days': peak_days,
                    'metrics': {
                        'total_tasks': len(tasks),
                        'total_bau': len(bau_activities),
                        'avg_daily_workload': avg_daily_workload,
                        'capacity_percent': round(capacity_percent, 1)
                    }
                })
            
            # Sort by capacity (highest first)
            workload_data.sort(key=lambda x: x['metrics']['capacity_percent'], reverse=True)
            
            return {
                'status': 'success',
                'data': workload_data
            }
            
        except Exception as e:
            _logger.error('Error in workload analysis: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error fetching workload data: {str(e)}'
            }

    @http.route('/web/v2/content/dashboard/risk', type='json', auth='user', methods=['POST'], csrf=False)
    def get_risk_assessment(self, **kw):
        """
        Get risk assessment for projects and tasks
        """
        try:
            # Get all active projects
            projects = request.env['content.project'].sudo().search([
                ('state', '=', 'in_progress')
            ])
            
            risk_data = {
                'at_risk_projects': [],
                'at_risk_tasks': [],
                'overdue_tasks': [],
                'bottlenecks': []
            }
            
            # Identify at-risk projects
            for project in projects:
                risk_factors = []
                risk_score = 0
                
                # Check deadline proximity
                if project.date_end:
                    days_left = (project.date_end - fields.Date.today()).days
                    if days_left < 0:
                        risk_factors.append("Project is past deadline")
                        risk_score += 50
                    elif days_left < 7:
                        risk_factors.append(f"Deadline approaching ({days_left} days left)")
                        risk_score += 30
                    elif days_left < 14:
                        risk_factors.append(f"Deadline approaching ({days_left} days left)")
                        risk_score += 15
                
                # Check progress vs time passed
                if project.date_start and project.date_end and project.progress:
                    total_days = (project.date_end - project.date_start).days
                    days_passed = (fields.Date.today() - project.date_start).days
                    
                    if total_days > 0 and 0 <= days_passed <= total_days:
                        expected_progress = (days_passed / total_days) * 100
                        progress_gap = expected_progress - project.progress
                        
                        if progress_gap > 30:
                            risk_factors.append(f"Significant progress gap ({round(progress_gap)}%)")
                            risk_score += 40
                        elif progress_gap > 15:
                            risk_factors.append(f"Progress gap ({round(progress_gap)}%)")
                            risk_score += 20
                
                # Check for delayed tasks
                delayed_tasks = 0
                for task in project.task_ids:
                    if task.state != 'done' and task.planned_date_end and fields.Datetime.now() > task.planned_date_end:
                        delayed_tasks += 1
                
                if delayed_tasks > 5:
                    risk_factors.append(f"Many delayed tasks ({delayed_tasks})")
                    risk_score += 40
                elif delayed_tasks > 0:
                    risk_factors.append(f"Some delayed tasks ({delayed_tasks})")
                    risk_score += delayed_tasks * 5
                
                # Check for excessive revisions
                excessive_revisions = len(project.task_ids.filtered(lambda t: t.has_excessive_revisions))
                if excessive_revisions > 3:
                    risk_factors.append(f"Multiple tasks with excessive revisions ({excessive_revisions})")
                    risk_score += 30
                elif excessive_revisions > 0:
                    risk_factors.append(f"Some tasks with excessive revisions ({excessive_revisions})")
                    risk_score += 15
                
                # Add to at-risk list if score is high
                if risk_score >= 30:
                    risk_level = "high" if risk_score >= 60 else "medium" if risk_score >= 30 else "low"
                    
                    risk_data['at_risk_projects'].append({
                        'id': project.id,
                        'name': project.name,
                        'manager': {
                            'id': project.project_manager_id.id,
                            'name': project.project_manager_id.name
                        },
                        'deadline': project.date_end,
                        'progress': project.progress,
                        'risk_factors': risk_factors,
                        'risk_score': risk_score,
                        'risk_level': risk_level
                    })
            
            # Sort at-risk projects by risk score
            risk_data['at_risk_projects'].sort(key=lambda x: x['risk_score'], reverse=True)
            
            # Identify at-risk tasks
            all_active_tasks = request.env['content.task'].sudo().search([
                ('state', 'in', ['draft', 'in_progress', 'review', 'revision'])
            ])
            
            for task in all_active_tasks:
                risk_factors = []
                risk_score = 0
                
                # Check deadline proximity
                if task.planned_date_end:
                    days_left = (task.planned_date_end - fields.Datetime.now()).days
                    if days_left < 0:
                        risk_factors.append("Task is past deadline")
                        risk_score += 50
                    elif days_left < 2:
                        risk_factors.append(f"Imminent deadline ({days_left} days left)")
                        risk_score += 40
                    elif days_left < 5:
                        risk_factors.append(f"Approaching deadline ({days_left} days left)")
                        risk_score += 20
                
                # Check revision count
                if task.revision_count > 3:
                    risk_factors.append(f"Multiple revisions ({task.revision_count})")
                    risk_score += task.revision_count * 5
                
                # Check if task is stuck in a status
                if task.state == 'in_progress' and task.actual_date_start:
                    days_in_progress = (fields.Datetime.now() - task.actual_date_start).days
                    if days_in_progress > 14:
                        risk_factors.append(f"Stuck in progress ({days_in_progress} days)")
                        risk_score += 30
                    elif days_in_progress > 7:
                        risk_factors.append(f"Long time in progress ({days_in_progress} days)")
                        risk_score += 15
                
                elif task.state == 'review':
                    # Assume review info is in activity logs/tracking
                    # This is a simplification - you may need to extract actual review time
                    risk_factors.append("Awaiting review")
                    risk_score += 10
                
                # Add to at-risk list if score is high
                if risk_score >= 30:
                    risk_level = "high" if risk_score >= 50 else "medium" if risk_score >= 30 else "low"
                    
                    at_risk_task = {
                        'id': task.id,
                        'name': task.name,
                        'project': {
                            'id': task.project_id.id,
                            'name': task.project_id.name
                        },
                        'assigned_to': [{
                            'id': member.id,
                            'name': member.name
                        } for member in task.assigned_to],
                        'deadline': task.planned_date_end,
                        'state': task.state,
                        'risk_factors': risk_factors,
                        'risk_score': risk_score,
                        'risk_level': risk_level
                    }
                    
                    # Add to at-risk tasks
                    risk_data['at_risk_tasks'].append(at_risk_task)
                    
                    # Also add to overdue if past deadline
                    if task.planned_date_end and fields.Datetime.now() > task.planned_date_end:
                        risk_data['overdue_tasks'].append(at_risk_task)
            
            # Sort at-risk tasks by risk score
            risk_data['at_risk_tasks'].sort(key=lambda x: x['risk_score'], reverse=True)
            risk_data['overdue_tasks'].sort(key=lambda x: x['risk_score'], reverse=True)
            
            # Identify bottlenecks - areas where tasks get stuck
            status_counts = defaultdict(int)
            for task in all_active_tasks:
                status_counts[task.state] += 1
            
            bottlenecks = []
            for status, count in status_counts.items():
                if count > 5:  # Arbitrary threshold
                    bottlenecks.append({
                        'status': status,
                        'task_count': count,
                        'percentage': round(count / len(all_active_tasks) * 100, 1) if all_active_tasks else 0
                    })
            
            # Sort bottlenecks by count
            bottlenecks.sort(key=lambda x: x['task_count'], reverse=True)
            risk_data['bottlenecks'] = bottlenecks
            
            return {
                'status': 'success',
                'data': risk_data
            }
            
        except Exception as e:
            _logger.error('Error in risk assessment: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error in risk assessment: {str(e)}'
            }

    @http.route('/web/v2/content/dashboard/efficiency', type='json', auth='user', methods=['POST'], csrf=False)
    def get_efficiency_metrics(self, **kw):
        """
        Get efficiency metrics and benchmarks for content production
        """
        try:
            # Dapatkan filter dari parameter
            date_from = kw.get('date_from', (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'))
            date_to = kw.get('date_to', datetime.now().strftime('%Y-%m-%d'))
            
            # Get completed tasks in date range
            completed_tasks = request.env['content.task'].sudo().search([
                ('state', '=', 'done'),
                ('actual_date_end', '>=', date_from),
                ('actual_date_end', '<=', date_to)
            ])
            
            efficiency_data = {
                'completion_time': {
                    'by_type': {},
                    'by_team_size': {},
                    'top_performers': []
                },
                'revision_efficiency': {
                    'by_type': {},
                    'by_assigned_to': []
                },
                'benchmarks': {
                    'ideal_completion_days': {},
                    'revision_benchmarks': {}
                }
            }
            
            # Analyze completion time by content type
            completion_by_type = defaultdict(list)
            
            for task in completed_tasks:
                if task.actual_date_start and task.actual_date_end and task.content_type:
                    # Calculate completion days
                    completion_days = (task.actual_date_end - task.actual_date_start).days + 1
                    
                    # Track by content type
                    completion_by_type[task.content_type].append({
                        'task_id': task.id,
                        'days': completion_days,
                        'assigned_to': len(task.assigned_to)
                    })
            
            # Calculate averages by type
            for content_type, tasks in completion_by_type.items():
                avg_days = sum(task['days'] for task in tasks) / len(tasks) if tasks else 0
                
                efficiency_data['completion_time']['by_type'][content_type] = {
                    'avg_days': round(avg_days, 1),
                    'task_count': len(tasks),
                    'fastest': min(tasks, key=lambda x: x['days'])['days'] if tasks else 0,
                    'slowest': max(tasks, key=lambda x: x['days'])['days'] if tasks else 0
                }
            
            # Analyze completion time by team size
            completion_by_team_size = defaultdict(list)
            
            for task in completed_tasks:
                if task.actual_date_start and task.actual_date_end:
                    team_size = len(task.assigned_to)
                    completion_days = (task.actual_date_end - task.actual_date_start).days + 1
                    
                    completion_by_team_size[team_size].append({
                        'task_id': task.id,
                        'days': completion_days,
                        'content_type': task.content_type
                    })
            
            # Calculate averages by team size
            for team_size, tasks in completion_by_team_size.items():
                avg_days = sum(task['days'] for task in tasks) / len(tasks) if tasks else 0
                
                efficiency_data['completion_time']['by_team_size'][str(team_size)] = {
                    'avg_days': round(avg_days, 1),
                    'task_count': len(tasks)
                }
            
            # Identify top performers
            employee_efficiency = defaultdict(lambda: {'tasks': 0, 'total_days': 0, 'revisions': 0})
            
            for task in completed_tasks:
                if task.actual_date_start and task.actual_date_end:
                    completion_days = (task.actual_date_end - task.actual_date_start).days + 1
                    
                    for employee in task.assigned_to:
                        employee_efficiency[employee.id]['name'] = employee.name
                        employee_efficiency[employee.id]['tasks'] += 1
                        employee_efficiency[employee.id]['total_days'] += completion_days
                        employee_efficiency[employee.id]['revisions'] += task.revision_count
            
            # Calculate efficiency metrics for employees
            top_performers = []
            for employee_id, data in employee_efficiency.items():
                if data['tasks'] >= 3:  # Only include employees with enough tasks for meaningful data
                    avg_days = data['total_days'] / data['tasks']
                    avg_revisions = data['revisions'] / data['tasks']
                    
                    efficiency_score = 100 - (avg_days * 5) - (avg_revisions * 10)  # Simple scoring formula
                    
                    top_performers.append({
                        'id': employee_id,
                        'name': data['name'],
                        'tasks_completed': data['tasks'],
                        'avg_days_per_task': round(avg_days, 1),
                        'avg_revisions': round(avg_revisions, 1),
                        'efficiency_score': max(round(efficiency_score, 1), 0)  # Ensure score isn't negative
                    })
            
            # Sort by efficiency score (highest first)
            top_performers.sort(key=lambda x: x['efficiency_score'], reverse=True)
            efficiency_data['completion_time']['top_performers'] = top_performers[:5]  # Top 5
            
            # Analyze revision efficiency
            revision_by_type = defaultdict(list)
            
            for task in completed_tasks:
                if task.content_type:
                    revision_by_type[task.content_type].append(task.revision_count)
            
            # Calculate revision averages by type
            for content_type, revisions in revision_by_type.items():
                avg_revisions = sum(revisions) / len(revisions) if revisions else 0
                
                efficiency_data['revision_efficiency']['by_type'][content_type] = {
                    'avg_revisions': round(avg_revisions, 1),
                    'min_revisions': min(revisions) if revisions else 0,
                    'max_revisions': max(revisions) if revisions else 0,
                    'task_count': len(revisions)
                }
            
            # Get revision efficiency by employee
            revision_by_employee = defaultdict(lambda: {'tasks': 0, 'revisions': 0})
            
            for task in completed_tasks:
                for employee in task.assigned_to:
                    revision_by_employee[employee.id]['name'] = employee.name
                    revision_by_employee[employee.id]['tasks'] += 1
                    revision_by_employee[employee.id]['revisions'] += task.revision_count
            
            # Calculate employee revision efficiency
            for employee_id, data in revision_by_employee.items():
                if data['tasks'] >= 3:  # Only include employees with enough tasks
                    avg_revisions = data['revisions'] / data['tasks']
                    
                    efficiency_data['revision_efficiency']['by_assigned_to'].append({
                        'id': employee_id,
                        'name': data['name'],
                        'tasks': data['tasks'],
                        'avg_revisions': round(avg_revisions, 1)
                    })
            
            # Sort by average revisions (lowest first, as fewer is better)
            efficiency_data['revision_efficiency']['by_assigned_to'].sort(key=lambda x: x['avg_revisions'])
            
            # Set benchmarks based on collected data
            for content_type, metrics in efficiency_data['completion_time']['by_type'].items():
                # Set ideal completion time as slightly better than average
                ideal_days = max(1, round(metrics['avg_days'] * 0.8, 1))  # 20% faster than average
                efficiency_data['benchmarks']['ideal_completion_days'][content_type] = ideal_days
            
            for content_type, metrics in efficiency_data['revision_efficiency']['by_type'].items():
                # Set revision benchmark as slightly better than average
                ideal_revisions = max(0, round(metrics['avg_revisions'] * 0.7, 1))  # 30% fewer revisions
                efficiency_data['benchmarks']['revision_benchmarks'][content_type] = ideal_revisions
            
            return {
                'status': 'success',
                'data': efficiency_data
            }
            
        except Exception as e:
            _logger.error('Error in efficiency metrics: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error calculating efficiency metrics: {str(e)}'
            }
        
    @http.route('/web/v2/content/dashboard/forecast', type='json', auth='user', methods=['POST'], csrf=False)
    def get_forecast_data(self, **kw):
        """
        Get forecast data for resource planning and delivery predictions
        """
        try:
            # Get filter parameters
            weeks_ahead = int(kw.get('weeks_ahead', 4))
            date_from = fields.Date.today()
            date_to = date_from + timedelta(days=weeks_ahead * 7)
            
            # Initialize forecast data
            forecast_data = {
                'resource_forecast': [],
                'delivery_forecast': [],
                'capacity_planning': {}
            }
            
            # Get all active projects
            active_projects = request.env['content.project'].sudo().search([
                ('state', '=', 'in_progress')
            ])
            
            # Get all pending tasks
            pending_tasks = request.env['content.task'].sudo().search([
                ('state', 'in', ['draft', 'in_progress', 'review', 'revision']),
                '|',
                ('planned_date_end', '>=', date_from),
                ('planned_date_end', '=', False)
            ])
            
            # Group tasks by planned completion date
            tasks_by_week = defaultdict(list)
            for task in pending_tasks:
                if task.planned_date_end:
                    week_num = (task.planned_date_end.date() - date_from).days // 7
                    if 0 <= week_num < weeks_ahead:
                        week_str = f"Week {week_num+1}"
                        tasks_by_week[week_str].append(task)
            
            # Format delivery forecast by week
            for week_num in range(weeks_ahead):
                week_str = f"Week {week_num+1}"
                week_start = date_from + timedelta(days=week_num * 7)
                week_end = week_start + timedelta(days=6)
                
                week_tasks = tasks_by_week.get(week_str, [])
                
                # Count by type
                video_count = len([t for t in week_tasks if t.content_type == 'video'])
                design_count = len([t for t in week_tasks if t.content_type == 'design'])
                
                forecast_data['delivery_forecast'].append({
                    'week': week_str,
                    'date_range': f"{week_start} to {week_end}",
                    'video_count': video_count,
                    'design_count': design_count,
                    'total_tasks': len(week_tasks),
                    'projects': len(set(t.project_id.id for t in week_tasks if t.project_id))
                })
            
            # Get all employees involved in content tasks
            employees_domain = []
            employees = request.env['hr.employee'].sudo().search(employees_domain)
            
            # Calculate resource allocation by week
            employee_allocations = {}
            for employee in employees:
                # Get tasks assigned to this employee in forecast period
                assigned_tasks = request.env['content.task'].sudo().search([
                    ('assigned_to', 'in', [employee.id]),
                    ('state', 'in', ['draft', 'in_progress', 'review', 'revision']),
                    '|',
                    '&', ('planned_date_start', '>=', date_from), ('planned_date_start', '<=', date_to),
                    '&', ('planned_date_end', '>=', date_from), ('planned_date_end', '<=', date_to)
                ])
                
                # Skip employees without upcoming tasks
                if not assigned_tasks:
                    continue
                
                # Initialize allocation data
                employee_data = {
                    'id': employee.id,
                    'name': employee.name,
                    'position': employee.job_id.name if employee.job_id else '',
                    'weekly_allocation': []
                }
                
                # Calculate allocation by week
                for week_num in range(weeks_ahead):
                    week_start = date_from + timedelta(days=week_num * 7)
                    week_end = week_start + timedelta(days=6)
                    week_str = f"Week {week_num+1}"
                    
                    # Count tasks active during this week
                    week_tasks = []
                    for task in assigned_tasks:
                        if (task.planned_date_start and task.planned_date_end and
                            ((task.planned_date_start.date() <= week_end and task.planned_date_end.date() >= week_start) or
                            (task.planned_date_start.date() >= week_start and task.planned_date_start.date() <= week_end))):
                            week_tasks.append(task)
                    
                    # Calculate allocation percentage (5 tasks = 100% allocation)
                    allocation_percent = min(len(week_tasks) * 20, 100)
                    
                    employee_data['weekly_allocation'].append({
                        'week': week_str,
                        'date_range': f"{week_start} to {week_end}",
                        'task_count': len(week_tasks),
                        'allocation_percent': allocation_percent,
                        'task_ids': [t.id for t in week_tasks]
                    })
                
                forecast_data['resource_forecast'].append(employee_data)
            
            # Sort by highest allocation
            forecast_data['resource_forecast'].sort(
                key=lambda x: sum(w['allocation_percent'] for w in x['weekly_allocation']), 
                reverse=True
            )
            
            # Calculate team capacity planning
            video_capacity = sum(1 for e in employees if e.job_id and 'video' in e.job_id.name.lower()) * 5  # Assuming 5 videos per video specialist per week
            design_capacity = sum(1 for e in employees if e.job_id and 'design' in e.job_id.name.lower()) * 5  # Assuming 5 designs per designer per week
            
            # If job titles don't include these terms, estimate based on past tasks
            if video_capacity == 0 or design_capacity == 0:
                # Get tasks in past 30 days
                past_tasks = request.env['content.task'].sudo().search([
                    ('state', '=', 'done'),
                    ('actual_date_end', '>=', fields.Date.today() - timedelta(days=30))
                ])
                
                # Count by type
                video_completed = len([t for t in past_tasks if t.content_type == 'video'])
                design_completed = len([t for t in past_tasks if t.content_type == 'design'])
                
                # Estimate weekly capacity
                if video_capacity == 0:
                    video_capacity = video_completed // 4  # Divide by 4 weeks
                if design_capacity == 0:
                    design_capacity = design_completed // 4  # Divide by 4 weeks
            
            # Calculate capacity utilization for each week
            capacity_utilization = []
            for week_num in range(weeks_ahead):
                week_str = f"Week {week_num+1}"
                week_forecast = next((w for w in forecast_data['delivery_forecast'] if w['week'] == week_str), None)
                
                if week_forecast:
                    video_utilization = (week_forecast['video_count'] / video_capacity * 100) if video_capacity > 0 else 0
                    design_utilization = (week_forecast['design_count'] / design_capacity * 100) if design_capacity > 0 else 0
                    
                    capacity_utilization.append({
                        'week': week_str,
                        'video': {
                            'capacity': video_capacity,
                            'planned': week_forecast['video_count'],
                            'utilization_percent': round(video_utilization, 1)
                        },
                        'design': {
                            'capacity': design_capacity,
                            'planned': week_forecast['design_count'],
                            'utilization_percent': round(design_utilization, 1)
                        }
                    })
            
            forecast_data['capacity_planning'] = {
                'weekly_utilization': capacity_utilization,
                'team_capacity': {
                    'video': video_capacity,
                    'design': design_capacity
                }
            }
            
            return {
                'status': 'success',
                'data': forecast_data
            }
            
        except Exception as e:
            _logger.error('Error in forecast data: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error generating forecast: {str(e)}'
            }

    @http.route('/web/v2/content/dashboard/kpi', type='json', auth='user', methods=['POST'], csrf=False)
    def get_kpi_metrics(self, **kw):
        """
        Get KPI metrics for dashboard
        """
        try:
            # Get filter parameters
            date_from = kw.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            date_to = kw.get('date_to', datetime.now().strftime('%Y-%m-%d'))
            
            # Initialize KPI data
            kpi_data = {
                'task_metrics': {},
                'project_metrics': {},
                'team_metrics': {},
                'quality_metrics': {}
            }
            
            # Get tasks in date range
            task_domain = [
                '|',
                '&', ('planned_date_start', '>=', date_from), ('planned_date_start', '<=', date_to),
                '&', ('actual_date_end', '>=', date_from), ('actual_date_end', '<=', date_to)
            ]
            
            tasks = request.env['content.task'].sudo().search(task_domain)
            
            # Task completion KPIs
            completed_tasks = tasks.filtered(lambda t: t.state == 'done')
            total_tasks = len(tasks)
            completion_rate = (len(completed_tasks) / total_tasks * 100) if total_tasks > 0 else 0
            
            # On-time delivery
            on_time_tasks = 0
            delayed_tasks = 0
            
            for task in completed_tasks:
                if task.planned_date_end and task.actual_date_end:
                    if task.actual_date_end <= task.planned_date_end:
                        on_time_tasks += 1
                    else:
                        delayed_tasks += 1
            
            on_time_rate = (on_time_tasks / len(completed_tasks) * 100) if completed_tasks else 0
            
            # Average time to complete
            completion_days = []
            for task in completed_tasks:
                if task.actual_date_start and task.actual_date_end:
                    days = (task.actual_date_end - task.actual_date_start).days + 1
                    completion_days.append(days)
            
            avg_completion_days = sum(completion_days) / len(completion_days) if completion_days else 0
            
            # Task KPIs
            kpi_data['task_metrics'] = {
                'total_tasks': total_tasks,
                'completed_tasks': len(completed_tasks),
                'completion_rate': round(completion_rate, 1),
                'on_time_delivery_rate': round(on_time_rate, 1),
                'avg_days_to_complete': round(avg_completion_days, 1),
                'by_content_type': {}
            }
            
            # KPIs by content type
            for content_type in ['video', 'design']:
                type_tasks = tasks.filtered(lambda t: t.content_type == content_type)
                type_completed = type_tasks.filtered(lambda t: t.state == 'done')
                
                if type_tasks:
                    type_completion_rate = (len(type_completed) / len(type_tasks) * 100)
                    
                    # Calculate on-time rate for this type
                    type_on_time = 0
                    for task in type_completed:
                        if task.planned_date_end and task.actual_date_end and task.actual_date_end <= task.planned_date_end:
                            type_on_time += 1
                    
                    type_on_time_rate = (type_on_time / len(type_completed) * 100) if type_completed else 0
                    
                    # Calculate average completion days
                    type_days = []
                    for task in type_completed:
                        if task.actual_date_start and task.actual_date_end:
                            days = (task.actual_date_end - task.actual_date_start).days + 1
                            type_days.append(days)
                    
                    type_avg_days = sum(type_days) / len(type_days) if type_days else 0
                    
                    kpi_data['task_metrics']['by_content_type'][content_type] = {
                        'total': len(type_tasks),
                        'completed': len(type_completed),
                        'completion_rate': round(type_completion_rate, 1),
                        'on_time_rate': round(type_on_time_rate, 1),
                        'avg_days': round(type_avg_days, 1)
                    }
            
            # Project KPIs
            projects = request.env['content.project'].sudo().search([
                '|',
                '&', ('date_start', '>=', date_from), ('date_start', '<=', date_to),
                '&', ('date_end', '>=', date_from), ('date_end', '<=', date_to)
            ])
            
            active_projects = len(projects.filtered(lambda p: p.state == 'in_progress'))
            completed_projects = len(projects.filtered(lambda p: p.state == 'completed'))
            
            # Calculate average project completion percentage
            avg_progress = sum(p.progress for p in projects) / len(projects) if projects else 0
            
            # Calculate estimated completion accuracy
            completion_accuracy = 0
            completed_with_dates = projects.filtered(lambda p: p.state == 'completed' and p.date_start and p.date_end)
            if completed_with_dates:
                for project in completed_with_dates:
                    planned_days = (project.date_end - project.date_start).days
                    # This is an estimation since we don't have actual completion date
                    # In a real system, you might store actual completion date
                    # For now, we'll use today's date as a proxy for completed projects
                    actual_days = (fields.Date.today() - project.date_start).days
                    
                    accuracy = (1 - abs(planned_days - actual_days) / planned_days) * 100 if planned_days > 0 else 0
                    completion_accuracy += accuracy
                
                completion_accuracy /= len(completed_with_dates)
            
            kpi_data['project_metrics'] = {
                'total_projects': len(projects),
                'active_projects': active_projects,
                'completed_projects': completed_projects,
                'avg_progress': round(avg_progress, 1),
                'completion_estimate_accuracy': round(completion_accuracy, 1)
            }
            
            # Team KPIs
            # Get all employees involved in content tasks
            employee_ids = set()
            for task in tasks:
                for employee in task.assigned_to:
                    employee_ids.add(employee.id)
            
            employees = request.env['hr.employee'].sudo().browse(list(employee_ids))
            
            # Calculate workload and productivity metrics
            productivity_data = []
            for employee in employees:
                employee_tasks = tasks.filtered(lambda t: employee.id in t.assigned_to.ids)
                completed = len(employee_tasks.filtered(lambda t: t.state == 'done'))
                
                # Skip employees with no completed tasks
                if completed == 0:
                    continue
                
                total = len(employee_tasks)
                
                # Calculate productivity score
                completion_rate = (completed / total * 100) if total > 0 else 0
                
                # Calculate average days to complete
                avg_days = 0
                days_count = 0
                for task in employee_tasks.filtered(lambda t: t.state == 'done' and t.actual_date_start and t.actual_date_end):
                    avg_days += (task.actual_date_end - task.actual_date_start).days + 1
                    days_count += 1
                
                if days_count > 0:
                    avg_days /= days_count
                
                # Calculate quality score based on revisions
                avg_revisions = sum(task.revision_count for task in employee_tasks) / total if total > 0 else 0
                quality_score = max(0, 100 - (avg_revisions * 15))  # Simple formula: fewer revisions = higher quality
                
                # Calculate overall productivity score
                productivity_score = (completion_rate * 0.4) + ((1 / (avg_days or 1)) * 50) + (quality_score * 0.3)
                
                productivity_data.append({
                    'id': employee.id,
                    'name': employee.name,
                    'position': employee.job_id.name if employee.job_id else '',
                    'tasks_total': total,
                    'tasks_completed': completed,
                    'completion_rate': round(completion_rate, 1),
                    'avg_days_to_complete': round(avg_days, 1),
                    'avg_revisions': round(avg_revisions, 1),
                    'quality_score': round(quality_score, 1),
                    'productivity_score': round(min(productivity_score, 100), 1)  # Cap at 100
                })
            
            # Sort by productivity score
            productivity_data.sort(key=lambda x: x['productivity_score'], reverse=True)
            
            kpi_data['team_metrics'] = {
                'team_size': len(employees),
                'avg_tasks_per_person': round(total_tasks / len(employees), 1) if employees else 0,
                'productivity_ranking': productivity_data,
                'avg_team_productivity': round(sum(p['productivity_score'] for p in productivity_data) / len(productivity_data), 1) if productivity_data else 0
            }
            
            # Quality KPIs
            revisions_data = []
            for task in tasks:
                if task.revision_count > 0:
                    revisions_data.append(task.revision_count)
            
            avg_revisions = sum(revisions_data) / len(revisions_data) if revisions_data else 0
            revision_rate = (len(revisions_data) / total_tasks * 100) if total_tasks > 0 else 0
            
            # Calculate first-time approval rate
            first_time_approved = len(tasks.filtered(lambda t: t.state == 'done' and t.revision_count == 0))
            first_time_approval_rate = (first_time_approved / len(completed_tasks) * 100) if completed_tasks else 0
            
            kpi_data['quality_metrics'] = {
                'avg_revisions_per_task': round(avg_revisions, 1),
                'tasks_with_revisions_percent': round(revision_rate, 1),
                'first_time_approval_rate': round(first_time_approval_rate, 1),
                'excessive_revisions_count': len(tasks.filtered(lambda t: t.has_excessive_revisions))
            }
            
            return {
                'status': 'success',
                'data': kpi_data
            }
            
        except Exception as e:
            _logger.error('Error in KPI metrics: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error calculating KPI metrics: {str(e)}'
            }
