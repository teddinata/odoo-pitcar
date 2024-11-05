import json
from functools import wraps
from odoo import http
from odoo.http import Response, request

def cors_handler(*args, **kwargs):
    """Decorator to handle CORS and JSON responses"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.httprequest.method == 'OPTIONS':
                headers = {
                    'Access-Control-Allow-Origin': 'http://localhost:5173',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                    'Access-Control-Allow-Credentials': 'true',
                }
                return Response(status=200, headers=headers)

            result = f(*args, **kwargs)

            headers = {
                'Access-Control-Allow-Origin': 'http://localhost:5173',
                'Access-Control-Allow-Credentials': 'true',
                'Content-Type': 'application/json',
            }

            if isinstance(result, Response):
                for key, value in headers.items():
                    result.headers[key] = value
                return result
            else:
                # Wrap the result in proper JSON-RPC format
                response = {
                    'jsonrpc': '2.0',
                    'id': None,
                    'result': result
                }
                return Response(
                    json.dumps(response),
                    headers=headers,
                    content_type='application/json'
                )

        return wrapper
    return decorator