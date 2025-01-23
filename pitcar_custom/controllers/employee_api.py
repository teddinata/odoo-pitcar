# File: controllers/employee_api.py

from odoo import http
from odoo.http import request, Response
import json
import math
import logging
import pytz
from datetime import datetime
from odoo.exceptions import ValidationError
import base64

_logger = logging.getLogger(__name__)

class EmployeeAPI(http.Controller):

    def _get_base_domain(self):
        """Get base domain for active employees"""
        return [('active', '=', True)]  # Base filter for active employees

    def _validate_pagination_params(self, page, limit):
        """Validate and normalize pagination parameters"""
        try:
            page = int(page)
            if page < 1:
                page = 1
                
            limit = int(limit)
            if limit not in [10, 20, 30, 50]:
                limit = 20
                
            return page, limit
        except (ValueError, TypeError):
            return 1, 20

    def _format_employee_data(self, employee):
      """Format employee data for API response"""
      try:
          avatar_data = False
          if employee.image_1920:
              avatar_data = {
                  'full': employee.image_1920.decode('utf-8') if employee.image_1920 else False,
                  'medium': employee.image_128.decode('utf-8') if employee.image_128 else False,
                  'small': employee.image_512.decode('utf-8') if employee.image_512 else False
              }

          # Format department data
          department_data = False
          if employee.department_id:
              department_data = {
                  'id': employee.department_id.id,
                  'name': employee.department_id.name,
                  'manager': employee.department_id.manager_id.name if employee.department_id.manager_id else False
              }

          # Format job position data
          position_data = False
          if employee.job_id:
              position_data = {
                  'id': employee.job_id.id,
                  'name': employee.job_id.name
              }

          # Format work location data
          location_data = False
          if employee.work_location_id:
              location_data = {
                  'id': employee.work_location_id.id,
                  'name': employee.work_location_id.name,
                  'address': employee.work_location_id.address
              }

          return {
              'id': employee.id,
              'name': employee.name,
              'avatar': avatar_data,
              'work_email': employee.work_email or False,
              'job_title': employee.job_title or False,
              'department': department_data,
              'position': position_data,
              'work_location': location_data,
              'work_phone': employee.work_phone or False,
              'mobile_phone': employee.mobile_phone or False,
              'company': employee.company_id.name if employee.company_id else False,
              'manager': employee.parent_id.name if employee.parent_id else False,
              'coach': employee.coach_id.name if employee.coach_id else False,
              'address_home': employee.address_id.name_get()[0][1] if employee.address_id else False,
              'active': employee.active,
              'gender': dict(employee._fields['gender'].selection).get(employee.gender, False),
              'marital': dict(employee._fields['marital'].selection).get(employee.marital, False),
              'birthday': str(employee.birthday) if employee.birthday else False,
              'identification_id': employee.identification_id or False,
              'passport_id': employee.passport_id or False,
              'children': employee.children or 0,
              'emergency_contact': employee.emergency_contact or False,
              'emergency_phone': employee.emergency_phone or False,
              'notes': employee.notes or False,
              'color': employee.color or 0,
              'barcode': employee.barcode or False,
              'pin': employee.pin or False,
              'create_date': str(employee.create_date),
              'write_date': str(employee.write_date)
          }
      except Exception as e:
          _logger.error(f"Error formatting employee data: {str(e)}")
          return {}
        
    @http.route('/api/employees/masters', type='json', auth='user', methods=['POST'], csrf=False)
    def get_employee_masters(self, **kw):
        """Get master data for employees (departments, positions, locations)"""
        try:
            # Get Departments
            departments = request.env['hr.department'].search([])
            department_list = [{
                'id': dept.id,
                'name': dept.name,
                'manager': dept.manager_id.name if dept.manager_id else False,
                'parent_dept': dept.parent_id.name if dept.parent_id else False,
                'total_employees': len(dept.member_ids)
            } for dept in departments]

            # Get Job Positions
            positions = request.env['hr.job'].search([])
            position_list = [{
                'id': job.id,
                'name': job.name,
                'department': job.department_id.name if job.department_id else False,
                'total_employees': job.no_of_employee,
                'description': job.description
            } for job in positions]

            # Get Work Locations - removed address field
            locations = request.env['pitcar.work.location'].search([])
            location_list = [{
                'id': loc.id,
                'name': loc.name
            } for loc in locations]

            # Get additional data if needed
            employee_count = request.env['hr.employee'].search_count([('active', '=', True)])

            return {
                'status': 'success',
                'data': {
                    'departments': department_list,
                    'positions': position_list,
                    'locations': location_list,
                    'summary': {
                        'total_departments': len(departments),
                        'total_positions': len(positions),
                        'total_locations': len(locations),
                        'total_employees': employee_count
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_employee_masters: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/employees', type='json', auth='user', methods=['POST'], csrf=False)
    def get_employees(self, **kw):
        try:
            # Extract parameters
            page = kw.get('page', 1)
            limit = kw.get('limit', 20)
            search_query = kw.get('search', '').strip()
            sort_by = kw.get('sort_by', 'id')
            sort_order = kw.get('sort_order', 'desc')
            department_id = kw.get('department_id')
            
            # Validate pagination
            page, limit = self._validate_pagination_params(page, limit)
            
            # Build domain
            domain = self._get_base_domain()
            
            # Add department filter
            if department_id:
                domain.append(('department_id', '=', int(department_id)))
            
            # Add search conditions
            if search_query:
                search_domain = ['|', '|', '|', '|',
                    ('name', 'ilike', search_query),
                    ('work_email', 'ilike', search_query),
                    ('job_title', 'ilike', search_query),
                    ('work_phone', 'ilike', search_query),
                    ('identification_id', 'ilike', search_query)
                ]
                domain.extend(search_domain)
            
            # Prepare sorting
            order_mapping = {
                'id': 'id',
                'name': 'name',
                'job_title': 'job_title',
                'department': 'department_id',
                'create_date': 'create_date'
            }
            sort_field = order_mapping.get(sort_by, 'id')
            order = f'{sort_field} {sort_order}'
            
            # Get total count
            Employee = request.env['hr.employee']
            total_count = Employee.search_count(domain)
            total_pages = math.ceil(total_count / limit)
            
            # Calculate offset
            offset = (page - 1) * limit
            
            # Get paginated records
            employees = Employee.search(domain, limit=limit, offset=offset, order=order)
            
            # Format response data
            rows = []
            for emp in employees:
                rows.append(self._format_employee_data(emp))
            
            # Prepare summary data
            summary = {
                'total_employees': total_count,
                'active_employees': Employee.search_count([('active', '=', True)]),
                'departments': {
                    'total': request.env['hr.department'].search_count([]),
                    'with_employees': len(set(employees.mapped('department_id.id')))
                }
            }
            
            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'summary': summary,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': total_pages,
                        'current_page': page,
                        'items_per_page': limit,
                        'has_next': page < total_pages,
                        'has_previous': page > 1
                    }
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_employees: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    # File: controllers/employee_api.py

    @http.route('/api/employees/detail', type='json', auth='user', methods=['POST'], csrf=False)
    def get_employee_detail(self, **kw):
        try:
            # Get params from request
            params = request.get_json_data()
            employee_id = params.get('employee_id')

            if not employee_id:
                return {
                    'status': 'error',
                    'message': 'Employee ID is required'
                }
            
            employee = request.env['hr.employee'].browse(int(employee_id))
            if not employee.exists():
                return {
                    'status': 'error',
                    'message': 'Employee not found'
                }
            
            return {
                'status': 'success',
                'data': self._format_employee_data(employee)
            }
            
        except Exception as e:
            _logger.error(f"Error in get_employee_detail: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/employees/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_employee(self, **kw):
        try:
             # Get file data
            avatar_file = request.httprequest.files.get('avatar')
            # Get params from request
            params = request.get_json_data()

            Employee = request.env['hr.employee']
            required_fields = ['name']
            
            # Validate required fields
            missing_fields = [field for field in required_fields if not params.get(field)]
            if missing_fields:
                return {
                    'status': 'error',
                    'message': f"Missing required fields: {', '.join(missing_fields)}"
                }
            
            # Handle avatar file
            if avatar_file:
                try:
                    file_data = avatar_file.read()
                    params['image_1920'] = base64.b64encode(file_data)
                except Exception as e:
                    return json.dumps({
                        'status': 'error',
                        'message': f"Error processing avatar: {str(e)}"
                    })
            
            # Process dates if provided
            if params.get('birthday'):
                try:
                    params['birthday'] = datetime.strptime(params['birthday'], '%Y-%m-%d').date()
                except ValueError:
                    return {
                        'status': 'error',
                        'message': "Invalid birthday format. Use YYYY-MM-DD"
                    }
            
            # Create employee
            employee = Employee.create(params)
            
            return {
                'status': 'success',
                'data': self._format_employee_data(employee),
                'message': 'Employee created successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in create_employee: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/employees/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_employee(self, **kw):
        try:
            # Get params from request
            data = request.get_json_data()
            params = data.get('params', {})  # Ambil params dari jsonrpc
            
            employee_id = params.get('employee_id')
            if not employee_id:
                return {
                    'status': 'error',
                    'message': 'Employee ID is required'
                }
            
            # Copy params untuk dimodifikasi
            update_vals = params.copy()
            
            # Hapus employee_id dari values yang akan di update
            update_vals.pop('employee_id', None)
            
            # Handle avatar jika ada
            if 'avatar' in update_vals:
                try:
                    avatar_data = update_vals.pop('avatar')
                    if avatar_data:
                        if 'data:image' in avatar_data:
                            # Jika data dalam format data URL, ekstrak bagian base64
                            avatar_data = avatar_data.split(',')[1]
                        update_vals['image_1920'] = avatar_data
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f"Error processing avatar: {str(e)}"
                    }

            employee = request.env['hr.employee'].browse(int(employee_id))
            if not employee.exists():
                return {
                    'status': 'error',
                    'message': 'Employee not found'
                }
            
            # Process dates if provided
            if update_vals.get('birthday'):
                try:
                    update_vals['birthday'] = datetime.strptime(update_vals['birthday'], '%Y-%m-%d').date()
                except ValueError:
                    return {
                        'status': 'error',
                        'message': "Invalid birthday format. Use YYYY-MM-DD"
                    }
            
            # Update employee
            employee.write(update_vals)
            
            return {
                'status': 'success',
                'data': self._format_employee_data(employee),
                'message': 'Employee updated successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in update_employee: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/employees/delete', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_employee(self, **kw):
        try:
            # Get params from request
            params = request.get_json_data()
            employee_id = params.get('employee_id')

            if not employee_id:
                return {
                    'status': 'error',
                    'message': 'Employee ID is required'
                }
            
            employee = request.env['hr.employee'].browse(int(employee_id))
            if not employee.exists():
                return {
                    'status': 'error',
                    'message': 'Employee not found'
                }
            
            # Archive employee instead of deleting
            employee.write({'active': False})
            
            return {
                'status': 'success',
                'message': 'Employee archived successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in delete_employee: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }