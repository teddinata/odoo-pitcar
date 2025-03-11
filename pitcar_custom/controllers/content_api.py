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
        """Helper method to delete project"""
        try:
            if not data.get('project_id'):
                return {'status': 'error', 'message': 'Project ID is required'}

            project = request.env['content.project'].sudo().browse(int(data['project_id']))
            if not project.exists():
                return {'status': 'error', 'message': 'Project not found'}

            # Check if project has tasks
            if project.task_ids:
                return {
                    'status': 'error',
                    'message': 'Cannot delete project with existing tasks. Please delete or move tasks first.'
                }

            # Create activity log before deletion
            project.message_post(
                body=f"Project '{project.name}' was deleted by {request.env.user.name}",
                message_type='notification'
            )

            # Delete the project
            project.unlink()

            return {
                'status': 'success',
                'message': 'Project deleted successfully'
            }

        except Exception as e:
            _logger.error('Error deleting project: %s', str(e))
            return {
                'status': 'error',
                'message': f'Error deleting project: {str(e)}'
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
                    'impact_on_delivery': kw.get('impact_on_delivery', ''),
                    'target_hours': float(kw.get('target_hours', 2.0)),
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
            
            elif operation == 'update':
                if not kw.get('bau_id'):
                    return {'status': 'error', 'message': 'Missing BAU ID'}
                    
                try:
                    bau = request.env['content.bau'].sudo().browse(int(kw['bau_id']))
                    if not bau.exists():
                        return {'status': 'error', 'message': 'BAU activity not found'}
                        
                    update_values = {}
                    if kw.get('name'):
                        update_values['name'] = kw['name']
                    if kw.get('activity_type'):
                        update_values['activity_type'] = kw['activity_type']
                    if kw.get('hours_spent'):
                        update_values['hours_spent'] = float(kw['hours_spent'])
                    if kw.get('date'):
                        update_values['date'] = kw['date']
                    if kw.get('description') is not None:
                        update_values['description'] = kw['description']
                    if kw.get('impact_on_delivery') is not None:
                        update_values['impact_on_delivery'] = kw['impact_on_delivery']
                    if kw.get('target_hours'):
                        update_values['target_hours'] = float(kw['target_hours'])
                        
                    # Update BAU record
                    bau.write(update_values)
                    return {
                        'status': 'success',
                        'data': self._prepare_bau_data(bau),
                        'message': 'BAU activity updated successfully'
                    }
                    
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Error updating BAU activity: {str(e)}'
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
            'impact_on_delivery': bau.impact_on_delivery,
            # Tambahkan field baru
            'target_hours': bau.target_hours,
            'is_target_achieved': bau.is_target_achieved,
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
            # Validasi input
            if not kw.get('date_from') or not kw.get('date_to'):
                return {'status': 'error', 'message': 'Date range is required'}
                
            domain = [
                ('date', '>=', kw['date_from']),
                ('date', '<=', kw['date_to'])
            ]
            
            if kw.get('creator_id'):
                domain.append(('creator_id', '=', int(kw['creator_id'])))
                
            # Ambil data BAU
            bau_activities = request.env['content.bau'].sudo().search(domain)
            
            # Kelompokkan berdasarkan creator dan tanggal
            grouped_data = {}
            for bau in bau_activities:
                key = (bau.creator_id.id, bau.date)
                if key not in grouped_data:
                    grouped_data[key] = {
                        'creator_id': bau.creator_id.id,
                        'creator_name': bau.creator_id.name,
                        'date': bau.date,
                        'total_hours': 0,
                        'target_achieved': False,
                        'activities': []
                    }
                
                grouped_data[key]['total_hours'] += bau.hours_spent
                grouped_data[key]['activities'].append(self._prepare_bau_data(bau))
                
                # Update target achieved flag
                target_hours = bau.target_hours if hasattr(bau, 'target_hours') else 2.0  # Default 2 jam
                grouped_data[key]['target_achieved'] = grouped_data[key]['total_hours'] >= target_hours
            
            # Hitung statistik
            report_data = {
                'daily_data': list(grouped_data.values()),
                'summary': {
                    'total_bau_days': len(grouped_data),
                    'total_target_achieved': sum(1 for d in grouped_data.values() if d['target_achieved']),
                    'achievement_rate': round(sum(1 for d in grouped_data.values() if d['target_achieved']) / max(len(grouped_data), 1) * 100, 2)
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
        """Handle batch BAU activities creation"""
        try:
            if not kw.get('activities') or not isinstance(kw['activities'], list):
                return {'status': 'error', 'message': 'Activities list is required'}
                
            created_baus = []
            errors = []
            
            for activity in kw['activities']:
                # Validate required fields
                required_fields = ['name', 'creator_id', 'date', 'activity_type', 'hours_spent']
                if not all(activity.get(field) for field in required_fields):
                    errors.append(f"Missing required fields for activity: {activity.get('name', 'Unnamed')}")
                    continue
                    
                try:
                    values = {
                        'name': activity['name'],
                        'creator_id': int(activity['creator_id']),
                        'date': activity['date'],
                        'activity_type': activity['activity_type'],
                        'hours_spent': float(activity['hours_spent']),
                        'project_id': int(activity['project_id']) if activity.get('project_id') else False,
                        'description': activity.get('description', ''),
                        'impact_on_delivery': activity.get('impact_on_delivery', ''),
                        'target_hours': float(activity.get('target_hours', 2.0)),
                    }
                    
                    bau = request.env['content.bau'].sudo().create(values)
                    created_baus.append(self._prepare_bau_data(bau))
                    
                except Exception as e:
                    errors.append(f"Error creating activity {activity.get('name', 'Unnamed')}: {str(e)}")
                    
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