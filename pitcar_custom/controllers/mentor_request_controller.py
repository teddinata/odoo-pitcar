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

            # Create request dengan transaction handling yang tepat
            mentor_request = request.env['pitcar.mentor.request'].sudo().create(values)

            return {
                "status": "success",
                "data": self._get_request_details(mentor_request),
                "message": "Permintaan bantuan berhasil dibuat, silakan pilih mentor pada langkah berikutnya"
            }

        except Exception as e:
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
                return {
                    "status": "error",
                    "message": "Action not specified"
                }

            # Cek keberadaan request sekali saja
            req = request.env['pitcar.mentor.request'].sudo().browse(request_id)
            if not req.exists():
                return {
                    "status": "error",
                    "message": "Request not found"
                }

            # Handle berbagai tipe action
            action = kw.get('action')
            if action == 'start':
                return self._handle_start_action(req, kw)
            elif action == 'solve':
                return self._handle_solve_action(req, kw)
            elif action == 'cancel':
                return self._handle_cancel_action(req)
            else:
                return {
                    "status": "error",
                    "message": "Invalid action specified"
                }

        except Exception as e:
            _logger.error(f"Error handling request action: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _handle_start_action(self, req, kw):
        """Handler untuk action start"""
        if not kw.get('mentor_id'):
            return {
                "status": "error", 
                "message": "Mentor ID required"
            }
        
        mentor = request.env['pitcar.mechanic.new'].sudo().browse(kw['mentor_id'])
        if not mentor.exists():
            return {
                "status": "error",
                "message": f"Mechanic with ID {kw['mentor_id']} does not exist"
            }
        
        # Gunakan dengan transaction handling yang tepat
        req.sudo().write({'mentor_id': kw['mentor_id']})
        req.sudo().action_start_mentoring()

        return {
            "status": "success",
            "data": self._get_request_details(req),
            "message": "Permintaan bantuan telah dimulai oleh mentor"
        }
        
    def _handle_solve_action(self, req, kw):
        """Handler untuk action solve"""
        if not kw.get('resolution_notes'):
            return {
                "status": "error",
                "message": "Resolution notes required"
            }
        
        values = {
            'resolution_notes': kw['resolution_notes'],
            'learning_points': kw.get('learning_points', False),
            'mechanic_rating': kw.get('mechanic_rating', False)
        }
        
        # Gunakan dengan transaction handling yang tepat
        req.sudo().write(values)
        req.sudo().action_mark_solved()

        return {
            "status": "success",
            "data": self._get_request_details(req),
            "message": "Permintaan telah diselesaikan"
        }
        
    def _handle_cancel_action(self, req):
        """Handler untuk action cancel"""
        req.sudo().action_cancel_request()
        
        return {
            "status": "success",
            "data": self._get_request_details(req),
            "message": "Permintaan telah dibatalkan"
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
        """Format request details dengan optimasi"""
        if not req:
            return {}
            
        # Format fields dengan metode yang lebih efisien
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
                'request': date_utils.json_default(req.request_datetime) if req.request_datetime else None,
                'start': date_utils.json_default(req.start_datetime) if req.start_datetime else None,
                'end': date_utils.json_default(req.end_datetime) if req.end_datetime else None
            },
            'resolution': {
                'notes': req.resolution_notes or "",
                'learning_points': req.learning_points or "",
                'mechanic_rating': req.mechanic_rating or ""
            }
        }
    
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
        """Get dashboard statistics dengan optimasi batch dan caching"""
        try:
            # Get date range dengan default values
            date_from = kw.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            date_to = kw.get('date_to', datetime.now().strftime('%Y-%m-%d'))
            
            # Base domain untuk semua queries
            base_domain = [
                ('create_date', '>=', date_from),
                ('create_date', '<=', date_to)
            ]
            
            # Gunakan ORM cache dengan menggunakan env.cache.get
            MentorRequest = request.env['pitcar.mentor.request'].sudo()
            
            # Batch process semua state counts
            state_counts = {}
            states = ['requested', 'in_progress', 'solved', 'cancelled', 'draft']
            for state in states:
                count = MentorRequest.search_count(base_domain + [('state', '=', state)])
                state_counts[state] = count
            
            # Compute derived stats
            total_requests = sum(state_counts.values())
            solved_requests = state_counts.get('solved', 0)
            pending_requests = state_counts.get('draft', 0) + state_counts.get('requested', 0)
            inprogress_requests = state_counts.get('in_progress', 0)
            cancelled_requests = state_counts.get('cancelled', 0)
            
            # Calculate resolution time hanya untuk solved requests
            avg_resolution_time = self._calculate_avg_resolution_time(MentorRequest, base_domain)
            
            # Process top categories dengan batch
            categories = self._get_top_categories(MentorRequest, base_domain)
            
            # Process top mentors dan mechanics
            top_mentors = self._get_top_mentors(MentorRequest, base_domain)
            top_mechanics = self._get_top_mechanics(MentorRequest, base_domain)
            
            # Get trend data if needed
            trend = []
            if kw.get('show_trend', True):
                trend = self._get_trend_data(MentorRequest, date_from, date_to)
            
            # Compile hasil
            result = {
                'overview': {
                    'total_requests': total_requests,
                    'solved_requests': solved_requests,
                    'pending_requests': pending_requests,
                    'inprogress_requests': inprogress_requests,
                    'cancelled_requests': cancelled_requests,
                    'success_rate': round((solved_requests / total_requests * 100), 2) if total_requests else 0,
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