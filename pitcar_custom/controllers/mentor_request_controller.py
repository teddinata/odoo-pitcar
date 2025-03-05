from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta
import pytz
import json
import logging
import math
from odoo.tools import date_utils

_logger = logging.getLogger(__name__)

class MentorRequestController(http.Controller):
    @http.route('/web/mentor/request/create', type='json', auth='user', methods=['POST'])
    def create_request(self, **kw):
        """Create new mentor request (Step 1: Daftar kenapa perlu bantuan)"""
        try:
            # Validasi field yang diperlukan
            required_fields = ['sale_order_id', 'mechanic_ids', 'problem_category', 'problem_description']
            missing = [field for field in required_fields if field not in kw]
            if missing:
                return {
                    "status": "error",
                    "message": f"Missing required field(s): {', '.join(missing)}"
                }

            # Validasi mechanic IDs
            mechanic_ids = kw['mechanic_ids'] if isinstance(kw['mechanic_ids'], list) else [kw['mechanic_ids']]
            if not mechanic_ids:
                return {
                    "status": "error",
                    "message": "At least one mechanic must be specified"
                }

            # Begin a new savepoint to allow rollback on error
            with request.env.cr.savepoint():
                # Validasi keberadaan mechanic
                mechanics = request.env['pitcar.mechanic.new'].sudo().browse(mechanic_ids)
                if not mechanics.exists() or len(mechanics) != len(mechanic_ids):
                    return {
                        "status": "error",
                        "message": "One or more mechanic IDs do not exist"
                    }
                
                # Validasi keberadaan sale order
                sale_order = request.env['sale.order'].sudo().browse(kw['sale_order_id'])
                if not sale_order.exists():
                    return {
                        "status": "error",
                        "message": f"Sale Order with ID {kw['sale_order_id']} does not exist"
                    }

                # Persiapkan values untuk create
                values = {
                    'sale_order_id': kw['sale_order_id'],
                    'mechanic_ids': [(6, 0, mechanic_ids)],
                    'problem_category': kw['problem_category'],
                    'problem_description': kw['problem_description'],
                    'priority': kw.get('priority', 'normal'),
                    'state': 'draft'
                }

                # Create request
                mentor_request = request.env['pitcar.mentor.request'].sudo().create(values)

                # Setelah membuat mentor_request, periksa apakah ada followers yang duplikat
                followers = request.env['mail.followers'].sudo().search([
                    ('res_model', '=', 'pitcar.mentor.request'),
                    ('res_id', '=', mentor_request.id)
                ])

                # Log followers untuk debugging
                _logger.info(f"Followers after create: {followers.mapped('partner_id.name')}")
                    
                # Explicitly flush the changes to the database
                request.env.cr.flush()

            return {
                "status": "success",
                "data": self._get_request_details(mentor_request),
                "message": "Permintaan bantuan berhasil dibuat, silakan pilih mentor pada langkah berikutnya"
            }

        except Exception as e:
            # Log the error but ensure we don't break the transaction for other operations
            _logger.error(f"Error creating mentor request: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

    @http.route('/web/mentor/request/search', type='json', auth='user', methods=['POST'])
    def search_requests(self, **kw):
        """Search mentor requests dengan optimasi performa"""
        try:
            # Bangun domain pencarian
            domain = self._build_search_domain(kw)
            
            # Pagination parameters
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 20))
            offset = (page - 1) * limit

            # Optimasi: query count dan search dalam satu batch
            MentorRequest = request.env['pitcar.mentor.request'].sudo()
            
            # Cache results untuk mengurangi akses database
            requests = MentorRequest.search(domain, limit=limit, offset=offset)
            total_count = MentorRequest.search_count(domain)
            
            # Format results dengan batch processing
            formatted_results = []
            if requests:
                formatted_results = [self._get_request_details(req) for req in requests]

            return {
                "status": "success",
                "data": {
                    'total': total_count,
                    'page': page,
                    'pages': math.ceil(total_count / limit) if limit > 0 else 0,
                    'items': formatted_results
                }
            }

        except Exception as e:
            _logger.error(f"Error searching requests: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _build_search_domain(self, kw):
        """Helper untuk membangun domain pencarian"""
        domain = []
        
        # Filter berdasarkan state
        if kw.get('state'):
            domain.append(('state', '=', kw['state']))
        
        # Filter berdasarkan priority
        if kw.get('priority'):
            domain.append(('priority', '=', kw['priority']))
        
        # Filter berdasarkan category
        if kw.get('category'):
            domain.append(('problem_category', '=', kw['category']))
        
        # Filter berdasarkan mechanic
        if kw.get('mechanic_ids'):
            mechanic_ids = kw['mechanic_ids'] if isinstance(kw['mechanic_ids'], list) else [kw['mechanic_ids']]
            domain.append(('mechanic_ids', 'in', mechanic_ids))
        
        # Filter berdasarkan mentor
        if kw.get('mentor_id'):
            domain.append(('mentor_id', '=', kw['mentor_id']))
        
        # Filter berdasarkan sale order
        if kw.get('sale_order_id'):
            domain.append(('sale_order_id', '=', kw['sale_order_id']))

        # Filter berdasarkan date range
        if kw.get('date_from'):
            domain.append(('create_date', '>=', kw['date_from']))
        if kw.get('date_to'):
            domain.append(('create_date', '<=', kw['date_to']))
            
        return domain

    @http.route('/web/mentor/mechanics', type='json', auth='user', methods=['POST'])
    def get_mechanics(self, **kw):
        """Get all mechanics dengan optimasi performa"""
        try:
            # Build domain dengan optimasi
            domain = []
            if kw.get('search'):
                domain.append(('name', 'ilike', kw['search']))
                
            # Tambahkan filter posisi jika diperlukan
            if kw.get('position_codes'):
                position_codes = kw['position_codes'] if isinstance(kw['position_codes'], list) else [kw['position_codes']]
                domain.append(('position_code', 'in', position_codes))

            # Optimasi: hanya ambil field yang diperlukan
            mechanics = request.env['pitcar.mechanic.new'].sudo().search_read(
                domain, 
                fields=['id', 'name', 'position_code', 'position_id'],
                limit=kw.get('limit', 100)
            )
            
            return {
                "status": "success",
                "data": mechanics
            }

        except Exception as e:
            _logger.error(f"Error getting mechanics: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

    @http.route('/web/mentor/request/<int:request_id>/action', type='json', auth='user', methods=['POST'])
    def handle_request_action(self, request_id, **kw):
        """Handle request actions dengan optimasi performa"""
        try:
            if 'action' not in kw:
                return {"status": "error", "message": "Action not specified"}

            req = request.env['pitcar.mentor.request'].sudo().browse(request_id)
            if not req.exists():
                return {"status": "error", "message": "Request not found"}

            action = kw.get('action')
            if action == 'start':
                return self._handle_start_action(req, kw)
            elif action == 'solve':
                return self._handle_solve_action(req, kw)
            elif action == 'cancel':
                return self._handle_cancel_action(req)
            else:
                return {"status": "error", "message": "Invalid action specified"}
        except Exception as e:
            _logger.error(f"Error handling request action: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _handle_start_action(self, req, kw):
        _logger.info(f"Start action called with params: {kw}")
        
        mentor_id = None
        if 'mentor_id' in kw and kw['mentor_id']:
            mentor_id = kw['mentor_id']
            mentor = request.env['hr.employee'].sudo().browse(mentor_id)
            _logger.info(f"Received mentor_id: {mentor_id}, mentor name: {mentor.name if mentor.exists() else 'Not Found'}")
            if not mentor.exists():
                return {"status": "error", "message": f"Mentor with ID {mentor_id} not found"}
        
        if not mentor_id and req.mentor_id:
            mentor_id = req.mentor_id.id
        
        if not mentor_id:
            return {"status": "error", "message": "Mentor ID required"}

        try:
            # Gunakan savepoint untuk transaksi
            with request.env.cr.savepoint():
                values = {
                    'mentor_id': mentor_id  # Simpan langsung ke mentor_id (hr.employee)
                }
                if req.state == 'draft':
                    values.update({
                        'state': 'requested',
                        'request_datetime': fields.Datetime.now()
                    })
                elif req.state == 'requested':
                    values.update({
                        'state': 'in_progress',
                        'start_datetime': fields.Datetime.now()
                    })
                
                _logger.info(f"Writing values to request {req.id}: {values}")
                req.sudo().write(values)
                
                # Gunakan context untuk mencegah auto-subscription
                req = req.with_context(mail_create_nosubscribe=True, mail_auto_subscribe_no_notify=True)
                req._send_mentor_assignment_notifications(mentor_id, req)
                
                # Flush perubahan
                request.env.cr.flush()
                
                response = {
                    "status": "success",
                    "data": self._get_request_details(req),
                    "message": "Permintaan bantuan telah dimulai"
                }
                _logger.info(f"Response: {response}")
                return response
        except Exception as e:
            _logger.exception(f"Error updating request: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _create_request_notification(self, req):
        """Buat notifikasi untuk request baru"""
        try:
            # Cek apakah model notification ada
            Notification = request.env['pitcar.notification'].sudo()
            if not Notification:
                return False
                
            # Data untuk notifikasi
            mechanic_names = ", ".join(req.mechanic_ids.mapped('name')) if req.mechanic_ids else 'Unknown'
            title = f"Permintaan Bantuan Baru: {req.name}"
            message = f"Mekanik {mechanic_names} membutuhkan bantuan untuk {dict(req._fields['problem_category'].selection).get(req.problem_category)}"
            
            # Data tambahan
            data = {
                'request_id': req.id,
                'state': req.state,
                'category': req.problem_category,
                'priority': req.priority,
                'mechanic_names': mechanic_names,
                'problem_description': req.problem_description,
                'sale_order': req.sale_order_id.name if req.sale_order_id else '',
                'total_items': 1
            }
            
            # Buat notifikasi
            notification = Notification.create_or_update_notification(
                model='pitcar.mentor.request',
                res_id=req.id,
                type='new_mentor_request',
                title=title,
                message=message,
                request_time=fields.Datetime.now(),
                data=data
            )
            
            return True
        except Exception as e:
            _logger.error(f"Error creating notification: {str(e)}", exc_info=True)
            return False
        
    def _handle_solve_action(self, req, kw):
        """Handler untuk action solve"""
        if not kw.get('resolution_notes'):
            return {
                "status": "error",
                "message": "Resolution notes required"
            }
        
        try:
            # Update data penyelesaian
            values = {
                'resolution_notes': kw['resolution_notes'],
                'learning_points': kw.get('learning_points', False),
                'mechanic_rating': kw.get('mechanic_rating', False),
                'state': 'solved',
                'end_datetime': fields.Datetime.now()
            }
            
            # Hitung waktu penyelesaian jika ada start_datetime
            if req.start_datetime:
                end_time = fields.Datetime.now()
                start_time = req.start_datetime
                # Hitung durasi dalam menit
                duration_minutes = (end_time - start_time).total_seconds() / 60
                values['resolution_time'] = duration_minutes
            
            # Gunakan dengan transaction handling yang tepat
            req.sudo().write(values)
            
            return {
                "status": "success",
                "data": self._get_request_details(req),
                "message": "Permintaan telah diselesaikan"
            }
        except Exception as e:
            _logger.error(f"Error solving request: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
        
    def _handle_cancel_action(self, req):
        """Handler untuk action cancel"""
        try:
            # Implementasi langsung untuk pembatalan permintaan
            values = {
                'state': 'cancelled',
                'end_datetime': fields.Datetime.now()
            }
            
            # Update record
            req.sudo().write(values)
            
            return {
                "status": "success",
                "data": self._get_request_details(req),
                "message": "Permintaan telah dibatalkan"
            }
        except Exception as e:
            _logger.error(f"Error cancelling request: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

    @http.route('/web/mentor/dashboard', type='json', auth='user', methods=['POST'])
    def get_dashboard_data(self, **kw):
        """Get dashboard statistics dengan optimasi performa"""
        try:
            return self.get_dashboard_stats(**kw)
        except Exception as e:
            _logger.error(f"Error getting dashboard data: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

    def _get_request_details(self, req):
        """Format request details dengan optimasi dan UTC+7 timestamp"""
        if not req:
            return {}
            
        # Format fields dengan metode yang lebih efisien
        try:
            # Timezone Jakarta (UTC+7)
            jakarta_tz = pytz.timezone('Asia/Jakarta')
            
            # Format timestamps with Jakarta timezone
            request_time = self._format_to_jakarta_time(req.request_datetime) if req.request_datetime else None
            start_time = self._format_to_jakarta_time(req.start_datetime) if req.start_datetime else None
            end_time = self._format_to_jakarta_time(req.end_datetime) if req.end_datetime else None
            
            return {
                'id': req.id,
                'name': req.name,
                'state': req.state,
                'priority': req.priority,
                'category': req.problem_category,
                'description': req.problem_description,
                'mechanics': [{'id': m.id, 'name': m.name} for m in req.mechanic_ids],
                'mentor': {
                    'id': req.mentor_id.id,
                    'name': req.mentor_id.name
                } if req.mentor_id else {},
                'sale_order': {
                    'id': req.sale_order_id.id,
                    'name': req.sale_order_id.name
                } if req.sale_order_id else {},
                'timestamps': {
                    'request': request_time,
                    'start': start_time,
                    'end': end_time
                },
                'resolution': {
                    'notes': req.resolution_notes or "",
                    'learning_points': req.learning_points or "",
                    'mechanic_rating': req.mechanic_rating or ""
                },
                'resolution_time': req.resolution_time if hasattr(req, 'resolution_time') else None
            }
        except Exception as e:
            _logger.error(f"Error formatting request details: {str(e)}", exc_info=True)
            # Return minimal data if error occurs
            return {
                'id': req.id,
                'name': req.name,
                'state': req.state
            }
        
    def _format_to_jakarta_time(self, dt):
        """Convert UTC datetime to Jakarta timezone (UTC+7) and format to string"""
        if not dt:
            return None
        
        # Ensure the datetime has timezone info
        if not dt.tzinfo:
            dt = pytz.UTC.localize(dt)
        
        # Convert to Jakarta timezone
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        jakarta_dt = dt.astimezone(jakarta_tz)
        
        # Format to ISO string
        return jakarta_dt.isoformat()
    
    @http.route('/web/mentor/request/notify', type='json', auth='user', methods=['POST'])
    def notify_mentors(self, **kw):
        """Send notification to specified mentors menggunakan metode yang dioptimalkan"""
        try:
            # Validasi field yang diperlukan
            required_fields = ['request_id', 'mentor_ids']
            missing = [field for field in required_fields if field not in kw]
            if missing:
                return {
                    "status": "error",
                    "message": f"Missing required field(s): {', '.join(missing)}"
                }
            
            # Validasi keberadaan request
            mentor_request = request.env['pitcar.mentor.request'].sudo().browse(kw['request_id'])
            if not mentor_request.exists():
                return {
                    "status": "error",
                    "message": f"Request with ID {kw['request_id']} does not exist"
                }
            
            # Validasi keberadaan mentor
            mentor_ids = kw['mentor_ids'] if isinstance(kw['mentor_ids'], list) else [kw['mentor_ids']]
            mentors = request.env['pitcar.mechanic.new'].sudo().browse(mentor_ids)
            valid_mentors = mentors.filtered(lambda m: m.exists() and m.user_id and m.user_id.partner_id)
            
            if not valid_mentors:
                return {
                    "status": "error",
                    "message": "No valid mentors found to notify"
                }
            
            # Menggunakan metode _send_notifications yang dioptimalkan
            notification_type = 'new_mentor_request'
            title_template = "Permintaan Bantuan Baru: {name}"
            message_template = "Mekanik {mechanic_names} membutuhkan bantuan untuk {category}"
            
            # Gunakan metode yang dioptimalkan melalui model
            success = mentor_request._send_notifications(
                notification_type,
                title_template,
                message_template,
                valid_mentors
            )
            
            if success:
                return {
                    "status": "success",
                    "message": f"Notification sent to {len(valid_mentors)} mentors",
                    "data": {
                        "mentors_notified": valid_mentors.mapped('name')
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to send notifications"
                }
                
        except Exception as e:
            _logger.error(f"Error sending notifications: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
        
    @http.route('/web/mentor/observer', type='json', auth='user')
    def observe_mentor_requests(self, last_checked=None):
        """Observer untuk notifikasi mentor request dengan optimasi performa"""
        try:
            _logger.info(f"Mentor Observer called with last_checked: {last_checked}")
            
            # Tentukan domain untuk mencari notifikasi
            Notification = request.env['pitcar.notification']
            domain = [
                ('model', '=', 'pitcar.mentor.request'),
                ('request_time', '>=', datetime.now() - timedelta(days=30)),
                ('res_id', '!=', 0),
                ('name', '!=', 'Unknown')
            ]
            
            # Filter berdasarkan last_checked jika ada
            if last_checked:
                try:
                    check_time = fields.Datetime.from_string(last_checked)
                    domain.append(('request_time', '>', check_time))
                except Exception as e:
                    _logger.warning(f"Could not parse last_checked: {e}")
            
            # Get current user info
            user_id = request.env.user.id
            
            # Cari apakah user saat ini adalah mekanik dan dapatkan role-nya
            mechanic = request.env['pitcar.mechanic.new'].sudo().search([('user_id', '=', user_id)], limit=1)
            
            if mechanic:
                domain = self._apply_mechanic_role_filters(domain, mechanic)
                
                # Jika empty domain dikembalikan, berarti tidak ada notifikasi yang relevan
                if domain is None:
                    return self._build_empty_notification_response()
            
            # Optimasi: Cari notifikasi dengan prefetch
            notifications = Notification.with_context(prefetch_fields=True).search(
                domain, order='request_time desc', limit=10
            )
            
            # Jika tidak ada notifikasi, kembalikan response kosong
            if not notifications:
                return self._build_empty_notification_response()
                
            _logger.info(f"Found {len(notifications)} mentor notifications")
            
            # Batch process notifications dengan optimasi
            result = self._process_notifications(notifications)
            
            # Format current time untuk response
            jakarta_time = self._get_jakarta_time(datetime.now())
            
            # Build final response
            response_data = {
                'status': 'success',
                'data': {
                    'timestamp': jakarta_time.isoformat(),
                    'notifications': result
                }
            }
            
            return response_data
            
        except Exception as e:
            _logger.error(f"Error in observe_mentor_requests: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _apply_mechanic_role_filters(self, domain, mechanic):
        """Terapkan filter domain berdasarkan role mekanik"""
        # Tentukan apakah mekanik ini memiliki posisi senior (leader/foreman)
        is_senior = mechanic.position_code in ['leader', 'foreman']
        
        # Untuk mekanik senior, tampilkan semua notifikasi (tidak perlu filter tambahan)
        if is_senior:
            return domain
            
        # Untuk mekanik biasa, hanya tampilkan notifikasi yang relevan dengan mereka
        mentor_requests = request.env['pitcar.mentor.request'].sudo().search([
            ('mechanic_ids', 'in', [mechanic.id])
        ])
        
        if not mentor_requests:
            # Jika tidak ada permintaan yang terkait, kembalikan None (akan menghasilkan response kosong)
            return None
            
        # Tambahkan filter untuk hanya menampilkan notifikasi terkait request ini
        domain.append(('res_id', 'in', mentor_requests.ids))
        return domain
    
    def _build_empty_notification_response(self):
        """Buat response untuk notifikasi kosong"""
        jakarta_time = self._get_jakarta_time(datetime.now())
        return {
            'status': 'success',
            'data': {
                'timestamp': jakarta_time.isoformat(),
                'notifications': []
            }
        }
    
    def _process_notifications(self, notifications):
        """Process notifications dengan optimasi batch"""
        result = []
        
        # Cache res_ids untuk batch read
        res_ids = notifications.mapped('res_id')
        models = list(set(notifications.mapped('model')))
        
        # Batch read semua related records
        related_records = {}
        for model in models:
            model_res_ids = notifications.filtered(lambda n: n.model == model).mapped('res_id')
            if model_res_ids:
                related_records[model] = request.env[model].sudo().browse(model_res_ids)
        
        # Process notifications
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        
        for notif in notifications:
            # Konversi UTC ke Jakarta time
            utc_time = notif.request_time
            jakarta_dt = pytz.UTC.localize(utc_time).astimezone(jakarta_tz)
            
            # Parse data JSON jika ada
            data = json.loads(notif.data) if notif.data else {}
            
            # Get related record from cache
            record = None
            if notif.model in related_records and notif.res_id:
                records = related_records[notif.model]
                record = records.filtered(lambda r: r.id == notif.res_id)
                record = record[0] if record else None
            
            # Prepare request details
            request_details = {}
            if record and notif.model == 'pitcar.mentor.request':
                mechanic_names = ", ".join(record.mechanic_ids.mapped('name'))
                request_details = {
                    'id': record.id,
                    'name': record.name,
                    'mechanics': mechanic_names,
                    'category': record.problem_category,
                    'priority': record.priority,
                    'state': record.state,
                    'sale_order': record.sale_order_id.name if record.sale_order_id else '',
                }
            
            # Format notifikasi untuk response
            request_data = {
                'id': notif.id,
                'res_id': notif.res_id,
                'model': notif.model,
                'name': notif.name,
                'request_time': jakarta_dt.isoformat(),
                'title': notif.title,
                'message': notif.message,
                'is_read': notif.is_read,
                'type': notif.type,
                'request_details': request_details,
                'data': data
            }
            result.append(request_data)
            
        return result
    
    def _get_jakarta_time(self, dt):
        """Konversi datetime ke timezone Jakarta"""
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        utc_dt = pytz.UTC.localize(dt) if dt.tzinfo is None else dt
        return utc_dt.astimezone(jakarta_tz)
    
    @http.route('/web/mentor/notification/mark-read', type='json', auth='user')
    def mark_notification_read(self, notification_ids=None, res_ids=None, model='pitcar.mentor.request'):
        """Mark notifications as read dengan optimasi batch"""
        try:
            if not notification_ids and not res_ids:
                return {'status': 'error', 'message': 'notification_ids or res_ids must be provided'}
            
            # Build domain untuk mencari notifikasi
            domain = [('model', '=', model)]
            
            if notification_ids:
                notification_ids = notification_ids if isinstance(notification_ids, list) else [notification_ids]
                domain.append(('id', 'in', notification_ids))
            
            if res_ids:
                res_ids = res_ids if isinstance(res_ids, list) else [res_ids]
                domain.append(('res_id', 'in', res_ids))
            
            # Batch update semua notifikasi dalam satu operasi
            Notification = request.env['pitcar.notification'].sudo()
            notifications = Notification.search(domain)
            
            if notifications:
                # Optimasi: gunakan write dengan force_write untuk menghindari triggers yang tidak perlu
                notifications.with_context(tracking_disable=True).write({'is_read': True})
                count = len(notifications)
                
                # Hapus caching yang tidak perlu
                request.env.invalidate_all()
                
                return {
                    'status': 'success',
                    'data': {'updated': count}
                }
            else:
                return {
                    'status': 'warning',
                    'message': 'No notifications found matching the criteria',
                    'data': {'updated': 0}
                }
            
        except Exception as e:
            _logger.error(f"Error in mark_notification_read: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/web/mentor/notification/count', type='json', auth='user')
    def get_unread_notification_count(self):
        """Get count of unread notifications dengan optimasi performa"""
        try:
            # Get current user info
            user_id = request.env.user.id
            
            # Cari apakah user saat ini adalah mekanik
            mechanic = request.env['pitcar.mechanic.new'].sudo().search([('user_id', '=', user_id)], limit=1)
            
            # Define domain for notifications
            domain = [
                ('model', '=', 'pitcar.mentor.request'),
                ('is_read', '=', False),
                ('request_time', '>=', datetime.now() - timedelta(days=30))
            ]
            
            # Modify domain based on mechanic role
            if mechanic:
                domain = self._apply_mechanic_role_filters(domain, mechanic)
                if domain is None:
                    return {
                        'status': 'success',
                        'data': {'count': 0}
                    }
            
            # Optimasi: hanya hitung total tanpa membaca records
            count = request.env['pitcar.notification'].sudo().search_count(domain)
            
            return {
                'status': 'success',
                'data': {'count': count}
            }
            
        except Exception as e:
            _logger.error(f"Error getting unread notification count: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/web/mentor/dashboard/stats', type='json', auth='user')
    def get_dashboard_stats(self, **kw):
        """Get dashboard statistics for mentor requests"""
        try:
            date_from = kw.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            date_to = kw.get('date_to', datetime.now().strftime('%Y-%m-%d'))
            
            domain = [
                ('create_date', '>=', date_from),
                ('create_date', '<=', date_to)
            ]
            
            MentorRequest = request.env['pitcar.mentor.request'].sudo()
            
            # Get overall stats
            total_requests = MentorRequest.search_count(domain)
            solved_requests = MentorRequest.search_count(domain + [('state', '=', 'solved')])
            cancelled_requests = MentorRequest.search_count(domain + [('state', '=', 'cancelled')])
            pending_requests = MentorRequest.search_count(domain + [('state', 'in', ['draft', 'requested'])])
            inprogress_requests = MentorRequest.search_count(domain + [('state', '=', 'in_progress')])
            
            # Calculate average resolution time
            solved_query = MentorRequest.search(domain + [
                ('state', '=', 'solved'),
                ('start_datetime', '!=', False),
                ('end_datetime', '!=', False)
            ])
            
            total_duration = 0
            for req in solved_query:
                if req.start_datetime and req.end_datetime:
                    duration = (req.end_datetime - req.start_datetime).total_seconds() / 3600  # in hours
                    total_duration += duration
            
            avg_resolution_time = total_duration / len(solved_query) if solved_query else 0
            
            # Dapatkan top categories dengan cara manual
            categories_count = {}
            all_requests = MentorRequest.search(domain)
            for req in all_requests:
                category = req.problem_category
                if category in categories_count:
                    categories_count[category] += 1
                else:
                    categories_count[category] = 1
            
            # Konversi hitungan kategori ke format yang diharapkan
            categories = []
            category_mapping = dict(MentorRequest._fields['problem_category'].selection)
            for category, count in categories_count.items():
                categories.append({
                    'name': category_mapping.get(category, category),
                    'count': count
                })
            # Urutkan berdasarkan count (descending)
            categories = sorted(categories, key=lambda x: x['count'], reverse=True)
            
            # Get top mentors dengan cara yang sama
            mentors_count = {}
            solved_reqs = MentorRequest.search(domain + [('state', '=', 'solved')])
            for req in solved_reqs:
                if req.mentor_id:
                    mentor_id = req.mentor_id.id
                    mentor_name = req.mentor_id.name
                    if mentor_id in mentors_count:
                        mentors_count[mentor_id]['solved_count'] += 1
                    else:
                        mentors_count[mentor_id] = {
                            'id': mentor_id,
                            'name': mentor_name,
                            'solved_count': 1
                        }
            
            # Konversi ke list dan urutkan
            top_mentors = list(mentors_count.values())
            top_mentors = sorted(top_mentors, key=lambda x: x.get('solved_count', 0), reverse=True)[:5]
            
            # Get top mechanics requesting help
            mechanics_count = {}
            requests = MentorRequest.search(domain)
            for req in requests:
                for mechanic in req.mechanic_ids:
                    if mechanic.id in mechanics_count:
                        mechanics_count[mechanic.id]['count'] += 1
                    else:
                        mechanics_count[mechanic.id] = {
                            'id': mechanic.id,
                            'name': mechanic.name,
                            'count': 1
                        }
            
            top_mechanics = sorted(list(mechanics_count.values()), key=lambda x: x['count'], reverse=True)[:5]
            
            # Get trend data (jika diminta)
            trend = []
            if kw.get('show_trend', True):
                date_start = datetime.strptime(date_from, '%Y-%m-%d')
                date_end = datetime.strptime(date_to, '%Y-%m-%d')
                delta = (date_end - date_start).days
                
                # Tentukan interval berdasarkan rentang waktu
                interval = 'day'
                if delta > 60:
                    interval = 'week'
                elif delta > 365:
                    interval = 'month'
                
                # Buat bin untuk setiap interval
                current = date_start
                while current <= date_end:
                    next_date = None
                    date_label = None
                    
                    if interval == 'day':
                        next_date = current + timedelta(days=1)
                        date_label = current.strftime('%d %b')
                    elif interval == 'week':
                        next_date = current + timedelta(days=7)
                        date_label = f"{current.strftime('%d %b')} - {(current + timedelta(days=6)).strftime('%d %b')}"
                    elif interval == 'month':
                        if current.month == 12:
                            next_date = datetime(current.year + 1, 1, 1)
                        else:
                            next_date = datetime(current.year, current.month + 1, 1)
                        date_label = current.strftime('%b %Y')
                    
                    # Hitung jumlah request untuk interval ini
                    interval_domain = [
                        ('create_date', '>=', current.strftime('%Y-%m-%d')),
                        ('create_date', '<', next_date.strftime('%Y-%m-%d'))
                    ]
                    interval_count = MentorRequest.search_count(interval_domain)
                    
                    trend.append({
                        'date': date_label,
                        'count': interval_count
                    })
                    
                    current = next_date
            
            # Compile hasil
            result = {
                'overview': {
                    'total_requests': total_requests,
                    'solved_requests': solved_requests,
                    'pending_requests': pending_requests,
                    'inprogress_requests': inprogress_requests,
                    'cancelled_requests': cancelled_requests,
                    'success_rate': round((solved_requests / total_requests * 100), 2) if total_requests > 0 else 0,
                    'avg_resolution_time': round(avg_resolution_time, 2)  # in hours
                },
                'top_categories': categories,
                'top_mentors': top_mentors,
                'top_mechanics': top_mechanics,
                'trend': trend
            }
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"Error getting dashboard stats: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _calculate_avg_resolution_time(self, MentorRequest, base_domain):
        """Calculate average resolution time dengan optimasi"""
        # Query untuk solved requests dengan one batch
        solved_reqs = MentorRequest.search(
            base_domain + [
                ('state', '=', 'solved'),
                ('start_datetime', '!=', False),
                ('end_datetime', '!=', False)
            ]
        )
        
        # Calculate average time
        if not solved_reqs:
            return 0
            
        # Optimasi: gunakan sum() daripada loop untuk total_duration
        total_duration = sum([(req.end_datetime - req.start_datetime).total_seconds() / 3600 for req in solved_reqs])
        return total_duration / len(solved_reqs) if solved_reqs else 0
    
    def _get_top_categories(self, MentorRequest, base_domain):
        """Get top categories dengan optimasi batch"""
        # Gunakan read_group untuk efisiensi
        category_data = MentorRequest.read_group(
            base_domain, 
            fields=['problem_category'], 
            groupby=['problem_category'], 
            orderby='problem_category_count DESC'
        )
        
        # Cache mapping untuk selection field
        category_mapping = dict(MentorRequest._fields['problem_category'].selection)
        
        # Format results
        categories = []
        for category in category_data:
            category_key = category.get('problem_category')
            if category_key:
                category_name = category_mapping.get(category_key, category_key)
                categories.append({
                    'name': category_name,
                    'count': category['problem_category_count']
                })
        
        return categories
    
    def _get_top_mentors(self, MentorRequest, base_domain):
        """Get top mentors dengan optimasi batch"""
        # Gunakan read_group untuk efisiensi
        mentor_data = MentorRequest.read_group(
            base_domain + [('state', '=', 'solved')], 
            fields=['mentor_id'], 
            groupby=['mentor_id'], 
            orderby='mentor_id_count DESC',
            limit=5
        )
        
        # Format results
        top_mentors = []
        for mentor in mentor_data:
            mentor_info = mentor.get('mentor_id')
            if mentor_info and isinstance(mentor_info, tuple) and len(mentor_info) >= 2:
                mentor_id, mentor_name = mentor_info[0], mentor_info[1]
                top_mentors.append({
                    'id': mentor_id,
                    'name': mentor_name,
                    'solved_count': mentor['mentor_id_count']
                })
        
        return top_mentors
    
    def _get_top_mechanics(self, MentorRequest, base_domain):
        """Get top mechanics dengan pendekatan yang dioptimalkan"""
        # Get all requests with mechanics in one go to reduce database calls
        requests = MentorRequest.search(base_domain)
        
        # Use dictionary for counting to optimize performance
        mechanics_count = {}
        
        # Preload mechanic_ids relation to avoid multiple lazy loading
        requests.mapped('mechanic_ids')
        
        # Count mechanics with optimized approach
        for req in requests:
            for mechanic in req.mechanic_ids:
                if mechanic.id in mechanics_count:
                    mechanics_count[mechanic.id]['count'] += 1
                else:
                    mechanics_count[mechanic.id] = {
                        'id': mechanic.id,
                        'name': mechanic.name,
                        'count': 1
                    }
        
        # Sort and get top 5
        top_mechanics = sorted(mechanics_count.values(), key=lambda x: x['count'], reverse=True)[:5]
        return top_mechanics
    
    def _get_trend_data(self, MentorRequest, date_from, date_to):
        """Get trend data dengan optimasi interval"""
        try:
            date_start = datetime.strptime(date_from, '%Y-%m-%d')
            date_end = datetime.strptime(date_to, '%Y-%m-%d')
            delta = (date_end - date_start).days
            
            # Pilih interval yang sesuai berdasarkan range
            interval = 'day'
            if delta > 60:
                interval = 'week'
            elif delta > 365:
                interval = 'month'
            
            trend = []
            # Buat bin untuk setiap interval
            current = date_start
            
            # Pre-compute bin edges untuk kurangi overhead dalam loop
            bin_edges = []
            while current <= date_end:
                next_date = None
                date_label = None
                
                if interval == 'day':
                    next_date = current + timedelta(days=1)
                    date_label = current.strftime('%d %b')
                elif interval == 'week':
                    next_date = current + timedelta(days=7)
                    date_label = f"{current.strftime('%d %b')} - {(current + timedelta(days=6)).strftime('%d %b')}"
                elif interval == 'month':
                    if current.month == 12:
                        next_date = datetime(current.year + 1, 1, 1)
                    else:
                        next_date = datetime(current.year, current.month + 1, 1)
                    date_label = current.strftime('%b %Y')
                
                bin_edges.append((current, next_date, date_label))
                current = next_date
            
            # Gunakan search_read untuk efisiensi
            all_requests = MentorRequest.search_read(
                [
                    ('create_date', '>=', date_start.strftime('%Y-%m-%d')),
                    ('create_date', '<=', date_end.strftime('%Y-%m-%d'))
                ],
                ['create_date']
            )
            
            # Group requests by bin in memory (faster than multiple DB queries)
            bins = {i: 0 for i in range(len(bin_edges))}
            for req in all_requests:
                create_date = fields.Datetime.from_string(req['create_date'])
                for i, (start, end, _) in enumerate(bin_edges):
                    if start <= create_date < end:
                        bins[i] += 1
                        break
            
            # Format trend data
            for i, (_, _, label) in enumerate(bin_edges):
                trend.append({
                    'date': label,
                    'count': bins[i]
                })
            
            return trend
        except Exception as e:
            _logger.error(f"Error generating trend data: {str(e)}", exc_info=True)
            return []