from odoo import http, fields
from odoo.http import request
import logging
import json
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)

class SessionController(http.Controller):
    @http.route('/web/session/get_session_info', type='json', auth='user', methods=['POST'])
    def get_session_info(self, **kw):
        """
        Endpoint untuk mendapatkan informasi sesi pengguna beserta informasi notifikasi.
        """
        try:
            user = request.env.user
            company = user.company_id
            
            # Dapatkan jumlah notifikasi yang belum dibaca
            unread_notifications_count = request.env['pitcar.notification'].sudo().search_count([
                ('is_read', '=', False)
            ])
            
            # Cek apakah user merupakan mekanik
            mechanic = request.env['pitcar.mechanic.new'].sudo().search([('user_id', '=', user.id)], limit=1)
            is_mechanic = bool(mechanic)
            
            # Cek posisi atau role khusus
            is_mentor = mechanic.is_mentor if mechanic else False
            position_code = mechanic.position_code if mechanic else False
            
            # Siapkan data untuk respons
            tz = pytz.timezone('Asia/Jakarta')
            now = fields.Datetime.now().astimezone(tz)
            
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
                    },
                    'company': {
                        'id': company.id,
                        'name': company.name,
                        'currency_id': company.currency_id.id,
                        'currency_symbol': company.currency_id.symbol,
                    },
                    'roles': {
                        'is_mechanic': is_mechanic,
                        'is_mentor': is_mentor,
                        'position_code': position_code,
                    },
                    'notifications': {
                        'unread_count': unread_notifications_count,
                        'last_checked': now.isoformat(),
                    },
                    'timestamp': now.isoformat(),
                }
            }
            
            return session_info
            
        except Exception as e:
            _logger.error(f"Error getting session info: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }