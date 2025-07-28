# controllers/lms_api.py
from odoo import http, fields
from odoo.http import request
import logging
import json
import csv
import io
import base64
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo.tools import float_utils

_logger = logging.getLogger(__name__)

class LMSCoreAPI(http.Controller):
    """API untuk Core LMS Operations (Courses, Categories, Modules)"""
    
    @http.route('/web/v1/lms/courses', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_courses_operations(self, **params):
        """
        Endpoint untuk operasi course management
        
        Operations:
        - search: Mencari courses dengan filter
        - create: Membuat course baru
        - update: Update course
        - delete: Hapus course
        - publish: Publish/unpublish course
        - enroll: Enroll user ke course
        - stats: Statistik course
        
        Example JSON-RPC Body:
        {
            "jsonrpc": "2.0",
            "params": {
                "operation": "search",
                "category_id": 1,
                "difficulty_level": "basic",
                "is_published": true,
                "is_mandatory": false,
                "search": "odoo",
                "page": 1,
                "limit": 25,
                "sort_by": "name",
                "sort_order": "asc",
                "include_stats": true
            }
        }
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_courses(params)
            elif operation == 'create':
                return self._create_course(params)
            elif operation == 'update':
                return self._update_course(params)
            elif operation == 'delete':
                return self._delete_course(params)
            elif operation == 'publish':
                return self._publish_course(params)
            elif operation == 'enroll':
                return self._enroll_course(params)
            elif operation == 'stats':
                return self._course_stats(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS courses API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/enrollments', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_enrollments_operations(self, **params):
        """
        Endpoint untuk enrollment management
        
        Operations:
        - search: Mencari enrollments dengan filter
        - create: Enroll user ke course
        - update_progress: Update progress enrollment
        - complete: Mark enrollment as completed
        - reset: Reset progress
        - my_enrollments: Get enrollments untuk current user
        - bulk_enroll: Bulk enrollment untuk multiple users
        
        Example JSON-RPC Body:
        {
            "jsonrpc": "2.0",
            "params": {
                "operation": "search",
                "user_id": 1,
                "course_id": 2,
                "status": "in_progress",
                "enrollment_type": "mandatory",
                "date_from": "2025-01-01",
                "date_to": "2025-12-31",
                "page": 1,
                "limit": 50,
                "include_progress": true
            }
        }
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_enrollments(params)
            elif operation == 'create':
                return self._create_enrollment(params)
            elif operation == 'update_progress':
                return self._update_enrollment_progress(params)
            elif operation == 'complete':
                return self._complete_enrollment(params)
            elif operation == 'reset':
                return self._reset_enrollment(params)
            elif operation == 'my_enrollments':
                return self._get_my_enrollments(params)
            elif operation == 'bulk_enroll':
                return self._bulk_enroll(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS enrollments API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/assessments', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_assessments_operations(self, **params):
        """
        Endpoint untuk assessment management
        
        Operations:
        - search: Mencari assessments
        - create: Membuat assessment baru
        - submit: Submit assessment answers
        - get_questions: Get questions untuk assessment
        - results: Get assessment results
        - retry: Retry assessment
        
        Example JSON-RPC Body:
        {
            "jsonrpc": "2.0",
            "params": {
                "operation": "submit",
                "assessment_id": 1,
                "answers": {
                    "1": "option_a",
                    "2": "option_b",
                    "3": "true"
                },
                "time_spent": 1800
            }
        }
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_assessments(params)
            elif operation == 'create':
                return self._create_assessment(params)
            elif operation == 'submit':
                return self._submit_assessment(params)
            elif operation == 'get_questions':
                return self._get_assessment_questions(params)
            elif operation == 'results':
                return self._get_assessment_results(params)
            elif operation == 'retry':
                return self._retry_assessment(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS assessments API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/competencies', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_competencies_operations(self, **params):
        """
        Endpoint untuk competency management
        
        Operations:
        - search: Mencari competencies
        - my_competencies: Get competencies untuk current user
        - validate: Validate competency achievement
        - search_users: Cari user competencies
        - leaderboard: Competency leaderboard
        
        Example JSON-RPC Body:
        {
            "jsonrpc": "2.0",
            "params": {
                "operation": "my_competencies",
                "status": "achieved",
                "category": "technical",
                "include_progress": true
            }
        }
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_competencies(params)
            elif operation == 'my_competencies':
                return self._get_my_competencies(params)
            elif operation == 'validate':
                return self._validate_competency(params)
            elif operation == 'search_users':
                return self._search_user_competencies(params)
            elif operation == 'leaderboard':
                return self._competency_leaderboard(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS competencies API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/dashboard', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_dashboard_operations(self, **params):
        """
        Endpoint untuk dashboard data
        
        Operations:
        - my_dashboard: Personal learning dashboard
        - manager_dashboard: Manager dashboard untuk team
        - company_overview: Company-wide learning overview
        - analytics: Learning analytics
        
        Example JSON-RPC Body:
        {
            "jsonrpc": "2.0",
            "params": {
                "operation": "my_dashboard",
                "include_recommendations": true,
                "include_recent_activity": true,
                "date_range": "last_30_days"
            }
        }
        """
        try:
            operation = params.get('operation', 'my_dashboard')
            
            if operation == 'my_dashboard':
                return self._get_my_dashboard(params)
            elif operation == 'manager_dashboard':
                return self._get_manager_dashboard(params)
            elif operation == 'company_overview':
                return self._get_company_overview(params)
            elif operation == 'analytics':
                return self._get_learning_analytics(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS dashboard API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    # ==================== COURSE OPERATIONS ====================
    
    def _search_courses(self, params):
        """Search courses dengan filter - FIXED"""
        try:
            # Build domain
            domain = [('active', '=', True)]
            
            # Filters - PERBAIKI CARA APPEND DOMAIN
            if params.get('category_id'):
                domain.append(('category_id', '=', int(params['category_id'])))
            if params.get('difficulty_level'):
                domain.append(('difficulty_level', '=', params['difficulty_level']))
            if params.get('is_published') is not None:
                domain.append(('is_published', '=', params['is_published']))
            if params.get('is_mandatory') is not None:
                domain.append(('is_mandatory', '=', params['is_mandatory']))
            if params.get('search'):
                search_term = params['search']
                # PERBAIKI INI - GUNAKAN += BUKAN APPEND
                domain += ['|', ('name', 'ilike', search_term), ('description', 'ilike', search_term)]
            
            # Pagination
            page = int(params.get('page', 1))
            limit = int(params.get('limit', 25))
            offset = (page - 1) * limit
            
            # Sorting
            sort_by = params.get('sort_by', 'name')
            sort_order = params.get('sort_order', 'asc')
            order = f"{sort_by} {sort_order}"
            
            # Get records
            Course = request.env['lms.course'].sudo()
            courses = Course.search(domain, limit=limit, offset=offset, order=order)
            total_count = Course.search_count(domain)
            
            # Prepare response
            courses_data = []
            for course in courses:
                course_data = {
                    'id': course.id,
                    'name': course.name,
                    'code': course.code,
                    'category': course.category_id.name if course.category_id else '',
                    'category_id': course.category_id.id if course.category_id else None,
                    'description': course.short_description or '',
                    'difficulty_level': course.difficulty_level,
                    'duration_hours': course.duration_hours,
                    'completion_points': course.completion_points,
                    'is_mandatory': course.is_mandatory,
                    'is_published': course.is_published,
                    'module_count': course.module_count,
                    'enrollment_count': course.enrollment_count,
                    'completion_rate': round(course.completion_rate, 2),
                    'average_score': round(course.average_score, 2),
                    'create_date': course.create_date.strftime('%Y-%m-%d %H:%M:%S'),
                }
                
                # Include detailed stats if requested
                if params.get('include_stats'):
                    course_data.update({
                        'modules': [{
                            'id': m.id,
                            'name': m.name,
                            'content_type': m.content_type,
                            'duration_minutes': m.duration_minutes,
                            'is_assessment': m.is_assessment
                        } for m in course.module_ids],
                        'prerequisites': [p.name for p in course.prerequisite_course_ids],
                        'target_roles': [r.name for r in course.target_role_ids]
                    })
                
                courses_data.append(course_data)
            
            return self._success_response({
                'courses': courses_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total_count,
                    'total_pages': (total_count + limit - 1) // limit
                }
            })
            
        except Exception as e:
            return self._error_response(f'Error searching courses: {str(e)}')

    def _create_course(self, params):
        """Create new course"""
        try:
            # Validate required fields
            required_fields = ['name', 'code', 'category_id']
            for field in required_fields:
                if not params.get(field):
                    return self._error_response(f'Field "{field}" is required')
            
            # Prepare values
            values = {
                'name': params['name'],
                'code': params['code'],
                'category_id': int(params['category_id']),
                'description': params.get('description', ''),
                'short_description': params.get('short_description', ''),
                'difficulty_level': params.get('difficulty_level', 'basic'),
                'duration_hours': float(params.get('duration_hours', 1.0)),
                'completion_points': int(params.get('completion_points', 10)),
                'is_mandatory': params.get('is_mandatory', False),
            }
            
            # Create course
            course = request.env['lms.course'].sudo().create(values)
            
            return self._success_response({
                'course_id': course.id,
                'message': f'Course "{course.name}" created successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error creating course: {str(e)}')
        
    def _update_course(self, params):
        """Update course - MISSING METHOD"""
        try:
            course_id = params.get('course_id')
            if not course_id:
                return self._error_response('course_id is required')
            
            course = request.env['lms.course'].sudo().browse(int(course_id))
            if not course.exists():
                return self._error_response('Course not found')
            
            # Update values
            update_values = {}
            
            # Fields yang bisa diupdate
            updatable_fields = [
                'name', 'description', 'short_description', 'difficulty_level',
                'duration_hours', 'completion_points', 'is_mandatory'
            ]
            
            for field in updatable_fields:
                if field in params:
                    if field in ['duration_hours']:
                        update_values[field] = float(params[field])
                    elif field in ['completion_points']:
                        update_values[field] = int(params[field])
                    elif field in ['is_mandatory']:
                        update_values[field] = bool(params[field])
                    else:
                        update_values[field] = params[field]
            
            if update_values:
                course.write(update_values)
                
            return self._success_response({
                'course_id': course.id,
                'message': f'Course "{course.name}" updated successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error updating course: {str(e)}')

    def _delete_course(self, params):
        """Delete course - MISSING METHOD"""
        try:
            course_id = params.get('course_id')
            if not course_id:
                return self._error_response('course_id is required')
            
            course = request.env['lms.course'].sudo().browse(int(course_id))
            if not course.exists():
                return self._error_response('Course not found')
            
            course_name = course.name
            
            # Check if course has enrollments
            enrollments = request.env['lms.enrollment'].sudo().search_count([
                ('course_id', '=', course.id)
            ])
            
            if enrollments > 0:
                return self._error_response('Cannot delete course with existing enrollments')
            
            # Set inactive instead of delete
            course.write({'active': False})
            
            return self._success_response({
                'message': f'Course "{course_name}" deleted successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error deleting course: {str(e)}')

    def _publish_course(self, params):
        """Publish/unpublish course - MISSING METHOD"""
        try:
            course_id = params.get('course_id')
            is_published = params.get('is_published')
            
            if not course_id:
                return self._error_response('course_id is required')
            if is_published is None:
                return self._error_response('is_published is required')
            
            course = request.env['lms.course'].sudo().browse(int(course_id))
            if not course.exists():
                return self._error_response('Course not found')
            
            course.write({'is_published': bool(is_published)})
            
            status = 'published' if is_published else 'unpublished'
            return self._success_response({
                'course_id': course.id,
                'is_published': bool(is_published),
                'message': f'Course "{course.name}" {status} successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error publishing course: {str(e)}')

    def _course_stats(self, params):
        """Get course statistics - MISSING METHOD"""
        try:
            course_id = params.get('course_id')
            if not course_id:
                return self._error_response('course_id is required')
            
            course = request.env['lms.course'].sudo().browse(int(course_id))
            if not course.exists():
                return self._error_response('Course not found')
            
            enrollments = course.enrollment_ids
            completed = enrollments.filtered(lambda e: e.status == 'completed')
            in_progress = enrollments.filtered(lambda e: e.status == 'in_progress')
            not_started = enrollments.filtered(lambda e: e.status == 'not_started')
            
            # Calculate additional stats
            scores = completed.mapped('final_score')
            avg_score = sum(scores) / len(scores) if scores else 0
            
            stats_data = {
                'course_info': {
                    'id': course.id,
                    'name': course.name,
                    'code': course.code,
                    'total_modules': len(course.module_ids)
                },
                'enrollment_stats': {
                    'total_enrollments': len(enrollments),
                    'completed': len(completed),
                    'in_progress': len(in_progress),
                    'not_started': len(not_started),
                    'completion_rate': round(course.completion_rate, 2)
                },
                'performance_stats': {
                    'average_score': round(avg_score, 2),
                    'highest_score': max(scores) if scores else 0,
                    'lowest_score': min(scores) if scores else 0,
                    'passing_rate': len([s for s in scores if s >= 70]) / len(scores) * 100 if scores else 0
                },
                'time_stats': {
                    'average_completion_time_days': self._calculate_avg_completion_time(completed),
                    'total_learning_hours': sum(enrollments.mapped('course_id.duration_hours'))
                }
            }
            
            return self._success_response(stats_data)
            
        except Exception as e:
            return self._error_response(f'Error getting course stats: {str(e)}')

    def _enroll_course(self, params):
        """Enroll user to course"""
        try:
            course_id = params.get('course_id')
            user_id = params.get('user_id', request.env.user.id)
            
            if not course_id:
                return self._error_response('course_id is required')
            
            # Check if already enrolled
            existing = request.env['lms.enrollment'].sudo().search([
                ('user_id', '=', int(user_id)),
                ('course_id', '=', int(course_id))
            ])
            
            if existing:
                return self._error_response('User already enrolled in this course')
            
            # Create enrollment
            enrollment = request.env['lms.enrollment'].sudo().create({
                'user_id': int(user_id),
                'course_id': int(course_id),
                'enrollment_type': params.get('enrollment_type', 'self'),
                'enrolled_by': request.env.user.id
            })
            
            return self._success_response({
                'enrollment_id': enrollment.id,
                'message': 'Successfully enrolled in course'
            })
            
        except Exception as e:
            return self._error_response(f'Error enrolling in course: {str(e)}')

    # ==================== ENROLLMENT OPERATIONS ====================
    
    def _search_enrollments(self, params):
        """Search enrollments dengan filter - FIXED"""
        try:
            domain = []
            
            # Filters
            if params.get('user_id'):
                domain.append(('user_id', '=', int(params['user_id'])))
            if params.get('course_id'):
                domain.append(('course_id', '=', int(params['course_id'])))
            if params.get('status'):
                domain.append(('status', '=', params['status']))
            if params.get('enrollment_type'):
                domain.append(('enrollment_type', '=', params['enrollment_type']))
            if params.get('date_from'):
                domain.append(('enrollment_date', '>=', params['date_from']))
            if params.get('date_to'):
                domain.append(('enrollment_date', '<=', params['date_to']))
            
            # Pagination
            page = int(params.get('page', 1))
            limit = int(params.get('limit', 50))
            offset = (page - 1) * limit
            
            # Get records
            Enrollment = request.env['lms.enrollment'].sudo()
            enrollments = Enrollment.search(domain, limit=limit, offset=offset, order='enrollment_date desc')
            total_count = Enrollment.search_count(domain)
            
            # Prepare response
            enrollments_data = []
            for enrollment in enrollments:
                enrollment_data = {
                    'id': enrollment.id,
                    'user_name': enrollment.user_id.name,
                    'course_name': enrollment.course_id.name,
                    'status': enrollment.status,
                    'progress_percentage': round(enrollment.progress_percentage, 2),
                    'final_score': enrollment.final_score,
                    'passed': enrollment.passed,
                    'enrollment_date': enrollment.enrollment_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'start_date': enrollment.start_date.strftime('%Y-%m-%d %H:%M:%S') if enrollment.start_date else None,
                    'completion_date': enrollment.completion_date.strftime('%Y-%m-%d %H:%M:%S') if enrollment.completion_date else None,
                    'points_earned': enrollment.points_earned,
                    'enrollment_type': enrollment.enrollment_type
                }
                
                # Include progress details if requested
                if params.get('include_progress'):
                    enrollment_data['module_progress'] = [{
                        'module_name': p.module_id.name,
                        'status': p.status,
                        'completion_percentage': p.completion_percentage,
                        'time_spent_minutes': p.time_spent_minutes,
                        'best_score': p.best_score
                    } for p in enrollment.progress_ids]
                
                enrollments_data.append(enrollment_data)
            
            return self._success_response({
                'enrollments': enrollments_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total_count,
                    'total_pages': (total_count + limit - 1) // limit
                }
            })
            
        except Exception as e:
            return self._error_response(f'Error searching enrollments: {str(e)}')

    def _create_enrollment(self, params):
        """Create enrollment - MISSING METHOD"""
        try:
            user_id = params.get('user_id')
            course_id = params.get('course_id')
            
            if not user_id:
                return self._error_response('user_id is required')
            if not course_id:
                return self._error_response('course_id is required')
            
            # Check if already enrolled
            existing = request.env['lms.enrollment'].sudo().search([
                ('user_id', '=', int(user_id)),
                ('course_id', '=', int(course_id))
            ])
            
            if existing:
                return self._error_response('User already enrolled in this course')
            
            # Create enrollment
            enrollment = request.env['lms.enrollment'].sudo().create({
                'user_id': int(user_id),
                'course_id': int(course_id),
                'enrollment_type': params.get('enrollment_type', 'self'),
                'enrolled_by': request.env.user.id
            })
            
            return self._success_response({
                'enrollment_id': enrollment.id,
                'message': 'Enrollment created successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error creating enrollment: {str(e)}')

    def _update_enrollment_progress(self, params):
        """Update enrollment progress - MISSING METHOD"""
        try:
            enrollment_id = params.get('enrollment_id')
            module_id = params.get('module_id')
            progress_percentage = params.get('progress_percentage')
            
            if not enrollment_id:
                return self._error_response('enrollment_id is required')
            if not module_id:
                return self._error_response('module_id is required')
            if progress_percentage is None:
                return self._error_response('progress_percentage is required')
            
            enrollment = request.env['lms.enrollment'].sudo().browse(int(enrollment_id))
            if not enrollment.exists():
                return self._error_response('Enrollment not found')
            
            # Find or create progress record
            progress = request.env['lms.progress'].sudo().search([
                ('enrollment_id', '=', enrollment.id),
                ('module_id', '=', int(module_id))
            ], limit=1)
            
            if not progress:
                progress = request.env['lms.progress'].sudo().create({
                    'enrollment_id': enrollment.id,
                    'module_id': int(module_id),
                    'status': 'in_progress'
                })
            
            # Update progress
            update_vals = {
                'completion_percentage': float(progress_percentage),
                'last_accessed': datetime.now()
            }
            
            if params.get('time_spent_minutes'):
                update_vals['time_spent_minutes'] = int(params['time_spent_minutes'])
            
            if float(progress_percentage) >= 100:
                update_vals.update({
                    'status': 'completed',
                    'completion_date': datetime.now()
                })
            elif float(progress_percentage) > 0:
                update_vals['status'] = 'in_progress'
            
            progress.write(update_vals)
            
            return self._success_response({
                'progress_id': progress.id,
                'message': 'Progress updated successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error updating progress: {str(e)}')

    def _complete_enrollment(self, params):
        """Complete enrollment - MISSING METHOD"""
        try:
            enrollment_id = params.get('enrollment_id')
            final_score = params.get('final_score', 0)
            
            if not enrollment_id:
                return self._error_response('enrollment_id is required')
            
            enrollment = request.env['lms.enrollment'].sudo().browse(int(enrollment_id))
            if not enrollment.exists():
                return self._error_response('Enrollment not found')
            
            enrollment.write({
                'status': 'completed',
                'completion_date': datetime.now(),
                'final_score': float(final_score),
                'points_earned': enrollment.course_id.completion_points
            })
            
            return self._success_response({
                'enrollment_id': enrollment.id,
                'message': 'Enrollment completed successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error completing enrollment: {str(e)}')

    def _reset_enrollment(self, params):
        """Reset enrollment - MISSING METHOD"""
        try:
            enrollment_id = params.get('enrollment_id')
            
            if not enrollment_id:
                return self._error_response('enrollment_id is required')
            
            enrollment = request.env['lms.enrollment'].sudo().browse(int(enrollment_id))
            if not enrollment.exists():
                return self._error_response('Enrollment not found')
            
            # Reset enrollment
            enrollment.write({
                'status': 'not_started',
                'progress_percentage': 0,
                'final_score': 0,
                'start_date': False,
                'completion_date': False,
                'points_earned': 0
            })
            
            # Reset all progress records
            enrollment.progress_ids.write({
                'status': 'not_started',
                'completion_percentage': 0,
                'completion_date': False,
                'time_spent_minutes': 0
            })
            
            return self._success_response({
                'enrollment_id': enrollment.id,
                'message': 'Enrollment reset successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error resetting enrollment: {str(e)}')

    def _bulk_enroll(self, params):
        """Bulk enrollment - MISSING METHOD"""
        try:
            course_id = params.get('course_id')
            user_ids = params.get('user_ids', [])
            enrollment_type = params.get('enrollment_type', 'manager')
            
            if not course_id:
                return self._error_response('course_id is required')
            if not user_ids:
                return self._error_response('user_ids is required')
            
            course = request.env['lms.course'].sudo().browse(int(course_id))
            if not course.exists():
                return self._error_response('Course not found')
            
            enrolled_count = 0
            skipped_count = 0
            
            for user_id in user_ids:
                # Check if already enrolled
                existing = request.env['lms.enrollment'].sudo().search([
                    ('user_id', '=', int(user_id)),
                    ('course_id', '=', course.id)
                ])
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Create enrollment
                request.env['lms.enrollment'].sudo().create({
                    'user_id': int(user_id),
                    'course_id': course.id,
                    'enrollment_type': enrollment_type,
                    'enrolled_by': request.env.user.id
                })
                enrolled_count += 1
            
            return self._success_response({
                'enrolled_count': enrolled_count,
                'skipped_count': skipped_count,
                'message': f'Bulk enrollment completed. {enrolled_count} users enrolled, {skipped_count} skipped.'
            })
            
        except Exception as e:
            return self._error_response(f'Error in bulk enrollment: {str(e)}')

    def _get_my_enrollments(self, params):
        """Get enrollments for current user"""
        params['user_id'] = request.env.user.id
        return self._search_enrollments(params)

    # ==================== ASSESSMENT OPERATIONS ====================

    def _search_assessments(self, params):
        """Search assessments - MISSING METHOD"""
        try:
            domain = [('active', '=', True)]
            
            if params.get('course_id'):
                domain.append(('course_id', '=', int(params['course_id'])))
            if params.get('assessment_type'):
                domain.append(('assessment_type', '=', params['assessment_type']))
            
            assessments = request.env['lms.assessment'].sudo().search(domain, order='name')
            
            assessments_data = []
            for assessment in assessments:
                assessments_data.append({
                    'id': assessment.id,
                    'name': assessment.name,
                    'course_name': assessment.course_id.name if assessment.course_id else '',
                    'assessment_type': assessment.assessment_type,
                    'passing_score': assessment.passing_score,
                    'max_attempts': assessment.max_attempts,
                    'time_limit_minutes': assessment.time_limit_minutes,
                    'question_count': assessment.question_count,
                    'total_points': assessment.total_points,
                    'attempt_count': assessment.attempt_count,
                    'average_score': assessment.average_score,
                    'is_published': assessment.is_published
                })
            
            return self._success_response({
                'assessments': assessments_data
            })
            
        except Exception as e:
            return self._error_response(f'Error searching assessments: {str(e)}')

    def _create_assessment(self, params):
        """Create assessment - MISSING METHOD"""
        try:
            required_fields = ['name', 'course_id']
            for field in required_fields:
                if not params.get(field):
                    return self._error_response(f'Field "{field}" is required')
            
            values = {
                'name': params['name'],
                'course_id': int(params['course_id']),
                'assessment_type': params.get('assessment_type', 'quiz'),
                'description': params.get('description', ''),
                'instructions': params.get('instructions', ''),
                'passing_score': float(params.get('passing_score', 70.0)),
                'max_attempts': int(params.get('max_attempts', 3)),
                'time_limit_minutes': int(params.get('time_limit_minutes', 0)),
                'shuffle_questions': params.get('shuffle_questions', True),
                'show_correct_answers': params.get('show_correct_answers', True)
            }
            
            assessment = request.env['lms.assessment'].sudo().create(values)
            
            return self._success_response({
                'assessment_id': assessment.id,
                'message': f'Assessment "{assessment.name}" created successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error creating assessment: {str(e)}')

    def _get_assessment_results(self, params):
        """Get assessment results - MISSING METHOD"""
        try:
            assessment_id = params.get('assessment_id')
            user_id = params.get('user_id', request.env.user.id)
            
            if not assessment_id:
                return self._error_response('assessment_id is required')
            
            assessment = request.env['lms.assessment'].sudo().browse(int(assessment_id))
            if not assessment.exists():
                return self._error_response('Assessment not found')
            
            # Get results for user
            results = request.env['lms.result'].sudo().search([
                ('assessment_id', '=', assessment.id),
                ('user_id', '=', int(user_id))
            ], order='attempt_number desc')
            
            results_data = []
            for result in results:
                results_data.append({
                    'id': result.id,
                    'attempt_number': result.attempt_number,
                    'score_percentage': result.score_percentage,
                    'score_points': result.score_points,
                    'total_questions': result.total_questions,
                    'correct_answers': result.correct_answers,
                    'passed': result.passed,
                    'status': result.status,
                    'start_time': result.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': result.end_time.strftime('%Y-%m-%d %H:%M:%S') if result.end_time else None,
                    'duration_minutes': result.duration_minutes,
                    'points_earned': result.points_earned
                })
            
            return self._success_response({
                'assessment_info': {
                    'id': assessment.id,
                    'name': assessment.name,
                    'passing_score': assessment.passing_score,
                    'max_attempts': assessment.max_attempts
                },
                'results': results_data,
                'best_result': results_data[0] if results_data else None
            })
            
        except Exception as e:
            return self._error_response(f'Error getting assessment results: {str(e)}')

    def _retry_assessment(self, params):
        """Retry assessment - MISSING METHOD"""
        try:
            assessment_id = params.get('assessment_id')
            
            if not assessment_id:
                return self._error_response('assessment_id is required')
            
            assessment = request.env['lms.assessment'].sudo().browse(int(assessment_id))
            if not assessment.exists():
                return self._error_response('Assessment not found')
            
            # Check if user has attempts left
            user_results = request.env['lms.result'].sudo().search([
                ('assessment_id', '=', assessment.id),
                ('user_id', '=', request.env.user.id)
            ])
            
            if len(user_results) >= assessment.max_attempts:
                return self._error_response('Maximum attempts reached for this assessment')
            
            # Create new attempt
            next_attempt = len(user_results) + 1
            
            return self._success_response({
                'assessment_id': assessment.id,
                'next_attempt_number': next_attempt,
                'attempts_remaining': assessment.max_attempts - len(user_results),
                'message': 'Ready for retry. You can start the assessment again.'
            })
            
        except Exception as e:
            return self._error_response(f'Error retrying assessment: {str(e)}')
    
    def _submit_assessment(self, params):
        """Submit assessment answers"""
        try:
            assessment_id = params.get('assessment_id')
            answers = params.get('answers', {})
            
            if not assessment_id:
                return self._error_response('assessment_id is required')
            if not answers:
                return self._error_response('answers are required')
            
            # Get assessment
            assessment = request.env['lms.assessment'].sudo().browse(int(assessment_id))
            if not assessment.exists():
                return self._error_response('Assessment not found')
            
            # Create result record
            result = request.env['lms.result'].sudo().create({
                'user_id': request.env.user.id,
                'assessment_id': assessment.id,
                'attempt_number': self._get_next_attempt_number(assessment.id, request.env.user.id),
                'start_time': datetime.now(),
                'total_questions': len(assessment.question_ids),
                'status': 'in_progress'
            })
            
            # Submit answers and calculate score
            score_percentage = result.action_submit_assessment(answers)
            
            return self._success_response({
                'result_id': result.id,
                'score_percentage': round(score_percentage, 2),
                'passed': result.passed,
                'points_earned': result.points_earned,
                'message': 'Assessment submitted successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error submitting assessment: {str(e)}')

    def _get_assessment_questions(self, params):
        """Get questions for assessment"""
        try:
            assessment_id = params.get('assessment_id')
            if not assessment_id:
                return self._error_response('assessment_id is required')
            
            assessment = request.env['lms.assessment'].sudo().browse(int(assessment_id))
            if not assessment.exists():
                return self._error_response('Assessment not found')
            
            questions_data = []
            for question in assessment.question_ids:
                question_data = {
                    'id': question.id,
                    'question_text': question.question_text,
                    'question_type': question.question_type,
                    'points': question.points,
                    'sequence': question.sequence
                }
                
                # Add options for multiple choice and true/false
                if question.question_type in ['multiple_choice', 'true_false']:
                    question_data['options'] = [{
                        'id': opt.id,
                        'text': opt.option_text,
                        'sequence': opt.sequence
                    } for opt in question.option_ids]
                
                questions_data.append(question_data)
            
            return self._success_response({
                'assessment': {
                    'id': assessment.id,
                    'name': assessment.name,
                    'instructions': assessment.instructions,
                    'time_limit_minutes': assessment.time_limit_minutes,
                    'max_attempts': assessment.max_attempts,
                    'passing_score': assessment.passing_score
                },
                'questions': questions_data
            })
            
        except Exception as e:
            return self._error_response(f'Error getting assessment questions: {str(e)}')

    # ==================== COMPETENCY OPERATIONS ====================

    def _search_competencies(self, params):
        """Search competencies - MISSING METHOD"""
        try:
            domain = [('active', '=', True)]
            
            if params.get('category'):
                domain.append(('category', '=', params['category']))
            if params.get('level'):
                domain.append(('proficiency_levels', '=', params['level']))
            
            competencies = request.env['lms.competency'].sudo().search(domain, order='category, name')
            
            competencies_data = []
            for competency in competencies:
                competencies_data.append({
                    'id': competency.id,
                    'name': competency.name,
                    'code': competency.code,
                    'category': competency.category,
                    'description': competency.description or '',
                    'proficiency_levels': competency.proficiency_levels,
                    'min_score_required': competency.min_score_required,
                    'validity_months': competency.validity_months,
                    'requires_renewal': competency.requires_renewal,
                    'points_awarded': competency.points_awarded,
                    'achiever_count': competency.achiever_count,
                    'average_score': competency.average_score,
                    'required_courses': [c.name for c in competency.required_course_ids]
                })
            
            return self._success_response({
                'competencies': competencies_data
            })
            
        except Exception as e:
            return self._error_response(f'Error searching competencies: {str(e)}')

    def _validate_competency(self, params):
        """Validate competency - MISSING METHOD"""
        try:
            competency_id = params.get('competency_id')
            user_id = params.get('user_id')
            validation_type = params.get('validation_type', 'manager')
            notes = params.get('notes', '')
            
            if not competency_id:
                return self._error_response('competency_id is required')
            if not user_id:
                return self._error_response('user_id is required')
            
            # Find or create user competency record
            user_competency = request.env['lms.user.competency'].sudo().search([
                ('user_id', '=', int(user_id)),
                ('competency_id', '=', int(competency_id))
            ], limit=1)
            
            if not user_competency:
                user_competency = request.env['lms.user.competency'].sudo().create({
                    'user_id': int(user_id),
                    'competency_id': int(competency_id),
                    'status': 'in_progress'
                })
            
            # Validate competency
            success = user_competency.action_validate_competency()
            
            if success:
                # Add validation notes
                user_competency.write({
                    'validated_by': request.env.user.id,
                    'validation_date': datetime.now()
                })
                
                return self._success_response({
                    'user_competency_id': user_competency.id,
                    'status': user_competency.status,
                    'certificate_number': user_competency.certificate_number,
                    'message': 'Competency validated successfully'
                })
            else:
                return self._error_response('Competency validation failed. Requirements not met.')
            
        except Exception as e:
            return self._error_response(f'Error validating competency: {str(e)}')

    def _search_user_competencies(self, params):
        """Search user competencies - MISSING METHOD"""
        try:
            competency_id = params.get('competency_id')
            
            if not competency_id:
                return self._error_response('competency_id is required')
            
            domain = [('competency_id', '=', int(competency_id))]
            
            if params.get('status'):
                domain.append(('status', '=', params['status']))
            if params.get('department_id'):
                domain.append(('employee_id.department_id', '=', int(params['department_id'])))
            
            user_competencies = request.env['lms.user.competency'].sudo().search(domain)
            
            users_data = []
            for uc in user_competencies:
                users_data.append({
                    'user_id': uc.user_id.id,
                    'user_name': uc.user_id.name,
                    'employee_name': uc.employee_id.name if uc.employee_id else '',
                    'department': uc.employee_id.department_id.name if uc.employee_id and uc.employee_id.department_id else '',
                    'job_title': uc.employee_id.job_id.name if uc.employee_id and uc.employee_id.job_id else '',
                    'status': uc.status,
                    'current_score': uc.current_score,
                    'proficiency_level': uc.proficiency_level,
                    'achieved_date': uc.achieved_date.strftime('%Y-%m-%d') if uc.achieved_date else None,
                    'progress_percentage': uc.progress_percentage,
                    'certificate_number': uc.certificate_number
                })
            
            return self._success_response({
                'competency_info': {
                    'id': competency_id,
                    'name': request.env['lms.competency'].sudo().browse(int(competency_id)).name
                },
                'users': users_data,
                'total_users': len(users_data)
            })
            
        except Exception as e:
            return self._error_response(f'Error searching user competencies: {str(e)}')

    def _competency_leaderboard(self, params):
        """Competency leaderboard - MISSING METHOD"""
        try:
            domain = [('status', '=', 'achieved')]
            
            if params.get('category'):
                domain.append(('competency_id.category', '=', params['category']))
            
            # Get date range for period
            period = params.get('period', 'month')
            if period == 'week':
                date_from = datetime.now() - timedelta(days=7)
            elif period == 'month':
                date_from = datetime.now() - timedelta(days=30)
            elif period == 'quarter':
                date_from = datetime.now() - timedelta(days=90)
            else:
                date_from = datetime.now() - timedelta(days=365)
            
            domain.append(('achieved_date', '>=', date_from))
            
            # Group by user and count competencies
            user_competencies = request.env['lms.user.competency'].sudo().search(domain)
            
            # Count competencies per user
            user_counts = {}
            for uc in user_competencies:
                user_id = uc.user_id.id
                if user_id not in user_counts:
                    user_counts[user_id] = {
                        'user_name': uc.user_id.name,
                        'employee_name': uc.employee_id.name if uc.employee_id else '',
                        'department': uc.employee_id.department_id.name if uc.employee_id and uc.employee_id.department_id else '',
                        'competency_count': 0,
                        'total_score': 0,
                        'competencies': []
                    }
                
                user_counts[user_id]['competency_count'] += 1
                user_counts[user_id]['total_score'] += uc.current_score
                user_counts[user_id]['competencies'].append({
                    'name': uc.competency_id.name,
                    'score': uc.current_score,
                    'achieved_date': uc.achieved_date.strftime('%Y-%m-%d')
                })
            
            # Calculate average scores and sort
            leaderboard = []
            for user_id, data in user_counts.items():
                data['average_score'] = data['total_score'] / data['competency_count'] if data['competency_count'] > 0 else 0
                leaderboard.append(data)
            
            # Sort by competency count, then by average score
            leaderboard.sort(key=lambda x: (x['competency_count'], x['average_score']), reverse=True)
            
            # Limit results
            limit = int(params.get('limit', 10))
            leaderboard = leaderboard[:limit]
            
            return self._success_response({
                'period': period,
                'category': params.get('category', 'all'),
                'leaderboard': leaderboard,
                'total_participants': len(user_counts)
            })
            
        except Exception as e:
            return self._error_response(f'Error getting competency leaderboard: {str(e)}')

    
    def _get_my_competencies(self, params):
        """Get competencies for current user"""
        try:
            domain = [('user_id', '=', request.env.user.id)]
            
            # Filters
            if params.get('status'):
                domain.append(('status', '=', params['status']))
            if params.get('category'):
                domain.append(('competency_id.category', '=', params['category']))
            
            user_competencies = request.env['lms.user.competency'].sudo().search(domain)
            
            competencies_data = []
            for uc in user_competencies:
                comp_data = {
                    'competency_name': uc.competency_id.name,
                    'competency_code': uc.competency_id.code,
                    'category': uc.competency_id.category,
                    'status': uc.status,
                    'current_score': uc.current_score,
                    'proficiency_level': uc.proficiency_level,
                    'progress_percentage': round(uc.progress_percentage, 2),
                    'achieved_date': uc.achieved_date.strftime('%Y-%m-%d') if uc.achieved_date else None,
                    'expiry_date': uc.expiry_date.strftime('%Y-%m-%d') if uc.expiry_date else None,
                    'points_awarded': uc.competency_id.points_awarded
                }
                
                if params.get('include_progress'):
                    comp_data.update({
                        'completed_courses': uc.completed_courses,
                        'required_courses': uc.required_courses,
                        'certificate_number': uc.certificate_number
                    })
                
                competencies_data.append(comp_data)
            
            return self._success_response({
                'competencies': competencies_data,
                'summary': {
                    'total': len(competencies_data),
                    'achieved': len([c for c in competencies_data if c['status'] == 'achieved']),
                    'in_progress': len([c for c in competencies_data if c['status'] == 'in_progress'])
                }
            })
            
        except Exception as e:
            return self._error_response(f'Error getting competencies: {str(e)}')

    # ==================== DASHBOARD OPERATIONS ====================
    
    def _get_my_dashboard(self, params):
        """Get personal learning dashboard"""
        try:
            user = request.env.user
            employee = user.employee_id
            
            if not employee:
                return self._error_response('Employee record not found')
            
            # Get dashboard data using existing method
            dashboard_data = request.env['lms.dashboard'].sudo().get_user_dashboard_data(user.id)
            
            if 'error' in dashboard_data:
                return self._error_response(dashboard_data['error'])
            
            # Add additional data if requested
            if params.get('include_recommendations'):
                # Get recommended courses
                recommended_courses = self._get_recommended_courses(user.id)
                dashboard_data['recommended_courses'] = recommended_courses
            
            if params.get('include_recent_activity'):
                # Get recent learning activity
                recent_activity = self._get_recent_activity(user.id, params.get('date_range', 'last_30_days'))
                dashboard_data['recent_activity'] = recent_activity
            
            return self._success_response(dashboard_data)
            
        except Exception as e:
            return self._error_response(f'Error getting dashboard: {str(e)}')

    # ==================== UTILITY METHODS ====================
    
    def _get_next_attempt_number(self, assessment_id, user_id):
        """Get next attempt number for assessment"""
        last_result = request.env['lms.result'].sudo().search([
            ('assessment_id', '=', assessment_id),
            ('user_id', '=', user_id)
        ], order='attempt_number desc', limit=1)
        
        return (last_result.attempt_number + 1) if last_result else 1
    
    def _get_recommended_courses(self, user_id):
        """Get recommended courses for user"""
        try:
            user = request.env['res.users'].sudo().browse(user_id)
            employee = user.employee_id
            
            if not employee or not employee.job_id:
                return []
            
            # Get courses for user's job position that they haven't enrolled in
            job_courses = request.env['lms.course'].sudo().search([
                ('target_role_ids', 'in', [employee.job_id.id]),
                ('is_published', '=', True)
            ])
            
            enrolled_courses = employee.lms_enrollments.mapped('course_id')
            recommended = job_courses - enrolled_courses
            
            return [{
                'id': course.id,
                'name': course.name,
                'description': course.short_description,
                'duration_hours': course.duration_hours,
                'difficulty_level': course.difficulty_level,
                'completion_points': course.completion_points
            } for course in recommended[:5]]
            
        except Exception:
            return []
    
    def _get_recent_activity(self, user_id, date_range='last_30_days'):
        """Get recent learning activity"""
        try:
            # Calculate date range
            if date_range == 'last_7_days':
                date_from = datetime.now() - timedelta(days=7)
            elif date_range == 'last_30_days':
                date_from = datetime.now() - timedelta(days=30)
            else:
                date_from = datetime.now() - timedelta(days=30)
            
            # Get recent progress
            recent_progress = request.env['lms.progress'].sudo().search([
                ('user_id', '=', user_id),
                ('last_accessed', '>=', date_from)
            ], order='last_accessed desc', limit=10)
            
            activity = []
            for progress in recent_progress:
                activity.append({
                    'type': 'module_progress',
                    'module_name': progress.module_id.name,
                    'course_name': progress.course_id.name,
                    'status': progress.status,
                    'completion_percentage': progress.completion_percentage,
                    'date': progress.last_accessed.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return activity
            
        except Exception:
            return []
        
    @http.route('/web/v1/lms/categories', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_categories_operations(self, **params):
        """
        Endpoint untuk category management
        
        Operations:
        - search: Mencari categories
        - create: Membuat category baru
        - update: Update category
        - delete: Hapus category
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_categories(params)
            elif operation == 'create':
                return self._create_category(params)
            elif operation == 'update':
                return self._update_category(params)
            elif operation == 'delete':
                return self._delete_category(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS categories API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/modules', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_modules_operations(self, **params):
        """
        Endpoint untuk module management
        
        Operations:
        - search: Mencari modules
        - create: Membuat module baru
        - update: Update module
        - delete: Hapus module
        - upload_content: Upload content file
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_modules(params)
            elif operation == 'create':
                return self._create_module(params)
            elif operation == 'update':
                return self._update_module(params)
            elif operation == 'delete':
                return self._delete_module(params)
            elif operation == 'upload_content':
                return self._upload_module_content(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS modules API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/learning-paths', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_learning_paths_operations(self, **params):
        """
        Endpoint untuk learning path management
        
        Operations:
        - search: Mencari learning paths
        - create: Membuat learning path baru
        - update: Update learning path
        - delete: Hapus learning path
        - enroll: Enroll user ke learning path
        - progress: Get progress learning path
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_learning_paths(params)
            elif operation == 'create':
                return self._create_learning_path(params)
            elif operation == 'update':
                return self._update_learning_path(params)
            elif operation == 'delete':
                return self._delete_learning_path(params)
            elif operation == 'enroll':
                return self._enroll_learning_path(params)
            elif operation == 'progress':
                return self._learning_path_progress(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS learning paths API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/badges', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_badges_operations(self, **params):
        """
        Endpoint untuk badge management
        
        Operations:
        - search: Mencari badges
        - my_badges: Get badges untuk current user
        - leaderboard: Badge leaderboard
        - award: Award badge ke user
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_badges(params)
            elif operation == 'my_badges':
                return self._get_my_badges(params)
            elif operation == 'leaderboard':
                return self._badge_leaderboard(params)
            elif operation == 'award':
                return self._award_badge(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS badges API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/analytics', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_analytics_operations(self, **params):
        """
        Endpoint untuk analytics & reporting
        
        Operations:
        - course_analytics: Analytics per course
        - user_analytics: Analytics per user
        - department_analytics: Analytics per department
        - trend_analysis: Trend analysis
        - custom_report: Custom report dengan filters
        """
        try:
            operation = params.get('operation', 'course_analytics')
            
            if operation == 'course_analytics':
                return self._get_course_analytics(params)
            elif operation == 'user_analytics':
                return self._get_user_analytics(params)
            elif operation == 'department_analytics':
                return self._get_department_analytics(params)
            elif operation == 'trend_analysis':
                return self._get_trend_analysis(params)
            elif operation == 'custom_report':
                return self._get_custom_report(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS analytics API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    @http.route('/web/v1/lms/employees', type='json', auth='user', methods=['POST'], csrf=False)
    def lms_employees_operations(self, **params):
        """
        Endpoint untuk employee LMS integration
        
        Operations:
        - search: Mencari employees dengan LMS data
        - profile: Get employee LMS profile
        - auto_enroll: Auto enroll mandatory courses
        - compliance_report: Compliance report
        - performance_impact: Performance impact analysis
        """
        try:
            operation = params.get('operation', 'search')
            
            if operation == 'search':
                return self._search_employees_lms(params)
            elif operation == 'profile':
                return self._get_employee_lms_profile(params)
            elif operation == 'auto_enroll':
                return self._auto_enroll_employee(params)
            elif operation == 'compliance_report':
                return self._employee_compliance_report(params)
            elif operation == 'performance_impact':
                return self._performance_impact_analysis(params)
            else:
                return self._error_response(f'Operation "{operation}" not supported')
                
        except Exception as e:
            _logger.error('Error in LMS employees API: %s', str(e))
            return self._error_response(f'An error occurred: {str(e)}')

    # ==================== CATEGORY OPERATIONS ====================
    
    def _search_categories(self, params):
        """Search categories - FIXED"""
        try:
            domain = [('active', '=', True)]
            
            if params.get('parent_id'):
                domain.append(('parent_id', '=', int(params['parent_id'])))
            elif params.get('parent_id') is None and 'parent_id' in params:
                # If parent_id is explicitly null, search for root categories
                domain.append(('parent_id', '=', False))
                
            if params.get('search'):
                search_term = params['search']
                # PERBAIKI INI - GUNAKAN += BUKAN APPEND
                domain += ['|', ('name', 'ilike', search_term), ('description', 'ilike', search_term)]
            
            categories = request.env['lms.category'].sudo().search(domain, order='sequence, name')
            
            categories_data = []
            for category in categories:
                categories_data.append({
                    'id': category.id,
                    'name': category.name,
                    'parent_id': category.parent_id.id if category.parent_id else None,
                    'parent_name': category.parent_id.name if category.parent_id else None,
                    'description': category.description or '',
                    'color': category.color,
                    'icon': category.icon or '',
                    'course_count': category.course_count,
                    'sequence': category.sequence
                })
            
            return self._success_response({
                'categories': categories_data
            })
            
        except Exception as e:
            return self._error_response(f'Error searching categories: {str(e)}')
        
    def _create_category(self, params):
        """Create new category"""
        try:
            required_fields = ['name']
            for field in required_fields:
                if not params.get(field):
                    return self._error_response(f'Field "{field}" is required')
            
            values = {
                'name': params['name'],
                'description': params.get('description', ''),
                'color': params.get('color', 1),
                'icon': params.get('icon', ''),
                'sequence': params.get('sequence', 10)
            }
            
            if params.get('parent_id'):
                values['parent_id'] = int(params['parent_id'])
            
            category = request.env['lms.category'].sudo().create(values)
            
            return self._success_response({
                'category_id': category.id,
                'message': f'Category "{category.name}" created successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error creating category: {str(e)}')

    def _update_category(self, params):
        """Update category - MISSING METHOD"""
        try:
            category_id = params.get('category_id')
            if not category_id:
                return self._error_response('category_id is required')
            
            category = request.env['lms.category'].sudo().browse(int(category_id))
            if not category.exists():
                return self._error_response('Category not found')
            
            # Update values
            update_values = {}
            updatable_fields = ['name', 'description', 'color', 'icon', 'sequence']
            
            for field in updatable_fields:
                if field in params:
                    if field in ['color', 'sequence']:
                        update_values[field] = int(params[field])
                    else:
                        update_values[field] = params[field]
            
            if update_values:
                category.write(update_values)
            
            return self._success_response({
                'category_id': category.id,
                'message': f'Category "{category.name}" updated successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error updating category: {str(e)}')

    def _delete_category(self, params):
        """Delete category - MISSING METHOD"""
        try:
            category_id = params.get('category_id')
            if not category_id:
                return self._error_response('category_id is required')
            
            category = request.env['lms.category'].sudo().browse(int(category_id))
            if not category.exists():
                return self._error_response('Category not found')
            
            # Check if category has courses
            course_count = request.env['lms.course'].sudo().search_count([
                ('category_id', '=', category.id)
            ])
            
            if course_count > 0:
                return self._error_response('Cannot delete category with existing courses')
            
            category_name = category.name
            category.write({'active': False})
            
            return self._success_response({
                'message': f'Category "{category_name}" deleted successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error deleting category: {str(e)}')


    

    # ==================== MODULE OPERATIONS ====================
    
    def _search_modules(self, params):
        """Search modules"""
        try:
            domain = [('active', '=', True)]
            
            if params.get('course_id'):
                domain.append(('course_id', '=', int(params['course_id'])))
            if params.get('content_type'):
                domain.append(('content_type', '=', params['content_type']))
            
            modules = request.env['lms.module'].sudo().search(domain, order='course_id, sequence')
            
            modules_data = []
            for module in modules:
                modules_data.append({
                    'id': module.id,
                    'name': module.name,
                    'course_id': module.course_id.id,
                    'course_name': module.course_id.name,
                    'content_type': module.content_type,
                    'duration_minutes': module.duration_minutes,
                    'is_mandatory': module.is_mandatory,
                    'is_assessment': module.is_assessment,
                    'sequence': module.sequence,
                    'learning_objectives': module.learning_objectives,
                    'content_url': module.content_url,
                    'has_content_file': bool(module.content_file)
                })
            
            return self._success_response({
                'modules': modules_data
            })
            
        except Exception as e:
            return self._error_response(f'Error searching modules: {str(e)}')

    def _create_module(self, params):
        """Create new module"""
        try:
            required_fields = ['name', 'course_id', 'content_type']
            for field in required_fields:
                if not params.get(field):
                    return self._error_response(f'Field "{field}" is required')
            
            values = {
                'name': params['name'],
                'course_id': int(params['course_id']),
                'content_type': params['content_type'],
                'description': params.get('description', ''),
                'duration_minutes': int(params.get('duration_minutes', 15)),
                'is_mandatory': params.get('is_mandatory', True),
                'sequence': int(params.get('sequence', 10)),
                'learning_objectives': params.get('learning_objectives', ''),
                'content_url': params.get('content_url', '')
            }
            
            module = request.env['lms.module'].sudo().create(values)
            
            return self._success_response({
                'module_id': module.id,
                'message': f'Module "{module.name}" created successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error creating module: {str(e)}')
        
    def _update_module(self, params):
        """Update module - MISSING METHOD"""
        try:
            module_id = params.get('module_id')
            if not module_id:
                return self._error_response('module_id is required')
            
            module = request.env['lms.module'].sudo().browse(int(module_id))
            if not module.exists():
                return self._error_response('Module not found')
            
            # Update values
            update_values = {}
            updatable_fields = [
                'name', 'description', 'content_type', 'duration_minutes',
                'is_mandatory', 'sequence', 'learning_objectives', 'content_url'
            ]
            
            for field in updatable_fields:
                if field in params:
                    if field in ['duration_minutes', 'sequence']:
                        update_values[field] = int(params[field])
                    elif field in ['is_mandatory']:
                        update_values[field] = bool(params[field])
                    else:
                        update_values[field] = params[field]
            
            if update_values:
                module.write(update_values)
            
            return self._success_response({
                'module_id': module.id,
                'message': f'Module "{module.name}" updated successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error updating module: {str(e)}')

    def _delete_module(self, params):
        """Delete module - MISSING METHOD"""
        try:
            module_id = params.get('module_id')
            if not module_id:
                return self._error_response('module_id is required')
            
            module = request.env['lms.module'].sudo().browse(int(module_id))
            if not module.exists():
                return self._error_response('Module not found')
            
            module_name = module.name
            module.write({'active': False})
            
            return self._success_response({
                'message': f'Module "{module_name}" deleted successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error deleting module: {str(e)}')

    def _upload_module_content(self, params):
        """Upload module content - MISSING METHOD"""
        try:
            module_id = params.get('module_id')
            content_data = params.get('content_data')  # base64 encoded
            filename = params.get('filename')
            
            if not module_id:
                return self._error_response('module_id is required')
            if not content_data:
                return self._error_response('content_data is required')
            
            module = request.env['lms.module'].sudo().browse(int(module_id))
            if not module.exists():
                return self._error_response('Module not found')
            
            # Save content file
            module.write({
                'content_file': content_data,
                'content_filename': filename or 'content_file'
            })
            
            return self._success_response({
                'module_id': module.id,
                'filename': filename,
                'message': 'Content uploaded successfully'
            })
            
        except Exception as e:
            return self._error_response(f'Error uploading content: {str(e)}')


    # ==================== LEARNING PATH OPERATIONS ====================
    
    def _search_learning_paths(self, params):
        """Search learning paths"""
        try:
            domain = [('active', '=', True)]
            
            if params.get('difficulty_level'):
                domain.append(('difficulty_level', '=', params['difficulty_level']))
            if params.get('target_role_id'):
                domain.append(('target_role_ids', 'in', [int(params['target_role_id'])]))
            
            paths = request.env['lms.learning.path'].sudo().search(domain, order='sequence, name')
            
            paths_data = []
            for path in paths:
                paths_data.append({
                    'id': path.id,
                    'name': path.name,
                    'code': path.code,
                    'description': path.description,
                    'difficulty_level': path.difficulty_level,
                    'estimated_duration_hours': path.estimated_duration_hours,
                    'completion_points': path.completion_points,
                    'is_mandatory': path.is_mandatory,
                    'enrollment_count': path.enrollment_count,
                    'completion_rate': path.completion_rate,
                    'course_count': len(path.course_ids),
                    'competency_count': len(path.competency_ids)
                })
            
            return self._success_response({
                'learning_paths': paths_data
            })
            
        except Exception as e:
            return self._error_response(f'Error searching learning paths: {str(e)}')

    def _enroll_learning_path(self, params):
        """Enroll user to learning path"""
        try:
            path_id = params.get('path_id')
            user_id = params.get('user_id', request.env.user.id)
            
            if not path_id:
                return self._error_response('path_id is required')
            
            # Check if already enrolled
            existing = request.env['lms.path.enrollment'].sudo().search([
                ('user_id', '=', int(user_id)),
                ('path_id', '=', int(path_id))
            ])
            
            if existing:
                return self._error_response('User already enrolled in this learning path')
            
            # Create path enrollment
            enrollment = request.env['lms.path.enrollment'].sudo().create({
                'user_id': int(user_id),
                'path_id': int(path_id),
                'enrolled_by': request.env.user.id
            })
            
            # Auto-enroll in first course if specified
            if params.get('auto_start_first_course', False):
                path = request.env['lms.learning.path'].sudo().browse(int(path_id))
                if path.course_ids:
                    first_course = path.course_ids[0]
                    request.env['lms.enrollment'].sudo().create({
                        'user_id': int(user_id),
                        'course_id': first_course.id,
                        'enrollment_type': 'mandatory'
                    })
            
            return self._success_response({
                'enrollment_id': enrollment.id,
                'message': 'Successfully enrolled in learning path'
            })
            
        except Exception as e:
            return self._error_response(f'Error enrolling in learning path: {str(e)}')

    # ==================== BADGE OPERATIONS ====================
    
    def _get_my_badges(self, params):
        """Get badges for current user"""
        try:
            user_badges = request.env['lms.user.badge'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], order='earned_date desc')
            
            badges_data = []
            for ub in user_badges:
                badges_data.append({
                    'id': ub.id,
                    'badge_name': ub.badge_id.name,
                    'badge_code': ub.badge_id.code,
                    'badge_type': ub.badge_id.badge_type,
                    'description': ub.badge_id.description,
                    'color': ub.badge_id.color,
                    'earned_date': ub.earned_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'reason': ub.reason,
                    'related_course': ub.course_id.name if ub.course_id else None,
                    'related_competency': ub.competency_id.name if ub.competency_id else None
                })
            
            return self._success_response({
                'badges': badges_data,
                'total_badges': len(badges_data)
            })
            
        except Exception as e:
            return self._error_response(f'Error getting badges: {str(e)}')

    # ==================== ANALYTICS OPERATIONS ====================
    
    def _get_course_analytics(self, params):
        """Get course analytics"""
        try:
            course_id = params.get('course_id')
            if not course_id:
                return self._error_response('course_id is required')
            
            course = request.env['lms.course'].sudo().browse(int(course_id))
            if not course.exists():
                return self._error_response('Course not found')
            
            enrollments = course.enrollment_ids
            completed = enrollments.filtered(lambda e: e.status == 'completed')
            in_progress = enrollments.filtered(lambda e: e.status == 'in_progress')
            
            analytics_data = {
                'course_info': {
                    'id': course.id,
                    'name': course.name,
                    'code': course.code
                },
                'enrollment_stats': {
                    'total_enrollments': len(enrollments),
                    'completed': len(completed),
                    'in_progress': len(in_progress),
                    'completion_rate': course.completion_rate,
                    'average_score': course.average_score
                },
                'time_analytics': {
                    'average_completion_time': self._calculate_avg_completion_time(completed),
                    'fastest_completion': self._get_fastest_completion(completed),
                    'slowest_completion': self._get_slowest_completion(completed)
                },
                'score_distribution': self._get_score_distribution(completed)
            }
            
            return self._success_response(analytics_data)
            
        except Exception as e:
            return self._error_response(f'Error getting course analytics: {str(e)}')

    # ==================== EMPLOYEE OPERATIONS ====================
    
    def _get_employee_lms_profile(self, params):
        """Get employee LMS profile"""
        try:
            employee_id = params.get('employee_id')
            if not employee_id:
                return self._error_response('employee_id is required')
            
            employee = request.env['hr.employee'].sudo().browse(int(employee_id))
            if not employee.exists():
                return self._error_response('Employee not found')
            
            profile_data = {
                'employee_info': {
                    'id': employee.id,
                    'name': employee.name,
                    'job_title': employee.job_id.name if employee.job_id else '',
                    'department': employee.department_id.name if employee.department_id else ''
                },
                'learning_stats': {
                    'total_courses_completed': employee.total_courses_completed,
                    'total_learning_hours': employee.total_learning_hours,
                    'average_assessment_score': employee.average_assessment_score,
                    'competencies_achieved': employee.competencies_achieved,
                    'badges_earned': employee.badges_earned,
                    'mandatory_training_compliance': employee.mandatory_training_compliance,
                    'overdue_trainings': employee.overdue_trainings
                },
                'preferences': {
                    'learning_style': employee.learning_style,
                    'preferred_learning_time': employee.preferred_learning_time
                },
                'recent_activity': self._get_employee_recent_activity(employee.user_id.id),
                'current_enrollments': self._get_employee_current_enrollments(employee.user_id.id)
            }
            
            return self._success_response(profile_data)
            
        except Exception as e:
            return self._error_response(f'Error getting employee profile: {str(e)}')

    # ==================== UTILITY METHODS ====================
    
    def _calculate_avg_completion_time(self, completed_enrollments):
        """Calculate average completion time"""
        if not completed_enrollments:
            return 0
        
        total_days = 0
        count = 0
        for enrollment in completed_enrollments:
            if enrollment.enrollment_date and enrollment.completion_date:
                delta = enrollment.completion_date - enrollment.enrollment_date
                total_days += delta.days
                count += 1
        
        return total_days / count if count > 0 else 0
    
    def _get_fastest_completion(self, completed_enrollments):
        """Get fastest completion time"""
        if not completed_enrollments:
            return None
        
        fastest = None
        min_days = float('inf')
        
        for enrollment in completed_enrollments:
            if enrollment.enrollment_date and enrollment.completion_date:
                delta = enrollment.completion_date - enrollment.enrollment_date
                if delta.days < min_days:
                    min_days = delta.days
                    fastest = enrollment
        
        return {
            'user_name': fastest.user_id.name,
            'completion_days': min_days
        } if fastest else None
    
    def _get_slowest_completion(self, completed_enrollments):
        """Get slowest completion time"""
        if not completed_enrollments:
            return None
        
        slowest = None
        max_days = 0
        
        for enrollment in completed_enrollments:
            if enrollment.enrollment_date and enrollment.completion_date:
                delta = enrollment.completion_date - enrollment.enrollment_date
                if delta.days > max_days:
                    max_days = delta.days
                    slowest = enrollment
        
        return {
            'user_name': slowest.user_id.name,
            'completion_days': max_days
        } if slowest else None
    
    def _get_score_distribution(self, completed_enrollments):
        """Get score distribution"""
        if not completed_enrollments:
            return {}
        
        scores = completed_enrollments.mapped('final_score')
        return {
            'excellent': len([s for s in scores if s >= 90]),
            'good': len([s for s in scores if 80 <= s < 90]),
            'satisfactory': len([s for s in scores if 70 <= s < 80]),
            'needs_improvement': len([s for s in scores if s < 70])
        }
    
    def _get_employee_recent_activity(self, user_id):
        """Get employee recent activity"""
        recent_progress = request.env['lms.progress'].sudo().search([
            ('user_id', '=', user_id),
            ('last_accessed', '!=', False)
        ], order='last_accessed desc', limit=5)
        
        return [{
            'module_name': p.module_id.name,
            'course_name': p.course_id.name,
            'last_accessed': p.last_accessed.strftime('%Y-%m-%d %H:%M:%S'),
            'status': p.status,
            'completion_percentage': p.completion_percentage
        } for p in recent_progress]
    
    def _get_employee_current_enrollments(self, user_id):
        """Get employee current enrollments"""
        current_enrollments = request.env['lms.enrollment'].sudo().search([
            ('user_id', '=', user_id),
            ('status', '=', 'in_progress')
        ])
        
        return [{
            'course_name': e.course_id.name,
            'progress_percentage': e.progress_percentage,
            'enrollment_date': e.enrollment_date.strftime('%Y-%m-%d'),
            'start_date': e.start_date.strftime('%Y-%m-%d') if e.start_date else None
        } for e in current_enrollments]
    
    def _get_manager_dashboard(self, params):
        """Get manager dashboard - MISSING METHOD"""
        try:
            user = request.env.user
            employee = user.employee_id
            
            # Get team members
            if employee:
                team_employees = request.env['hr.employee'].sudo().search([
                    ('parent_id', '=', employee.id)
                ])
            else:
                team_employees = request.env['hr.employee'].sudo().search([])
            
            # Get team stats
            team_stats = []
            for emp in team_employees:
                if emp.user_id:
                    team_stats.append({
                        'employee_id': emp.id,
                        'name': emp.name,
                        'job_title': emp.job_id.name if emp.job_id else '',
                        'department': emp.department_id.name if emp.department_id else '',
                        'completed_courses': emp.total_courses_completed,
                        'learning_hours': emp.total_learning_hours,
                        'compliance_rate': emp.mandatory_training_compliance,
                        'overdue_trainings': emp.overdue_trainings
                    })
            
            dashboard_data = {
                'team_overview': {
                    'total_team_members': len(team_employees),
                    'average_compliance': sum(emp.mandatory_training_compliance for emp in team_employees) / len(team_employees) if team_employees else 0,
                    'total_overdue': sum(emp.overdue_trainings for emp in team_employees),
                    'active_learners': len([emp for emp in team_employees if emp.total_courses_completed > 0])
                },
                'team_stats': team_stats
            }
            
            return self._success_response(dashboard_data)
            
        except Exception as e:
            return self._error_response(f'Error getting manager dashboard: {str(e)}')

    def _get_company_overview(self, params):
        """Get company overview - MISSING METHOD"""
        try:
            # Get all employees
            all_employees = request.env['hr.employee'].sudo().search([])
            
            # Calculate company-wide stats
            total_employees = len(all_employees)
            total_courses = request.env['lms.course'].sudo().search_count([('active', '=', True)])
            total_enrollments = request.env['lms.enrollment'].sudo().search_count([])
            completed_enrollments = request.env['lms.enrollment'].sudo().search_count([('status', '=', 'completed')])
            
            overview_data = {
                'company_stats': {
                    'total_employees': total_employees,
                    'total_courses': total_courses,
                    'total_enrollments': total_enrollments,
                    'completion_rate': (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0,
                    'active_learners': len([emp for emp in all_employees if emp.total_courses_completed > 0])
                },
                'department_breakdown': self._get_department_breakdown(),
                'recent_completions': self._get_recent_completions()
            }
            
            return self._success_response(overview_data)
            
        except Exception as e:
            return self._error_response(f'Error getting company overview: {str(e)}')

    def _get_learning_analytics(self, params):
        """Get learning analytics - MISSING METHOD"""
        try:
            metric_type = params.get('metric_type', 'completion_rate')
            
            analytics_data = {
                'metric_type': metric_type,
                'current_period': self._get_current_period_stats(metric_type),
                'previous_period': self._get_previous_period_stats(metric_type),
                'trends': self._get_metric_trends(metric_type),
                'top_performers': self._get_top_performers(),
                'popular_courses': self._get_popular_courses()
            }
            
            return self._success_response(analytics_data)
            
        except Exception as e:
            return self._error_response(f'Error getting learning analytics: {str(e)}')

    # Helper methods for analytics
    def _get_department_breakdown(self):
        departments = request.env['hr.department'].sudo().search([])
        breakdown = []
        for dept in departments:
            employees = dept.member_ids
            breakdown.append({
                'department': dept.name,
                'employee_count': len(employees),
                'average_compliance': sum(emp.mandatory_training_compliance for emp in employees) / len(employees) if employees else 0
            })
        return breakdown

    def _get_recent_completions(self):
        recent = request.env['lms.enrollment'].sudo().search([
            ('status', '=', 'completed'),
            ('completion_date', '>=', datetime.now() - timedelta(days=7))
        ], order='completion_date desc', limit=10)
        
        return [{
            'user_name': e.user_id.name,
            'course_name': e.course_id.name,
            'completion_date': e.completion_date.strftime('%Y-%m-%d'),
            'final_score': e.final_score
        } for e in recent]

    def _get_current_period_stats(self, metric_type):
        # Implementation for current period stats
        return {'value': 0, 'period': 'current_month'}

    def _get_previous_period_stats(self, metric_type):
        # Implementation for previous period stats
        return {'value': 0, 'period': 'previous_month'}

    def _get_metric_trends(self, metric_type):
        # Implementation for metric trends
        return []

    def _get_top_performers(self):
        # Implementation for top performers
        return []

    def _get_popular_courses(self):
        # Implementation for popular courses
        return []
    
    def _success_response(self, data, message=None):
        """Generate success response"""
        response = {
            'status': 'success',
            'data': data
        }
        if message:
            response['message'] = message
        return response

    def _error_response(self, message):
        """Generate error response"""
        return {
            'status': 'error',
            'message': message
        }