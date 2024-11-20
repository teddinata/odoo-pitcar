from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.http import Controller, route, request, Response
import json
import logging
import pytz

_logger = logging.getLogger(__name__)

class CustomerRatingAPI(Controller):
    def _validate_token(self, token):
        """Validate API token"""
        if not token:
            return False
        # Implement your token validation logic here
        return True

    def _validate_date(self, date_str):
        """Validate date string format"""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            return None

    @route('/web/rating/orders', type='json', auth='public', methods=['POST'], csrf=False)
    def get_available_orders(self, **kwargs):
        """Get list of orders available for rating (completed today)"""
        try:
            # Get parameters from kwargs directly
            params = kwargs
            dbname = params.get('db')
            search_date = params.get('date')

            _logger.info(f"Received parameters: {params}")
            
            if not dbname:
                return {
                    'status': 'error',
                    'message': 'Database name is required'
                }

            # Get user's timezone
            tz = pytz.timezone(request.env.user.tz or 'UTC')
            today = datetime.now(tz).strftime('%Y-%m-%d')
            
            # Use provided date or default to today
            search_date = search_date or today
            
            _logger.info(f"Searching orders for date: {search_date} in database: {dbname}")

            SaleOrder = request.env['sale.order'].sudo()
            
            # Debug: Cek total orders tanpa filter
            all_orders = SaleOrder.search([])
            _logger.info(f"Total orders in system: {len(all_orders)}")
            
            # Debug: Cek orders dengan state
            state_orders = SaleOrder.search([('state', 'in', ['sale', 'done'])])
            _logger.info(f"Orders with state sale/done: {len(state_orders)}")
            
            # Debug: Cek orders dengan sa_cetak_pkb
            pkb_orders = SaleOrder.search([('sa_cetak_pkb', '!=', False)])
            _logger.info(f"Orders with sa_cetak_pkb: {len(pkb_orders)}")
            for order in pkb_orders:
                _logger.info(f"PKB Order: {order.name} - Date: {order.sa_cetak_pkb}")

            # Bangun domain step by step
            domain = [
                ('state', 'in', ['sale', 'done']),  # Base state filter
            ]
            
            # Convert date strings dengan timezone yang benar
            local_dt = datetime.strptime(f"{search_date} 00:00:00", '%Y-%m-%d %H:%M:%S')
            local_dt = tz.localize(local_dt)
            date_start = local_dt.astimezone(pytz.UTC)
            
            local_dt_end = datetime.strptime(f"{search_date} 23:59:59", '%Y-%m-%d %H:%M:%S')
            local_dt_end = tz.localize(local_dt_end)
            date_end = local_dt_end.astimezone(pytz.UTC)

            date_domain = [
                '|',  # OR untuk sa_cetak_pkb dan create_date
                ('sa_cetak_pkb', '>=', date_start.strftime('%Y-%m-%d %H:%M:%S')),
                ('sa_cetak_pkb', '<=', date_end.strftime('%Y-%m-%d %H:%M:%S')),
            ]
            
            domain.extend(date_domain)
            
            # Debug: Print full domain
            _logger.info(f"Search domain: {domain}")
            
            orders = SaleOrder.search(domain)
            _logger.info(f"Found {len(orders)} orders with current domain")
            
            # Debug: Print found orders
            for order in orders:
                _logger.info(f"""
                Found order:
                - ID: {order.id}
                - Name: {order.name}
                - State: {order.state}
                - Create Date: {order.create_date}
                - SA Cetak PKB: {order.sa_cetak_pkb}
                - Car Info: {order.partner_car_id.number_plate if order.partner_car_id else 'No car'}
                """)

            result = []
            for order in orders:
                order_data = {
                    'id': order.id,
                    'name': order.name,
                    'plate_number': order.partner_car_id.number_plate if order.partner_car_id else 'No Plate',
                    'completion_time': order.sa_cetak_pkb.strftime('%Y-%m-%d %H:%M:%S') if order.sa_cetak_pkb else order.create_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'customer_name': order.partner_id.name if order.partner_id else '',
                    'car_brand': order.partner_car_brand.name if order.partner_car_brand else '',
                    'car_type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
                    'state': order.state,
                    'has_rating': bool(order.customer_rating)
                }
                result.append(order_data)

            if not result:
                # Return debug info jika tidak ada hasil
                return {
                    'status': 'success',
                    'data': [],
                    'debug_info': {
                        'total_orders': len(all_orders),
                        'state_filtered_orders': len(state_orders),
                        'pkb_orders': len(pkb_orders),
                        'search_date': search_date,
                        'date_start': date_start.strftime('%Y-%m-%d %H:%M:%S'),
                        'date_end': date_end.strftime('%Y-%m-%d %H:%M:%S'),
                        'timezone': request.env.user.tz or 'UTC',
                        'domain': domain
                    }
                }

            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"Error in get_available_orders: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'debug_info': {
                    'error_type': type(e).__name__,
                    'search_date': search_date if 'search_date' in locals() else None,
                    'timezone': request.env.user.tz or 'UTC',
                    'traceback': logging.traceback.format_exc()
                }
            }


    def _get_order_domain(self, date_str=None):
        """Helper method to generate order search domain"""
        tz = pytz.timezone(request.env.user.tz or 'UTC')
        
        if not date_str:
            date_str = datetime.now(tz).strftime('%Y-%m-%d')
            
        date_start = datetime.strptime(f"{date_str} 00:00:00", '%Y-%m-%d %H:%M:%S')
        date_end = datetime.strptime(f"{date_str} 23:59:59", '%Y-%m-%d %H:%M:%S')
        
        date_start = tz.localize(date_start).astimezone(pytz.UTC)
        date_end = tz.localize(date_end).astimezone(pytz.UTC)
        
        return [
            ('sa_cetak_pkb', '>=', date_start.strftime('%Y-%m-%d %H:%M:%S')),
            ('sa_cetak_pkb', '<=', date_end.strftime('%Y-%m-%d %H:%M:%S')),
            ('state', 'in', ['sale', 'done']),
            '|',
            ('customer_rating', '=', False),
            ('customer_rating', '=', '')
        ]

    @route('/web/rating/order-details', type='json', auth='public', methods=['POST'], csrf=False)
    def get_order_details(self, **kwargs):
        """Get detailed information about specific order"""
        try:
            params = kwargs
            dbname = params.get('db')
            order_id = params.get('order_id')
            
            if not dbname:
                return {'status': 'error', 'message': 'Database name is required'}
            
            if not order_id:
                return {'status': 'error', 'message': 'Order ID is required'}

            _logger.info(f"Getting details for order ID: {order_id}")
            SaleOrder = request.env['sale.order'].sudo()
            order = SaleOrder.browse(int(order_id))
            
            if not order.exists():
                return {'status': 'error', 'message': 'Order not found'}

            # Debug log
            _logger.info(f"""
            Order found:
            - ID: {order.id}
            - Name: {order.name}
            - State: {order.state}
            - Car Info: {order.partner_car_id.number_plate if order.partner_car_id else 'No car'}
            """)

            # Format order details
            result = {
                'order_id': order.id,
                'order_name': order.name,
                'customer_name': order.partner_id.name if order.partner_id else '',
                'car_details': {
                    'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
                    'brand': order.partner_car_brand.name if order.partner_car_brand else '',
                    'model': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
                    'year': order.partner_car_year or '',
                    'color': order.partner_car_id.color if order.partner_car_id else '',
                    'engine_type': order.partner_car_id.engine_type if order.partner_car_id else '',
                },
                'service_details': {
                    'completion_time': order.sa_cetak_pkb.strftime('%Y-%m-%d %H:%M:%S') if order.sa_cetak_pkb else '',
                    'service_items': [{
                        'product': line.product_id.name,
                        'quantity': line.product_uom_qty,
                        'price': line.price_unit,
                        'subtotal': line.price_subtotal,
                    } for line in order.order_line if line.product_id],
                    'total_amount': order.amount_total,
                },
                'rating_status': {
                    'has_rating': bool(order.customer_rating),
                    'current_rating': order.customer_rating if order.customer_rating else None,
                    'feedback': order.customer_feedback if order.customer_feedback else None,
                }
            }
            
            return {'status': 'success', 'data': result}
            
        except Exception as e:
            _logger.error(f"Error in get_order_details: {str(e)}")
            return {
                'status': 'error', 
                'message': str(e),
                'debug_info': {
                    'error_type': type(e).__name__,
                    'order_id': post.get('order_id'),
                    'traceback': logging.traceback.format_exc()
                }
            }
        finally:
            if request.env.cr:
                request.env.cr.close()

    @route('/web/rating/submit', type='json', auth='public', methods=['POST'], csrf=False)
    def submit_rating(self, **kwargs):
        """Submit customer rating"""
        try:
            params = kwargs
            dbname = params.get('db')
            
            if not dbname:
                return {'status': 'error', 'message': 'Database name is required'}
            
            # Validate required fields
            required_fields = {
                'order_id': int,
                'service_rating': int,
                'price_rating': int,
                'facility_rating': int,
                'feedback': str
            }

            _logger.info(f"Received rating submission for order: {post.get('order_id')}")

            # Validate field types and presence
            for field, field_type in required_fields.items():
                if field not in post:
                    return {'status': 'error', 'message': f'Missing required field: {field}'}
                try:
                    if field != 'feedback':  # Don't convert feedback to int
                        post[field] = field_type(post[field])
                except (ValueError, TypeError):
                    return {'status': 'error', 'message': f'Invalid value for field: {field}'}

            # Validate rating values
            for rating_field in ['service_rating', 'price_rating', 'facility_rating']:
                if not 1 <= post[rating_field] <= 5:
                    return {'status': 'error', 'message': f'{rating_field} must be between 1 and 5'}

            SaleOrder = request.env['sale.order'].sudo()
            order = SaleOrder.browse(post['order_id'])
            
            if not order.exists():
                return {'status': 'error', 'message': 'Order not found'}

            if order.customer_rating:
                return {'status': 'error', 'message': 'Order already has a rating'}

            # Calculate average rating
            ratings = [
                post['service_rating'],
                post['price_rating'],
                post['facility_rating']
            ]
            average_rating = sum(ratings) / len(ratings)
            
            # Debug log before update
            _logger.info(f"""
            Submitting rating for order {order.name}:
            - Service: {post['service_rating']}
            - Price: {post['price_rating']}
            - Facility: {post['facility_rating']}
            - Average: {average_rating}
            - Feedback: {post['feedback']}
            """)

            # Update order with ratings
            order.write({
                'is_willing_to_feedback': 'yes',
                'customer_rating': str(round(average_rating)),
                'customer_feedback': post['feedback'],
                'detailed_ratings': {
                    'service_rating': post['service_rating'],
                    'price_rating': post['price_rating'],
                    'facility_rating': post['facility_rating'],
                    'submission_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'submission_source': 'web_api'
                }
            })

            # Update customer satisfaction
            rating_to_satisfaction = {
                1: 'very_dissatisfied',
                2: 'dissatisfied',
                3: 'neutral',
                4: 'satisfied',
                5: 'very_satisfied'
            }
            
            satisfaction = rating_to_satisfaction.get(round(average_rating), 'neutral')
            order.write({'customer_satisfaction': satisfaction})

            return {
                'status': 'success', 
                'message': 'Rating submitted successfully',
                'data': {
                    'order_id': order.id,
                    'average_rating': round(average_rating),
                    'satisfaction_level': satisfaction
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in submit_rating: {str(e)}")
            return {
                'status': 'error', 
                'message': str(e),
                'debug_info': {
                    'error_type': type(e).__name__,
                    'order_id': post.get('order_id'),
                    'traceback': logging.traceback.format_exc()
                }
            }
        finally:
            if request.env.cr:
                request.env.cr.close()

    def _generate_order_token(self, order):
        """Generate unique token for order validation"""
        import hashlib
        import hmac
        import base64
        
        # Create a unique string using order details
        unique_string = f"{order.id}-{order.sa_cetak_pkb}-{order.partner_car_id.license_plate}"
        # Add your secret key here
        secret_key = "your_secret_key_here"
        
        # Generate HMAC
        hmac_obj = hmac.new(
            secret_key.encode('utf-8'),
            unique_string.encode('utf-8'),
            hashlib.sha256
        )
        
        # Return base64 encoded token
        return base64.b64encode(hmac_obj.digest()).decode('utf-8')

    def _validate_order_token(self, order, token):
        """Validate order token"""
        expected_token = self._generate_order_token(order)
        return hmac.compare_digest(token, expected_token)

    def _update_customer_satisfaction(self, order, average_rating):
        """Update customer satisfaction based on average rating"""
        rating_to_satisfaction = {
            1: 'very_dissatisfied',
            2: 'dissatisfied',
            3: 'neutral',
            4: 'satisfied',
            5: 'very_satisfied'
        }
        
        rounded_rating = round(average_rating)
        satisfaction = rating_to_satisfaction.get(rounded_rating, 'neutral')
        order.write({'customer_satisfaction': satisfaction})
