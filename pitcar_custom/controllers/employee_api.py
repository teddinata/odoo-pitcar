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
            # Format avatar data
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
                    'name': employee.job_id.name,
                    'department_id': employee.job_id.department_id.id if employee.job_id.department_id else False
                }

            # Format work location data
            location_data = False
            if employee.work_location_id:
                location_data = {
                    'id': employee.work_location_id.id,
                    'name': employee.work_location_id.name,
                    'address': employee.work_location_id.address if hasattr(employee.work_location_id, 'address') else False
                }

            # Get selection field values
            gender_selection = dict(employee._fields['gender'].selection or [])
            marital_selection = dict(employee._fields['marital'].selection or [])

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
                'parent_id': employee.parent_id.id if employee.parent_id else False,
                'coach': employee.coach_id.name if employee.coach_id else False,
                'address_home': employee.address_id.name_get()[0][1] if employee.address_id else False,
                'active': employee.active,
                'gender': employee.gender or False,
                'gender_display': gender_selection.get(employee.gender, False),
                'marital': employee.marital or False,
                'marital_display': marital_selection.get(employee.marital, False),
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
        
    # @http.route('/web/employees/masters', type='json', auth='user', methods=['POST'], csrf=False)
    # def get_employee_masters(self, **kw):
    #     """Get master data for employees (departments, positions, locations, and selection fields)"""
    #     try:
    #         # Get Departments
    #         Department = request.env['hr.department']
    #         departments = Department.search([])
    #         department_list = [{
    #             'id': dept.id,
    #             'name': dept.name,
    #             'manager': dept.manager_id.name if dept.manager_id else None,
    #             'parent_dept': dept.parent_id.name if dept.parent_id else None,
    #             'total_employees': len(dept.member_ids)
    #         } for dept in departments]

    #         # Get Job Positions
    #         Job = request.env['hr.job']
    #         jobs = Job.search([])
    #         position_list = [{
    #             'id': job.id,
    #             'name': job.name,
    #             'department_id': job.department_id.id if job.department_id else None,
    #             'department': {
    #                 'id': job.department_id.id,
    #                 'name': job.department_id.name,
    #                 'manager_id': job.department_id.manager_id.id if job.department_id.manager_id else None,
    #                 'manager_name': job.department_id.manager_id.name if job.department_id.manager_id else None
    #             } if job.department_id else None,
    #             'total_employees': job.no_of_employee,
    #             'description': job.description or None
    #         } for job in jobs]

    #         # Get Work Locations
    #         Location = request.env['pitcar.work.location']
    #         locations = Location.search([])
    #         location_list = [{
    #             'id': loc.id,
    #             'name': loc.name,
    #             'address': loc.address if hasattr(loc, 'address') else None
    #         } for loc in locations]

    #         # Get Selection Fields
    #         Employee = request.env['hr.employee']
    #         selection_fields = {
    #             'gender': dict(Employee._fields['gender'].selection or []),
    #             'marital': dict(Employee._fields['marital'].selection or [])
    #         }

    #         # Get employee count
    #         employee_count = Employee.search_count([('active', '=', True)])

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'departments': department_list,
    #                 'positions': position_list,
    #                 'locations': location_list,
    #                 'selection_fields': selection_fields,
    #                 'summary': {
    #                     'total_departments': len(departments),
    #                     'total_positions': len(jobs),
    #                     'total_locations': len(locations),
    #                     'total_employees': employee_count
    #                 }
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in get_employee_masters: {str(e)}", exc_info=True)
    #         return {
    #             'status': 'error',
    #             'message': str(e)
    #         }

    # Perbarui API endpoint untuk mendukung multiple departments
    @http.route('/web/employees/masters', type='json', auth='user', methods=['POST'], csrf=False)
    def get_employees(self, **kw):
        try:
            # Log untuk debugging
            _logger.info(f"Get employees called with params: {kw.get('params', {})}")
            
            params = kw.get('params', {})
            
            # Dapatkan departemen (single atau multiple)
            department_id = params.get('department_id')
            department_ids = params.get('department_ids', [])
            
            # Jika ada department_ids, gunakan itu
            if department_ids:
                # Pastikan department_ids dalam bentuk list
                if not isinstance(department_ids, list):
                    department_ids = [department_ids]
            # Jika tidak, fallback ke department_id lama
            elif department_id:
                department_ids = [department_id]
            
            # Konversi ke integer
            department_ids = [int(dept_id) for dept_id in department_ids if dept_id]
            
            # Buat domain search
            domain = [('active', '=', True)]
            
            # Filter berdasarkan departemen jika ada
            if department_ids:
                domain.append(('department_id', 'in', department_ids))
            
            # Tampilkan log untuk debugging
            _logger.info(f"Fetching employees with domain: {domain}")
            
            # Cari employee berdasarkan domain
            employees = request.env['hr.employee'].sudo().search_read(
                domain=domain,
                fields=['id', 'name', 'job_id', 'department_id'],
                limit=params.get('limit', 100),
                order=f"{params.get('sort_by', 'name')} {params.get('sort_order', 'asc')}"
            )
            
            # Format response
            result = []
            for employee in employees:
                position_name = employee.get('job_id') and employee['job_id'][1] or ''
                department_name = employee.get('department_id') and employee['department_id'][1] or ''
                
                emp_data = {
                    'id': employee['id'],
                    'name': employee['name'],
                    'position': {'id': employee.get('job_id') and employee['job_id'][0] or False, 'name': position_name},
                    'department': department_name
                }
                
                result.append(emp_data)
            
            _logger.info(f"Found {len(result)} employees for department_ids: {department_ids}")
            
            return {
                'status': 'success',
                'data': {
                    'rows': result,
                    'total': len(result)
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_employees: {str(e)}")
            return {
                'status': 'error', 
                'message': str(e)
            }

    @http.route('/web/employees', type='json', auth='user', methods=['POST'], csrf=False)
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
            Employee = request.env['hr.employee'].sudo()
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

    @http.route('/web/employees/detail', type='json', auth='user', methods=['POST'], csrf=False)
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

    @http.route('/web/employees/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_employee(self, **kw):
        try:
            # Get params from request
            data = request.get_json_data()
            params = data.get('params', {})  # Ambil params dari jsonrpc
            
            Employee = request.env['hr.employee']
            required_fields = ['name']
            
            # Validate required fields
            if not params.get('name'):
                return {
                    'status': 'error',
                    'message': f"Missing required fields: name"
                }

            # Handle parent_id/manager
            if 'parent_id' in params:
                parent_id = params.get('parent_id')
                if parent_id:
                    params['parent_id'] = int(parent_id)
                else:
                    params['parent_id'] = False
                    
            # Handle department_id
            if 'department_id' in params:
                department_id = params.get('department_id')
                if department_id:
                    params['department_id'] = int(department_id)
                else:
                    params['department_id'] = False
                    
            # Handle job_id
            if 'job_id' in params:
                job_id = params.get('job_id')
                if job_id:
                    params['job_id'] = int(job_id)
                else:
                    params['job_id'] = False
                    
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

    @http.route('/web/employees/update', type='json', auth='user', methods=['POST'], csrf=False)
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
                
             # Handle parent_id/manager
            if 'parent_id' in update_vals:
                # Konversi parent_id ke integer jika tidak None
                parent_id = update_vals.get('parent_id')
                if parent_id:
                    update_vals['parent_id'] = int(parent_id)
                else:
                    update_vals['parent_id'] = False
            
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

    @http.route('/web/employees/delete', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_employee(self, **kw):
        try:
            # Get params from request
            data = request.get_json_data()
            params = data.get('params', {})
            employee_id = params.get('employee_id')

            if not employee_id:
                return {
                    'status': 'error',
                    'message': 'Employee ID is required'
                }
                
            try:
                employee_id = int(employee_id)
            except (ValueError, TypeError):
                return {
                    'status': 'error',
                    'message': 'Invalid employee ID format'
                }
                
            employee = request.env['hr.employee'].browse(employee_id)
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
        
    # Add these methods to your EmployeeAPI class
    @http.route('/web/department/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_department(self, **kw):
        try:
            params = request.get_json_data()
            
            required_fields = ['name']
            missing_fields = [field for field in required_fields if not params.get(field)]
            if missing_fields:
                return {
                    'status': 'error',
                    'message': f"Missing required fields: {', '.join(missing_fields)}"
                }
                
            Department = request.env['hr.department']
            vals = {
                'name': params.get('name'),
                'manager_id': int(params.get('manager_id')) if params.get('manager_id') else False,
                'parent_id': int(params.get('parent_id')) if params.get('parent_id') else False,
            }
            
            department = Department.create(vals)
            
            return {
                'status': 'success',
                'data': {
                    'id': department.id,
                    'name': department.name,
                    'manager': department.manager_id.name if department.manager_id else None,
                    'parent_dept': department.parent_id.name if department.parent_id else None
                },
                'message': 'Department created successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in create_department: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/position/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_position(self, **kw):
        try:
            params = request.get_json_data()
            
            required_fields = ['name']
            missing_fields = [field for field in required_fields if not params.get(field)]
            if missing_fields:
                return {
                    'status': 'error',
                    'message': f"Missing required fields: {', '.join(missing_fields)}"
                }
                
            Job = request.env['hr.job']
            vals = {
                'name': params.get('name'),
                'department_id': int(params.get('department_id')) if params.get('department_id') else False,
                'description': params.get('description', ''),
            }
            
            position = Job.create(vals)
            
            return {
                'status': 'success',
                'data': {
                    'id': position.id,
                    'name': position.name,
                    'department_id': position.department_id.id if position.department_id else None,
                    'department_name': position.department_id.name if position.department_id else None,
                    'description': position.description
                },
                'message': 'Position created successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in create_position: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/department/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_department(self, **kw):
        try:
            data = request.get_json_data()
            params = data.get('params', {})
            
            if not params.get('id'):
                return {
                    'status': 'error',
                    'message': 'Department ID is required'
                }
                
            Department = request.env['hr.department']
            department = Department.browse(int(params['id']))
            
            if not department.exists():
                return {
                    'status': 'error',
                    'message': 'Department not found'
                }
                
            vals = {
                'name': params.get('name'),
                'manager_id': int(params.get('manager_id')) if params.get('manager_id') else False,
                'parent_id': int(params.get('parent_id')) if params.get('parent_id') else False
            }
            
            department.write(vals)
            
            return {
                'status': 'success',
                'data': {
                    'id': department.id,
                    'name': department.name,
                    'manager': department.manager_id.name if department.manager_id else None,
                    'parent_dept': department.parent_id.name if department.parent_id else None,
                    'total_employees': len(department.member_ids)
                },
                'message': 'Department updated successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in update_department: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/position/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_position(self, **kw):
        try:
            data = request.get_json_data()
            params = data.get('params', {})
            
            if not params.get('id'):
                return {
                    'status': 'error',
                    'message': 'Position ID is required'
                }
                
            Job = request.env['hr.job']
            position = Job.browse(int(params['id']))
            
            if not position.exists():
                return {
                    'status': 'error',
                    'message': 'Position not found'
                }
                
            vals = {
                'name': params.get('name'),
                'department_id': int(params.get('department_id')) if params.get('department_id') else False,
                'description': params.get('description', '')
            }
            
            position.write(vals)
            
            return {
                'status': 'success',
                'data': {
                    'id': position.id,
                    'name': position.name,
                    'department_id': position.department_id.id if position.department_id else None,
                    'department_name': position.department_id.name if position.department_id else None,
                    'description': position.description,
                    'total_employees': position.no_of_employee
                },
                'message': 'Position updated successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in update_position: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    # Optional: Endpoint untuk soft delete department/position jika diperlukan
    @http.route('/web/department/archive', type='json', auth='user', methods=['POST'], csrf=False)
    def archive_department(self, **kw):
        try:
            data = request.get_json_data()
            params = data.get('params', {})
            
            if not params.get('id'):
                return {
                    'status': 'error',
                    'message': 'Department ID is required'
                }
                
            Department = request.env['hr.department']
            department = Department.browse(int(params['id']))
            
            if not department.exists():
                return {
                    'status': 'error',
                    'message': 'Department not found'
                }
                
            # Check if department has active employees
            if department.member_ids.filtered(lambda e: e.active):
                return {
                    'status': 'error',
                    'message': 'Cannot archive department with active employees'
                }
                
            department.write({'active': False})
            
            return {
                'status': 'success',
                'message': 'Department archived successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in archive_department: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/web/position/archive', type='json', auth='user', methods=['POST'], csrf=False)
    def archive_position(self, **kw):
        try:
            data = request.get_json_data()
            params = data.get('params', {})
            
            if not params.get('id'):
                return {
                    'status': 'error',
                    'message': 'Position ID is required'
                }
                
            Job = request.env['hr.job']
            position = Job.browse(int(params['id']))
            
            if not position.exists():
                return {
                    'status': 'error',
                    'message': 'Position not found'
                }
                
            # Check if position has employees
            if position.no_of_employee > 0:
                return {
                    'status': 'error',
                    'message': 'Cannot archive position with active employees'
                }
                
            position.write({'active': False})
            
            return {
                'status': 'success',
                'message': 'Position archived successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in archive_position: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }