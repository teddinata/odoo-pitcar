# controllers/attendance_api.py
from odoo import http
from odoo.http import request
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import logging
import json
import math
import io
import csv
import secrets
import time

_logger = logging.getLogger(__name__)

class AttendanceAPI(http.Controller):
    def _get_working_days(self, month, year):
        """Helper method to get working days configuration"""
        config = request.env['hr.working.days.config'].sudo().search([
            ('month', '=', month),
            ('year', '=', year)
        ], limit=1)
        return config.working_days if config else 26
    def _euclidean_distance(self, descriptor1, descriptor2):
        """Calculate Euclidean distance between two face descriptors"""
        try:
            if len(descriptor1) != len(descriptor2):
                return float('inf')
                
            sum_squares = 0
            for d1, d2 in zip(descriptor1, descriptor2):
                diff = d1 - d2
                sum_squares += diff * diff
                
            distance = math.sqrt(sum_squares)
            # Convert distance to similarity score (0 to 1)
            similarity = 1 / (1 + distance)
            return similarity
            
        except Exception as e:
            _logger.error(f"Error calculating face similarity: {str(e)}")
            return 0
        
    @http.route('/web/v2/attendance/verify-face', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def verify_face(self, **kw):
        """Verify face descriptor against registered face"""
        try:
            # Extract params from JSONRPC request
            params = kw.get('params', kw)
            face_descriptor = params.get('face_descriptor')
            
            if not face_descriptor:
                return {'status': 'error', 'message': 'Face descriptor is required'}

            # Get employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            # Get stored face descriptor
            stored_descriptor = employee.face_descriptor
            if not stored_descriptor:
                return {'status': 'error', 'message': 'No registered face found'}

            # Verify face
            verification_result = self._verify_face(face_descriptor, stored_descriptor)
            
            return {
                'status': 'success',
                'data': {
                    'is_match': verification_result['is_match'],
                    'similarity': verification_result['similarity'],
                    'employee_name': employee.name if verification_result['is_match'] else None
                }
            }

        except Exception as e:
            _logger.error(f"Error in verify_face: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _verify_face(self, current_descriptor, stored_descriptor, threshold=0.4):
        """Verify face with custom threshold"""
        try:
            # Convert stored descriptor from string if needed
            if isinstance(stored_descriptor, str):
                stored_descriptor = json.loads(stored_descriptor)
                
            # Convert descriptors to list of floats
            current_descriptor = [float(x) for x in current_descriptor]
            stored_descriptor = [float(x) for x in stored_descriptor]
            
            # Calculate similarity
            similarity = self._euclidean_distance(current_descriptor, stored_descriptor)
            
            return {
                'is_match': similarity >= threshold,
                'similarity': similarity
            }
            
        except Exception as e:
            _logger.error(f"Face verification error: {str(e)}")
            return {
                'is_match': False,
                'similarity': 0
            }

    @http.route('/web/v2/attendance/check', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def check_attendance(self, **kw):
        try:
            # Extract params
            params = kw.get('params', kw)
            
            # Basic validation
            required_fields = {
                'action_type': params.get('action_type'),
                'face_descriptor': params.get('face_descriptor'),
                'face_image': params.get('face_image'),  # Tambahkan face_image
                'location': params.get('location', {})
            }

            missing_fields = [k for k, v in required_fields.items() if not v]
            if missing_fields:
                return {'status': 'error', 'message': f"Missing required fields: {', '.join(missing_fields)}"}

            # Get employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            # Verify face
            verification_result = self._verify_face(
                params['face_descriptor'], 
                employee.face_descriptor
            )
            
            if not verification_result['is_match']:
                return {'status': 'error', 'message': 'Face verification failed'}

            # Set timezone and get current time
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            now_utc = now.astimezone(pytz.UTC).replace(tzinfo=None)

            # Create/update attendance
            values = {
                'employee_id': employee.id,
                'face_descriptor': json.dumps(params['face_descriptor']),
                'face_image': params['face_image']  # Simpan gambar wajah
            }

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
                    'location': params['location']
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
            # Extract params
            params = kw.get('params', kw)
            face_descriptor = params.get('face_descriptor')
            
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            # Set timezone to Asia/Jakarta
            jakarta_tz = pytz.timezone('Asia/Jakarta')
            
            # Get current datetime in Jakarta timezone
            now = datetime.now(jakarta_tz)
            today = now.date()
            
            # Get start and end of today in UTC (for database queries)
            today_start_utc = jakarta_tz.localize(datetime.combine(today, time.min)).astimezone(pytz.UTC)
            today_end_utc = jakarta_tz.localize(datetime.combine(today, time.max)).astimezone(pytz.UTC)

            # Get today's attendance using UTC times for query
            today_attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', today_start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<', today_end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ], limit=1, order='check_in desc')

            # Get last 2 attendances (excluding today)
            last_attendances = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_in', '<', today_start_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ], limit=2, order='check_in desc')

            # Get current month summary
            first_day = today.replace(day=1)
            last_day = (first_day + relativedelta(months=1, days=-1))
            
            # Convert month boundaries to UTC for database query
            month_start_utc = jakarta_tz.localize(datetime.combine(first_day, time.min)).astimezone(pytz.UTC)
            month_end_utc = jakarta_tz.localize(datetime.combine(last_day, time.max)).astimezone(pytz.UTC)
            
            month_attendances = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', month_start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', month_end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ])

            # Calculate monthly statistics
            present_days = len(set(att.check_in.astimezone(jakarta_tz).date() for att in month_attendances))
            total_working_days = self._get_working_days(month=now.month, year=now.year)
            
            # Standard work start time in Jakarta (8 AM)
            work_start_time = time(8, 1) # 8:01 AM
            
            # Count late attendances
            late_attendances = []
            total_late_minutes = 0
            
            for att in month_attendances:
                check_in_jkt = att.check_in.astimezone(jakarta_tz)
                if check_in_jkt.time() > work_start_time:
                    late_attendances.append(att)
                    scheduled_start = jakarta_tz.localize(
                        datetime.combine(check_in_jkt.date(), work_start_time)
                    )
                    late_minutes = (check_in_jkt - scheduled_start).total_seconds() / 60
                    total_late_minutes += late_minutes

            # Face verification if descriptor provided
            face_verification = None
            if face_descriptor and employee.face_descriptor:
                face_verification = self._verify_face(face_descriptor, employee.face_descriptor)

            # Check if currently checked in
            current_attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], limit=1)

            def format_attendance(attendance):
                if not attendance:
                    return None
                    
                check_in_jkt = attendance.check_in.astimezone(jakarta_tz)
                is_late = check_in_jkt.time() > work_start_time
                late_duration = 0
                
                if is_late:
                    scheduled_start = jakarta_tz.localize(
                        datetime.combine(check_in_jkt.date(), work_start_time)
                    )
                    late_duration = (check_in_jkt - scheduled_start).total_seconds() / 60

                working_hours = 0
                if attendance.check_out:
                    check_out_jkt = attendance.check_out.astimezone(jakarta_tz)
                    
                    # Calculate total duration
                    total_duration = (check_out_jkt - check_in_jkt).total_seconds() / 3600
                    
                    # Define break time (12:00-13:00)
                    break_start = jakarta_tz.localize(datetime.combine(check_in_jkt.date(), time(12, 0)))
                    break_end = jakarta_tz.localize(datetime.combine(check_in_jkt.date(), time(13, 0)))
                    
                    # Calculate break duration if work hours overlap with break time
                    break_duration = 0
                    if check_in_jkt < break_end and check_out_jkt > break_start:
                        overlap_start = max(check_in_jkt, break_start)
                        overlap_end = min(check_out_jkt, break_end)
                        break_duration = (overlap_end - overlap_start).total_seconds() / 3600
                        
                    working_hours = max(0, total_duration - break_duration)

                return {
                    'id': attendance.id,
                    'date': check_in_jkt.date().isoformat(),
                    'status': 'present',
                    'check_in': check_in_jkt.isoformat(),
                    'check_out': attendance.check_out.astimezone(jakarta_tz).isoformat() if attendance.check_out else None,
                    'is_late': is_late,
                    'late_duration': int(late_duration),
                    'working_hours': round(working_hours, 2)
                }

            # Calculate total and average working hours with break time adjustment
            total_hours = 0
            for att in month_attendances:
                if att.check_out:
                    check_in_jkt = att.check_in.astimezone(jakarta_tz)
                    check_out_jkt = att.check_out.astimezone(jakarta_tz)
                    
                    # Calculate total duration
                    total_duration = (check_out_jkt - check_in_jkt).total_seconds() / 3600
                    
                    # Define break time (12:00-13:00)
                    break_start = jakarta_tz.localize(datetime.combine(check_in_jkt.date(), time(12, 0)))
                    break_end = jakarta_tz.localize(datetime.combine(check_in_jkt.date(), time(13, 0)))
                    
                    # Calculate break duration if work hours overlap with break time
                    break_duration = 0
                    if check_in_jkt < break_end and check_out_jkt > break_start:
                        overlap_start = max(check_in_jkt, break_start)
                        overlap_end = min(check_out_jkt, break_end)
                        break_duration = (overlap_end - overlap_start).total_seconds() / 3600
                        
                    total_hours += max(0, total_duration - break_duration)
                    
            avg_hours = round(total_hours / present_days, 2) if present_days > 0 else 0

            return {
                'status': 'success',
                'data': {
                    'is_checked_in': bool(current_attendance),
                    'has_face_registered': bool(employee.face_descriptor),
                    'face_verification': face_verification,
                    'has_fingerprint_registered': bool(employee.fingerprint_registered),
                    'today_attendance': format_attendance(today_attendance) if today_attendance else None,
                    'last_attendances': [format_attendance(att) for att in last_attendances if att],
                    'monthly_summary': {
                        'month': now.strftime('%B'),
                        'year': now.year,
                        'total_working_days': total_working_days,
                        'attendance_summary': {
                            'present': present_days,
                            'absent': total_working_days - present_days,
                            'leave': 0
                        },
                        'late_summary': {
                            'total_late_days': len(late_attendances),
                            'total_late_hours': round(total_late_minutes / 60, 1),
                            'average_late_duration': round(total_late_minutes / len(late_attendances) if late_attendances else 0)
                        },
                        'working_hours_summary': {
                            'total_hours': round(total_hours, 2),
                            'average_hours': avg_hours
                        }
                    },
                    'employee': {
                        'id': employee.id,
                        'name': employee.name
                    }
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
                worked_hours = attendance.actual_worked_hours or 0
                data['total_hours'] += worked_hours
                data['attendance_count'] += 1

                # Calculate late/on-time (example: late if check-in after 8:01 AM)
                check_in_time = pytz.utc.localize(attendance.check_in).astimezone(tz)
                target_time = check_in_time.replace(hour=8, minute=1, second=0)
                
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

    # Tambahkan endpoint-endpoint berikut ke class AttendanceAPI
    @http.route('/web/v2/work-locations', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_work_locations(self, **kw):
        """Get all work locations"""
        try:
            locations = request.env['pitcar.work.location'].sudo().search([])
            return {
                'status': 'success',
                'data': [{
                    'id': loc.id,
                    'name': loc.name,
                    'latitude': loc.latitude,
                    'longitude': loc.longitude,
                    'radius': loc.radius,
                    'address': loc.address,
                    'active': loc.active
                } for loc in locations]
            }
        except Exception as e:
            _logger.error(f"Error in get_work_locations: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/work-locations/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_work_location(self, **kw):
        """Create new work location"""
        try:
            # Debug logging
            _logger.info(f"Received kw: {kw}")
            
            # Get params from JSONRPC request
            params = kw
            if isinstance(kw, dict) and 'params' in kw:
                params = kw['params']
            
            _logger.info(f"Extracted params: {params}")

            required_fields = ['name', 'latitude', 'longitude', 'radius']
            
            # Detailed validation logging
            for field in required_fields:
                _logger.info(f"Checking field {field}: {params.get(field)}")
                
            # Validate required fields
            missing_fields = [field for field in required_fields if not params.get(field)]
            if missing_fields:
                _logger.error(f"Missing fields: {missing_fields}")
                return {
                    'status': 'error',
                    'message': f"Missing required fields: {', '.join(missing_fields)}"
                }
                
            # Create work location
            values = {
                'name': str(params['name']),
                'latitude': float(params['latitude']),
                'longitude': float(params['longitude']),
                'radius': int(params['radius']),
                'address': str(params.get('address', '')),
                'active': bool(params.get('active', True))
            }
            
            _logger.info(f"Creating location with values: {values}")
            
            location = request.env['pitcar.work.location'].sudo().create(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': location.id,
                    'name': location.name,
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'radius': location.radius,
                    'address': location.address,
                    'active': location.active
                }
            }
        except Exception as e:
            _logger.error(f"Error in create_work_location: {str(e)}")
            _logger.error(f"Full traceback:", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/work-locations/update/<int:location_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def update_work_location(self, location_id, **kw):
        """Update existing work location"""
        try:
            # Check if location exists
            location = request.env['pitcar.work.location'].sudo().browse(location_id)
            if not location.exists():
                return {'status': 'error', 'message': 'Location not found'}
                
            # Extract params
            params = kw.get('params', {})
            
            # Update values if provided
            values = {}
            if 'name' in params:
                values['name'] = params['name']
            if 'latitude' in params:
                values['latitude'] = float(params['latitude'])
            if 'longitude' in params:
                values['longitude'] = float(params['longitude'])
            if 'radius' in params:
                values['radius'] = int(params['radius'])
            if 'address' in params:
                values['address'] = params['address']
            if 'active' in params:
                values['active'] = bool(params['active'])
                
            location.write(values)
            
            return {
                'status': 'success',
                'data': {
                    'id': location.id,
                    'name': location.name,
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'radius': location.radius,
                    'address': location.address,
                    'active': location.active
                }
            }
        except Exception as e:
            _logger.error(f"Error in update_work_location: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/work-locations/delete/<int:location_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def delete_work_location(self, location_id, **kw):
        """Delete work location"""
        try:
            location = request.env['pitcar.work.location'].sudo().browse(location_id)
            if not location.exists():
                return {'status': 'error', 'message': 'Location not found'}
                
            location.unlink()
            
            return {
                'status': 'success',
                'message': 'Location deleted successfully'
            }
        except Exception as e:
            _logger.error(f"Error in delete_work_location: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/work-locations/<int:location_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_work_location(self, location_id, **kw):
        """Get single work location by ID"""
        try:
            location = request.env['pitcar.work.location'].sudo().browse(location_id)
            if not location.exists():
                return {'status': 'error', 'message': 'Location not found'}
                
            return {
                'status': 'success',
                'data': {
                    'id': location.id,
                    'name': location.name,
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'radius': location.radius,
                    'address': location.address,
                    'active': location.active
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_work_location: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _get_date_range(self, period_type, start_date=None, end_date=None):
        """Helper to get date range based on period type or custom range"""
        tz = pytz.timezone('Asia/Jakarta')
        now = datetime.now(tz)
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                return (
                    tz.localize(start.replace(hour=0, minute=0, second=0)),
                    tz.localize(end.replace(hour=23, minute=59, second=59))
                )
            except (ValueError, TypeError):
                _logger.error(f"Invalid date format: start={start_date}, end={end_date}")
                return None, None
                
        if period_type == 'today':
            start = now.replace(hour=0, minute=0, second=0)
            end = now
        elif period_type == 'yesterday':
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0)
            end = yesterday.replace(hour=23, minute=59, second=59)
        elif period_type == 'week':
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
            end = now
        elif period_type == 'month':
            start = now.replace(day=1, hour=0, minute=0, second=0)
            end = now
        else:  # default to today
            start = now.replace(hour=0, minute=0, second=0)
            end = now
            
        return start, end

    def _format_attendance(self, attendance, tz):
        """Format single attendance record with timezone handling"""
        if not attendance:
            return None
            
        # Standard work time (8 AM)
        work_start_time = time(8, 1) # 8:01 AM
        
        # Convert times to local timezone
        check_in_local = pytz.UTC.localize(attendance.check_in).astimezone(tz)
        check_out_local = attendance.check_out and pytz.UTC.localize(attendance.check_out).astimezone(tz)
        
        # Calculate late status
        is_late = check_in_local.time() > work_start_time
        late_duration = 0
        if is_late:
            scheduled_start = tz.localize(
                datetime.combine(check_in_local.date(), work_start_time)
            )
            late_duration = round((check_in_local - scheduled_start).total_seconds() / 60)
        
        # Calculate working hours
        working_hours = 0
        if check_out_local:
            working_hours = round((check_out_local - check_in_local).total_seconds() / 3600, 2)
        
        return {
            'id': attendance.id,
            'date': check_in_local.date().isoformat(),
            'check_in': check_in_local.isoformat(),
            'check_out': check_out_local.isoformat() if check_out_local else None,
            'is_late': is_late,
            'late_duration': late_duration,
            'working_hours': working_hours,
            'status': 'present'
        }

    @http.route('/web/v2/attendance/history', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_attendance_history(self, **kw):
        """Get attendance history with date filtering"""
        try:
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Get date parameters from payload
            data = request.get_json_data()
            params = data.get('params', {})
            
            # Extract parameters
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            period = params.get('period')  # 'today', 'week', 'month'
            year = params.get('year', now.year)
            
            _logger.info(f"Received parameters: start_date={start_date}, end_date={end_date}, period={period}, year={year}")

            # Initialize variables
            start_utc = None
            end_utc = None
            date_range_start = None
            date_range_end = None

            # Process date filters
            try:
                if start_date and end_date:
                    # Create naive datetime and localize it
                    start = datetime.strptime(f"{start_date} 00:00:00", '%Y-%m-%d %H:%M:%S')
                    end = datetime.strptime(f"{end_date} 23:59:59", '%Y-%m-%d %H:%M:%S')
                    
                    # Set date range
                    date_range_start = start_date
                    date_range_end = end_date
                    
                elif period:
                    if period == 'today':
                        today = now.date()
                        start = datetime.combine(today, datetime.min.time())
                        end = datetime.combine(today, datetime.max.time())
                        
                    elif period == 'week':
                        # Get start of week (Monday)
                        week_start = now - timedelta(days=now.weekday())
                        start = datetime.combine(week_start.date(), datetime.min.time())
                        end = datetime.combine(now.date(), datetime.max.time())
                        
                    elif period == 'month':
                        # Get start of month
                        start = datetime.combine(now.replace(day=1).date(), datetime.min.time())
                        # Get end of month
                        next_month = now.replace(day=28) + timedelta(days=4)
                        end = datetime.combine((next_month - timedelta(days=next_month.day)).date(), 
                                            datetime.max.time())
                    else:
                        # Default to today
                        today = now.date()
                        start = datetime.combine(today, datetime.min.time())
                        end = datetime.combine(today, datetime.max.time())
                    
                    # Set date range
                    date_range_start = start.strftime('%Y-%m-%d')
                    date_range_end = end.strftime('%Y-%m-%d')
                    
                else:
                    # Default to today if no filter specified
                    today = now.date()
                    start = datetime.combine(today, datetime.min.time())
                    end = datetime.combine(today, datetime.max.time())
                    
                    date_range_start = today.strftime('%Y-%m-%d')
                    date_range_end = today.strftime('%Y-%m-%d')

                # Localize dates
                start = tz.localize(start)
                end = tz.localize(end)
                
                # Convert to UTC for database
                start_utc = start.astimezone(pytz.UTC).replace(tzinfo=None)
                end_utc = end.astimezone(pytz.UTC).replace(tzinfo=None)
                
                _logger.info(f"Processed date range UTC: {start_utc} to {end_utc}")
                _logger.info(f"Display date range: {date_range_start} to {date_range_end}")

            except (ValueError, TypeError) as e:
                _logger.error(f"Date processing error: {str(e)}")
                return {'status': 'error', 'message': 'Invalid date format or values'}

            # Get employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            # Build domain
            domain = [
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_utc),
                ('check_in', '<', end_utc)
            ]

            _logger.info(f"Search domain: {domain}")
            
            # Get attendance records
            attendances = request.env['hr.attendance'].sudo().search(domain, order='check_in desc')
            
            # Process records
            records = []
            total_hours = 0
            total_late = 0
            total_ontime = 0
            
            work_start_time = time(8, 1)  # 8:01 AM
            
            for attendance in attendances:
                check_in_utc = attendance.check_in
                check_out_utc = attendance.check_out
                
                # Convert times to local timezone
                check_in_local = pytz.UTC.localize(check_in_utc).astimezone(tz)
                check_out_local = check_out_utc and pytz.UTC.localize(check_out_utc).astimezone(tz)
                
                # Calculate late status
                is_late = check_in_local.time() > work_start_time
                late_duration = 0
                
                if is_late:
                    scheduled_start = datetime.combine(check_in_local.date(), work_start_time)
                    scheduled_start = tz.localize(scheduled_start)
                    late_duration = round((check_in_local - scheduled_start).total_seconds() / 60)
                    total_late += 1
                else:
                    total_ontime += 1
                
                # Calculate working hours
                working_hours = 0
                if check_out_local:
                    # Calculate total duration
                    total_duration = (check_out_local - check_in_local).total_seconds() / 3600
                    
                    # Define break time (12:00-13:00)
                    break_start = tz.localize(datetime.combine(check_in_local.date(), time(12, 0)))
                    break_end = tz.localize(datetime.combine(check_in_local.date(), time(13, 0)))
                    
                    # Calculate break duration if work hours overlap with break time
                    break_duration = 0
                    if check_in_local < break_end and check_out_local > break_start:
                        overlap_start = max(check_in_local, break_start)
                        overlap_end = min(check_out_local, break_end)
                        break_duration = (overlap_end - overlap_start).total_seconds() / 3600
                        
                    working_hours = max(0, total_duration - break_duration)
                    total_hours += working_hours
                
                record = {
                    'id': attendance.id,
                    'date': check_in_local.date().isoformat(),
                    'check_in': check_in_local.isoformat(),
                    'check_out': check_out_local.isoformat() if check_out_local else None,
                    'is_late': is_late,
                    'late_duration': late_duration,
                    'working_hours': working_hours
                }
                
                records.append(record)
            
            # Calculate summary
            total_records = len(records)
            summary = {
                'total_records': total_records,
                'late_count': total_late,
                'ontime_count': total_ontime,
                'total_hours': round(total_hours, 2),
                'average_hours': round(total_hours / total_records, 2) if total_records > 0 else 0,
                'punctuality_rate': round((total_ontime / total_records * 100), 2) if total_records > 0 else 0
            }

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'start': date_range_start,
                        'end': date_range_end
                    },
                    'records': records,
                    'summary': summary
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_attendance_history: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/attendance/report', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_attendance_report(self, **kw):
        """Get attendance report with proper month filtering"""
        try:
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Get date parameters from payload
            data = request.get_json_data()
            params = data.get('params', {})
            
            # Extract parameters
            month = params.get('month')  # 0-11 from frontend
            year = params.get('year', now.year)
            
            _logger.info(f"Received report parameters: month={month}, year={year}")

            # Initialize variables
            start_utc = None
            end_utc = None
            
            # Process month and year
            try:
                if month is not None:
                    # Convert JavaScript month (0-11) to Python month (1-12)
                    python_month = int(month) + 1
                    
                    if not 1 <= python_month <= 12:
                        return {'status': 'error', 'message': 'Month must be between 0 and 11'}
                    
                    # Create start date (first day of month)
                    start = datetime(year, python_month, 1, 0, 0, 0)
                    
                    # Create end date (first day of next month)
                    if python_month == 12:
                        end = datetime(year + 1, 1, 1, 0, 0, 0)
                    else:
                        end = datetime(year, python_month + 1, 1, 0, 0, 0)
                    
                    # Adjust end date to last moment of selected month
                    end = end - timedelta(seconds=1)
                else:
                    # Default to current month
                    current_month = now.month
                    start = datetime(now.year, current_month, 1, 0, 0, 0)
                    if current_month == 12:
                        end = datetime(now.year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
                    else:
                        end = datetime(now.year, current_month + 1, 1, 0, 0, 0) - timedelta(seconds=1)

                # Localize dates
                start = tz.localize(start)
                end = tz.localize(end)
                
                _logger.info(f"Calculated date range - Start: {start}, End: {end}")

                # Convert to UTC for database queries
                start_utc = start.astimezone(pytz.UTC).replace(tzinfo=None)
                end_utc = end.astimezone(pytz.UTC).replace(tzinfo=None)

            except (ValueError, TypeError) as e:
                _logger.error(f"Date processing error: {str(e)}")
                return {'status': 'error', 'message': 'Invalid date format or values'}

            # Get employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            # Build domain
            domain = [
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_utc),
                ('check_in', '<', end_utc)
            ]

            _logger.info(f"Search domain: {domain}")

            # Get attendance records
            attendances = request.env['hr.attendance'].sudo().search(domain, order='check_in asc')
            
            # Calculate working days (excluding weekends)
            # total_days = 0
            # current = start.date()
            # while current <= end.date():
            #     if current.weekday() < 5:  # Monday = 0, Sunday = 6
            #         total_days += 1
            #     current += timedelta(days=1)
            # Calculate actual working days but cap at 26
            total_days = 26
            # current = start.date()
            # while current <= end.date():
            #     if current.weekday() < 5:  # Monday = 0, Friday = 4
            #         total_days += 1
            #     current += timedelta(days=1)
            # total_days = min(total_days, 26)  # Cap at 26 days

            # Process records
            present_days = set()
            total_late = 0
            total_late_minutes = 0
            total_hours = 0
            on_time_count = 0
            daily_hours = {}
            work_start_time = time(8, 1) # 8:01 AM

            for attendance in attendances:
                check_in_utc = attendance.check_in
                check_out_utc = attendance.check_out
                
                # Convert to local time
                check_in_local = pytz.UTC.localize(check_in_utc).astimezone(tz)
                check_out_local = check_out_utc and pytz.UTC.localize(check_out_utc).astimezone(tz)
                
                # Count present days
                present_days.add(check_in_local.date())
                
                # Calculate late status
                is_late = check_in_local.time() > work_start_time
                if is_late:
                    total_late += 1
                    scheduled_start = datetime.combine(check_in_local.date(), work_start_time)
                    scheduled_start = tz.localize(scheduled_start)
                    late_minutes = round((check_in_local - scheduled_start).total_seconds() / 60)
                    total_late_minutes += late_minutes
                else:
                    on_time_count += 1
                
                # Calculate working hours
                if check_out_local:
                    # Calculate total duration
                    total_duration = (check_out_local - check_in_local).total_seconds() / 3600
                    
                    # Define break time (12:00-13:00)
                    break_start = tz.localize(datetime.combine(check_in_local.date(), time(12, 0)))
                    break_end = tz.localize(datetime.combine(check_in_local.date(), time(13, 0)))
                    
                    # Calculate break duration if work hours overlap with break time
                    break_duration = 0
                    if check_in_local < break_end and check_out_local > break_start:
                        overlap_start = max(check_in_local, break_start)
                        overlap_end = min(check_out_local, break_end)
                        break_duration = (overlap_end - overlap_start).total_seconds() / 3600
                        
                    working_hours = max(0, total_duration - break_duration)
                    total_hours += working_hours
                    
                    # Aggregate daily hours for chart
                    day_str = f"{check_in_local.day:02d}"
                    if day_str in daily_hours:
                        daily_hours[day_str] += working_hours
                    else:
                        daily_hours[day_str] = working_hours

            # Prepare chart data
            chart_data = [
                {"date": day, "hours": round(hours, 2)}
                for day, hours in sorted(daily_hours.items())
            ]

            # Calculate final metrics
            total_present = len(present_days)
            
            summary = {
                'present': total_present,
                'totalDays': total_days,
                'late': total_late,
                'lateHours': round(total_late_minutes / 60, 1),
                'avgHours': round(total_hours / total_present, 2) if total_present > 0 else 0,
                'punctuality': round((on_time_count / total_present * 100), 1) if total_present > 0 else 100,
                'totalHours': round(total_hours, 1),
                'onTime': on_time_count
            }

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'month': int(month) if month is not None else now.month - 1,  # Convert back to JS month (0-11)
                        'year': year,
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'summary': summary,
                    'chartData': chart_data
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_attendance_report: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/mechanic/check-credential', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def check_mechanic_credential(self, **kw):
        """Check mechanic's temporary password by email"""
        try:
            # Extract params from request
            params = kw.get('params', kw)
            email = params.get('email')

            if not email:
                return {
                    'status': 'error',
                    'message': 'Email is required'
                }

            # Search for mechanic by email through user
            user = request.env['res.users'].sudo().search([
                ('login', '=', email)
            ], limit=1)

            if not user:
                return {
                    'status': 'error',
                    'message': 'Email not found'
                }

            # Get mechanic record
            mechanic = request.env['pitcar.mechanic.new'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)

            if not mechanic or not mechanic.temp_password:
                return {
                    'status': 'error',
                    'message': 'No temporary password found for this email'
                }

            # Return credential information
            return {
                'status': 'success',
                'data': {
                    'name': mechanic.name,
                    'email': email,
                    'temp_password': mechanic.temp_password,
                    'message': 'Please change your password after first login'
                }
            }

        except Exception as e:
            _logger.error(f"Error in check_mechanic_credential: {str(e)}")
            return {
                'status': 'error',
                'message': 'Internal server error'
            }
        
    @http.route('/web/v2/mechanic/profile', type='json', auth='user', methods=['GET'], csrf=False, cors='*')
    def get_mechanic_profile(self, **kw):
        """Get mechanic profile information"""
        try:
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            mechanic = request.env['pitcar.mechanic.new'].sudo().search([
                ('employee_id', '=', employee.id)
            ], limit=1)

            if not mechanic:
                return {'status': 'error', 'message': 'Mechanic profile not found'}

            return {
                'status': 'success',
                'data': {
                    'id': mechanic.id,
                    'name': mechanic.name,
                    'email': request.env.user.login,
                    'position': mechanic.position_id.name if mechanic.position_id else None,
                    'profile_picture': employee.image_1920.decode() if employee.image_1920 else None,
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_mechanic_profile: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/mechanic/profile/update', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def update_mechanic_profile(self, **kw):
        """Update mechanic profile information (name and profile picture)"""
        try:
            params = kw.get('params', kw)
            
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}

            mechanic = request.env['pitcar.mechanic.new'].sudo().search([
                ('employee_id', '=', employee.id)
            ], limit=1)

            if not mechanic:
                return {'status': 'error', 'message': 'Mechanic profile not found'}

            # Update values if provided
            update_vals = {}
            employee_vals = {}

            if 'name' in params:
                new_name = params['name'].strip()
                if new_name:
                    update_vals['name'] = new_name
                    employee_vals['name'] = new_name
                else:
                    return {'status': 'error', 'message': 'Name cannot be empty'}

            if 'profile_picture' in params:
                # Assuming profile_picture is base64 encoded image
                employee_vals['image_1920'] = params['profile_picture']

            # Update mechanic record
            if update_vals:
                mechanic.write(update_vals)

            # Update employee record
            if employee_vals:
                employee.write(employee_vals)

            return {
                'status': 'success',
                'message': 'Profile updated successfully',
                'data': {
                    'id': mechanic.id,
                    'name': mechanic.name,
                    'email': request.env.user.login,
                    'profile_picture': employee.image_1920.decode() if employee.image_1920 else None
                }
            }

        except Exception as e:
            _logger.error(f"Error in update_mechanic_profile: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/mechanic/password/update', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def update_mechanic_password(self, **kw):
        """Update mechanic password"""
        try:
            params = kw.get('params', kw)
            
            # Validate required parameters
            if not params.get('current_password'):
                return {'status': 'error', 'message': 'Current password is required'}
            
            if not params.get('new_password'):
                return {'status': 'error', 'message': 'New password is required'}

            if len(params['new_password']) < 8:
                return {'status': 'error', 'message': 'New password must be at least 8 characters long'}

            user = request.env.user

            # Verify current password
            try:
                request.env['res.users'].check_credentials(request.env.user.id, params['current_password'])
            except:
                return {'status': 'error', 'message': 'Current password is incorrect'}

            # Update password
            user.write({'password': params['new_password']})

            # Clear temporary password if exists
            mechanic = request.env['pitcar.mechanic.new'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)
            
            if mechanic and mechanic.temp_password:
                mechanic.write({'temp_password': False})

            return {
                'status': 'success',
                'message': 'Password updated successfully'
            }

        except Exception as e:
            _logger.error(f"Error in update_mechanic_password: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # HR Attendance API Admin
    @http.route('/web/v2/hr/attendance/overview', type='json', auth='user', methods=['POST'], csrf=False)
    def get_hr_attendance_overview(self, **kw):
        """Get attendance overview/summary"""
        try:
            # Get date range parameters
            date_range = kw.get('date_range', 'today')
            start_date = kw.get('start_date')
            end_date = kw.get('end_date')
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Calculate date range
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    start = tz.localize(start.replace(hour=0, minute=0, second=0))
                    end = tz.localize(end.replace(hour=23, minute=59, second=59))
                except (ValueError, TypeError):
                    return {'status': 'error', 'message': 'Invalid date format'}
            else:
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

            # Get all active employees
            employees = request.env['hr.employee'].sudo().search([('active', '=', True)])
            total_employees = len(employees)

            # Get attendance records
            domain = [
                ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ]
            
            attendances = request.env['hr.attendance'].sudo().search(domain)

            # Calculate metrics
            present_employees = len(set(att.employee_id.id for att in attendances))
            late_attendances = len([att for att in attendances if att.is_late])
            total_late_minutes = sum(att.late_duration for att in attendances if att.is_late)
            total_work_hours = sum(att.actual_worked_hours for att in attendances if att.check_out)

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range if not (start_date and end_date) else 'custom',
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'overview': {
                        'total_employees': total_employees,
                        'present': present_employees,
                        'absent': total_employees - present_employees,
                        'late': late_attendances,
                        'total_late_hours': round(total_late_minutes / 60, 1),
                        'total_work_hours': round(total_work_hours, 1),
                        'attendance_rate': round((present_employees / total_employees * 100), 1) if total_employees > 0 else 0
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_hr_attendance_overview: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/hr/attendance/records', type='json', auth='user', methods=['POST'], csrf=False)
    def get_hr_attendance_records(self, **kw):
        try:
            # Extract parameters
            params = kw.get('params', kw)
            
            # Basic parameters
            search_query = params.get('search', '')
            department_id = params.get('department_id')
            date_range = params.get('date_range', 'today')
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            employee_ids = params.get('employee_ids', [])
            is_late = params.get('is_late')
            
            # Pagination parameters
            limit = int(params.get('limit', 50))
            offset = int(params.get('offset', 0))
            sort_by = params.get('sort_by', 'check_in')
            sort_order = params.get('sort_order', 'desc')
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Calculate date range
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    start = tz.localize(start.replace(hour=0, minute=0, second=0))
                    end = tz.localize(end.replace(hour=23, minute=59, second=59))
                except (ValueError, TypeError):
                    return {'status': 'error', 'message': 'Invalid date format'}
            else:
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

            # Build domain for filtering
            domain = [
                ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ]

            # Add search filters
            if search_query:
                domain += [
                    '|', '|', '|',
                    ('employee_id.name', 'ilike', search_query),
                    ('employee_id.department_id.name', 'ilike', search_query),
                    ('employee_id.job_title', 'ilike', search_query),
                    ('employee_id.work_email', 'ilike', search_query)
                ]

            # Employee filter
            if employee_ids:
                if isinstance(employee_ids, list):
                    domain.append(('employee_id', 'in', employee_ids))
                else:
                    domain.append(('employee_id', '=', employee_ids))

            # Department filter
            if department_id:
                domain.append(('employee_id.department_id', '=', department_id))

            # Late status filter
            if is_late is not None:
                domain.append(('is_late', '=', is_late))

            # Get Attendance Model
            AttendanceModel = request.env['hr.attendance'].sudo()

            # Get filter options data
            departments = request.env['hr.department'].sudo().search_read(
                [], ['id', 'name'], order='name'
            )
            employees = request.env['hr.employee'].sudo().search_read(
                [], ['id', 'name', 'department_id'], order='name'
            )

            # Get ALL records for summary calculation
            all_attendances = AttendanceModel.search(domain)
            
            # Initialize counters for summary
            total_attendance = 0
            total_work_hours = 0
            total_late = 0
            on_time_attendance = 0
            
            # Group attendance by employee for summary calculation
            for attendance in all_attendances:
                # Count total attendance
                total_attendance += 1
                
                # Calculate work hours if checked out
                if attendance.check_out:
                    worked_hours = attendance.actual_worked_hours
                    total_work_hours += worked_hours

                # Count late/on-time attendance
                if attendance.is_late:
                    total_late += 1
                else:
                    on_time_attendance += 1

            # Build summary with accurate calculations
            summary = {
                'total_attendance': total_attendance,
                'total_work_hours': round(total_work_hours, 1),
                'average_work_hours': round(total_work_hours / total_attendance, 1) if total_attendance > 0 else 0,
                'punctuality': {
                    'on_time': on_time_attendance,
                    'late': total_late,
                    'on_time_rate': round((on_time_attendance / total_attendance * 100), 1) if total_attendance > 0 else 0
                }
            }

            # Get paginated records for display
            paginated_attendances = AttendanceModel.search(
                domain,
                limit=limit,
                offset=offset,
                order=f"{sort_by} {sort_order}"
            )
            
            # Count total records for pagination
            total_count = AttendanceModel.search_count(domain)

            # Process paginated records
            records = []
            for attendance in paginated_attendances:
                check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                check_out = attendance.check_out and pytz.utc.localize(attendance.check_out).astimezone(tz)

                # Calculate working hours with break time adjustment
                worked_hours = 0
                if check_out:
                    # Calculate total duration
                    total_duration = (check_out - check_in).total_seconds() / 3600
                    
                    # Define break time (12:00-13:00)
                    break_start = tz.localize(datetime.combine(check_in.date(), time(12, 0)))
                    break_end = tz.localize(datetime.combine(check_in.date(), time(13, 0)))
                    
                    # Calculate break duration if work hours overlap with break time
                    break_duration = 0
                    if check_in < break_end and check_out > break_start:
                        overlap_start = max(check_in, break_start)
                        overlap_end = min(check_out, break_end)
                        break_duration = (overlap_end - overlap_start).total_seconds() / 3600
                        
                    worked_hours = max(0, total_duration - break_duration)

                records.append({
                    'id': attendance.id,
                    'employee': {
                        'id': attendance.employee_id.id,
                        'name': attendance.employee_id.name,
                        'department': {
                            'id': attendance.employee_id.department_id.id if attendance.employee_id.department_id else None,
                            'name': attendance.employee_id.department_id.name if attendance.employee_id.department_id else None
                        },
                        'job_title': attendance.employee_id.job_title
                    },
                    'attendance': {
                        'check_in': check_in.strftime('%Y-%m-%d %H:%M:%S'),
                        'check_out': check_out.strftime('%Y-%m-%d %H:%M:%S') if check_out else None,
                        'worked_hours': round(worked_hours, 2),
                        'is_late': attendance.is_late,
                        'late_duration': round(attendance.late_duration, 0) if attendance.is_late else 0
                    },
                    'face_image': attendance.face_image if attendance.face_image else None
                })

            # Return complete response
            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range if not (start_date and end_date) else 'custom',
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'filter_options': {
                        'departments': departments,
                        'employees': employees
                    },
                    'summary': summary,
                    'records': records,
                    'pagination': {
                        'total': total_count,
                        'offset': offset,
                        'limit': limit,
                        'page_count': math.ceil(total_count / limit) if limit > 0 else 0
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_hr_attendance_records: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/hr/attendance/employee/<int:employee_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_employee_attendance(self, employee_id, **kw):
        """Get specific employee attendance details with period filtering"""
        try:
            # Extract params from request
            params = kw.get('params', kw)
            
            # Get period parameters
            date_range = params.get('date_range', 'today')
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            include_records = params.get('include_records', True)  # Option to include detailed records
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Get employee
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            if not employee.exists():
                return {'status': 'error', 'message': 'Employee not found'}

            # Calculate date range
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    start = tz.localize(start.replace(hour=0, minute=0, second=0))
                    end = tz.localize(end.replace(hour=23, minute=59, second=59))
                except (ValueError, TypeError):
                    return {'status': 'error', 'message': 'Invalid date format'}
            else:
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

            # Build domain
            domain = [
                ('employee_id', '=', employee_id),
                ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ]

            # Get attendance records
            attendances = request.env['hr.attendance'].sudo().search(domain, order='check_in asc')

            # Calculate metrics
            total_work_hours = 0
            total_late = 0
            total_late_minutes = 0
            on_time_count = 0
            attendance_dates = set()  # For tracking unique dates

            attendance_records = []
            for attendance in attendances:
                # Convert times to local timezone
                check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                check_out = attendance.check_out and pytz.utc.localize(attendance.check_out).astimezone(tz)
                
                # Track unique dates
                attendance_dates.add(check_in.date())
                
                # Calculate worked hours
                worked_hours = attendance.actual_worked_hours if attendance.check_out else 0
                total_work_hours += worked_hours

                # Track late/on-time and late duration
                if attendance.is_late:
                    total_late += 1
                    total_late_minutes += attendance.late_duration
                else:
                    on_time_count += 1

                if include_records:
                    attendance_records.append({
                        'date': check_in.strftime('%Y-%m-%d'),
                        'check_in': check_in.strftime('%H:%M:%S'),
                        'check_out': check_out.strftime('%H:%M:%S') if check_out else None,
                        'worked_hours': round(worked_hours, 2),
                        'is_late': attendance.is_late,
                        'late_duration': round(attendance.late_duration, 0) if attendance.is_late else 0,
                        'face_image': attendance.face_image if attendance.face_image else None
                    })

            # Calculate summary metrics
            total_attendance = len(attendance_dates)  # Using unique dates
            
            return {
                'status': 'success',
                'data': {
                    'employee': {
                        'id': employee.id,
                        'name': employee.name,
                        'department': employee.department_id.name if employee.department_id else None,
                        'job_title': employee.job_title,
                        'work_phone': employee.work_phone,
                        'work_email': employee.work_email,
                        'image': employee.image_1920.decode() if employee.image_1920 else None
                    },
                    'date_range': {
                        'type': date_range if not (start_date and end_date) else 'custom',
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'summary': {
                        'attendance': {
                            'total_days': total_attendance,
                            'total_records': len(attendances),
                            'late_count': total_late,
                            'on_time_count': on_time_count,
                            'punctuality_rate': round((on_time_count / len(attendances) * 100), 1) if attendances else 0
                        },
                        'work_hours': {
                            'total': round(total_work_hours, 1),
                            'average_per_day': round(total_work_hours / total_attendance, 1) if total_attendance > 0 else 0
                        },
                        'late_summary': {
                            'total_late_hours': round(total_late_minutes / 60, 1),
                            'average_late_duration': round(total_late_minutes / total_late, 0) if total_late > 0 else 0
                        }
                    },
                    'attendance_records': attendance_records if include_records else []
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_employee_attendance: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/hr/attendance/report', type='json', auth='user', methods=['POST'], csrf=False)
    def generate_attendance_report(self, **kw):
        """Generate comprehensive attendance report with department and employee breakdowns"""
        try:
            # Extract params
            params = kw.get('params', kw)
            
            # Get parameters with defaults
            date_range = params.get('date_range', 'this_month')
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            department_id = params.get('department_id')  # Optional department filter
            include_inactive = params.get('include_inactive', False)
            group_by = params.get('group_by', 'department')  # 'department' or 'employee'
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Calculate date range
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    start = tz.localize(start.replace(hour=0, minute=0, second=0))
                    end = tz.localize(end.replace(hour=23, minute=59, second=59))
                except (ValueError, TypeError):
                    return {'status': 'error', 'message': 'Invalid date format'}
            else:
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
                elif date_range == 'last_month':
                    last_month = now - timedelta(days=now.day)
                    start = last_month.replace(day=1, hour=0, minute=0, second=0)
                    end = now.replace(day=1, hour=0, minute=0, second=0) - timedelta(seconds=1)
                else:
                    start = now.replace(hour=0, minute=0, second=0)
                    end = now

            # Convert to UTC for database queries
            start_utc = start.astimezone(pytz.UTC)
            end_utc = end.astimezone(pytz.UTC)

            # Build employee domain
            employee_domain = []
            if not include_inactive:
                employee_domain.append(('active', '=', True))
            if department_id:
                if isinstance(department_id, list):
                    employee_domain.append(('department_id', 'in', department_id))
                else:
                    employee_domain.append(('department_id', '=', department_id))

            # Get employees
            employees = request.env['hr.employee'].sudo().search(employee_domain)
            employee_ids = employees.mapped('id')

            # Build attendance domain
            attendance_domain = [
                ('employee_id', 'in', employee_ids),
                ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ]

            # Get attendance records
            attendances = request.env['hr.attendance'].sudo().search(attendance_domain)

            # Initialize data structures for analysis
            department_stats = {}
            employee_stats = {}
            attendance_dates = {}  # Track unique dates per employee

            # Process attendance records
            for attendance in attendances:
                emp = attendance.employee_id
                dept_id = emp.department_id.id if emp.department_id else 'no_dept'
                emp_id = emp.id
                
                # Initialize department stats if needed
                if dept_id not in department_stats:
                    department_stats[dept_id] = {
                        'id': dept_id,
                        'name': emp.department_id.name if emp.department_id else 'No Department',
                        'employee_count': 0,
                        'total_attendance': 0,
                        'late_count': 0,
                        'total_work_hours': 0,
                        'total_late_minutes': 0,
                        'present_employees': set()
                    }

                # Initialize employee stats if needed
                if emp_id not in employee_stats:
                    employee_stats[emp_id] = {
                        'id': emp_id,
                        'name': emp.name,
                        'department_id': dept_id,
                        'department_name': emp.department_id.name if emp.department_id else 'No Department',
                        'total_attendance': 0,
                        'late_count': 0,
                        'total_work_hours': 0,
                        'total_late_minutes': 0,
                        'attendance_dates': set()
                    }

                # Convert check-in time to local timezone for date tracking
                check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                date_str = check_in.date()

                # Update employee statistics
                employee_stats[emp_id]['attendance_dates'].add(date_str)
                employee_stats[emp_id]['total_attendance'] += 1
                
                if attendance.is_late:
                    employee_stats[emp_id]['late_count'] += 1
                    employee_stats[emp_id]['total_late_minutes'] += attendance.late_duration
                
                if attendance.check_out:
                    employee_stats[emp_id]['total_work_hours'] += attendance.actual_worked_hours

                # Update department statistics
                department_stats[dept_id]['present_employees'].add(emp_id)
                department_stats[dept_id]['total_attendance'] += 1
                
                if attendance.is_late:
                    department_stats[dept_id]['late_count'] += 1
                    department_stats[dept_id]['total_late_minutes'] += attendance.late_duration
                
                if attendance.check_out:
                    department_stats[dept_id]['total_work_hours'] += attendance.actual_worked_hours

            # Calculate employee counts per department
            for emp in employees:
                dept_id = emp.department_id.id if emp.department_id else 'no_dept'
                if dept_id in department_stats:
                    department_stats[dept_id]['employee_count'] += 1

            # Format department statistics
            formatted_departments = []
            total_employees = len(employees)
            total_present = 0
            total_work_hours = 0
            total_late_count = 0
            total_late_minutes = 0

            for dept_id, stats in department_stats.items():
                present_count = len(stats['present_employees'])
                total_present += present_count
                total_work_hours += stats['total_work_hours']
                total_late_count += stats['late_count']
                total_late_minutes += stats['total_late_minutes']

                formatted_departments.append({
                    'department': {
                        'id': stats['id'],
                        'name': stats['name']
                    },
                    'metrics': {
                        'employees': {
                            'total': stats['employee_count'],
                            'present': present_count,
                            'attendance_rate': round((present_count / stats['employee_count'] * 100), 1) if stats['employee_count'] > 0 else 0
                        },
                        'attendance': {
                            'total': stats['total_attendance'],
                            'late_count': stats['late_count'],
                            'on_time_count': stats['total_attendance'] - stats['late_count'],
                            'punctuality_rate': round(((stats['total_attendance'] - stats['late_count']) / stats['total_attendance'] * 100), 1) if stats['total_attendance'] > 0 else 0
                        },
                        'work_hours': {
                            'total': round(stats['total_work_hours'], 1),
                            'average_per_employee': round(stats['total_work_hours'] / present_count, 1) if present_count > 0 else 0
                        },
                        'late_summary': {
                            'total_hours': round(stats['total_late_minutes'] / 60, 1),
                            'average_per_incident': round(stats['total_late_minutes'] / stats['late_count'], 0) if stats['late_count'] > 0 else 0
                        }
                    }
                })

            # Format employee statistics
            formatted_employees = []
            for emp_id, stats in employee_stats.items():
                total_attendance = stats['total_attendance']
                formatted_employees.append({
                    'employee': {
                        'id': stats['id'],
                        'name': stats['name'],
                        'department': {
                            'id': stats['department_id'],
                            'name': stats['department_name']
                        }
                    },
                    'metrics': {
                        'attendance': {
                            'days_present': len(stats['attendance_dates']),
                            'total_records': total_attendance,
                            'late_count': stats['late_count'],
                            'on_time_count': total_attendance - stats['late_count'],
                            'punctuality_rate': round(((total_attendance - stats['late_count']) / total_attendance * 100), 1) if total_attendance > 0 else 0
                        },
                        'work_hours': {
                            'total': round(stats['total_work_hours'], 1),
                            'average_per_day': round(stats['total_work_hours'] / len(stats['attendance_dates']), 1) if stats['attendance_dates'] else 0
                        },
                        'late_summary': {
                            'total_hours': round(stats['total_late_minutes'] / 60, 1),
                            'average_duration': round(stats['total_late_minutes'] / stats['late_count'], 0) if stats['late_count'] > 0 else 0
                        }
                    }
                })

            # Calculate overall summary
            overall_summary = {
                'employees': {
                    'total': total_employees,
                    'present': total_present,
                    'attendance_rate': round((total_present / total_employees * 100), 1) if total_employees > 0 else 0
                },
                'attendance': {
                    'total_records': sum(dept['metrics']['attendance']['total'] for dept in formatted_departments),
                    'late_count': total_late_count,
                    'punctuality_rate': round(((sum(dept['metrics']['attendance']['total'] for dept in formatted_departments) - total_late_count) / 
                                            sum(dept['metrics']['attendance']['total'] for dept in formatted_departments) * 100), 1) 
                                        if sum(dept['metrics']['attendance']['total'] for dept in formatted_departments) > 0 else 0
                },
                'work_hours': {
                    'total': round(total_work_hours, 1),
                    'average_per_employee': round(total_work_hours / total_present, 1) if total_present > 0 else 0
                },
                'late_summary': {
                    'total_hours': round(total_late_minutes / 60, 1),
                    'average_per_incident': round(total_late_minutes / total_late_count, 0) if total_late_count > 0 else 0
                }
            }

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range if not (start_date and end_date) else 'custom',
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'summary': overall_summary,
                    'departments': formatted_departments,
                    'employees': formatted_employees if group_by == 'employee' else []
                }
            }

        except Exception as e:
            _logger.error(f"Error in generate_attendance_report: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/hr/attendance/monthly-summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_monthly_attendance_summary(self, **kw):
        """Get monthly attendance summary with detailed statistics"""
        try:
            # Extract params
            params = kw.get('params', kw)
            
            # Get parameters
            month = int(params.get('month', datetime.now().month))
            year = int(params.get('year', datetime.now().year))
            department_id = params.get('department_id')
            include_details = params.get('include_details', True)
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Calculate first and last day of the month
            start = datetime(year, month, 1)
            if month == 12:
                end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end = datetime(year, month + 1, 1) - timedelta(seconds=1)

            # Localize dates
            start = tz.localize(start)
            end = tz.localize(end)
            
            # Convert to UTC for database queries
            start_utc = start.astimezone(pytz.UTC)
            end_utc = end.astimezone(pytz.UTC)

            # Calculate working days (excluding weekends)
            # working_days = 0
            # current = start.date()
            # weekend_days = set()
            # while current <= end.date():
            #     if current.weekday() < 5:  # Monday = 0, Sunday = 6
            #         working_days += 1
            #     else:
            #         weekend_days.add(current)
            #     current += timedelta(days=1)
            
            # Cap working days at 26 as per standard
            # working_days = min(working_days, 26)
            # working_days = 26
            # Dapatkan working days dari konfigurasi
            working_days = self._get_working_days(month, year)

            # Build employee domain
            employee_domain = [('active', '=', True)]
            if department_id:
                if isinstance(department_id, list):
                    employee_domain.append(('department_id', 'in', department_id))
                else:
                    employee_domain.append(('department_id', '=', department_id))

            # Get employees
            employees = request.env['hr.employee'].sudo().search(employee_domain)

            # Get attendance records
            attendance_domain = [
                ('employee_id', 'in', employees.ids),
                ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ]

            attendances = request.env['hr.attendance'].sudo().search(attendance_domain)

            # Track metrics
            employee_stats = {}
            department_stats = {}
            
            # Initialize stats for all employees
            for employee in employees:
                emp_id = employee.id
                dept_id = employee.department_id.id if employee.department_id else 'no_dept'
                dept_name = employee.department_id.name if employee.department_id else 'No Department'
                
                employee_stats[emp_id] = {
                    'id': emp_id,
                    'name': employee.name,
                    'department_id': dept_id,
                    'department_name': dept_name,
                    'attendance_dates': set(),
                    'total_work_hours': 0,
                    'late_count': 0,
                    'total_late_minutes': 0,
                    'early_leaves': 0,
                    'overtime_hours': 0
                }
                
                if dept_id not in department_stats:
                    department_stats[dept_id] = {
                        'name': dept_name,
                        'employee_count': 0,
                        'present_employees': set(),
                        'total_work_hours': 0,
                        'late_count': 0,
                        'total_late_minutes': 0,
                        'early_leaves': 0,
                        'overtime_hours': 0
                    }
                department_stats[dept_id]['employee_count'] += 1

            # Standard work hours
            work_start_time = time(8, 1)  # 8:01 AM
            work_end_time = time(17, 0)   # 5 PM
            standard_work_hours = 8.0

            # Process attendance records
            for attendance in attendances:
                emp_id = attendance.employee_id.id
                dept_id = attendance.employee_id.department_id.id if attendance.employee_id.department_id else 'no_dept'
                
                # Convert times to local timezone
                check_in = pytz.utc.localize(attendance.check_in).astimezone(tz)
                check_out = attendance.check_out and pytz.utc.localize(attendance.check_out).astimezone(tz)
                
                # Skip weekends if needed
                # if check_in.date() in weekend_days:
                #     continue
                
                # Track attendance date
                employee_stats[emp_id]['attendance_dates'].add(check_in.date())
                department_stats[dept_id]['present_employees'].add(emp_id)
                
                # Calculate late arrival
                if check_in.time() > work_start_time:
                    employee_stats[emp_id]['late_count'] += 1
                    department_stats[dept_id]['late_count'] += 1
                    
                    scheduled_start = tz.localize(datetime.combine(check_in.date(), work_start_time))
                    late_minutes = (check_in - scheduled_start).total_seconds() / 60
                    
                    employee_stats[emp_id]['total_late_minutes'] += late_minutes
                    department_stats[dept_id]['total_late_minutes'] += late_minutes
                
                # Calculate work hours and overtime
                # Calculate work hours with break time
                if check_out:
                    # Calculate total duration
                    total_duration = (check_out - check_in).total_seconds() / 3600
                    
                    # Define break time (12:00-13:00)
                    break_start = tz.localize(datetime.combine(check_in.date(), time(12, 0)))
                    break_end = tz.localize(datetime.combine(check_in.date(), time(13, 0)))
                    
                    # Calculate break duration if work hours overlap with break time
                    break_duration = 0
                    if check_in < break_end and check_out > break_start:
                        overlap_start = max(check_in, break_start)
                        overlap_end = min(check_out, break_end)
                        break_duration = (overlap_end - overlap_start).total_seconds() / 3600
                        
                    worked_hours = max(0, total_duration - break_duration)
                    
                    employee_stats[emp_id]['total_work_hours'] += worked_hours
                    department_stats[dept_id]['total_work_hours'] += worked_hours
                    
                    # Check for early leave
                    if check_out.time() < work_end_time:
                        employee_stats[emp_id]['early_leaves'] += 1
                        department_stats[dept_id]['early_leaves'] += 1
                    
                    # Calculate overtime (after adjusting for break time)
                    scheduled_end = tz.localize(datetime.combine(check_out.date(), work_end_time))
                    if check_out > scheduled_end:
                        overtime_hours = (check_out - scheduled_end).total_seconds() / 3600
                        if check_out > break_end and scheduled_end < break_start:
                            overtime_hours -= 1  # Subtract break hour from overtime if applicable
                        overtime_hours = max(0, overtime_hours)
                        employee_stats[emp_id]['overtime_hours'] += overtime_hours
                        department_stats[dept_id]['overtime_hours'] += overtime_hours

            # Format employee details
            employee_details = []
            if include_details:
                for emp_id, stats in employee_stats.items():
                    attendance_days = len(stats['attendance_dates'])
                    employee_details.append({
                        'employee': {
                            'id': stats['id'],
                            'name': stats['name'],
                            'department': {
                                'id': stats['department_id'],
                                'name': stats['department_name']
                            }
                        },
                        'attendance': {
                            'working_days': working_days,
                            'present_days': attendance_days,
                            'absent_days': working_days - attendance_days,
                            'attendance_rate': round((attendance_days / working_days * 100), 1),
                            'late_count': stats['late_count'],
                            'early_leaves': stats['early_leaves']
                        },
                        'work_hours': {
                            'total': round(stats['total_work_hours'], 1),
                            'target': working_days * standard_work_hours,
                            'average_per_day': round(stats['total_work_hours'] / attendance_days, 1) if attendance_days > 0 else 0,
                            'overtime': round(stats['overtime_hours'], 1)
                        },
                        'late_summary': {
                            'total_hours': round(stats['total_late_minutes'] / 60, 1),
                            'average_minutes': round(stats['total_late_minutes'] / stats['late_count'], 0) if stats['late_count'] > 0 else 0
                        }
                    })

            # Format department summary
            department_summary = []
            for dept_id, stats in department_stats.items():
                present_count = len(stats['present_employees'])
                department_summary.append({
                    'department': {
                        'id': dept_id,
                        'name': stats['name']
                    },
                    'metrics': {
                        'employees': {
                            'total': stats['employee_count'],
                            'active': present_count,
                            'participation_rate': round((present_count / stats['employee_count'] * 100), 1)
                        },
                        'attendance': {
                            'late_count': stats['late_count'],
                            'early_leaves': stats['early_leaves']
                        },
                        'work_hours': {
                            'total': round(stats['total_work_hours'], 1),
                            'average_per_employee': round(stats['total_work_hours'] / present_count, 1) if present_count > 0 else 0,
                            'overtime': round(stats['overtime_hours'], 1)
                        },
                        'late_summary': {
                            'total_hours': round(stats['total_late_minutes'] / 60, 1),
                            'average_per_incident': round(stats['total_late_minutes'] / stats['late_count'], 0) if stats['late_count'] > 0 else 0
                        }
                    }
                })

            # Calculate overall metrics
            total_employees = len(employees)
            total_present = len(set().union(*[stats['attendance_dates'] for stats in employee_stats.values()]))
            total_work_hours = sum(stats['total_work_hours'] for stats in employee_stats.values())
            total_late_count = sum(stats['late_count'] for stats in employee_stats.values())
            total_late_minutes = sum(stats['total_late_minutes'] for stats in employee_stats.values())
            total_early_leaves = sum(stats['early_leaves'] for stats in employee_stats.values())
            total_overtime = sum(stats['overtime_hours'] for stats in employee_stats.values())

            overall_summary = {
                'period': {
                    'month': month,
                    'year': year,
                    'working_days': working_days
                },
                'employees': {
                    'total': total_employees,
                    'present': len([emp for emp in employee_stats.values() if emp['attendance_dates']]),
                    'attendance_rate': round((total_present / (total_employees * working_days) * 100), 1) if total_employees > 0 else 0
                },
                'attendance': {
                    'late_count': total_late_count,
                    'early_leaves': total_early_leaves,
                    'punctuality_rate': round(((total_present - total_late_count) / total_present * 100), 1) if total_present > 0 else 0
                },
                'work_hours': {
                    'total': round(total_work_hours, 1),
                    'target': total_employees * working_days * standard_work_hours,
                    'average_per_employee': round(total_work_hours / total_employees, 1) if total_employees > 0 else 0,
                    'overtime': round(total_overtime, 1)
                },
                'late_summary': {
                    'total_hours': round(total_late_minutes / 60, 1),
                    'average_minutes': round(total_late_minutes / total_late_count, 0) if total_late_count > 0 else 0
                }
            }

            return {
                'status': 'success',
                'data': {
                    'summary': overall_summary,
                    'departments': department_summary,
                    'employees': employee_details if include_details else []
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_monthly_attendance_summary: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/hr/attendance/export', type='http', auth='user', methods=['GET'], csrf=False)
    def export_attendance(self, **kw):
        try:
            # Extract params
            month = int(kw.get('month', datetime.now().month))
            year = int(kw.get('year', datetime.now().year))
            department_id = kw.get('department_id')
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            
            # Calculate first and last day of month
            start = datetime(year, month, 1)
            if month == 12:
                end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end = datetime(year, month + 1, 1) - timedelta(seconds=1)
                
            # Localize dates
            start = tz.localize(start)
            end = tz.localize(end)
            
            # Convert to UTC for database queries
            start_utc = start.astimezone(pytz.UTC)
            end_utc = end.astimezone(pytz.UTC)

            # Get all dates in month
            dates = []
            current = start
            while current <= end:
                dates.append(current.date())
                current += timedelta(days=1)

            # Get employees
            domain = [('active', '=', True)]
            if department_id:
                domain.append(('department_id', '=', int(department_id)))
            employees = request.env['hr.employee'].sudo().search(domain)

            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write main header
            month_name = start.strftime('%B %Y')
            writer.writerow([f'Attendance Report - {month_name}'])
            writer.writerow([])  # Empty row for spacing
            
            # Create date headers
            headers = ['Nama', 'Departemen']  # First columns
            for date in dates:
                headers.append(date.strftime('%d/%m'))  # Add date headers
            writer.writerow(headers)
            
            # Standard work time
            work_start_time = time(8, 1)  # 8:01 AM

            # Process each employee
            for employee in employees:
                department_name = employee.department_id.name if employee.department_id else 'No Department'
                
                # Get attendance records for this employee
                attendances = request.env['hr.attendance'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', start_utc),
                    ('check_in', '<=', end_utc)
                ])

                # Create attendance dict by date
                attendance_by_date = {}
                for att in attendances:
                    check_in = pytz.utc.localize(att.check_in).astimezone(tz)
                    check_out = att.check_out and pytz.utc.localize(att.check_out).astimezone(tz)
                    date = check_in.date()
                    
                    # Format the attendance string
                    check_in_str = check_in.strftime('%H:%M')
                    check_out_str = check_out.strftime('%H:%M') if check_out else '--:--'
                    
                    # Add status indicator if late
                    if check_in.time() > work_start_time:
                        check_in_str = f"{check_in_str}*"  # Add asterisk for late attendance
                    
                    attendance_by_date[date] = f"{check_in_str}-{check_out_str}"

                # Create row for employee
                row = [employee.name, department_name]
                
                # Add attendance data for each date
                for date in dates:
                    row.append(attendance_by_date.get(date, '--:----:--'))
                
                writer.writerow(row)

            # Add legend at the bottom
            writer.writerow([])  # Empty row
            writer.writerow(['Keterangan:'])
            writer.writerow(['* = Terlambat'])
            writer.writerow(['--:----:-- = Tidak Hadir'])

            # Prepare response
            output_str = output.getvalue()
            output.close()
            
            filename = f'attendance_report_{year}_{month:02d}.csv'
            
            headers = [
                ('Content-Type', 'text/csv;charset=utf-8'),
                ('Content-Disposition', f'attachment; filename={filename}'),
                ('Cache-Control', 'no-cache')
            ]

            return request.make_response(
                output_str.encode('utf-8-sig'),  # Use UTF-8 with BOM for Excel compatibility
                headers=headers
            )

        except Exception as e:
            _logger.error(f"Error in export_attendance: {str(e)}")
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')]
            )
        

    # 3. Tambahkan endpoint untuk manajemen hari kerja
    @http.route('/web/v2/hr/working-days', type='json', auth='user', methods=['POST'], csrf=False)
    def get_working_days(self, **kw):
        """Get working days configuration"""
        try:
            params = kw.get('params', kw)
            month = params.get('month')
            year = params.get('year')
            
            if not month or not year:
                return {'status': 'error', 'message': 'Month and year are required'}
            
            working_days = self._get_working_days(month, year)
            
            # Get configuration if exists
            config = request.env['hr.working.days.config'].sudo().search([
                ('month', '=', month),
                ('year', '=', year)
            ], limit=1)
            
            return {
                'status': 'success',
                'data': {
                    'working_days': working_days,
                    'is_default': not bool(config),  # Indicate if using default value
                    'name': config.name if config else None,
                    'notes': config.notes if config else None
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_working_days: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/hr/working-days/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_working_days(self, **kw):
        """Update working days configuration"""
        try:
            params = kw.get('params', kw)
            
            required_fields = ['month', 'year', 'working_days']
            for field in required_fields:
                if field not in params:
                    return {'status': 'error', 'message': f'{field} is required'}
                    
            # Validate working days
            if not (1 <= params['working_days'] <= 31):
                return {'status': 'error', 'message': 'Working days must be between 1 and 31'}
                
            config = request.env['hr.working.days.config'].sudo().search([
                ('month', '=', params['month']),
                ('year', '=', params['year'])
            ], limit=1)
            
            values = {
                'name': params.get('name', f'Config {params["month"]}/{params["year"]}'),
                'month': params['month'],
                'year': params['year'],
                'working_days': params['working_days'],
                'notes': params.get('notes')
            }
            
            if config:
                config.write(values)
            else:
                config = request.env['hr.working.days.config'].sudo().create(values)
                
            return {
                'status': 'success',
                'data': {
                    'id': config.id,
                    'name': config.name,
                    'month': config.month,
                    'year': config.year,
                    'working_days': config.working_days,
                    'notes': config.notes
                }
            }
        except Exception as e:
            _logger.error(f"Error in update_working_days: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/hr/working-days/history', type='json', auth='user', methods=['POST'], csrf=False)
    def get_working_days_history(self, **kw):
        """Get working days configuration history"""
        try:
            params = kw.get('params', kw)
            year = params.get('year', datetime.now().year)
            
            # Get all configurations for the year
            configs = request.env['hr.working.days.config'].sudo().search([
                ('year', '=', year)
            ], order='month asc')
            
            # Format response
            history = []
            for month in range(1, 13):
                config = configs.filtered(lambda c: c.month == month)
                
                history.append({
                    'month': month,
                    'month_name': datetime(year, month, 1).strftime('%B'),
                    'working_days': config.working_days if config else 26,  # Default value
                    'is_configured': bool(config),
                    'config': {
                        'id': config.id if config else None,
                        'name': config.name if config else None,
                        'notes': config.notes if config else None,
                        'created_at': config.create_date if config else None,
                        'created_by': config.create_uid.name if config and config.create_uid else None,
                        'last_modified': config.write_date if config else None,
                        'modified_by': config.write_uid.name if config and config.write_uid else None
                    } if config else None
                })
            
            return {
                'status': 'success',
                'data': {
                    'year': year,
                    'history': history,
                    'summary': {
                        'total_configured': len(configs),
                        'average_working_days': sum(h['working_days'] for h in history) / len(history)
                    }
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_working_days_history: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/attendance/webauthn/init', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def init_webauthn_registration(self, **kw):
        """Initialize WebAuthn registration process for fingerprint/biometric"""
        try:
            # DEBUG LOG
            _logger.info("Starting webauthn initialization")
            
            # Get employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}
            
            # Generate registration options
            challenge = secrets.token_urlsafe(32)  # Make sure 'secrets' module is imported
            _logger.info(f"Generated challenge: {challenge[:10]}...")
            
            # Store challenge in session for verification later
            request.session['webauthn_challenge'] = challenge
            
            # Generate unique user ID for this employee
            user_id = f"employee_{employee.id}"
            
            return {
                'status': 'success',
                'data': {
                    'options': {
                        'publicKey': {
                            'challenge': challenge,
                            'rp': {
                                'name': 'Pitcar Attendance System',
                                'id': request.httprequest.host
                            },
                            'user': {
                                'id': user_id,
                                'name': employee.name,
                                'displayName': employee.name
                            },
                            'pubKeyCredParams': [
                                {'type': 'public-key', 'alg': -7},  # ES256
                                {'type': 'public-key', 'alg': -257}  # RS256
                            ],
                            'timeout': 60000,
                            'attestation': 'direct',
                            'authenticatorSelection': {
                                'authenticatorAttachment': 'platform',  # Prefers built-in biometric
                                'userVerification': 'preferred',
                                'requireResidentKey': False
                            }
                        }
                    }
                }
            }
        except Exception as e:
            _logger.error(f"Error in init_webauthn_registration: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}



    @http.route('/web/v2/attendance/fingerprint/register', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def register_fingerprint(self, **kw):
        """Register fingerprint for employee"""
        try:
            params = kw.get('params', kw)
            
            fingerprint_data = params.get('fingerprint_data')
            webauthn_data = params.get('webauthn_data')
            device_id = params.get('device_id')
            
            if not fingerprint_data and not webauthn_data:
                return {'status': 'error', 'message': 'Either fingerprint data or WebAuthn data is required'}
                
            # Get employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}
            
            # Register fingerprint data
            if employee.register_fingerprint(
                fingerprint_data=fingerprint_data,
                webauthn_data=webauthn_data,
                device_id=device_id
            ):
                return {
                    'status': 'success',
                    'message': 'Fingerprint registered successfully',
                    'data': {
                        'employee_id': employee.id,
                        'name': employee.name,
                        'fingerprint_registered': True
                    }
                }
            else:
                return {'status': 'error', 'message': 'Failed to register fingerprint'}
                
        except Exception as e:
            _logger.error(f"Error in register_fingerprint: {str(e)}")
            return {'status': 'error', 'message': str(e)}


    @http.route('/web/v2/attendance/fingerprint/check', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def check_attendance_fingerprint(self, **kw):
        """Check attendance using fingerprint or biometric data"""
        try:
            # Extract params from request
            params = kw.get('params', kw)
            
            action_type = params.get('action_type')
            fingerprint_data = params.get('fingerprint_data')
            webauthn_data = params.get('webauthn_data')
            device_id = params.get('device_id')
            location = params.get('location', {})
            
            # Basic validation
            if not action_type:
                return {'status': 'error', 'message': 'Action type is required'}
                
            if not fingerprint_data and not webauthn_data:
                return {'status': 'error', 'message': 'Either fingerprint data or WebAuthn data is required'}
            
            # Get employee
            employee = request.env.user.employee_id
            if not employee:
                return {'status': 'error', 'message': 'Employee not found'}
                
            # Verify fingerprint
            if not employee.fingerprint_registered:
                return {'status': 'error', 'message': 'Fingerprint not registered for this employee'}
            
            is_verified = False
            
            # Verify based on authentication type
            if fingerprint_data and employee.fingerprint_data:
                # Implement fingerprint template matching logic here
                # This would require specialized fingerprint matching libraries
                # For demo, we'll assume it matches
                is_verified = True
                
            elif webauthn_data and employee.webauthn_credentials:
                # Implement WebAuthn verification logic
                # For demo, we'll assume it's verified if the device_id matches
                stored_creds = json.loads(employee.webauthn_credentials)
                is_verified = True  # Simplified for this example
                
            if not is_verified:
                return {'status': 'error', 'message': 'Fingerprint verification failed'}
            
            # Create/update attendance record
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            now_utc = now.astimezone(pytz.UTC).replace(tzinfo=None)
            
            values = {
                'employee_id': employee.id,
                'check_method': 'fingerprint'  # Add this field to hr.attendance model
            }
            
            if action_type == 'check_in':
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
            
            return {
                'status': 'success',
                'data': {
                    'attendance_id': attendance.id,
                    'employee': {
                        'id': employee.id,
                        'name': employee.name
                    },
                    'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': action_type,
                    'method': 'fingerprint',
                    'location': location
                }
            }
                
        except Exception as e:
            _logger.error(f"Error in check_attendance_fingerprint: {str(e)}")
            return {'status': 'error', 'message': str(e)}

