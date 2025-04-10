from odoo import models, fields, api, http
from odoo.http import Controller, route, request, Response
import odoo
from odoo.service import security
from datetime import datetime, timedelta
import json
import logging
import pytz
from math import ceil
import urllib.parse
import base64
import hmac
import base64
import hashlib
import time

_logger = logging.getLogger(__name__)

class CustomerRatingAPI(Controller):
    def _get_secret_key(self):
        """Get secret key from system parameter"""
        return request.env['ir.config_parameter'].sudo().get_param(
            'feedback.secret.key', 
            default='your-secret-key-here'
        )

    # OLD METHOD
    # def _encode_id(self, order_id):
    #     """Encode order ID dengan timestamp dan signature"""
    #     try:
    #         # Data yang akan dienkripsi
    #         data = {
    #             'id': order_id,
    #             'ts': int(time.time()),  # Unix timestamp
    #         }
            
    #         # Convert ke JSON dan encode ke base64
    #         json_data = json.dumps(data)
    #         encoded = base64.urlsafe_b64encode(json_data.encode()).decode()
            
    #         # Generate signature
    #         signature = hmac.new(
    #             self._get_secret_key().encode(),
    #             encoded.encode(),
    #             hashlib.sha256
    #         ).hexdigest()
            
    #         # Combine encoded data dan signature
    #         return f"{encoded}.{signature}"
    #     except Exception as e:
    #         _logger.error(f"Encoding error: {str(e)}")
    #         return None

    # def _decode_id(self, encoded_str):
    #     """Decode dan validasi encoded ID"""
    #     try:
    #         # Split encoded data dan signature
    #         encoded, signature = encoded_str.split('.')
            
    #         # Verify signature
    #         expected_sig = hmac.new(
    #             self._get_secret_key().encode(),
    #             encoded.encode(),
    #             hashlib.sha256
    #         ).hexdigest()
            
    #         if not hmac.compare_digest(signature, expected_sig):
    #             _logger.warning("Invalid signature detected")
    #             return None
            
    #         # Decode data
    #         json_data = base64.urlsafe_b64decode(encoded).decode()
    #         data = json.loads(json_data)
            
    #         # Check timestamp (optional, misal expired setelah 7 hari)
    #         if time.time() - data['ts'] > 7 * 24 * 3600:
    #             _logger.warning("Expired token detected")
    #             return None
            
    #         return data['id']
    #     except Exception as e:
    #         _logger.error(f"Decoding error: {str(e)}")
    #         return None

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
        """Get list of orders available for rating (completed today, in progress, or specifically rated today)"""
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
            search_date_str = parsed_date.strftime('%Y-%m-%d')

            _logger.info(f"Search range: {date_start} to {date_end}")

            # Get only today's orders to start
            todays_orders = SaleOrder.search([
                '|', '|',
                # Orders that started service today
                '&',
                ('controller_mulai_servis', '>=', date_start),
                ('controller_mulai_servis', '<=', date_end),
                # Orders that completed service today
                '&',
                ('controller_selesai', '>=', date_start),
                ('controller_selesai', '<=', date_end),
                # Orders that had PKB printed today
                '&',
                ('sa_cetak_pkb', '>=', date_start),
                ('sa_cetak_pkb', '<=', date_end)
            ], order='sa_cetak_pkb desc')
            
            # Get orders in progress (started service but not completed)
            in_progress = SaleOrder.search([
                ('controller_mulai_servis', '!=', False),  # Service has started
                ('controller_selesai', '=', False),  # But not completed
                ('sa_cetak_pkb', '!=', False)  # Has PKB printed
            ], order='controller_mulai_servis desc')
            
            _logger.info(f"Found orders: {len(todays_orders)} from today's service activities, {len(in_progress)} in progress")
            
            # Combine results, removing duplicates
            order_ids_seen = set()
            combined_orders = []
            
            # Process today's active orders first
            for order in todays_orders:
                if order.id not in order_ids_seen:
                    order_ids_seen.add(order.id)
                    # Determine status
                    if order.controller_selesai and order.controller_selesai.strftime('%Y-%m-%d') == search_date_str:
                        combined_orders.append((order, "Selesai Hari Ini"))
                    elif order.controller_mulai_servis and not order.controller_selesai:
                        combined_orders.append((order, "Servis Dimulai"))
                    else:
                        combined_orders.append((order, "PKB Dicetak Hari Ini"))
            
            # Add remaining in-progress orders (overnight stays)
            for order in in_progress:
                if order.id not in order_ids_seen:
                    # Only add if this is truly an overnight order
                    if (order.controller_mulai_servis and 
                        order.controller_mulai_servis.strftime('%Y-%m-%d') != search_date_str):
                        order_ids_seen.add(order.id)
                        combined_orders.append((order, "Menginap"))
            
            # Process results
            result = []
            for order, status in combined_orders:
                try:
                    # Determine if order has been rated (and potentially when)
                    has_rating = bool(order.customer_rating)
                    
                    order_data = {
                        'id': order.id,
                        'name': order.name,
                        'plate_number': order.partner_car_id.number_plate if order.partner_car_id else 'No Plate',
                        'completion_time': order.sa_cetak_pkb.strftime('%Y-%m-%d %H:%M:%S') if order.sa_cetak_pkb else '',
                        'customer_name': order.partner_id.name if order.partner_id else '',
                        'car_brand': order.partner_car_brand.name if order.partner_car_brand else '',
                        'car_type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
                        'has_rating': has_rating,
                        'status': "Sudah Dirating" if has_rating else status
                    }
                    result.append(order_data)
                    _logger.info(f"Added order {order.name}, status: {status}, has_rating: {has_rating}")
                    
                except Exception as e:
                    _logger.error(f"Error processing order {order.name}: {str(e)}")
                    # Continue to next order

            # Sort by completion_time
            result.sort(key=lambda x: x['completion_time'] if x['completion_time'] else '', reverse=True)
            
            _logger.info(f"Returning {len(result)} filtered orders")
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
            # ('state', 'in', ['sale', 'done']),
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

    @route('/web/rating/dashboard', type='json', auth='public', methods=['POST'], csrf=False)
    def get_rating_dashboard(self, **kwargs):
        """Get dashboard statistics for customer ratings"""
        try:
            params = kwargs
            dbname = params.get('db')
            date_range = params.get('date_range', 'all')  
            date_start = params.get('date_start')
            date_end = params.get('date_end')

            if not dbname:
                return {'status': 'error', 'message': 'Database name is required'}

            SaleOrder = request.env['sale.order'].sudo()
            tz = pytz.timezone('Asia/Jakarta')
            
            # Build base domain
            domain = [('state', 'in', ['sale', 'done'])]

            if date_range != 'all':
                now = datetime.now()
                now_local = tz.localize(now)
                
                if date_range == 'custom' and date_start and date_end:
                    try:
                        # Parse string dates to naive datetime
                        start_dt = datetime.strptime(date_start, '%Y-%m-%d')
                        end_dt = datetime.strptime(date_end, '%Y-%m-%d')
                        
                        # Set time range
                        start_dt = start_dt.replace(hour=0, minute=0, second=0)
                        end_dt = end_dt.replace(hour=23, minute=59, second=59)
                        
                        # Localize to Asia/Jakarta
                        start_dt = tz.localize(start_dt)
                        end_dt = tz.localize(end_dt)
                        
                    except ValueError:
                        return {'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD'}
                        
                    if start_dt > end_dt:
                        return {'status': 'error', 'message': 'Start date must be before end date'}
                else:
                    if date_range == 'today':
                        start_dt = now_local.replace(hour=0, minute=0, second=0)
                        end_dt = now_local
                    elif date_range == 'week':
                        start_dt = now_local - timedelta(days=now_local.weekday())
                        start_dt = start_dt.replace(hour=0, minute=0, second=0)
                        end_dt = now_local
                    elif date_range == 'month':
                        start_dt = now_local.replace(day=1, hour=0, minute=0, second=0)
                        end_dt = now_local
                    elif date_range == 'year':
                        start_dt = now_local.replace(month=1, day=1, hour=0, minute=0, second=0)
                        end_dt = now_local

                # Convert to UTC for database query
                start_utc = start_dt.astimezone(pytz.UTC)
                end_utc = end_dt.astimezone(pytz.UTC)

                domain.extend([
                    ('sa_cetak_pkb', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                    ('sa_cetak_pkb', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
                ])

            # Get all orders within range
            orders = SaleOrder.search(domain)
            
            # Calculate statistics
            total_services = len(orders)
            rated_orders = orders.filtered(lambda o: o.customer_rating)
            total_reviews = len(rated_orders)

            # Calculate rating distribution    
            rating_distribution = {str(i): 0 for i in range(1, 6)}
            for order in rated_orders:
                if order.customer_rating:
                    rating_distribution[str(order.customer_rating)] = rating_distribution.get(str(order.customer_rating), 0) + 1

            # Calculate satisfaction distribution
            satisfaction_distribution = {
                'very_satisfied': 0,
                'satisfied': 0,
                'neutral': 0,
                'dissatisfied': 0,
                'very_dissatisfied': 0
            }
            for order in rated_orders:
                if order.customer_satisfaction:
                    satisfaction_distribution[order.customer_satisfaction] = satisfaction_distribution.get(order.customer_satisfaction, 0) + 1

            # Get recent reviews
            recent_reviews = []
            for order in rated_orders.sorted(key=lambda r: r.sa_cetak_pkb, reverse=True)[:10]:
                if order.sa_cetak_pkb:
                    pkb_time_utc = pytz.UTC.localize(order.sa_cetak_pkb) if not order.sa_cetak_pkb.tzinfo else order.sa_cetak_pkb
                    pkb_time_local = pkb_time_utc.astimezone(tz)
                    review = {
                        'id': order.id,
                        'order_name': order.name,
                        'customer_name': order.partner_id.name if order.partner_id else '',
                        'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
                        'car_info': f"{order.partner_car_brand.name} {order.partner_car_brand_type.name}" if order.partner_car_brand and order.partner_car_brand_type else '',
                        'rating': float(order.customer_rating) if order.customer_rating else 0,
                        'satisfaction': order.customer_satisfaction,
                        'feedback': order.customer_feedback,
                        'date': pkb_time_local.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    recent_reviews.append(review)

            # Calculate average ratings
            category_ratings = {'service': 0, 'price': 0, 'facility': 0}
            post_service_stats = {'rating': 0, 'count': 0}
            if rated_orders:
                service_total = price_total = facility_total = 0
                initial_rating_count = 0
                rating_count = 0
                post_service_rating_total = 0
                post_service_count = 0
                
                for order in rated_orders:
                    if order.detailed_ratings:
                        try:
                            ratings = order.detailed_ratings
                            if isinstance(ratings, str):
                                ratings = json.loads(ratings)
                            service_total += ratings.get('service_rating', 0)
                            price_total += ratings.get('price_rating', 0)
                            facility_total += ratings.get('facility_rating', 0)
                            initial_rating_count += 1
                        except (json.JSONDecodeError, AttributeError):
                            continue

                    # Hitung post service rating (H+3)
                    if order.post_service_rating:
                        try:
                            rating_value = float(order.post_service_rating)
                            post_service_rating_total += rating_value
                            post_service_count += 1
                        except (ValueError, TypeError):
                            continue

                 # Calculate averages
                if initial_rating_count > 0:
                    category_ratings = {
                        'service': round(service_total / initial_rating_count, 2),
                        'price': round(price_total / initial_rating_count, 2),
                        'facility': round(facility_total / initial_rating_count, 2)
                    }

                if post_service_count > 0:
                    post_service_stats = {
                        'rating': round(post_service_rating_total / post_service_count, 2),
                        'count': post_service_count
                    }

            result = {
                'overview': {
                    'total_services': total_services,
                    'total_reviews': total_reviews,
                    'review_rate': round(total_reviews / total_services * 100, 2) if total_services > 0 else 0,
                    'average_rating': round(sum(float(order.customer_rating) for order in rated_orders if order.customer_rating) / total_reviews, 2) if total_reviews > 0 else 0
                },
                'rating_distribution': rating_distribution,
                'satisfaction_distribution': satisfaction_distribution,
                'category_ratings': category_ratings,
                'post_service_stats': post_service_stats,
                'recent_reviews': recent_reviews,
                'time_period': date_range
            }

            return {
                'status': 'success',
                'data': result
            }

        except Exception as e:
            _logger.error(f"Error in get_rating_dashboard: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    @route('/web/rating/reviews', type='json', auth='public', methods=['POST'], csrf=False)
    def get_all_reviews(self, **kwargs):
        """Get all reviews with pagination"""
        try:
            params = kwargs
            _logger.info(f"Received params: {params}")
            
            dbname = params.get('db')
            page = int(params.get('page', 1))
            limit = int(params.get('limit', 10))
            search = params.get('search', '')
            sort_by = params.get('sort_by', 'date')
            sort_order = params.get('sort_order', 'desc')
            date_range = params.get('date_range', 'all')
            rating_filter = params.get('rating')
            satisfaction_filter = params.get('satisfaction')
            date_start = params.get('date_start')
            date_end = params.get('date_end')
            
            service_rating = params.get('service_rating')
            price_rating = params.get('price_rating')
            facility_rating = params.get('facility_rating')

            if not dbname:
                return {'status': 'error', 'message': 'Database name is required'}

            SaleOrder = request.env['sale.order'].sudo()
            tz = pytz.timezone('Asia/Jakarta')
            
            # Build base domain untuk mencari order dengan rating
            domain = [
                ('state', 'in', ['sale', 'done']),
                ('customer_rating', '!=', False), 
            ]

            _logger.info(f"Base domain: {domain}")

            # Handle date range
            now = datetime.now()
            now_local = tz.localize(now)
            
            if date_range != 'all':
                if date_range == 'custom' and date_start and date_end:
                    try:
                        start_dt = datetime.strptime(date_start, '%Y-%m-%d')
                        end_dt = datetime.strptime(date_end, '%Y-%m-%d')
                        
                        start_dt = start_dt.replace(hour=0, minute=0, second=0)
                        end_dt = end_dt.replace(hour=23, minute=59, second=59)
                        
                        start_dt = tz.localize(start_dt)
                        end_dt = tz.localize(end_dt)
                    except ValueError:
                        return {'status': 'error', 'message': 'Invalid date format'}
                else:
                    if date_range == 'today':
                        start_dt = now_local.replace(hour=0, minute=0, second=0)
                        end_dt = now_local
                    elif date_range == 'week':
                        start_dt = (now_local - timedelta(days=now_local.weekday())).replace(hour=0, minute=0, second=0)
                        end_dt = now_local
                    elif date_range == 'month':
                        start_dt = now_local.replace(day=1, hour=0, minute=0, second=0)
                        end_dt = now_local
                    elif date_range == 'year':
                        start_dt = now_local.replace(month=1, day=1, hour=0, minute=0, second=0)
                        end_dt = now_local

                if 'start_dt' in locals() and 'end_dt' in locals():
                    start_utc = start_dt.astimezone(pytz.UTC)
                    end_utc = end_dt.astimezone(pytz.UTC)
                    
                    domain.extend([
                        ('sa_cetak_pkb', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                        ('sa_cetak_pkb', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
                    ])

            # Add rating filter
            if rating_filter:
                domain.append(('customer_rating', '=', str(rating_filter)))

            # Add satisfaction filter
            if satisfaction_filter:
                domain.append(('customer_satisfaction', '=', satisfaction_filter))

            # Add search filter if exists
            if search:
                domain.extend(['|', '|',
                    ('partner_id.name', 'ilike', search),
                    ('partner_car_id.number_plate', 'ilike', search),
                    ('name', 'ilike', search)
                ])

            # Calculate total before detailed ratings filter
            total_records = SaleOrder.search_count(domain)
            
            # Sort configuration
            sort_mapping = {
                'date': 'sa_cetak_pkb',
                'pkb_date': 'sa_cetak_pkb',
                'order_date': 'create_date',
                'rating': 'customer_rating',
                'customer': 'partner_id.name',
                'order': 'name'
            }
            sort_field = sort_mapping.get(sort_by, 'sa_cetak_pkb')

            # Get paginated records
            offset = (page - 1) * limit
            orders = SaleOrder.search(domain, order=f"{sort_field} {sort_order}", limit=limit, offset=offset)
            
            _logger.info(f"Retrieved {len(orders)} orders")

            # Process reviews
            reviews = []
            for order in orders:
                try:
                    # Get timestamps
                    pkb_date = order.sa_cetak_pkb.strftime('%Y-%m-%d %H:%M:%S') if order.sa_cetak_pkb else None
                    order_date = order.create_date.strftime('%Y-%m-%d %H:%M:%S') if order.create_date else None

                    # Get category ratings
                    category_ratings = {'service': 0, 'price': 0, 'facility': 0}
                    if order.detailed_ratings:
                        try:
                            ratings = order.detailed_ratings
                            if isinstance(ratings, str):
                                ratings = json.loads(ratings)
                            category_ratings = {
                                'service': float(ratings.get('service_rating', 0)),
                                'price': float(ratings.get('price_rating', 0)),
                                'facility': float(ratings.get('facility_rating', 0))
                            }
                        except (json.JSONDecodeError, AttributeError) as e:
                            _logger.warning(f"Error parsing ratings for order {order.id}: {str(e)}")
                    
                    # Apply category rating filters
                    if service_rating and category_ratings['service'] != float(service_rating):
                        continue
                    if price_rating and category_ratings['price'] != float(price_rating):
                        continue
                    if facility_rating and category_ratings['facility'] != float(facility_rating):
                        continue

                    review = {
                        'id': order.id,
                        'order_name': order.name,
                        'customer_name': order.partner_id.name if order.partner_id else '',
                        'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
                        'car_info': f"{order.partner_car_brand.name} {order.partner_car_brand_type.name}" if order.partner_car_brand and order.partner_car_brand_type else '',
                        'rating': float(order.customer_rating) if order.customer_rating else 0,
                        'category_ratings': category_ratings,
                        'satisfaction': order.customer_satisfaction,
                        'feedback': order.customer_feedback,
                        'pkb_date': pkb_date,
                        'order_date': order_date,
                        'has_response': bool(order.complaint_action),
                        'response': order.complaint_action if order.complaint_action else None
                    }
                    reviews.append(review)

                except Exception as e:
                    _logger.error(f"Error processing order {order.id}: {str(e)}")
                    continue

            return {
                'status': 'success',
                'data': {
                    'reviews': reviews,
                    'pagination': {
                        'total_records': total_records,
                        'total_pages': ceil(total_records / limit),
                        'current_page': page,
                        'limit': limit,
                        'has_next': page < ceil(total_records / limit),
                        'has_previous': page > 1
                    },
                    'filters': {
                        'date_range': date_range,
                        'date_type': 'pkb',
                        'search': search,
                        'sort_by': sort_by,
                        'sort_order': sort_order,
                        'rating': rating_filter,
                        'satisfaction': satisfaction_filter,
                        'service_rating': service_rating,
                        'price_rating': price_rating,
                        'facility_rating': facility_rating
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_all_reviews: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def _check_category_rating(self, order, category, target_rating):
        """
        Helper method untuk mengecek apakah rating kategori tertentu sesuai dengan filter
        """
        if not target_rating:
            return True
            
        try:
            if not order.detailed_ratings:
                return False
                
            ratings = order.detailed_ratings
            if isinstance(ratings, str):
                ratings = json.loads(ratings)
                
            actual_rating = ratings.get(category, 0)
            return float(actual_rating) == float(target_rating)
            
        except (json.JSONDecodeError, AttributeError, ValueError):
            return False
        
    # REMINDER API
    @route('/web/reminder/dashboard', type='json', auth='public', methods=['POST'])
    def get_reminder_dashboard(self, **kwargs):
        try:
            # Get params directly from kwargs since it's already the params object
            page = int(kwargs.get('page', 1))
            limit = int(kwargs.get('limit', 10))
            date_range = kwargs.get('date_range', 'all')
            search = kwargs.get('search', '').strip()
            reminder_status = kwargs.get('reminder_status', 'all')
             # Add custom date filter parameters
            custom_date_start = kwargs.get('date_start')
            custom_date_end = kwargs.get('date_end')

            # Validate limit
            if limit not in [10, 25, 50]:
                limit = 10

            _logger.info(f"""
            Received parameters:
            - Page: {page}
            - Limit: {limit}
            - Date Range: {date_range}
            - Search: {search}
            - Status: {reminder_status}
            """)

            SaleOrder = request.env['sale.order'].sudo()
            tz = pytz.timezone('Asia/Jakarta')
            today = datetime.now(tz).date()
            three_days_ago = today - timedelta(days=3)

            # Pending reminders domain (H+3)
            pending_domain = [
                ('date_completed', '>=', three_days_ago.strftime('%Y-%m-%d 00:00:00')),
                ('date_completed', '<=', three_days_ago.strftime('%Y-%m-%d 23:59:59')),
                ('state', 'in', ['sale', 'done']),
                ('reminder_sent', '=', False)
            ]

            # Base domain for history
            history_domain = [
                ('state', 'in', ['sale', 'done']),
                ('date_completed', '!=', False)
            ]

            # Add reminder status filter
            if reminder_status != 'all':
                if reminder_status == 'not_reminded':
                    history_domain.append(('reminder_sent', '=', False))
                elif reminder_status == 'reminded':
                    history_domain.append(('reminder_sent', '=', True))
                elif reminder_status == 'responded':
                    history_domain.extend([
                        ('reminder_sent', '=', True),
                        ('post_service_rating', '!=', False)
                    ])

            # Handle date filtering
            if custom_date_start and custom_date_end:
                # Parse the custom dates
                try:
                    date_start = datetime.strptime(custom_date_start, '%Y-%m-%d').date()
                    date_end = datetime.strptime(custom_date_end, '%Y-%m-%d').date()
                    
                    # Add date range filter with custom dates
                    history_domain.extend([
                        ('date_completed', '>=', date_start.strftime('%Y-%m-%d 00:00:00')),
                        ('date_completed', '<=', date_end.strftime('%Y-%m-%d 23:59:59'))
                    ])
                except ValueError as e:
                    _logger.error(f"Invalid date format: {str(e)}")
                    return {'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD'}
            else:
                # Original date range filter
                if date_range and date_range != 'all':
                    if date_range == 'today':
                        date_start = today
                        date_end = today
                    elif date_range == 'week':
                        date_start = today - timedelta(days=today.weekday())
                        date_end = today
                    elif date_range == 'month':
                        date_start = today.replace(day=1)
                        date_end = today
                    elif date_range == 'year':
                        date_start = today.replace(month=1, day=1)
                        date_end = today

                    history_domain.extend([
                        ('date_completed', '>=', date_start.strftime('%Y-%m-%d 00:00:00')),
                        ('date_completed', '<=', date_end.strftime('%Y-%m-%d 23:59:59'))
                    ])

            # Add search filter if search term is provided
            if search:
                search_domain = ['|', '|', '|',
                    ('name', 'ilike', search),
                    ('partner_id.name', 'ilike', search),
                    ('partner_car_id.number_plate', 'ilike', search),
                    ('partner_id.mobile', 'ilike', search)
                ]
                history_domain = ['&'] + history_domain + search_domain

            _logger.info(f"Final history domain: {history_domain}")

             # Get total count for pagination
            total_count = SaleOrder.search_count(history_domain)
            total_pages = ceil(total_count / limit)
            offset = (page - 1) * limit

            _logger.info(f"Pagination: total={total_count}, pages={total_pages}, offset={offset}, limit={limit}")

            # Get paginated records
            history_orders = SaleOrder.search(
                history_domain,
                order='date_completed desc',
                limit=limit,
                offset=offset
            )

            # Tambahkan perhitungan rata-rata post service rating
            rated_orders = SaleOrder.search([('post_service_rating', '!=', False)])
            post_service_total = sum(float(order.post_service_rating) for order in rated_orders if order.post_service_rating)
            post_service_count = len(rated_orders)

            result = {
                'pending_reminders': [{
                    'id': order.id,
                    'name': order.name,
                    'customer_name': order.partner_id.name,
                    'customer_phone': order.partner_id.mobile or order.partner_id.phone,  # Added phone fallback
                    'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
                    'completion_date': order.date_completed.strftime('%Y-%m-%d %H:%M:%S') if order.date_completed else '',
                    'service_advisors': [{'id': sa.id, 'name': sa.name} for sa in order.service_advisor_id],  # Added SA
                    'whatsapp_link': self._generate_whatsapp_link(order),
                } for order in SaleOrder.search(pending_domain)],
                
                'reminder_history': [{
                    'id': order.id,
                    'name': order.name,
                    'customer_name': order.partner_id.name,
                    'customer_phone': order.partner_id.mobile or order.partner_id.phone,  # Added phone fallback
                    'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
                    'completion_date': order.date_completed.strftime('%Y-%m-%d %H:%M:%S') if order.date_completed else '',
                    'reminder_date': order.reminder_sent_date.strftime('%Y-%m-%d %H:%M:%S') if order.reminder_sent_date else None,
                    'reminder_sent': bool(order.reminder_sent),
                    'has_feedback': bool(order.post_service_rating),
                    'rating': order.post_service_rating,
                    'feedback': order.post_service_feedback,  # Tambahkan feedback
                    'service_advisors': [{'id': sa.id, 'name': sa.name} for sa in order.service_advisor_id],  # Added SA
                    'whatsapp_link': self._generate_whatsapp_link(order)
                } for order in history_orders],

                'pagination': {
                    'total_records': total_count,
                    'total_pages': total_pages,
                    'current_page': page,
                    'limit': limit
                },

                'statistics': {
                    'total_pending': SaleOrder.search_count(pending_domain),
                    'total_reminders_sent': SaleOrder.search_count([('reminder_sent', '=', True)]),
                    'total_feedback_received': SaleOrder.search_count([('post_service_rating', '!=', False)]),
                    'response_rate': round(
                        (SaleOrder.search_count([('post_service_rating', '!=', False)]) / 
                        SaleOrder.search_count([('reminder_sent', '=', True)]) * 100)
                        if SaleOrder.search_count([('reminder_sent', '=', True)]) > 0 else 0,
                        2
                    ),
                    'average_post_service_rating': round(post_service_total / post_service_count, 2) if post_service_count > 0 else 0
                }
            }

            return {'status': 'success', 'data': result}

        except Exception as e:
            _logger.error(f"Error in get_reminder_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    # def _generate_feedback_token(self, order):
    #     try:
    #         # Ambil data yang akan dienkripsi
    #         data = {
    #             'order_id': order.id,
    #             'database': request.env.cr.dbname,
    #             'timestamp': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #         }
            
    #         # Enkripsi data menggunakan secret key
    #         secret_key = request.env['ir.config_parameter'].sudo().get_param('database.secret')
    #         encrypted = self._encrypt_data(data, secret_key)
            
    #         # Convert ke base64 agar aman di URL
    #         token = base64.urlsafe_b64encode(encrypted).decode()
            
    #         return token
            
    #     except Exception as e:
    #         _logger.error(f"Error generating token: {str(e)}")
    #         return None
        
    # def _generate_whatsapp_link(self, order):
    #     try:
    #         if not order.partner_id.mobile:
    #             return None

    #         # Clean phone number
    #         phone = order.partner_id.mobile
    #         clean_phone = ''.join(filter(str.isdigit, phone))
    #         if clean_phone.startswith('0'):
    #             clean_phone = '62' + clean_phone[1:]
    #         elif not clean_phone.startswith('62'):
    #             clean_phone = '62' + clean_phone

    #         # Generate encrypted token
    #         token = self._generate_feedback_token(order)
    #         if not token:
    #             return None

    #         # Generate message
    #         base_url = "https://pitscore.pitcar.co.id"
    #         feedback_url = f"{base_url}/feedback/{token}"
            
    #         message = f"""Halo {order.partner_id.name},

    # Terima kasih telah mempercayakan servis kendaraan {order.partner_car_id.number_plate if order.partner_car_id else ''} di bengkel kami.

    # Bagaimana kondisi kendaraan Anda setelah 3 hari servis? Mohon berikan penilaian Anda melalui link berikut:
    # {feedback_url}

    # Terima kasih atas feedback Anda!"""

    #         return f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"
            
    #     except Exception as e:
    #         _logger.error(f"Error generating WhatsApp link: {str(e)}")
    #         return None
        
    # def _generate_whatsapp_link(self, order):
    #     """Helper function to generate WhatsApp link"""
    #     try:
    #         if not order.partner_id.mobile:
    #             return None

    #         # Clean phone number
    #         phone = order.partner_id.mobile
    #         clean_phone = ''.join(filter(str.isdigit, phone))
    #         if clean_phone.startswith('0'):
    #             clean_phone = '62' + clean_phone[1:]
    #         elif not clean_phone.startswith('62'):
    #             clean_phone = '62' + clean_phone

    #         # Get current database
    #         database = request.env.cr.dbname

    #         # Generate message with database parameter
    #         base_url = "https://pitscore.pitcar.co.id"
    #         feedback_url = f"{base_url}/feedback/{order.id}?db={database}"
            
    #         message = f"""Halo {order.partner_id.name},

    # Terima kasih telah mempercayakan servis kendaraan {order.partner_car_id.number_plate if order.partner_car_id else ''} di bengkel kami.

    # Bagaimana kondisi kendaraan Anda setelah 3 hari servis? Mohon berikan penilaian Anda melalui link berikut:
    # {feedback_url}

    # Terima kasih atas feedback Anda!"""

    #         return f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"
        
    #     except Exception as e:
    #         _logger.error(f"Error generating WhatsApp link: {str(e)}")
    #         return None

    def _get_base62_chars(self):
        """Get base62 character set"""
        return "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    def _encode_base62(self, num):
        """Convert number to base62 string"""
        chars = self._get_base62_chars()
        base = len(chars)
        
        if num == 0:
            return chars[0]
        
        arr = []
        while num:
            num, rem = divmod(num, base)
            arr.append(chars[rem])
        arr.reverse()
        return ''.join(arr)

    def _decode_base62(self, string):
        """Convert base62 string to number"""
        chars = self._get_base62_chars()
        base = len(chars)
        num = 0

        for char in string:
            num = num * base + chars.index(char)
        
        return num

    def _encode_id(self, order_id):
        """Encode order ID dengan signature pendek"""
        try:
            # Convert order_id to base62
            base62_id = self._encode_base62(order_id)
            
            # Generate signature (4 karakter)
            signature = hmac.new(
                self._get_secret_key().encode(),
                base62_id.encode(),
                hashlib.sha256
            ).hexdigest()[:4]  # Ambil 4 karakter pertama
            
            # Return combined string
            return f"{base62_id}.{signature}"
        except Exception as e:
            _logger.error(f"Encoding error: {str(e)}")
            return None

    def _decode_id(self, encoded_str):
        """Decode dan validasi encoded ID"""
        try:
            # Split encoded data dan signature
            base62_id, signature = encoded_str.split('.')
            
            # Verify signature
            expected_sig = hmac.new(
                self._get_secret_key().encode(),
                base62_id.encode(),
                hashlib.sha256
            ).hexdigest()[:4]
            
            if not hmac.compare_digest(signature, expected_sig):
                _logger.warning("Invalid signature detected")
                return None
                
            # Decode dan return order ID
            return self._decode_base62(base62_id)
        except Exception as e:
            _logger.error(f"Decoding error: {str(e)}")
            return None


    # def _encode_id(self, order_id):
    #     """Encode order ID dengan timestamp dan signature yang lebih pendek"""
    #     try:
    #         # Convert order_id to base62
    #         base62_id = self._encode_base62(order_id)
            
    #         # Add timestamp (dalam menit, bukan detik, untuk mempersingkat)
    #         timestamp = int(time.time() / 60)  # Convert ke menit
    #         base62_ts = self._encode_base62(timestamp)
            
    #         # Combine data
    #         combined = f"{base62_id}.{base62_ts}"
            
    #         # Generate signature (menggunakan 8 karakter pertama saja)
    #         signature = hmac.new(
    #             self._get_secret_key().encode(),
    #             combined.encode(),
    #             hashlib.sha256
    #         ).hexdigest()[:8]  # Ambil 8 karakter pertama saja
            
    #         # Return combined string
    #         return f"{combined}.{signature}"
    #     except Exception as e:
    #         _logger.error(f"Encoding error: {str(e)}")
    #         return None

    # def _decode_id(self, encoded_str):
    #     """Decode dan validasi encoded ID yang lebih pendek"""
    #     try:
    #         # Split components
    #         components = encoded_str.split('.')
    #         if len(components) != 3:
    #             raise ValueError("Invalid format")
                
    #         base62_id, base62_ts, signature = components
            
    #         # Verify signature
    #         combined = f"{base62_id}.{base62_ts}"
    #         expected_sig = hmac.new(
    #             self._get_secret_key().encode(),
    #             combined.encode(),
    #             hashlib.sha256
    #         ).hexdigest()[:8]  # Bandingkan 8 karakter pertama
            
    #         if not hmac.compare_digest(signature, expected_sig):
    #             _logger.warning("Invalid signature detected")
    #             return None
            
    #         # Decode timestamp dan cek expired
    #         timestamp = self._decode_base62(base62_ts) * 60  # Convert kembali ke detik
    #         if time.time() - timestamp > 7 * 24 * 3600:  # 7 hari
    #             _logger.warning("Expired token detected")
    #             return None
            
    #         # Decode dan return order ID
    #         return self._decode_base62(base62_id)
    #     except Exception as e:
    #         _logger.error(f"Decoding error: {str(e)}")
    #         return None

#     def _generate_whatsapp_link(self, order):
#         """Helper function to generate WhatsApp link"""
#         try:
#             # Check for either mobile or phone number
#             phone = order.partner_id.mobile or order.partner_id.phone
#             if not phone:
#                 return None
                
#             # Clean phone number
#             clean_phone = ''.join(filter(str.isdigit, phone))
#             if clean_phone.startswith('0'):
#                 clean_phone = '62' + clean_phone[1:]
#             elif not clean_phone.startswith('62'):
#                 clean_phone = '62' + clean_phone

#             # Generate encoded order ID
#             encoded_id = self._encode_id(order.id)
#             if not encoded_id:
#                 return None

#             # Get current database
#             database = request.env.cr.dbname

#             # Generate message with encoded ID
#             base_url = "https://pitscore.pitcar.co.id"
#             feedback_url = f"{base_url}/feedback/{encoded_id}?db={database}"

#             # Get SA names
#             sa_names = ""
#             if order.service_advisor_id:
#                 sa_names = ", ".join([sa.user_id.name for sa in order.service_advisor_id if sa.user_id])
#                 if not sa_names:
#                     _logger.warning(f"No SA names found for order {order.id}")
            
#             message = f"""Halo, *{order.partner_id.name}*.
# Saya {sa_names} dari Pitcar,

# Terima kasih telah mempercayakan servis mobil {order.partner_car_id.number_plate if order.partner_car_id else ''} di Pitcar.

# Bagaimana kondisi kendaraan Anda setelah servis? Mohon berikan penilaian dan masukan melalui link berikut ya:
# {feedback_url}

# Oh iya, sekalian Mincar mau mengingatkan untuk garansi servisnya:
# - Garansi servis: 2 minggu
# - Garansi sparepart: 3 bulan (kecuali part dari luar ya)

# Terima kasih atas kepercayaan Anda kepada Pitcar!"""

#             return f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"
            
#         except Exception as e:
#             _logger.error(f"Error generating WhatsApp link: {str(e)}")
#             return None

    def _get_whatsapp_template(self, database, order):
        """Get WhatsApp message template based on database"""
        base_url = "https://pitscore.pitcar.co.id"
        encoded_id = self._encode_id(order.id)
        
        # Standardize database name handling
        db_mapping = {
            'pitcar1': 'Pitcar1',
            'pitcar.bodyrepair': 'pitcar.bodyrepair'
        }
        
        # Map standardized database name for URL
        url_db = db_mapping.get(database.lower(), database)
        feedback_url = f"{base_url}/feedback/{encoded_id}?db={url_db}"
        
        # Get SA names
        sa_names = ""
        if order.service_advisor_id:
            sa_names = ", ".join([sa.user_id.name for sa in order.service_advisor_id if sa.user_id])
            if not sa_names:
                _logger.warning(f"No SA names found for order {order.id}")

        templates = {
            'pitcar1': f"""Ganti oli mesin rutin selalu,
Ban mobil dirotasi dengan teliti.
Servis di Pitcar sudah berlalu,
Bagaimana rasanya, yuk nilai di sini! 

Hai, *{order.partner_id.name}*!
Saya {sa_names} dari Pitcar. Bagaimana performa mobil {order.partner_car_id.number_plate if order.partner_car_id else ''} setelah servis? 

Mohon luangkan waktu sebentar untuk memberikan penilaian melalui link berikut ya:
{feedback_url}

*Info Garansi*
- Servis: 2 minggu
- Sparepart: 3 bulan*
*kecuali part dari luar

Terima kasih atas kepercayaan Anda kepada Pitcar! 

Best regards,
Tim Pitcar""",

            'pitcar.bodyrepair': f"""Poles body sampai mengkilat,
Dempul halus tanpa celah.
Mobil sudah tampil hebat,
Yuk beri rating sekarang ya! 

Hai, *{order.partner_id.name}*!
Saya Wylda dari Pitcar. Terima kasih telah mempercayakan perbaikan mobil {order.partner_car_id.number_plate if order.partner_car_id else ''} kepada Pitcar Body Repair.

Yuk, berikan penilaian Anda melalui link berikut:
{feedback_url}

*Info Garansi*
- Garansi Pengecatan: 3 bulan
- Hubungi kami kapan saja jika ada keluhan

Terima kasih atas kepercayaan Anda kepada Pitcar! 

Best regards,
Tim Pitcar Body Repair"""
        }

        # Default template jika database tidak dikenali
        default_template = f"""
Ganti oli mesin rutin selalu,
Ban mobil dirotasi dengan teliti.
Servis di Pitcar sudah berlalu,
Bagaimana rasanya, yuk nilai di sini! 

Hai, *{order.partner_id.name}*!
Saya {sa_names} dari Pitcar. Bagaimana performa mobil {order.partner_car_id.number_plate if order.partner_car_id else ''} setelah servis? 

Mohon luangkan waktu sebentar untuk memberikan penilaian melalui link berikut ya:
{feedback_url}

*Info Garansi*
- Servis: 2 minggu
- Sparepart: 3 bulan*
   *kecuali part dari luar
   
Terima kasih atas kepercayaan Anda kepada Pitcar! 

Best regards,
Tim Pitcar"""

        # Get template using lowercase key
        template = templates.get(database.lower(), default_template)
        
        # Log untuk debugging
        _logger.info(f"Database name: {database}")
        _logger.info(f"Mapped DB name: {url_db}")
        _logger.info(f"Generated URL: {feedback_url}")
        
        return template

    def _generate_whatsapp_link(self, order):
        """Generate WhatsApp link with dynamic message based on database"""
        try:
            # Check for either mobile or phone number
            phone = order.partner_id.mobile or order.partner_id.phone
            if not phone:
                return None
                
            # Clean phone number
            clean_phone = ''.join(filter(str.isdigit, phone))
            if clean_phone.startswith('0'):
                clean_phone = '62' + clean_phone[1:]
            elif not clean_phone.startswith('62'):
                clean_phone = '62' + clean_phone

            # Get current database name
            database = request.env.cr.dbname.strip()  # Remove any whitespace
            
            # Log untuk debugging
            _logger.info(f"Current database: {database}")

            # Get message template based on database
            message = self._get_whatsapp_template(database, order)

            return f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"
            
        except Exception as e:
            _logger.error(f"Error generating WhatsApp link: {str(e)}")
            return None

        
    @route('/web/reminder/mark-sent', type='json', auth='public', methods=['POST'])
    def mark_reminders_sent(self, **kwargs):
        """Mark orders as reminder sent"""
        try:
            # Log raw input
            _logger.info(f"Raw input: {kwargs}")
            
            # Extract order_ids directly from kwargs
            order_ids = kwargs.get('order_ids', [])
            
            _logger.info(f"Extracted order_ids: {order_ids}")

            if not order_ids:
                return {
                    'status': 'error',
                    'message': 'Order IDs are required'
                }

            SaleOrder = request.env['sale.order'].sudo()
            orders = SaleOrder.browse(order_ids)

            if not orders.exists():
                return {
                    'status': 'error',
                    'message': 'No valid orders found'
                }

            # Set current time with timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Update orders
            for order in orders:
                order.write({
                    'reminder_sent': True,
                    'reminder_sent_date': now.strftime('%Y-%m-%d %H:%M:%S'),
                    'feedback_link_expiry': (now + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                })

            return {
                'status': 'success',
                'message': f'{len(orders)} reminder(s) marked as sent',
                'data': {
                    'updated_orders': order_ids,
                    'reminder_date': now.strftime('%Y-%m-%d %H:%M:%S')
                }
            }

        except Exception as e:
            _logger.error(f"Error in mark_reminders_sent: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    # Backend endpoint untuk mendapatkan detail feedback
    # @route('/web/after-service/feedback/details', type='json', auth='none', methods=['POST'])
    # def get_feedback_details(self, **kwargs):
    #     try:
    #         # Pastikan environment baru dibuat untuk setiap request
    #         env = request.env(context=request.context)
            
    #         # Log untuk debug
    #         _logger.info('Processing request without session')
            
    #         # Ambil params
    #         params = kwargs
    #         order_id = params.get('order_id')
    #         database = params.get('db')

    #         _logger.info(f'Params received: db={database}, order_id={order_id}')

    #         if not all([order_id, database]):
    #             return {'status': 'error', 'message': 'Missing required parameters'}

    #         # Set database untuk request ini
    #         if hasattr(request, 'session'):
    #             request.session.db = database
    #             _logger.info(f'Database set in session: {database}')

    #         # Gunakan sudo() untuk bypass security
    #         SaleOrder = env['sale.order'].sudo()
    #         order = SaleOrder.browse(int(order_id))

    #         if not order.exists():
    #             return {'status': 'error', 'message': 'Order not found'}


    #         # Pengecekan expiry
    #         if order.feedback_link_expiry and isinstance(order.feedback_link_expiry, fields.Datetime):
    #             if fields.Datetime.now() > order.feedback_link_expiry:
    #                 return {'status': 'error', 'message': 'Feedback link expired'}

    #         completion_date = order.date_completed.strftime('%Y-%m-%d') if order.date_completed else None

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'name': order.name,
    #                 'completion_date': completion_date,
    #                 'customer_name': order.partner_id.name if order.partner_id else '',
    #                 'vehicle': {
    #                     'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
    #                     'brand': order.partner_car_brand.name if order.partner_car_brand else '',
    #                     'type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
    #                 },
    #                 'services': [{
    #                     'name': line.product_id.name if line.product_id else '',
    #                     'quantity': line.product_uom_qty,
    #                 } for line in order.order_line if line.product_id],
    #                  'has_rated': bool(order.post_service_rating),  # Tambahkan has_rated
    #                 'rating': order.post_service_rating,           # Tambahkan current rating
    #                 'feedback': order.post_service_feedback        # Tambahkan current feedback
    #             }
    #         }
    #     except Exception as e:
    #         _logger.error(f"Error in get_feedback_details: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}


    # @route('/web/after-service/feedback/submit', type='json', auth='public', methods=['POST'])
    # def submit_feedback(self, **kwargs):
    #     """Submit feedback for order"""
    #     try:
    #         params = kwargs
    #         order_id = params.get('order_id')
    #         rating = params.get('rating')
    #         feedback = params.get('feedback')

    #         if not all([order_id, rating]):
    #             return {'status': 'error', 'message': 'Missing required fields'}

    #         SaleOrder = request.env['sale.order'].sudo()
    #         order = SaleOrder.browse(int(order_id))

    #         if not order.exists():
    #             return {'status': 'error', 'message': 'Order not found'}

    #         # Perbaikan pengecekan expiry
    #         if order.feedback_link_expiry and isinstance(order.feedback_link_expiry, fields.Datetime):
    #             if fields.Datetime.now() > order.feedback_link_expiry:
    #                 return {'status': 'error', 'message': 'Feedback link expired'}

    #         order.write({
    #             'post_service_rating': str(rating),
    #             'post_service_feedback': feedback
    #         })

    #         return {
    #             'status': 'success',
    #             'message': 'Thank you for your feedback!'
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in submit_feedback: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}

    #  Endpoint untuk CORS preflight requests
    # @http.route([
    #     '/web/after-service/feedback/details',
    #     '/web/after-service/feedback/submit'
    # ], type='http', auth='none', methods=['OPTIONS'], csrf=False)
    # def options(self):
    #     headers = {
    #         'Access-Control-Allow-Origin': '*',
    #         'Access-Control-Allow-Methods': 'POST, OPTIONS',
    #         'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With',
    #         'Access-Control-Max-Age': '86400',  # 24 hours
    #     }
    #     return Response(status=200, headers=headers)

    # @http.route('/web/after-service/feedback/details', type='http', auth='none', 
    #             methods=['POST'], csrf=False)
    # def get_feedback_details(self, **kwargs):
    #     headers = {
    #         'Content-Type': 'application/json',
    #         'Access-Control-Allow-Origin': '*',
    #     }
        
    #     try:
    #         # Parse body JSON
    #         body = json.loads(request.httprequest.data.decode())
    #         params = body.get('params', {})
            
    #         order_id = params.get('order_id')
    #         db = params.get('db')
            
    #         if not all([order_id, db]):
    #             return Response(
    #                 json.dumps({
    #                     'jsonrpc': '2.0',
    #                     'id': None,
    #                     'result': {
    #                         'status': 'error',
    #                         'message': 'Missing required parameters'
    #                     }
    #                 }),
    #                 status=400,
    #                 headers=headers
    #             )

    #         order = request.env['sale.order'].sudo().browse(int(order_id))
            
    #         if not order.exists():
    #             return Response(
    #                 json.dumps({
    #                     'jsonrpc': '2.0',
    #                     'id': None,
    #                     'result': {
    #                         'status': 'error',
    #                         'message': 'Order not found'
    #                     }
    #                 }),
    #                 status=404,
    #                 headers=headers
    #             )

    #         data = {
    #             'status': 'success',
    #             'data': {
    #                 'name': order.name,
    #                 'customer_name': order.partner_id.name if order.partner_id else '',
    #                 'vehicle': {
    #                     'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
    #                     'brand': order.partner_car_brand.name if order.partner_car_brand else '',
    #                     'type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
    #                 },
    #                 'has_rated': bool(order.post_service_rating),
    #                 'rating': order.post_service_rating,
    #                 'feedback': order.post_service_feedback
    #             }
    #         }

    #         return Response(
    #             json.dumps({
    #                 'jsonrpc': '2.0',
    #                 'id': None,
    #                 'result': data
    #             }),
    #             status=200,
    #             headers=headers
    #         )

    #     except Exception as e:
    #         _logger.error("Error in get_feedback_details: %s", str(e), exc_info=True)
    #         return Response(
    #             json.dumps({
    #                 'jsonrpc': '2.0',
    #                 'id': None,
    #                 'result': {
    #                     'status': 'error',
    #                     'message': str(e)
    #                 }
    #             }),
    #             status=500,
    #             headers=headers
    #         )

    # @http.route('/web/after-service/feedback/submit', type='http', auth='none', 
    #             methods=['POST'], csrf=False)
    # def submit_feedback(self, **kwargs):
    #     headers = {
    #         'Content-Type': 'application/json',
    #         'Access-Control-Allow-Origin': '*',
    #     }
        
    #     try:
    #         body = json.loads(request.httprequest.data.decode())
    #         params = body.get('params', {})
            
    #         order_id = params.get('order_id')
    #         rating = params.get('rating')
    #         feedback = params.get('feedback')
    #         db = params.get('db')

    #         if not all([order_id, rating, db]):
    #             return Response(
    #                 json.dumps({
    #                     'jsonrpc': '2.0',
    #                     'id': None,
    #                     'result': {
    #                         'status': 'error',
    #                         'message': 'Missing required fields'
    #                     }
    #                 }),
    #                 status=400,
    #                 headers=headers
    #             )

    #         order = request.env['sale.order'].sudo().browse(int(order_id))
            
    #         if not order.exists():
    #             return Response(
    #                 json.dumps({
    #                     'jsonrpc': '2.0',
    #                     'id': None,
    #                     'result': {
    #                         'status': 'error',
    #                         'message': 'Order not found'
    #                     }
    #                 }),
    #                 status=404,
    #                 headers=headers
    #             )

    #         order.write({
    #             'post_service_rating': str(rating),
    #             'post_service_feedback': feedback or ''
    #         })

    #         return Response(
    #             json.dumps({
    #                 'jsonrpc': '2.0',
    #                 'id': None,
    #                 'result': {
    #                     'status': 'success',
    #                     'message': 'Feedback submitted successfully'
    #                 }
    #             }),
    #             status=200,
    #             headers=headers
    #         )

    #     except Exception as e:
    #         _logger.error("Error in submit_feedback: %s", str(e), exc_info=True)
    #         return Response(
    #             json.dumps({
    #                 'jsonrpc': '2.0',
    #                 'id': None,
    #                 'result': {
    #                     'status': 'error',
    #                     'message': str(e)
    #                 }
    #             }),
    #             status=500,
    #             headers=headers
    #         )

    @http.route('/web/after-service/feedback/details', type='json', auth='public', methods=['POST'], csrf=False)
    def get_feedback_details(self, **kw):
        try:
            encoded_id = kw.get('order_id')
            database = kw.get('db')
            if not encoded_id:
                return {'status': 'error', 'message': 'Encoded Order ID is required'}
            
            # Decode order ID
            order_id = self._decode_id(encoded_id)
            if not order_id:
                return {'status': 'error', 'message': 'Invalid or expired order ID'}
            
            order = request.env['sale.order'].sudo().browse(int(order_id))
            
            if not order.exists():
                return {
                    'status': 'error',
                    'message': 'Order not found'
                }
            
            return {
                'status': 'success',
                'data': {
                    'name': order.name,
                    'customer_name': order.partner_id.name if order.partner_id else '',
                    'vehicle': {
                        'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
                        'brand': order.partner_car_brand.name if order.partner_car_brand else '',
                        'type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
                    },
                    'has_rated': bool(order.post_service_rating),
                    'rating': order.post_service_rating,
                    'feedback': order.post_service_feedback
                }
            }
            
        except Exception as e:
            _logger.error("Error in get_feedback_details: %s", str(e))
            return {
                'status': 'error',
                'message': str(e)
            }
        
    # @http.route('/web/after-service/feedback/submit', type='json', auth='public', methods=['POST'], csrf=False)
    # def submit_feedback(self, **kw):
    #     try:
    #         order_id = kw.get('order_id')
    #         rating = kw.get('rating')
    #         feedback = kw.get('feedback')
            
    #         if not all([order_id, rating]):
    #             return {
    #                 'status': 'error',
    #                 'message': 'Order ID and rating are required'
    #             }
            
    #         order = request.env['sale.order'].sudo().browse(int(order_id))
            
    #         if not order.exists():
    #             return {
    #                 'status': 'error',
    #                 'message': 'Order not found'
    #             }
            
    #         order.write({
    #             'post_service_rating': str(rating),
    #             'post_service_feedback': feedback or ''
    #         })
            
    #         return {
    #             'status': 'success',
    #             'message': 'Feedback submitted successfully'
    #         }
            
    #     except Exception as e:
    #         _logger.error("Error in submit_feedback: %s", str(e))
    #         return {
    #             'status': 'error',
    #             'message': str(e)
    #         }

    # @http.route('/web/after-service/feedback/details', type='json', auth='public', methods=['POST'], csrf=False)
    # def get_feedback_details(self, **kw):
    #     try:
    #         # Ambil database dan order_id dari parameter
    #         db = kw.get('db')
    #         order_id = kw.get('order_id')
            
    #         if not all([db, order_id]):
    #             return {
    #                 'status': 'error',
    #                 'message': 'Database and Order ID are required'
    #             }
            
    #         # Log untuk debugging
    #         _logger.info(f"Processing request for db: {db}, order_id: {order_id}")
            
    #         order = request.env['sale.order'].sudo().browse(int(order_id))
            
    #         if not order.exists():
    #             return {
    #                 'status': 'error',
    #                 'message': 'Order not found'
    #             }
            
    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'name': order.name,
    #                 'customer_name': order.partner_id.name if order.partner_id else '',
    #                 'vehicle': {
    #                     'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
    #                     'brand': order.partner_car_brand.name if order.partner_car_brand else '',
    #                     'type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
    #                 },
    #                 'has_rated': bool(order.post_service_rating),
    #                 'rating': order.post_service_rating,
    #                 'feedback': order.post_service_feedback
    #             }
    #         }
            
    #     except Exception as e:
    #         _logger.error(f"Error in get_feedback_details: {str(e)}", exc_info=True)
    #         return {
    #             'status': 'error',
    #             'message': str(e)
    #         }
    # @http.route('/web/after-service/feedback/details', type='json', auth='none', methods=['POST'], csrf=False)
    # def get_feedback_details(self, **kw):
    #     try:
    #         # Ambil database dan order_id dari parameter
    #         db_name = kw.get('db')
    #         order_id = kw.get('order_id')

    #         if not db_name or not order_id:
    #             return {
    #                 'status': 'error',
    #                 'message': 'Database name and Order ID are required'
    #             }

    #         # Dapatkan registry untuk database yang diminta
    #         registry = odoo.registry(db_name)
            
    #         # Gunakan registry dengan environment baru
    #         with registry.cursor() as cr:
    #             # Buat environment baru dengan SUPERUSER_ID
    #             env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                
    #             # Akses model dengan environment baru
    #             order = env['sale.order'].browse(int(order_id))
                
    #             if not order.exists():
    #                 return {
    #                     'status': 'error',
    #                     'message': 'Order not found'
    #                 }
                
    #             data = {
    #                 'status': 'success',
    #                 'data': {
    #                     'name': order.name,
    #                     'customer_name': order.partner_id.name if order.partner_id else '',
    #                     'vehicle': {
    #                         'plate_number': order.partner_car_id.number_plate if order.partner_car_id else '',
    #                         'brand': order.partner_car_brand.name if order.partner_car_brand else '',
    #                         'type': order.partner_car_brand_type.name if order.partner_car_brand_type else '',
    #                     },
    #                     'has_rated': bool(order.post_service_rating),
    #                     'rating': order.post_service_rating,
    #                     'feedback': order.post_service_feedback
    #                 }
    #             }
                
    #             return data

    #     except Exception as e:
    #         _logger.error(f"Error in get_feedback_details: {str(e)}")
    #         return {
    #             'status': 'error',
    #             'message': str(e)
    #         }


    @http.route('/web/after-service/feedback/submit', type='json', auth='public', methods=['POST'], csrf=False)
    def submit_feedback(self, **kw):
        try:
            encoded_id = kw.get('order_id')
            rating = kw.get('rating')      # Tambahkan ini
            feedback = kw.get('feedback')  # Tambahkan ini
            database = kw.get('db')
            if not encoded_id:
                return {'status': 'error', 'message': 'Encoded Order ID is required'}
            
            # Decode order ID
            order_id = self._decode_id(encoded_id)
            if not order_id:
                return {'status': 'error', 'message': 'Invalid or expired order ID'}
            
            order = request.env['sale.order'].sudo().browse(int(order_id))
            
            if not order.exists():
                return {
                    'status': 'error',
                    'message': 'Order not found'
                }
            
            order.write({
                'post_service_rating': str(rating),
                'post_service_feedback': feedback or ''
            })
            
            return {
                'status': 'success',
                'message': 'Feedback submitted successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error in submit_feedback: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }