# controllers/attendance_api.py
from odoo import http
from odoo.http import request
import pytz
from datetime import datetime, timedelta
import logging
import json

_logger = logging.getLogger(__name__)

class AttendanceAPI(http.Controller):
    @http.route('/web/v2/attendance/check', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def check_attendance(self, **kw):
        try:
            # Extract params from JSONRPC request
            if not isinstance(kw, dict):
                return {'status': 'error', 'message': 'Invalid request format'}
                
            # Handle both direct params and JSONRPC format
            params = kw.get('params', kw)
            
            # Basic validation of required fields
            required_fields = {
                'action_type': params.get('action_type'),
                'face_descriptor': params.get('face_descriptor'),
                'location': params.get('location', {})
            }

            # Check all required fields
            missing_fields = [k for k, v in required_fields.items() if not v]
            if missing_fields:
                return {'status': 'error', 'message': f"Missing required fields: {', '.join(missing_fields)}"}

            # Get current employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            # Set timezone and get current time
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            now_utc = now.astimezone(pytz.UTC).replace(tzinfo=None)

            # Verify face with more lenient threshold
            try:
                normalized_descriptor = [float(x) for x in params['face_descriptor']]
                if not employee.verify_face(normalized_descriptor, threshold=0.6):
                    return {'status': 'error', 'message': 'Face verification failed'}
            except Exception as e:
                _logger.error(f"Face verification error: {str(e)}")
                return {'status': 'error', 'message': 'Face verification error'}

            # Prepare attendance values
            values = {
                'employee_id': employee.id,
                'face_descriptor': json.dumps(normalized_descriptor),
                'face_image': params.get('face_image')
            }

            # Handle check in/out
            if params['action_type'] == 'check_in':
                values['check_in'] = now_utc
                attendance = request.env['hr.attendance'].sudo().create(values)
            else:  # check_out
                attendance = request.env['hr.attendance'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('check_out', '=', False)
                ], limit=1)
                
                if not attendance:
                    return {'status': 'error', 'message': 'No active attendance found'}
                
                values['check_out'] = now_utc
                attendance.write(values)

            # Return success response
            return {
                'status': 'success',
                'data': {
                    'attendance_id': attendance.id,
                    'employee': {
                        'id': employee.id,
                        'name': employee.name
                    },
                    'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': params['action_type'],
                    'location': {
                        'latitude': params['location'].get('latitude'),
                        'longitude': params['location'].get('longitude')
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in check_attendance: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/attendance/validate-location', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def validate_location(self, **kw):
        """Validate if user's location is within allowed work locations"""
        try:
            location = kw.get('location', {})
            
            # Get employee from current user
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            # Check if employee has valid work locations
            work_locations = request.env['pitcar.work.location'].sudo().search([])
            
            if not work_locations:
                # Jika tidak ada work location yang didefinisikan, anggap valid
                return {
                    'status': 'success',
                    'data': {
                        'isValid': True,
                        'allowed_locations': []
                    }
                }

            # Validate location
            is_valid = False
            for loc in work_locations:
                distance = loc.calculate_distance(
                    location.get('latitude'),
                    location.get('longitude')
                )
                if distance <= loc.radius:
                    is_valid = True
                    break

            return {
                'status': 'success',
                'data': {
                    'isValid': is_valid,
                    'allowed_locations': [{
                        'name': loc.name,
                        'latitude': loc.latitude,
                        'longitude': loc.longitude,
                        'radius': loc.radius
                    } for loc in work_locations]
                }
            }

        except Exception as e:
            _logger.error(f"Error in validate_location: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/attendance/register-face', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def register_face(self, **kw):
        """Register face descriptor and image for employee"""
        try:
            # Ambil params dari kw langsung seperti endpoint lain
            face_descriptor = kw.get('face_descriptor')
            face_image = kw.get('face_image')

            # Validasi face descriptor
            if not face_descriptor:
                return {'status': 'error', 'message': 'Face descriptor is required'}

            # Get employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            # Save to employee record
            values = {
                'face_descriptor': json.dumps(face_descriptor),
                'face_image': face_image if face_image else False
            }

            employee.write(values)

            return {
                'status': 'success',
                'message': 'Face registered successfully',
                'data': {
                    'employee_id': employee.id,
                    'name': employee.name
                }
            }

        except Exception as e:
            _logger.error(f"Error in register_face: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/attendance/status', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_attendance_status(self, **kw):
        try:
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], limit=1)

            last_attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id)
            ], limit=1)

            return {
                'status': 'success',
                'data': {
                    'is_checked_in': bool(attendance),
                    'has_face_registered': bool(employee.face_descriptor),
                    'last_attendance': {
                        'id': last_attendance.id,
                        'check_in': last_attendance.check_in.strftime('%Y-%m-%d %H:%M:%S') if last_attendance.check_in else None,
                        'check_out': last_attendance.check_out.strftime('%Y-%m-%d %H:%M:%S') if last_attendance.check_out else None,
                    } if last_attendance else None
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_attendance_status: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/attendance/dashboard', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_attendance_dashboard(self, **kw):
        """Get attendance dashboard data with metrics"""
        try:
            # Get date range parameters
            date_range = kw.get('date_range', 'today')
            start_date = kw.get('start_date')
            end_date = kw.get('end_date')
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Calculate date range similar to service advisor
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    start = tz.localize(start.replace(hour=0, minute=0, second=0))
                    end = tz.localize(end.replace(hour=23, minute=59, second=59))
                except (ValueError, TypeError):
                    return {'status': 'error', 'message': 'Invalid date format'}
            else:
                # Date range logic similar to service advisor
                if date_range == 'today':
                    start = now.replace(hour=0, minute=0, second=0)
                    end = now
                elif date_range == 'yesterday':
                    yesterday = now - timedelta(days=1)
                    start = yesterday.replace(hour=0, minute=0, second=0)
                    end = yesterday.replace(hour=23, minute=59, second=59)
                elif date_range == 'this_week':
                    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
                    end = now
                elif date_range == 'this_month':
                    start = now.replace(day=1, hour=0, minute=0, second=0)
                    end = now
                else:
                    start = now.replace(hour=0, minute=0, second=0)
                    end = now

            # Convert to UTC for database queries
            start_utc = start.astimezone(pytz.UTC)
            end_utc = end.astimezone(pytz.UTC)

            # Get all mechanics
            mechanics = request.env['pitcar.mechanic.new'].sudo().search([])
            mechanic_dict = {m.employee_id.id: m for m in mechanics}

            # Get all attendance records
            domain = [
                ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            
            all_attendances = request.env['hr.attendance'].sudo().search(domain)

            # Calculate metrics
            mechanic_data = {}
            total_hours = 0
            total_attendance = 0
            total_late = 0
            on_time_attendance = 0

            for attendance in all_attendances:
                employee = attendance.employee_id
                mechanic = mechanic_dict.get(employee.id)
                
                if not mechanic:
                    continue

                if mechanic.id not in mechanic_data:
                    mechanic_data[mechanic.id] = {
                        'id': mechanic.id,
                        'name': mechanic.name,
                        'position': mechanic.position_id.name,
                        'leader': mechanic.leader_id.name if mechanic.leader_id else None,
                        'total_hours': 0,
                        'attendance_count': 0,
                        'late_count': 0,
                        'on_time_count': 0,
                        'work_hours_target': mechanic.work_hours_target
                    }

                data = mechanic_data[mechanic.id]
                
                # Calculate working hours
                worked_hours = attendance.worked_hours or 0
                data['total_hours'] += worked_hours
                data['attendance_count'] += 1

                # Calculate late/on-time (example: late if check-in after 8 AM)
                check_in_time = pytz.utc.localize(attendance.check_in).astimezone(tz)
                target_time = check_in_time.replace(hour=8, minute=0, second=0)
                
                if check_in_time > target_time:
                    data['late_count'] += 1
                    total_late += 1
                else:
                    data['on_time_count'] += 1
                    on_time_attendance += 1

                total_hours += worked_hours
                total_attendance += 1

            # Format response similar to service advisor
            active_mechanics = []
            for data in mechanic_data.values():
                metrics = {
                    'attendance': {
                        'total_hours': data['total_hours'],
                        'target_hours': data['work_hours_target'] * data['attendance_count'],
                        'achievement': (data['total_hours'] / (data['work_hours_target'] * data['attendance_count']) * 100) 
                                    if data['attendance_count'] else 0
                    },
                    'punctuality': {
                        'total_attendance': data['attendance_count'],
                        'on_time': data['on_time_count'],
                        'late': data['late_count'],
                        'on_time_rate': (data['on_time_count'] / data['attendance_count'] * 100) 
                                    if data['attendance_count'] else 0
                    }
                }

                active_mechanics.append({
                    'id': data['id'],
                    'name': data['name'],
                    'position': data['position'],
                    'leader': data['leader'],
                    'metrics': metrics
                })

            # Calculate overview metrics
            overview = {
                'total_hours': total_hours,
                'total_attendance': total_attendance,
                'punctuality': {
                    'on_time': on_time_attendance,
                    'late': total_late,
                    'on_time_rate': (on_time_attendance / total_attendance * 100) if total_attendance else 0
                }
            }

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'overview': overview,
                    'mechanics': active_mechanics
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_attendance_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _verify_location(self, mechanic, location, device_info):
        """Helper method to verify location"""
        try:
            if device_info.get('isMockLocationOn'):
                return False

            if not mechanic or not mechanic.work_location_ids:
                return True

            lat = location.get('latitude')
            lon = location.get('longitude')

            for work_location in mechanic.work_location_ids:
                distance = work_location.calculate_distance(lat, lon)
                if distance <= work_location.radius:
                    return True

            return False
        except Exception as e:
            _logger.error(f"Location verification error: {str(e)}")
            return False

    @http.route('/web/v2/attendance/dashboard', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_attendance_dashboard(self, **kw):
        """Get attendance dashboard data with metrics"""
        try:
            # Get date range parameters
            date_range = kw.get('date_range', 'today')
            start_date = kw.get('start_date')
            end_date = kw.get('end_date')
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Calculate date range similar to service advisor
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    start = tz.localize(start.replace(hour=0, minute=0, second=0))
                    end = tz.localize(end.replace(hour=23, minute=59, second=59))
                except (ValueError, TypeError):
                    return {'status': 'error', 'message': 'Invalid date format'}
            else:
                # Date range logic similar to service advisor
                if date_range == 'today':
                    start = now.replace(hour=0, minute=0, second=0)
                    end = now
                elif date_range == 'yesterday':
                    yesterday = now - timedelta(days=1)
                    start = yesterday.replace(hour=0, minute=0, second=0)
                    end = yesterday.replace(hour=23, minute=59, second=59)
                elif date_range == 'this_week':
                    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
                    end = now
                elif date_range == 'this_month':
                    start = now.replace(day=1, hour=0, minute=0, second=0)
                    end = now
                else:
                    start = now.replace(hour=0, minute=0, second=0)
                    end = now

            # Convert to UTC for database queries
            start_utc = start.astimezone(pytz.UTC)
            end_utc = end.astimezone(pytz.UTC)

            # Get all mechanics
            mechanics = request.env['pitcar.mechanic.new'].sudo().search([])
            mechanic_dict = {m.employee_id.id: m for m in mechanics}

            # Get all attendance records
            domain = [
                ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            
            all_attendances = request.env['hr.attendance'].sudo().search(domain)

            # Calculate metrics
            mechanic_data = {}
            total_hours = 0
            total_attendance = 0
            total_late = 0
            on_time_attendance = 0

            for attendance in all_attendances:
                employee = attendance.employee_id
                mechanic = mechanic_dict.get(employee.id)
                
                if not mechanic:
                    continue

                if mechanic.id not in mechanic_data:
                    mechanic_data[mechanic.id] = {
                        'id': mechanic.id,
                        'name': mechanic.name,
                        'position': mechanic.position_id.name,
                        'leader': mechanic.leader_id.name if mechanic.leader_id else None,
                        'total_hours': 0,
                        'attendance_count': 0,
                        'late_count': 0,
                        'on_time_count': 0,
                        'work_hours_target': mechanic.work_hours_target
                    }

                data = mechanic_data[mechanic.id]
                
                # Calculate working hours
                worked_hours = attendance.worked_hours or 0
                data['total_hours'] += worked_hours
                data['attendance_count'] += 1

                # Calculate late/on-time (example: late if check-in after 8 AM)
                check_in_time = pytz.utc.localize(attendance.check_in).astimezone(tz)
                target_time = check_in_time.replace(hour=8, minute=0, second=0)
                
                if check_in_time > target_time:
                    data['late_count'] += 1
                    total_late += 1
                else:
                    data['on_time_count'] += 1
                    on_time_attendance += 1

                total_hours += worked_hours
                total_attendance += 1

            # Format response similar to service advisor
            active_mechanics = []
            for data in mechanic_data.values():
                metrics = {
                    'attendance': {
                        'total_hours': data['total_hours'],
                        'target_hours': data['work_hours_target'] * data['attendance_count'],
                        'achievement': (data['total_hours'] / (data['work_hours_target'] * data['attendance_count']) * 100) 
                                    if data['attendance_count'] else 0
                    },
                    'punctuality': {
                        'total_attendance': data['attendance_count'],
                        'on_time': data['on_time_count'],
                        'late': data['late_count'],
                        'on_time_rate': (data['on_time_count'] / data['attendance_count'] * 100) 
                                    if data['attendance_count'] else 0
                    }
                }

                active_mechanics.append({
                    'id': data['id'],
                    'name': data['name'],
                    'position': data['position'],
                    'leader': data['leader'],
                    'metrics': metrics
                })

            # Calculate overview metrics
            overview = {
                'total_hours': total_hours,
                'total_attendance': total_attendance,
                'punctuality': {
                    'on_time': on_time_attendance,
                    'late': total_late,
                    'on_time_rate': (on_time_attendance / total_attendance * 100) if total_attendance else 0
                }
            }

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'overview': overview,
                    'mechanics': active_mechanics
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_attendance_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _verify_location(self, mechanic, location, device_info):
        """Helper method to verify location"""
        try:
            if device_info.get('isMockLocationOn'):
                return False

            if not mechanic or not mechanic.work_location_ids:
                return True

            lat = location.get('latitude')
            lon = location.get('longitude')

            for work_location in mechanic.work_location_ids:
                distance = work_location.calculate_distance(lat, lon)
                if distance <= work_location.radius:
                    return True

            return False
        except Exception as e:
            _logger.error(f"Location verification error: {str(e)}")
            return False