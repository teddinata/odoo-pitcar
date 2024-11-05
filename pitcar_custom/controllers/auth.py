from odoo import http
from odoo.http import request, Response
from odoo.addons.web.controllers.session import Session
import json
import werkzeug.wrappers

class CustomSession(Session):
    @http.route(['/web/session/authenticate'], type='json', auth="none", 
                csrf=False, methods=['POST', 'OPTIONS'], cors='*')
    def authenticate(self, db, login, password, base_location=None):
        allowed_origins = [
            'https://antrean.pitcar.co.id',  # Production frontend
            'http://localhost:5173'         # Development frontend
        ]
        
        origin = request.httprequest.headers.get('Origin', '')
        
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': origin if origin in allowed_origins else allowed_origins[0],
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With',
                'Access-Control-Allow-Credentials': 'true',
                'Access-Control-Max-Age': '86400',
            }
            return Response(status=200, headers=headers)

        # Handle actual request
        headers = {
            'Access-Control-Allow-Origin': origin if origin in allowed_origins else allowed_origins[0],
            'Access-Control-Allow-Credentials': 'true',
        }
        
        try:
            request.session.authenticate(db, login, password)
            result = request.env['ir.http'].session_info()
            return Response(
                json.dumps({'result': result}),
                status=200,
                headers=headers,
                content_type='application/json'
            )
        except Exception as e:
            return Response(
                json.dumps({'error': str(e)}),
                status=401,
                headers=headers,
                content_type='application/json'
            )

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