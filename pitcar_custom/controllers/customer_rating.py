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
            params = kwargs
            dbname = params.get('db')
            search_date = params.get('date')

            _logger.info(f"Received parameters: {params}")
            
            if not dbname:
                return {
                    'status': 'error',
                    'message': 'Database name is required'
                }

            # Set timezone to Asia/Jakarta
            tz = pytz.timezone('Asia/Jakarta')
            
            # Parse and validate search date
            try:
                parsed_date = datetime.strptime(search_date, '%Y-%m-%d')
                _logger.info(f"Searching orders for date: {search_date}")
            except (ValueError, TypeError):
                today = datetime.now(tz)
                parsed_date = today
                _logger.warning(f"Invalid date format, using today: {today.strftime('%Y-%m-%d')}")

            SaleOrder = request.env['sale.order'].sudo()

            # Create datetime bounds for the search date
            start_of_day = parsed_date.replace(hour=0, minute=0, second=0)
            end_of_day = parsed_date.replace(hour=23, minute=59, second=59)

            # Format dates for query
            date_start = start_of_day.strftime('%Y-%m-%d %H:%M:%S')
            date_end = end_of_day.strftime('%Y-%m-%d %H:%M:%S')

            _logger.info(f"Search range: {date_start} to {date_end}")

            # Build domain for exact date match
            domain = [
                ('state', 'in', ['sale', 'done']),
                ('sa_cetak_pkb', '>=', date_start),
                ('sa_cetak_pkb', '<=', date_end)
            ]

            # Execute search with ordering
            orders = SaleOrder.search(domain, order='sa_cetak_pkb desc')
            _logger.info(f"Found {len(orders)} orders")

            # Process results
            result = []
            for order in orders:
                if order.sa_cetak_pkb:
                    # Extract the date part for comparison
                    order_date = order.sa_cetak_pkb.strftime('%Y-%m-%d')
                    search_date_str = parsed_date.strftime('%Y-%m-%d')
                    
                    # Only include if dates match exactly
                    if order_date == search_date_str:
                        order_data = {
                            'id': order.id,
                            'name': order.name,
                            'plate_number': order.partner_car_id.number_plate if order.partner_car_id else 'No Plate',
                            'completion_time': order.sa_cetak_pkb.strftime('%Y-%m-%d %H:%M:%S'),
                            'customer_name': order.partner_id.name if order.partner_id else '',
                            'car_brand': order.partner_car_brand.name if order.partner_car_brand else '',
                            'car_type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
                            'state': order.state,
                            'has_rating': bool(order.customer_rating)
                        }
                        result.append(order_data)
                        _logger.info(f"Added order {order.name} with date {order_date}")
                    else:
                        _logger.info(f"Skipped order {order.name} with date {order_date} (doesn't match {search_date_str})")

            if not result:
                _logger.info("No orders found, retrieving sample data with correct date filter")
                # If no results, get orders from any date for debugging
                sample_orders = SaleOrder.search([
                    ('state', 'in', ['sale', 'done']),
                    ('sa_cetak_pkb', '!=', False)
                ], limit=5, order='sa_cetak_pkb desc')
                
                sample_data = []
                for order in sample_orders:
                    sample_data.append({
                        'id': order.id,
                        'name': order.name,
                        'plate_number': order.partner_car_id.number_plate if order.partner_car_id else 'No Plate',
                        'completion_time': order.sa_cetak_pkb.strftime('%Y-%m-%d %H:%M:%S'),
                        'customer_name': order.partner_id.name if order.partner_id else '',
                        'car_brand': order.partner_car_brand.name if order.partner_car_brand else '',
                        'car_type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
                        'state': order.state,
                        'has_rating': bool(order.customer_rating)
                    })

                _logger.info(f"Sample data size: {len(sample_data)}")

                return {
                    'status': 'success',
                    'data': []  # Return empty data as requested
                }

            # Sort by completion_time if needed (should already be sorted from search)
            result.sort(key=lambda x: x['completion_time'], reverse=True)
            
            _logger.info(f"Returning {len(result)} orders")
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"Error in get_available_orders: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
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
            # Get parameters from kwargs directly
            params = kwargs
            _logger.info(f"Received rating submission params: {params}")

            # Validate required fields
            required_fields = {
                'db': str,
                'order_id': int,
                'service_rating': int,
                'price_rating': int,
                'facility_rating': int,
                'feedback': str
            }

            # Validate field types and presence
            for field, field_type in required_fields.items():
                if field not in params:
                    return {
                        'status': 'error',
                        'message': f'Missing required field: {field}'
                    }
                try:
                    if field != 'feedback':  # Don't convert feedback to int
                        params[field] = field_type(params[field])
                except (ValueError, TypeError):
                    return {
                        'status': 'error',
                        'message': f'Invalid value for field: {field}'
                    }

            # Validate rating values
            for rating_field in ['service_rating', 'price_rating', 'facility_rating']:
                if not 1 <= params[rating_field] <= 5:
                    return {
                        'status': 'error',
                        'message': f'{rating_field} must be between 1 and 5'
                    }

            SaleOrder = request.env['sale.order'].sudo()
            order = SaleOrder.browse(params['order_id'])
            
            if not order.exists():
                return {
                    'status': 'error',
                    'message': 'Order not found'
                }

            if order.customer_rating:
                return {
                    'status': 'error',
                    'message': 'Order already has a rating'
                }

            # Calculate average rating
            ratings = [
                params['service_rating'],
                params['price_rating'],
                params['facility_rating']
            ]
            average_rating = sum(ratings) / len(ratings)
            
            _logger.info(f"""
            Submitting rating for order {order.name}:
            - Service: {params['service_rating']}
            - Price: {params['price_rating']}
            - Facility: {params['facility_rating']}
            - Average: {average_rating}
            - Feedback: {params['feedback']}
            """)

            # Update order with ratings
            order.write({
                'is_willing_to_feedback': 'yes',
                'customer_rating': str(round(average_rating)),
                'customer_feedback': params['feedback'],
                'detailed_ratings': {
                    'service_rating': params['service_rating'],
                    'price_rating': params['price_rating'],
                    'facility_rating': params['facility_rating'],
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
                    'order_name': order.name,
                    'average_rating': round(average_rating),
                    'satisfaction_level': satisfaction
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in submit_rating: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

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
