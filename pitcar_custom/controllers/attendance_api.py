# controllers/attendance_api.py
from odoo import http
from odoo.http import request
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import logging
import json
import math

_logger = logging.getLogger(__name__)

class AttendanceAPI(http.Controller):
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
            # Use set to count unique dates in Jakarta timezone
            present_days = len(set(att.check_in.astimezone(jakarta_tz).date() for att in month_attendances))
            total_working_days = 26  # Standard working days per month
            
            # Standard work start time in Jakarta (8 AM)
            work_start_time = time(8, 0)
            
            # Count late attendances (check-in after 8 AM Jakarta time)
            late_attendances = []
            total_late_minutes = 0
            
            for att in month_attendances:
                check_in_jkt = att.check_in.astimezone(jakarta_tz)
                if check_in_jkt.time() > work_start_time:
                    late_attendances.append(att)
                    # Calculate late duration
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
                    working_hours = (check_out_jkt - check_in_jkt).total_seconds() / 3600

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

            # Calculate total and average working hours
            total_hours = sum(
                (att.check_out - att.check_in).total_seconds() / 3600 
                for att in month_attendances if att.check_out
            )
            avg_hours = round(total_hours / present_days, 2) if present_days > 0 else 0

            return {
                'status': 'success',
                'data': {
                    'is_checked_in': bool(current_attendance),
                    'has_face_registered': bool(employee.face_descriptor),
                    'face_verification': face_verification,
                    'today_attendance': format_attendance(today_attendance) if today_attendance else None,
                    'last_attendances': [format_attendance(att) for att in last_attendances if att],
                    'monthly_summary': {
                        'month': now.strftime('%B'),
                        'year': now.year,
                        'total_working_days': total_working_days,
                        'attendance_summary': {
                            'present': present_days,
                            'absent': total_working_days - present_days,
                            'leave': 0  # Optional: bisa ditambahkan jika ada sistem cuti
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
        work_start_time = time(8, 0)
        
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
            
            work_start_time = time(8, 0)  # 8 AM
            
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
                    working_hours = round((check_out_local - check_in_local).total_seconds() / 3600, 2)
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
            work_start_time = time(8, 0)

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
                    working_hours = round((check_out_local - check_in_local).total_seconds() / 3600, 2)
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