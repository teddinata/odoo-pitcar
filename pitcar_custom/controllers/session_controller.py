from odoo import http, fields
from odoo.http import request
import logging
import json
from datetime import datetime, date
import pytz

_logger = logging.getLogger(__name__)

class SessionController(http.Controller):
    def format_to_jakarta_time(self, dt):
        """Convert UTC datetime to Jakarta timezone (UTC+7) and format to string"""
        if not dt:
            return None
        
        # Convert date to datetime if needed
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime.min.time())
        
        # Ensure the datetime has timezone info
        if not dt.tzinfo:
            dt = pytz.UTC.localize(dt)
        
        # Convert to Jakarta timezone
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        jakarta_dt = dt.astimezone(jakarta_tz)
        
        # Format to string: YYYY-MM-DD HH:MM:SS
        return jakarta_dt.strftime("%Y-%m-%d %H:%M:%S")
        
    @http.route('/web/session/get_session_info', type='json', auth='user', methods=['POST'])
    def get_session_info(self, **kw):
        """
        Endpoint untuk mendapatkan informasi sesi pengguna beserta informasi notifikasi dan detail lainnya.
        """
        try:
            user = request.env.user
            company = user.company_id
            
            # Get current time in Jakarta timezone
            jakarta_tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(jakarta_tz)

            # Get unread notifications
            unread_notifications = request.env['pitcar.notification'].sudo().search([
                ('is_read', '=', False),
                ('recipient_id', '=', user.id),
            ])
            unread_notifications_count = len(unread_notifications)

            # Get user roles and permissions
            mechanic = request.env['pitcar.mechanic.new'].sudo().search([('user_id', '=', user.id)], limit=1)
            is_mechanic = bool(mechanic)
            is_mentor = mechanic.is_mentor if mechanic else False
            position_code = mechanic.position_code if mechanic else False
            is_admin = user.has_group('base.group_system')

            # Get all user groups
            group_ids = user.groups_id.mapped('id')
            groups = [
                {'id': group.id, 'name': group.name, 'category': group.category_id.name or 'No Category'}
                for group in user.groups_id
            ]

            # Get employee information
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            employee_data = {
                'id': employee.id if employee else False,
                'name': employee.name if employee else False,
                'job_title': employee.job_title if employee else False,
                'department': employee.department_id.name if employee and employee.department_id else False,
            }

            session_info = {
                'status': 'success',
                'data': {
                    'user': {
                        'id': user.id,
                        'name': user.name,
                        'login': user.login,
                        'email': user.email,
                        'partner_id': user.partner_id.id if user.partner_id else False,
                        'image_url': f'/web/image?model=res.users&id={user.id}&field=image_128',
                        'phone': user.phone or False,
                        'mobile': user.mobile or False,
                        'lang': user.lang or 'en_US',
                        'tz': user.tz or 'Asia/Jakarta',
                        'last_login': self.format_to_jakarta_time(user.login_date),
                    },
                    'company': {
                        'id': company.id,
                        'name': company.name,
                        'currency_id': company.currency_id.id,
                        'currency_symbol': company.currency_id.symbol,
                        'street': company.street or False,
                        'city': company.city or False,
                        'country': company.country_id.name or False,
                        'phone': company.phone or False,
                        'email': company.email or False,
                    },
                    'roles': {
                        'is_admin': is_admin,
                        'is_mechanic': is_mechanic,
                        'is_mentor': is_mentor,
                        'position_code': position_code,
                        'groups': groups,
                    },
                    'employee': employee_data,
                    'notifications': {
                        'unread_count': unread_notifications_count,
                        'unread_notifications': [
                            {
                                'id': notif.id,
                                'title': notif.title,
                                'message': notif.message,
                                'create_date': self.format_to_jakarta_time(notif.create_date),
                            } for notif in unread_notifications[:5]
                        ],
                        'last_checked': self.format_to_jakarta_time(now),
                    },
                    'preferences': {
                        'lang': user.lang or 'en_US',
                        'tz': user.tz or 'Asia/Jakarta',
                        'notification_type': user.notification_type or 'email',
                    },
                    'timestamp': self.format_to_jakarta_time(now),
                    'server_time': now.strftime("%Y-%m-%d %H:%M:%S"),
                }
            }
            
            return session_info
            
        except Exception as e:
            _logger.error(f"Error getting session info: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }