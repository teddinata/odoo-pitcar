from odoo import http
from odoo.http import request
import logging
import math
from odoo.tools import date_utils

_logger = logging.getLogger(__name__)

class MentorRequestController(http.Controller):
    @http.route('/web/mentor/request/create', type='json', auth='user', methods=['POST'])
    def create_request(self, **kw):
        """Create new mentor request"""
        try:
            # Validate required fields 
            required_fields = ['sale_order_id', 'mechanic_ids', 'problem_category', 'problem_description']
            missing = [field for field in required_fields if field not in kw]
            if missing:
                return {
                    "status": "error",
                    "message": f"Missing required field(s): {', '.join(missing)}"
                }

            # Pastikan mechanic_ids adalah list
            mechanic_ids = kw['mechanic_ids'] if isinstance(kw['mechanic_ids'], list) else [kw['mechanic_ids']]
            if not mechanic_ids:
                return {
                    "status": "error",
                    "message": "At least one mechanic must be specified"
                }

            # Verify that mechanic_ids exist
            mechanics = request.env['pitcar.mechanic.new'].sudo().browse(mechanic_ids)
            if not mechanics.exists() or len(mechanics) != len(mechanic_ids):
                return {
                    "status": "error",
                    "message": "One or more mechanic IDs do not exist"
                }
                
            # Verify that sale_order_id exists
            sale_order = request.env['sale.order'].sudo().browse(kw['sale_order_id'])
            if not sale_order.exists():
                return {
                    "status": "error",
                    "message": f"Sale Order with ID {kw['sale_order_id']} does not exist"
                }

            # Create request
            values = {
                'sale_order_id': kw['sale_order_id'],
                'mechanic_ids': [(6, 0, mechanic_ids)],  # Format Many2many untuk Odoo
                'problem_category': kw['problem_category'],
                'problem_description': kw['problem_description'],
                'priority': kw.get('priority', 'normal')
            }

            mentor_request = request.env['pitcar.mentor.request'].sudo().create(values)
            
            # Submit request if created successfully
            if mentor_request:
                mentor_request.sudo().action_submit_request()

            return {
                "status": "success",
                "data": self._get_request_details(mentor_request)
            }

        except Exception as e:
            _logger.error(f"Error creating mentor request: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    @http.route('/web/mentor/request/search', type='json', auth='user', methods=['POST'])
    def search_requests(self, **kw):
        """Search mentor requests"""
        try:
            domain = []
            
            # Build search domain
            if kw.get('state'):
                domain.append(('state', '=', kw['state']))
            if kw.get('priority'):
                domain.append(('priority', '=', kw['priority']))
            if kw.get('category'):
                domain.append(('problem_category', '=', kw['category']))
            if kw.get('mechanic_id'):
                domain.append(('mechanic_id', '=', kw['mechanic_id']))
            if kw.get('mentor_id'):
                domain.append(('mentor_id', '=', kw['mentor_id']))
            if kw.get('sale_order_id'):
                domain.append(('sale_order_id', '=', kw['sale_order_id']))

            # Date range
            if kw.get('date_from'):
                domain.append(('create_date', '>=', kw['date_from']))
            if kw.get('date_to'):
                domain.append(('create_date', '<=', kw['date_to']))

            # Pagination
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 20))
            offset = (page - 1) * limit

            # Search
            MentorRequest = request.env['pitcar.mentor.request'].sudo()
            total_count = MentorRequest.search_count(domain)
            requests = MentorRequest.search(domain, limit=limit, offset=offset)

            return {
                "status": "success",
                "data": {
                    'total': total_count,
                    'page': page,
                    'pages': math.ceil(total_count / limit),
                    'items': [self._get_request_details(req) for req in requests]
                }
            }

        except Exception as e:
            _logger.error(f"Error searching requests: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    @http.route('/web/mentor/mechanics', type='json', auth='user', methods=['POST'])
    def get_mechanics(self, **kw):
        """Get all mechanics without any filters"""
        try:
            # Empty domain - get all mechanics
            domain = []
            
            # Add search if provided, otherwise return all
            if kw.get('search'):
                domain.append(('name', 'ilike', kw['search']))

            mechanics = request.env['pitcar.mechanic.new'].sudo().search(domain)
            
            result = []
            for mechanic in mechanics:
                mechanic_data = {
                    'id': mechanic.id,
                    'name': mechanic.name
                }
                result.append(mechanic_data)

            return {
                "status": "success",
                "data": result
            }

        except Exception as e:
            _logger.error(f"Error getting mechanics: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    @http.route('/web/mentor/request/<int:request_id>/action', type='json', auth='user', methods=['POST'])
    def handle_request_action(self, request_id, **kw):
        """Handle request actions"""
        try:
            # Check for action
            if 'action' not in kw:
                return {
                    "status": "error",
                    "message": "Action not specified"
                }

            req = request.env['pitcar.mentor.request'].sudo().browse(request_id)
            if not req.exists():
                return {
                    "status": "error",
                    "message": "Request not found"
                }

            action = kw.get('action')
            if action == 'start':
                if not kw.get('mentor_id'):
                    return {
                        "status": "error", 
                        "message": "Mentor ID required"
                    }
                    
                # Verify mentor exists
                mentor = request.env['pitcar.mechanic.new'].sudo().browse(kw['mentor_id'])
                if not mentor.exists():
                    return {
                        "status": "error",
                        "message": f"Mechanic with ID {kw['mentor_id']} does not exist"
                    }
                
                req.sudo().write({'mentor_id': kw['mentor_id']})
                req.sudo().action_start_mentoring()

            elif action == 'solve':
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
                req.sudo().write(values)
                req.sudo().action_mark_solved()

            elif action == 'cancel':
                req.sudo().action_cancel_request()
                
            else:
                return {
                    "status": "error",
                    "message": "Invalid action specified"
                }

            return {
                "status": "success",
                "data": self._get_request_details(req)
            }

        except Exception as e:
            _logger.error(f"Error handling request action: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    @http.route('/web/mentor/dashboard', type='json', auth='user', methods=['POST'])
    def get_dashboard_data(self, **kw):
        """Get dashboard statistics"""
        try:
            domain = []
            if kw.get('date_from'):
                domain.append(('create_date', '>=', kw['date_from']))
            if kw.get('date_to'):
                domain.append(('create_date', '<=', kw['date_to']))

            MentorRequest = request.env['pitcar.mentor.request'].sudo()
            
            # Base metrics
            total_requests = MentorRequest.search_count(domain)
            solved_requests = MentorRequest.search_count(domain + [('state', '=', 'solved')])
            
            # Calculate metrics
            data = {
                'overview': {
                    'total_requests': total_requests,
                    'solved_requests': solved_requests,
                    'success_rate': (solved_requests / total_requests * 100) if total_requests else 0
                }
            }

            return {
                "status": "success",
                "data": data
            }

        except Exception as e:
            _logger.error(f"Error getting dashboard data: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    def _get_request_details(self, req):
        """Format request details"""
        if not req:
            return {}
            
        return {
            'id': req.id,
            'name': req.name,
            'state': req.state,
            'priority': req.priority,
            'category': req.problem_category,
            'description': req.problem_description,
            'mechanic': {
                'id': req.mechanic_id.id,
                'name': req.mechanic_id.name
            } if req.mechanic_id else {},
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
        """Send notification to specified mentors about a request"""
        try:
            # Validate required fields
            required_fields = ['request_id', 'mentor_ids']
            missing = [field for field in required_fields if field not in kw]
            if missing:
                return {
                    "status": "error",
                    "message": f"Missing required field(s): {', '.join(missing)}"
                }
            
            # Get the request
            mentor_request = request.env['pitcar.mentor.request'].sudo().browse(kw['request_id'])
            if not mentor_request.exists():
                return {
                    "status": "error",
                    "message": f"Request with ID {kw['request_id']} does not exist"
                }
                
            # Get mentors
            mentors = request.env['pitcar.mechanic.new'].sudo().browse(kw['mentor_ids'])
            valid_mentors = mentors.filtered(lambda m: m.exists() and m.user_id and m.user_id.partner_id)
            
            if not valid_mentors:
                return {
                    "status": "error",
                    "message": "No valid mentors found to notify"
                }
            
            # Prepare notification message
            message = f"""
                <p><strong>Permintaan Bantuan Baru</strong></p>
                <ul>
                    <li>Dari: {mentor_request.mechanic_id.name}</li>
                    <li>Work Order: {mentor_request.sale_order_id.name}</li>
                    <li>Kategori: {dict(mentor_request._fields['problem_category'].selection).get(mentor_request.problem_category)}</li>
                    <li>Prioritas: {dict(mentor_request._fields['priority'].selection).get(mentor_request.priority)}</li>
                    <li>Deskripsi: {mentor_request.problem_description}</li>
                </ul>
            """
            
            # Send notifications
            partner_ids = valid_mentors.mapped('user_id.partner_id.id')
            if partner_ids:
                mentor_request.message_post(
                    body=message,
                    message_type='notification',
                    partner_ids=partner_ids
                )
                
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
                    "message": "Failed to identify partner IDs for notification"
                }
                
        except Exception as e:
            _logger.error(f"Error sending notifications: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
        
    # EO@http.route('/web/mentor/notifications/list', type='json', auth='user', methods=['POST'])
    def list_notifications(self, **kw):
        """Get list of notifications for a mentor"""
        try:
            # Get parameters
            mentor_id = kw.get('mentor_id')
            if not mentor_id:
                return {"status": "error", "message": "mentor_id is required"}
                
            # Pagination
            page = int(kw.get('page', 1))
            limit = int(kw.get('limit', 10))
            offset = (page - 1) * limit
            
            # Status filter (default: requested)
            state = kw.get('state', 'requested')
            
            # Build domain
            domain = [
                ('state', '=', state)
            ]
                
            # Get requests that need mentor attention
            MentorRequest = request.env['pitcar.mentor.request'].sudo()
            total_count = MentorRequest.search_count(domain)
            requests = MentorRequest.search(domain, limit=limit, offset=offset)
            
            return {
                "status": "success",
                "data": {
                    'total': total_count,
                    'page': page,
                    'pages': math.ceil(total_count / limit),
                    'items': [self._get_notification_data(req) for req in requests]
                }
            }
            
        except Exception as e:
            _logger.error(f"Error listing notifications: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def _get_notification_data(self, req):
        """Format notification data"""
        return {
            'id': req.id,
            'name': req.name,
            'type': 'mentor_request',
            'title': f"Request: {req.name}",
            'message': f"Mechanic {req.mechanic_id.name} needs help with {dict(req._fields['problem_category'].selection).get(req.problem_category)}",
            'priority': req.priority,
            'timestamp': date_utils.json_default(req.create_date),
            'read': False,  # Placeholder - implement read status if needed
            'request_details': self._get_request_details(req)
        }
    
    @http.route('/web/mentor/notifications/count', type='json', auth='user', methods=['POST'])
    def get_notification_count(self, **kw):
        """Get count of unread notifications"""
        try:
            mentor_id = kw.get('mentor_id')
            if not mentor_id:
                return {"status": "error", "message": "mentor_id is required"}
                
            # Count pending requests
            domain = [
                ('state', '=', 'requested')
            ]
                
            count = request.env['pitcar.mentor.request'].sudo().search_count(domain)
            
            return {
                "status": "success",
                "data": {
                    "count": count
                }
            }
                
        except Exception as e:
            _logger.error(f"Error getting notification count: {str(e)}")
            return {"status": "error", "message": str(e)}