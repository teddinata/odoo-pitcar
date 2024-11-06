from odoo import http
from odoo.http import request, Response
from odoo.addons.web.controllers.session import Session
import json
import werkzeug.wrappers

class CustomSession(Session):
    @http.route(['/web/session/authenticate'], type='json', auth="user", csrf=False, methods=['POST', 'OPTIONS'], cors='*')
    def authenticate(self, db, login, password, base_location=None):
        if request.httprequest.method == 'OPTIONS':
            headers = {
                # 'Access-Control-Allow-Origin': request.httprequest.headers.get('Origin', '*'),
                'Access-Control-Allow-Origin': 'https://antrean.pitcar.co.id',
                # 'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Allow-Credentials': 'true',
                'Access-Control-Max-Age': '86400',  # 24 hours
            }
            return Response(status=200, headers=headers)

        try:
            request.session.authenticate(db, login, password)
            result = request.env['ir.http'].session_info()
            
            # Add custom response handling here if needed
            return {
                'jsonrpc': '2.0',
                'id': None,
                'result': result
            }
        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': None,
                'status': 'error',
                'error': {
                    'code': 401,
                    'message': str(e),
                    'data': {
                        'name': 'session_invalid',
                        'debug': str(e),
                    }
                }
            }

    # Optional: Add method for checking authentication status
    @http.route(['/web/session/check'], type='json', auth="none", cors='*')
    def check_session(self):
        if request.session.uid:
            return {'status': 'authenticated', 'uid': request.session.uid}
        return {'status': 'not_authenticated'}

    # @http.route('/web/session/authenticate', type='json', auth="none", csrf=False)
    # def authenticate(self, db, login, password, base_location=None):
    #     try:
    #         uid = request.session.authenticate(db, login, password)
    #         if uid:
    #             # Get user info
    #             user = request.env['res.users'].sudo().browse(uid)
    #             result = {
    #                 'uid': uid,
    #                 'name': user.name,
    #                 'username': user.login,
    #                 'session_id': request.session.sid,
    #                 'user_context': request.session.get_context() if uid else {},
    #                 'db': db,
    #                 'server_version': request.env['ir.module.module'].sudo().get_version_info(),
    #             }
    #             return result
    #         return None
    #     except Exception as e:
    #         return {
    #             'error': {
    #                 'code': 401,
    #                 'message': str(e)
    #             }
    #         }

    # @http.route('/web/session/authenticate', type='http', auth="none", csrf=False, methods=['OPTIONS'])
    # def authenticate_options(self):
    #     headers = {
    #         'Access-Control-Allow-Origin': 'http://localhost:5173',
    #         'Access-Control-Allow-Methods': 'POST, OPTIONS',
    #         'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With',
    #         'Access-Control-Allow-Credentials': 'true',
    #     }
    #     return Response(status=200, headers=headers)

    # def _apply_cors(self, response):
    #     if not isinstance(response, werkzeug.wrappers.Response):
    #         response = Response(json.dumps(response), content_type='application/json')
        
    #     response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
    #     response.headers['Access-Control-Allow-Credentials'] = 'true'
    #     return response