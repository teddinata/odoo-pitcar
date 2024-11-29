from odoo import http, fields
from odoo.http import request
import json
from datetime import datetime, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)

class KPIController(http.Controller):
    # def _get_date_range(self, range_type='today', start_date=None, end_date=None):
    #     """Helper to get date range based on type"""
    #     tz = pytz.timezone('Asia/Jakarta')
    #     now = datetime.now(tz)
        
    #     if start_date and end_date:
    #         try:
    #             # Convert string dates to datetime objects
    #             start = datetime.strptime(start_date, '%Y-%m-%d')
    #             end = datetime.strptime(end_date, '%Y-%m-%d')
    #             # Set time components
    #             start = tz.localize(start.replace(hour=0, minute=0, second=0))
    #             end = tz.localize(end.replace(hour=23, minute=59, second=59))
    #             return start, end
    #         except (ValueError, TypeError):
    #             return None, None
            
    #     if range_type == 'today':
    #         start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    #         end = now
    #     elif range_type == 'yesterday':
    #         start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    #         end = start.replace(hour=23, minute=59, second=59)
    #     elif range_type == 'this_week':
    #         start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    #         end = now
    #     elif range_type == 'this_month':
    #         start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    #         end = now
    #     elif range_type == 'last_month':
    #         last_month = now.replace(day=1) - timedelta(days=1)
    #         start = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    #         end = last_month.replace(day=last_month.day, hour=23, minute=59, second=59)
    #     elif range_type == 'this_year':
    #         start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    #         end = now
    #     else:  # default to today
    #         start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    #         end = now
            
    #     return start, end

    # @http.route('/web/smart/dashboard/mechanic', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    # def get_dashboard_overview(self, **kw):
    #     try:
    #         # Get parameters directly from kw
    #         date_range = kw.get('date_range', 'today')
    #         start_date = kw.get('start_date')
    #         end_date = kw.get('end_date')
            
    #         # Get date range
    #         start_date, end_date = self._get_date_range(date_range, start_date, end_date)
    #         if not start_date or not end_date:
    #             return {'status': 'error', 'message': 'Invalid date range'}

    #         # Convert to UTC for database queries
    #         start_date_utc = start_date.astimezone(pytz.UTC)
    #         end_date_utc = end_date.astimezone(pytz.UTC)
            
    #         # Get all mechanics
    #         mechanics = request.env['pitcar.mechanic.new'].search([])
    #         mechanic_data = []
    #         team_data = {}

    #         # Get all KPIs for the date range
    #         domain = [
    #             ('date', '>=', start_date_utc.date()),
    #             ('date', '<=', end_date_utc.date())
    #         ]
    #         all_kpis = request.env['mechanic.kpi'].search(domain)

    #         for mech in mechanics:
    #             # Get KPIs for this mechanic
    #             mech_kpis = all_kpis.filtered(lambda k: k.mechanic_id.id == mech.id)
                
    #             # Calculate metrics
    #             total_revenue = sum(mech_kpis.mapped('total_revenue'))
    #             monthly_target = mech.monthly_target or 64000000.0
                
    #             # Adjust target based on date range
    #             days_in_range = (end_date - start_date).days + 1
    #             adjusted_target = (monthly_target / 30) * days_in_range
    #             achievement = (total_revenue / adjusted_target * 100) if adjusted_target else 0

    #             mechanic_info = {
    #                 'id': mech.id,
    #                 'name': mech.name,
    #                 'position': 'Team Leader' if mech.position_code == 'leader' else 'Mechanic',
    #                 'metrics': {
    #                     'revenue': {
    #                         'total': total_revenue,
    #                         'target': adjusted_target,
    #                         'achievement': achievement
    #                     },
    #                     'orders': {
    #                         'total': len(mech_kpis),
    #                         'average_value': total_revenue / len(mech_kpis) if mech_kpis else 0
    #                     },
    #                     'performance': {
    #                         'on_time_rate': sum(mech_kpis.mapped('on_time_rate')) / len(mech_kpis) if mech_kpis else 0,
    #                         'average_rating': sum(mech_kpis.mapped('average_rating')) / len(mech_kpis) if mech_kpis else 0,
    #                         'duration_accuracy': sum(mech_kpis.mapped('duration_accuracy')) / len(mech_kpis) if mech_kpis else 0
    #                     }
    #                 },
    #                 'leader_id': mech.leader_id.id if mech.leader_id else None,
    #                 'team_members': []
    #             }

    #             # Group by team
    #             if mech.position_code == 'leader':
    #                 team_data[mech.id] = mechanic_info
    #             else:
    #                 mechanic_data.append(mechanic_info)
    #                 if mech.leader_id and mech.leader_id.id in team_data:
    #                     team_data[mech.leader_id.id]['team_members'].append(mechanic_info)

    #         # Calculate performance metrics
    #         performance_metrics = self._calculate_performance_metrics(all_kpis)
            
    #         # Calculate team summaries
    #         team_summaries = self._calculate_team_summaries(team_data)
            
    #         # Get trend data
    #         trend_data = self._get_trend_data(start_date_utc.date(), end_date_utc.date(), all_kpis)

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'date_range': {
    #                     'type': date_range,
    #                     'start': start_date.strftime('%Y-%m-%d'),
    #                     'end': end_date.strftime('%Y-%m-%d')
    #                 },
    #                 'overview': {
    #                     'total_revenue': sum(m['metrics']['revenue']['total'] for m in mechanic_data),
    #                     'total_orders': sum(m['metrics']['orders']['total'] for m in mechanic_data),
    #                     'average_rating': performance_metrics['quality']['average_rating'],
    #                     'on_time_rate': sum(m['metrics']['performance']['on_time_rate'] for m in mechanic_data) / len(mechanic_data) if mechanic_data else 0
    #                 },
    #                 'teams': team_summaries,
    #                 'mechanics': mechanic_data,
    #                 'performance': performance_metrics,
    #                 'trends': trend_data
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error(f"Error in get_dashboard_overview: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}

    # def _calculate_performance_metrics(self, kpis):
    #     """Helper method to calculate performance metrics"""
    #     if not kpis:
    #         return {
    #             'duration': {
    #                 'total_estimated': 0,
    #                 'total_actual': 0,
    #                 'accuracy': 0,
    #                 'average_deviation': 0
    #             },
    #             'timing': {
    #                 'early_starts': 0,
    #                 'late_starts': 0,
    #                 'early_completions': 0,
    #                 'late_completions': 0,
    #                 'average_delay': 0
    #             },
    #             'quality': {
    #                 'average_rating': 0,
    #                 'total_complaints': 0,
    #                 'complaint_rate': 0
    #             }
    #         }

    #     return {
    #         'duration': {
    #             'total_estimated': sum(kpis.mapped('total_estimated_duration')),
    #             'total_actual': sum(kpis.mapped('total_actual_duration')),
    #             'accuracy': sum(kpis.mapped('duration_accuracy')) / len(kpis),
    #             'average_deviation': sum(kpis.mapped('average_duration_deviation')) / len(kpis)
    #         },
    #         'timing': {
    #             'early_starts': sum(kpis.mapped('early_starts')),
    #             'late_starts': sum(kpis.mapped('late_starts')),
    #             'early_completions': sum(kpis.mapped('early_completions')),
    #             'late_completions': sum(kpis.mapped('late_completions')),
    #             'average_delay': sum(kpis.mapped('average_delay')) / len(kpis)
    #         },
    #         'quality': {
    #             'average_rating': sum(kpis.mapped('average_rating')) / len(kpis),
    #             'total_complaints': sum(kpis.mapped('total_complaints')),
    #             'complaint_rate': sum(kpis.mapped('complaint_rate')) / len(kpis)
    #         }
    #     }

    # def _calculate_team_summaries(self, team_data):
    #     """Helper method to calculate team summaries"""
    #     team_summaries = []
    #     for team_id, team_info in team_data.items():
    #         team_members = team_info['team_members']
    #         if not team_members:
    #             continue

    #         team_revenue = sum(m['metrics']['revenue']['total'] for m in team_members)
    #         team_target = sum(m['metrics']['revenue']['target'] for m in team_members)
            
    #         team_summaries.append({
    #             'team_id': team_id,
    #             'leader_name': team_info['name'],
    #             'member_count': len(team_members),
    #             'total_revenue': team_revenue,
    #             'target_revenue': team_target,
    #             'achievement': (team_revenue / team_target * 100) if team_target else 0,
    #             'average_performance': {
    #                 'on_time_rate': sum(m['metrics']['performance']['on_time_rate'] for m in team_members) / len(team_members),
    #                 'rating': sum(m['metrics']['performance']['average_rating'] for m in team_members) / len(team_members)
    #             }
    #         })

    #     return team_summaries

    # def _get_trend_data(self, start_date, end_date, kpis):
    #     """Helper method to generate trend data"""
    #     trend_data = []
    #     current_date = start_date
        
    #     while current_date <= end_date:
    #         # Filter KPIs for current date
    #         day_kpis = kpis.filtered(lambda k: k.date == current_date)
            
    #         if day_kpis:
    #             trend_data.append({
    #                 'date': current_date.strftime('%Y-%m-%d'),
    #                 'metrics': {
    #                     'revenue': sum(day_kpis.mapped('total_revenue')),
    #                     'orders': len(day_kpis),
    #                     'on_time_rate': sum(day_kpis.mapped('on_time_rate')) / len(day_kpis),
    #                     'rating': sum(day_kpis.mapped('average_rating')) / len(day_kpis)
    #                 }
    #             })
            
    #         current_date += timedelta(days=1)
            
    #     return trend_data

    def _get_date_range(self, range_type='today', start_date=None, end_date=None):
        """Helper to get date range based on type"""
        tz = pytz.timezone('Asia/Jakarta')
        now = datetime.now(tz)
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                start = tz.localize(start.replace(hour=0, minute=0, second=0))
                end = tz.localize(end.replace(hour=23, minute=59, second=59))
                return start, end
            except (ValueError, TypeError):
                return None, None
            
        ranges = {
            'today': (
                now.replace(hour=0, minute=0, second=0, microsecond=0),
                now
            ),
            'yesterday': (
                (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
                (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)
            ),
            'this_week': (
                (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0),
                now
            ),
            'this_month': (
                now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                now
            ),
            'last_month': (
                (now.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                (now.replace(day=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59)
            )
        }
        
        return ranges.get(range_type, ranges['today'])

    @http.route('/web/v2/dashboard/mechanic', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_mechanic_kpi_dashboard(self, **kw):
        try:
            # Get date range parameters
            date_range = kw.get('date_range', 'today')
            start_date = kw.get('start_date')
            end_date = kw.get('end_date')
            
            # Set timezone
            tz = pytz.timezone('Asia/Jakarta')
            now = datetime.now(tz)
            
            # Calculate date range
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    start = tz.localize(start.replace(hour=0, minute=0, second=0))
                    end = tz.localize(end.replace(hour=23, minute=59, second=59))
                except (ValueError, TypeError):
                    return {'status': 'error', 'message': 'Invalid date format'}
            else:
                if date_range == 'today':
                    start = now.replace(hour=0, minute=0, second=0)
                    end = now
                elif date_range == 'yesterday':
                    yesterday = now - timedelta(days=1)
                    start = yesterday.replace(hour=0, minute=0, second=0)
                    end = yesterday.replace(hour=23, minute=59, second=59)
                elif date_range == 'this_week':
                    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
                    end = now
                elif date_range == 'this_month':
                    start = now.replace(day=1, hour=0, minute=0, second=0)
                    end = now
                elif date_range == 'this_year':
                    start = now.replace(month=1, day=1, hour=0, minute=0, second=0)
                    end = now
                else:
                    start = now.replace(hour=0, minute=0, second=0)
                    end = now

            # Convert to UTC for database queries
            start_utc = start.astimezone(pytz.UTC)
            end_utc = end.astimezone(pytz.UTC)

            # Build domain for orders
            domain = [
                ('date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', '=', 'sale')
            ]

            # Get orders
            orders = request.env['sale.order'].sudo().search(domain)

            # Get all mechanics
            mechanics = request.env['pitcar.mechanic.new'].sudo().search([])
            mechanic_dict = {m.id: m for m in mechanics}

            # Calculate mechanic metrics
            mechanics_data = {}
            for order in orders:
                if not order.car_mechanic_id_new:
                    continue
                    
                for mechanic in order.car_mechanic_id_new:
                    if mechanic.id not in mechanics_data:
                        mechanics_data[mechanic.id] = {
                            'id': mechanic.id,
                            'name': mechanic.name,
                            'position': 'Team Leader' if mechanic.position_code == 'leader' else 'Mechanic',
                            'revenue': 0,
                            'orders': 0,
                            'total_rating': 0,
                            'rated_orders': 0,
                            'on_time_orders': 0,
                            'early_starts': 0,
                            'late_starts': 0,
                            'early_completions': 0,
                            'late_completions': 0,
                            'total_completions': 0
                        }
                    
                    mechanic_count = len(order.car_mechanic_id_new)
                    mech_data = mechanics_data[mechanic.id]
                    
                    # Basic metrics
                    mech_data['revenue'] += order.amount_total / mechanic_count
                    mech_data['orders'] += 1
                    
                    # Timing metrics
                    if all([order.controller_estimasi_mulai, order.controller_estimasi_selesai,
                        order.controller_mulai_servis, order.controller_selesai]):
                        
                        est_start = fields.Datetime.from_string(order.controller_estimasi_mulai)
                        est_end = fields.Datetime.from_string(order.controller_estimasi_selesai)
                        actual_start = fields.Datetime.from_string(order.controller_mulai_servis)
                        actual_end = fields.Datetime.from_string(order.controller_selesai)

                        mech_data['total_completions'] += 1
                        
                        if actual_start < est_start:
                            mech_data['early_starts'] += 1
                        elif actual_start > est_start:
                            mech_data['late_starts'] += 1

                        if actual_end < est_end:
                            mech_data['early_completions'] += 1
                            mech_data['on_time_orders'] += 1
                        elif actual_end > est_end:
                            mech_data['late_completions'] += 1

                    if order.customer_rating:
                        mech_data['total_rating'] += float(order.customer_rating)
                        mech_data['rated_orders'] += 1

            # Calculate team metrics using proper target calculation
            teams_data = {}
            for mechanic_id, data in mechanics_data.items():
                mechanic = mechanic_dict.get(mechanic_id)
                if not mechanic:
                    continue
                    
                leader_id = mechanic.leader_id.id if mechanic.leader_id else (mechanic_id if mechanic.position_code == 'leader' else None)
                
                if leader_id and mechanic.position_code != 'leader':
                    if leader_id not in teams_data:
                        leader = mechanic_dict.get(leader_id)
                        teams_data[leader_id] = {
                            'id': leader_id,
                            'name': leader.name,
                            'position': 'Team',
                            'member_count': 1,
                            'metrics': {
                                'revenue': {
                                    'total': 0,
                                    'target': leader.monthly_target,  # Get target from leader's monthly_target
                                    'achievement': 0
                                },
                                'orders': {
                                    'total': 0,
                                    'average_value': 0
                                },
                                'performance': {
                                    'on_time_rate': 0,
                                    'rating': 0,
                                    'early_completion_rate': 0,
                                    'late_completion_rate': 0
                                }
                            }
                        }
                    
                    team_data = teams_data[leader_id]
                    team_data['metrics']['revenue']['total'] += data['revenue']
                    team_data['metrics']['orders']['total'] += data['orders']
                    team_data['member_count'] += 1

                    if data['total_completions'] > 0:
                        completions = data['total_completions']
                        team_data['metrics']['performance']['early_completion_rate'] += (data['early_completions'] / completions * 100)
                        team_data['metrics']['performance']['late_completion_rate'] += (data['late_completions'] / completions * 100)
                        
                    if data['orders'] > 0:
                        team_data['metrics']['performance']['on_time_rate'] += (data['on_time_orders'] / data['orders'] * 100)
                    
                    if data['rated_orders'] > 0:
                        team_data['metrics']['performance']['rating'] += (data['total_rating'] / data['rated_orders'])

            # Format mechanic data with proper targets
            active_mechanics = []
            for data in mechanics_data.values():
                if data['orders'] > 0:
                    mechanic = mechanic_dict.get(data['id'])
                    if not mechanic:
                        continue

                    metrics = {
                        'revenue': {
                            'total': data['revenue'],
                            'target': mechanic.monthly_target,  # Get target from mechanic's monthly_target
                            'achievement': (data['revenue'] / mechanic.monthly_target * 100) if mechanic.monthly_target else 0
                        },
                        'orders': {
                            'total': data['orders'],
                            'average_value': data['revenue'] / data['orders'] if data['orders'] else 0
                        },
                        'performance': {
                            'on_time_rate': (data['on_time_orders'] / data['orders'] * 100) if data['orders'] else 0,
                            'rating': data['total_rating'] / data['rated_orders'] if data['rated_orders'] else 0,
                            'early_start_rate': (data['early_starts'] / data['total_completions'] * 100) if data['total_completions'] else 0,
                            'late_start_rate': (data['late_starts'] / data['total_completions'] * 100) if data['total_completions'] else 0,
                            'early_completion_rate': (data['early_completions'] / data['total_completions'] * 100) if data['total_completions'] else 0,
                            'late_completion_rate': (data['late_completions'] / data['total_completions'] * 100) if data['total_completions'] else 0
                        }
                    }
                    
                    active_mechanics.append({
                        'id': data['id'],
                        'name': data['name'],
                        'position': data['position'],
                        'metrics': metrics
                    })

            # Calculate overview metrics
            total_revenue = sum(order.amount_total for order in orders)
            total_orders = len(orders)
            total_completions = sum(order.controller_selesai is not None for order in orders)
            early_completions = sum(1 for order in orders if order.controller_selesai and 
                                order.controller_estimasi_selesai and 
                                order.controller_selesai <= order.controller_estimasi_selesai)
            late_completions = sum(1 for order in orders if order.controller_selesai and 
                                order.controller_estimasi_selesai and 
                                order.controller_selesai > order.controller_estimasi_selesai)
            
            rated_orders = orders.filtered(lambda o: o.customer_rating)
            average_rating = (
                sum(float(order.customer_rating) for order in rated_orders) / len(rated_orders)
                if rated_orders else 0
            )
            
            complaints = len(orders.filtered(lambda o: o.customer_rating in ['1', '2']))

            overview = {
                'total_revenue': total_revenue,
                'total_orders': total_orders,
                'average_rating': average_rating,
                'on_time_rate': (early_completions / total_completions * 100) if total_completions else 0,
                'complaints': {
                    'total': complaints,
                    'rate': (complaints / total_orders * 100) if total_orders else 0
                },
                'performance': {
                    'duration_accuracy': 0,
                    'early_completion_rate': (early_completions / total_completions * 100) if total_completions else 0,
                    'late_completion_rate': (late_completions / total_completions * 100) if total_completions else 0
                }
            }

            # Calculate daily trends
            trends = []
            current = start
            while current <= end:
                try:
                    current_end = min(current.replace(hour=23, minute=59, second=59), end)
                    current_start = current.replace(hour=0, minute=0, second=0)
                    
                    current_start_utc = current_start.astimezone(pytz.UTC)
                    current_end_utc = current_end.astimezone(pytz.UTC)
                    
                    day_domain = [
                        ('date_completed', '>=', current_start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                        ('date_completed', '<=', current_end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                        ('state', '=', 'sale')
                    ]
                    day_orders = request.env['sale.order'].sudo().search(day_domain)
                    
                    if day_orders:
                        daily_completions = sum(1 for order in day_orders if order.controller_selesai)
                        daily_early_completions = sum(1 for order in day_orders 
                                                if order.controller_selesai and order.controller_estimasi_selesai
                                                and order.controller_selesai <= order.controller_estimasi_selesai)

                        daily_revenue = sum(order.amount_total for order in day_orders)
                        daily_rated_orders = day_orders.filtered(lambda o: o.customer_rating)
                        daily_rating = (
                            sum(float(order.customer_rating) for order in daily_rated_orders) / len(daily_rated_orders)
                            if daily_rated_orders else 0
                        )
                        
                        trends.append({
                            'date': current.strftime('%Y-%m-%d'),
                            'metrics': {
                                'revenue': daily_revenue,
                                'orders': len(day_orders),
                                'on_time_rate': (daily_early_completions / daily_completions * 100) if daily_completions else 0,
                                'rating': daily_rating
                            }
                        })
                    
                    current += timedelta(days=1)
                except Exception as e:
                    _logger.error(f"Error calculating trends for {current.strftime('%Y-%m-%d')}: {str(e)}")
                    continue

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'overview': overview,
                    'teams': list(teams_data.values()),
                    'mechanics': active_mechanics,
                    'trends': trends
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_mechanic_kpi_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_mechanic_performance(self, kpis, days_in_range):
        """Calculate individual mechanic performance with proper filtering"""
        # Get unique mechanics from KPIs
        mechanic_ids = kpis.mapped('mechanic_id')
        mechanics = request.env['pitcar.mechanic.new'].sudo().browse(mechanic_ids.ids)
        
        result = []
        for mechanic in mechanics:
            # Filter KPIs specific to this mechanic and date range
            mechanic_kpis = kpis.filtered(lambda k: k.mechanic_id.id == mechanic.id)
            if not mechanic_kpis:
                continue

            # Calculate target based on position and days
            monthly_target = 128000000 if mechanic.position_code == 'leader' else 64000000
            adjusted_target = (monthly_target / 30) * days_in_range

            # Group revenue by date to avoid duplication
            daily_revenues = {}
            for kpi in mechanic_kpis:
                date_str = kpi.date.strftime('%Y-%m-%d')
                if date_str not in daily_revenues:
                    daily_revenues[date_str] = 0
                daily_revenues[date_str] += kpi.total_revenue

            # Calculate total unique daily revenue
            total_revenue = sum(daily_revenues.values())
            total_orders = len(mechanic_kpis)

            result.append({
                'id': mechanic.id,
                'name': mechanic.name,
                'position': 'Team Leader' if mechanic.position_code == 'leader' else 'Mechanic',
                'metrics': {
                    'revenue': {
                        'total': total_revenue,
                        'target': adjusted_target,
                        'achievement': (total_revenue / adjusted_target * 100) if adjusted_target else 0
                    },
                    'orders': {
                        'total': total_orders,
                        'average_value': total_revenue / total_orders if total_orders else 0
                    },
                    'performance': {
                        'on_time_rate': sum(mechanic_kpis.mapped('on_time_rate')) / len(mechanic_kpis) if mechanic_kpis else 0,
                        'rating': sum(mechanic_kpis.mapped('average_rating')) / len(mechanic_kpis) if mechanic_kpis else 0,
                        'duration_accuracy': sum(mechanic_kpis.mapped('duration_accuracy')) / len(mechanic_kpis) if mechanic_kpis else 0
                    }
                }
            })
        
        return result

    def _get_team_performance(self, kpis, leaders, days_in_range):
        """Calculate team performance metrics with proper filtering"""
        team_list = []
        
        for leader in leaders:
            # Get team members
            team_members = request.env['pitcar.mechanic.new'].sudo().search([
                ('leader_id', '=', leader.id)
            ])
            
            # Include leader in count
            member_count = len(team_members) + 1
            all_member_ids = team_members.ids + [leader.id]
            
            # Get team KPIs
            team_kpis = kpis.filtered(lambda k: k.mechanic_id.id in all_member_ids)
            if not team_kpis:
                continue

            # Calculate target
            monthly_target = 64000000 * member_count  # Base monthly target per member
            adjusted_target = (monthly_target / 30) * days_in_range

            # Group revenue by date to avoid duplication
            daily_revenues = {}
            for kpi in team_kpis:
                date_str = kpi.date.strftime('%Y-%m-%d')
                if date_str not in daily_revenues:
                    daily_revenues[date_str] = 0
                daily_revenues[date_str] += kpi.total_revenue

            # Calculate totals
            total_revenue = sum(daily_revenues.values())
            total_orders = len(team_kpis)

            team_list.append({
                'id': leader.id,
                'name': leader.name,
                'position': 'Team',
                'member_count': member_count,
                'metrics': {
                    'revenue': {
                        'total': total_revenue,
                        'target': adjusted_target,
                        'achievement': (total_revenue / adjusted_target * 100) if adjusted_target else 0
                    },
                    'orders': {
                        'total': total_orders,
                        'average_value': total_revenue / total_orders if total_orders else 0
                    },
                    'performance': {
                        'on_time_rate': sum(team_kpis.mapped('on_time_rate')) / len(team_kpis) if team_kpis else 0,
                        'rating': sum(team_kpis.mapped('average_rating')) / len(team_kpis) if team_kpis else 0,
                        'duration_accuracy': sum(team_kpis.mapped('duration_accuracy')) / len(team_kpis) if team_kpis else 0
                    }
                }
            })
        
        return team_list

    def _calculate_dashboard_metrics(self, kpis):
        """Calculate overall dashboard metrics with proper filtering"""
        if not kpis:
            return {
                'total_revenue': 0,
                'total_orders': 0,
                'average_rating': 0,
                'on_time_rate': 0,
                'complaints': {
                    'total': 0,
                    'rate': 0
                },
                'performance': {
                    'duration_accuracy': 0,
                    'early_completion_rate': 0,
                    'late_completion_rate': 0
                }
            }

        # Group revenue by date to avoid duplication
        daily_revenues = {}
        for kpi in kpis:
            date_str = kpi.date.strftime('%Y-%m-%d')
            if date_str not in daily_revenues:
                daily_revenues[date_str] = 0
            daily_revenues[date_str] += kpi.total_revenue

        total_revenue = sum(daily_revenues.values())
        total_orders = len(kpis)
        total_complaints = sum(kpis.mapped('total_complaints'))

        return {
            'total_revenue': total_revenue,
            'total_orders': total_orders,
            'average_rating': sum(kpis.mapped('average_rating')) / len(kpis) if kpis else 0,
            'on_time_rate': sum(kpis.mapped('on_time_rate')) / len(kpis) if kpis else 0,
            'complaints': {
                'total': total_complaints,
                'rate': (total_complaints / total_orders * 100) if total_orders else 0
            },
            'performance': {
                'duration_accuracy': sum(kpis.mapped('duration_accuracy')) / len(kpis) if kpis else 0,
                'early_completion_rate': (sum(kpis.mapped('early_completions')) / total_orders * 100) if total_orders else 0,
                'late_completion_rate': (sum(kpis.mapped('late_completions')) / total_orders * 100) if total_orders else 0
            }
        }

    # def _get_team_performance(self, kpis, mechanic_dict, start_date_utc, end_date_utc):
    #     """Calculate team performance metrics"""
    #     team_list = []
    #     days_in_range = (end_date_utc.date() - start_date_utc.date()).days + 1
        
    #     # Group KPIs by team leader
    #     team_kpis = {}
    #     for kpi in kpis:
    #         mechanic = mechanic_dict.get(kpi.mechanic_id.id)
    #         if not mechanic:
    #             continue
                
    #         leader_id = mechanic.leader_id.id if mechanic.leader_id else (
    #             mechanic.id if mechanic.position_code == 'leader' else None
    #         )
            
    #         if leader_id:
    #             if leader_id not in team_kpis:
    #                 team_kpis[leader_id] = []
    #             team_kpis[leader_id].append(kpi)
        
    #     # Calculate team metrics
    #     for leader_id, leader_kpis in team_kpis.items():
    #         leader = mechanic_dict.get(leader_id)
    #         if not leader or leader.position_code != 'leader':
    #             continue

    #         team_members = [m for m in mechanic_dict.values() if m.leader_id.id == leader_id]
    #         member_count = len(team_members) + 1  # Include leader
            
    #         # Calculate target based on days in range
    #         monthly_target = member_count * 64000000  # Base monthly target
    #         adjusted_target = (monthly_target / 30) * days_in_range
            
    #         total_revenue = sum(k.total_revenue for k in leader_kpis)
    #         total_orders = sum(k.total_orders for k in leader_kpis)
            
    #         team_list.append({
    #             'id': leader_id,
    #             'name': leader.name,
    #             'position': 'Team',
    #             'member_count': member_count,
    #             'metrics': {
    #                 'revenue': {
    #                     'total': total_revenue,
    #                     'target': adjusted_target,
    #                     'achievement': (total_revenue / adjusted_target * 100) if adjusted_target else 0
    #                 },
    #                 'orders': {
    #                     'total': total_orders,
    #                     'average_value': total_revenue / total_orders if total_orders else 0
    #                 },
    #                 'performance': {
    #                     'on_time_rate': sum(k.on_time_rate for k in leader_kpis) / len(leader_kpis) if leader_kpis else 0,
    #                     'rating': sum(k.average_rating for k in leader_kpis) / len(leader_kpis) if leader_kpis else 0,
    #                     'duration_accuracy': sum(k.duration_accuracy for k in leader_kpis) / len(leader_kpis) if leader_kpis else 0
    #                 }
    #             }
    #         })
        
    #     return team_list

    # def _get_mechanic_performance(self, kpis, mechanic_dict, start_date_utc, end_date_utc):
    #     """Calculate individual mechanic performance"""
    #     days_in_range = (end_date_utc.date() - start_date_utc.date()).days + 1
    #     mechanic_kpis = {}
        
    #     # Group KPIs by mechanic
    #     for kpi in kpis:
    #         mech_id = kpi.mechanic_id.id
    #         if mech_id not in mechanic_kpis:
    #             mechanic_kpis[mech_id] = []
    #         mechanic_kpis[mech_id].append(kpi)
        
    #     mechanics_data = []
    #     for mech_id, mech_kpis in mechanic_kpis.items():
    #         mechanic = mechanic_dict.get(mech_id)
    #         if not mechanic:
    #             continue
                
    #         # Calculate target based on days in range
    #         monthly_target = mechanic.monthly_target or 64000000
    #         adjusted_target = (monthly_target / 30) * days_in_range
            
    #         total_revenue = sum(k.total_revenue for k in mech_kpis)
    #         total_orders = sum(k.total_orders for k in mech_kpis)
            
    #         mechanics_data.append({
    #             'id': mech_id,
    #             'name': mechanic.name,
    #             'position': 'Team Leader' if mechanic.position_code == 'leader' else 'Mechanic',
    #             'metrics': {
    #                 'revenue': {
    #                     'total': total_revenue,
    #                     'target': adjusted_target,
    #                     'achievement': (total_revenue / adjusted_target * 100) if adjusted_target else 0
    #                 },
    #                 'orders': {
    #                     'total': total_orders,
    #                     'average_value': total_revenue / total_orders if total_orders else 0
    #                 },
    #                 'performance': {
    #                     'on_time_rate': sum(k.on_time_rate for k in mech_kpis) / len(mech_kpis) if mech_kpis else 0,
    #                     'rating': sum(k.average_rating for k in mech_kpis) / len(mech_kpis) if mech_kpis else 0,
    #                     'duration_accuracy': sum(k.duration_accuracy for k in mech_kpis) / len(mech_kpis) if mech_kpis else 0
    #                 }
    #             }
    #         })
        
    #     return mechanics_data
    
    def _calculate_adjusted_target(self, base_target, start_date, end_date):
        """Calculate target adjusted for the date range"""
        days_in_range = (end_date.date() - start_date.date()).days + 1
        if days_in_range >= 30:  # Full month or more
            return base_target
        return (base_target / 30) * days_in_range

    def _calculate_kpi_metrics(self, kpis, target):
        """Calculate KPI metrics for a given set of KPIs"""
        if not kpis:
            return {
                'revenue': {
                    'total': 0,
                    'target': target,
                    'achievement': 0
                },
                'orders': {
                    'total': 0,
                    'average_value': 0
                },
                'performance': {
                    'on_time_rate': 0,
                    'rating': 0,
                    'duration_accuracy': 0
                }
            }
            
        # Calculate daily revenue
        revenue_by_date = {}
        for kpi in kpis:
            date_str = kpi.date.strftime('%Y-%m-%d')
            if date_str not in revenue_by_date:
                revenue_by_date[date_str] = 0
            revenue_by_date[date_str] += kpi.total_revenue

        # Sum up unique daily revenues
        total_revenue = sum(revenue_by_date.values())
        total_orders = sum(kpi.total_orders for kpi in kpis)
        
        return {
            'revenue': {
                'total': total_revenue,
                'target': target,
                'achievement': (total_revenue / target * 100) if target else 0
            },
            'orders': {
                'total': total_orders,
                'average_value': total_revenue / total_orders if total_orders else 0
            },
            'performance': {
                'on_time_rate': sum(k.on_time_rate for k in kpis) / len(kpis) if kpis else 0,
                'rating': sum(k.average_rating for k in kpis) / len(kpis) if kpis else 0,
                'duration_accuracy': sum(k.duration_accuracy for k in kpis) / len(kpis) if kpis else 0
            }
        }

    # def _get_team_performance(self, kpis, mechanic_dict, start_date_utc, end_date_utc):
    #     """Calculate team performance metrics"""
    #     team_list = []
    #     base_monthly_target = 64000000  # Base monthly target per person
        
    #     # Group KPIs by team leader
    #     team_kpis = {}
    #     for kpi in kpis:
    #         mechanic = mechanic_dict.get(kpi.mechanic_id.id)
    #         if not mechanic:
    #             continue
                
    #         leader_id = mechanic.leader_id.id if mechanic.leader_id else (
    #             mechanic.id if mechanic.position_code == 'leader' else None
    #         )
            
    #         if leader_id:
    #             if leader_id not in team_kpis:
    #                 team_kpis[leader_id] = []
    #             team_kpis[leader_id].append(kpi)
        
    #     # Calculate team metrics
    #     for leader_id, leader_kpis in team_kpis.items():
    #         leader = mechanic_dict.get(leader_id)
    #         if not leader or leader.position_code != 'leader':
    #             continue

    #         team_members = [m for m in mechanic_dict.values() if m.leader_id.id == leader_id]
    #         member_count = len(team_members) + 1  # Include leader
            
    #         # Calculate adjusted target
    #         team_target = self._calculate_adjusted_target(
    #             base_monthly_target * member_count,
    #             start_date_utc,
    #             end_date_utc
    #         )
            
    #         team_metrics = self._calculate_kpi_metrics(leader_kpis, team_target)
    #         team_list.append({
    #             'id': leader_id,
    #             'name': leader.name,
    #             'position': 'Team',
    #             'member_count': member_count,
    #             'metrics': team_metrics
    #         })
        
    #     return team_list

    # def _get_mechanic_performance(self, kpis, mechanic_dict, start_date_utc, end_date_utc):
    #     """Calculate individual mechanic performance"""
    #     base_monthly_target = 64000000  # Base monthly target
    #     mechanics_data = []
        
    #     # Group KPIs by mechanic
    #     mechanic_kpis = {}
    #     for kpi in kpis:
    #         mech_id = kpi.mechanic_id.id
    #         if mech_id not in mechanic_kpis:
    #             mechanic_kpis[mech_id] = []
    #         mechanic_kpis[mech_id].append(kpi)
        
    #     for mech_id, mech_kpis in mechanic_kpis.items():
    #         mechanic = mechanic_dict.get(mech_id)
    #         if not mechanic:
    #             continue
                
    #         # Calculate adjusted target
    #         adjusted_target = self._calculate_adjusted_target(
    #             base_monthly_target if mechanic.position_code != 'leader' else base_monthly_target * 2,
    #             start_date_utc,
    #             end_date_utc
    #         )
            
    #         metrics = self._calculate_kpi_metrics(mech_kpis, adjusted_target)
    #         mechanics_data.append({
    #             'id': mech_id,
    #             'name': mechanic.name,
    #             'position': 'Team Leader' if mechanic.position_code == 'leader' else 'Mechanic',
    #             'metrics': metrics
    #         })
        
    #     return mechanics_data

    def _calculate_trends(self, kpis):
        """Calculate trend data for the dashboard"""
        if not kpis:
            return []

        dates = sorted(set(kpis.mapped('date')))
        trends = []

        for date in dates:
            day_kpis = kpis.filtered(lambda k: k.date == date)
            if day_kpis:
                total_revenue = sum(day_kpis.mapped('total_revenue'))
                total_orders = sum(day_kpis.mapped('total_orders'))
                
                trends.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'metrics': {
                        'revenue': total_revenue,
                        'orders': total_orders,
                        'on_time_rate': sum(day_kpis.mapped('on_time_rate')) / len(day_kpis) if day_kpis else 0,
                        'rating': sum(day_kpis.mapped('average_rating')) / len(day_kpis) if day_kpis else 0
                    }
                })

        return trends

    @http.route('/web/v2/dashboard/mechanic/<int:mechanic_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_mechanic_detail(self, mechanic_id, **kw):
        """Get detailed KPIs for a specific mechanic"""
        try:
            # Get date range
            date_range = kw.get('date_range', 'today')
            start_date, end_date = self._get_date_range(
                date_range, 
                kw.get('start_date'), 
                kw.get('end_date')
            )
            
            if not start_date or not end_date:
                return {'status': 'error', 'message': 'Invalid date range'}

            # Convert to UTC for database queries
            start_date_utc = start_date.astimezone(pytz.UTC)
            end_date_utc = end_date.astimezone(pytz.UTC)
            
            mechanic = request.env['pitcar.mechanic.new'].browse(mechanic_id)
            if not mechanic.exists():
                return {'status': 'error', 'message': 'Mechanic not found'}

            # Get KPIs
            kpis = request.env['mechanic.kpi'].search([
                ('mechanic_id', '=', mechanic_id),
                ('date', '>=', start_date_utc.date()),
                ('date', '<=', end_date_utc.date())
            ])

            # Calculate target
            monthly_target = mechanic.monthly_target or 64000000.0
            days_in_range = (end_date - start_date).days + 1
            adjusted_target = (monthly_target / 30) * days_in_range

            # Get team data if leader
            team_data = None
            if mechanic.position_code == 'leader':
                team_data = self._calculate_team_data(mechanic, kpis, start_date_utc, end_date_utc)

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start_date.strftime('%Y-%m-%d'),
                        'end': end_date.strftime('%Y-%m-%d')
                    },
                    'mechanic': {
                        'id': mechanic.id,
                        'name': mechanic.name,
                        'position': 'Team Leader' if mechanic.position_code == 'leader' else 'Mechanic',
                        'leader': {
                            'id': mechanic.leader_id.id,
                            'name': mechanic.leader_id.name
                        } if mechanic.leader_id else None
                    },
                    'metrics': self._calculate_detailed_metrics(kpis, adjusted_target),
                    'team_data': team_data,
                    'trends': self._get_daily_stats(kpis)
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_mechanic_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    def _calculate_detailed_metrics(self, kpis, target):
        """Calculate detailed metrics for a mechanic"""
        if not kpis:
            return {
                'revenue': {
                    'total': 0,
                    'target': target,
                    'achievement': 0
                },
                'orders': {
                    'total': 0,
                    'average_value': 0
                },
                'performance': {
                    'on_time_rate': 0,
                    'rating': 0,
                    'duration_accuracy': 0,
                    'complaints': 0,
                    'complaint_rate': 0
                },
                'timing': {
                    'early_starts': 0,
                    'late_starts': 0,
                    'early_completions': 0,
                    'late_completions': 0,
                    'average_delay': 0
                },
                'duration': {
                    'total_estimated': 0,
                    'total_actual': 0,
                    'accuracy': 0,
                    'average_deviation': 0
                }
            }

        total_revenue = sum(kpis.mapped('total_revenue'))
        total_orders = len(kpis)
        
        return {
            'revenue': {
                'total': total_revenue,
                'target': target,
                'achievement': (total_revenue / target * 100) if target else 0
            },
            'orders': {
                'total': total_orders,
                'average_value': total_revenue / total_orders if total_orders else 0
            },
            'performance': {
                'on_time_rate': sum(kpis.mapped('on_time_rate')) / len(kpis),
                'rating': sum(kpis.mapped('average_rating')) / len(kpis),
                'duration_accuracy': sum(kpis.mapped('duration_accuracy')) / len(kpis),
                'complaints': sum(kpis.mapped('total_complaints')),
                'complaint_rate': sum(kpis.mapped('complaint_rate')) / len(kpis)
            },
            'timing': {
                'early_starts': sum(kpis.mapped('early_starts')),
                'late_starts': sum(kpis.mapped('late_starts')),
                'early_completions': sum(kpis.mapped('early_completions')),
                'late_completions': sum(kpis.mapped('late_completions')),
                'average_delay': sum(kpis.mapped('average_delay')) / len(kpis)
            },
            'duration': {
                'total_estimated': sum(kpis.mapped('total_estimated_duration')),
                'total_actual': sum(kpis.mapped('total_actual_duration')),
                'accuracy': sum(kpis.mapped('duration_accuracy')) / len(kpis),
                'average_deviation': sum(kpis.mapped('average_duration_deviation')) / len(kpis)
            }
        }
    
    def _calculate_team_data(self, leader, leader_kpis, start_date_utc, end_date_utc):
        """Calculate team data for a leader"""
        team_members = request.env['pitcar.mechanic.new'].search([
            ('leader_id', '=', leader.id)
        ])
        
        # Get all team KPIs in one query
        team_kpis = request.env['mechanic.kpi'].search([
            ('mechanic_id', 'in', team_members.ids),
            ('date', '>=', start_date_utc.date()),
            ('date', '<=', end_date_utc.date())
        ])

        days_in_range = (end_date_utc - start_date_utc).days + 1
        
        # Calculate member metrics
        members = []
        for member in team_members:
            member_kpis = team_kpis.filtered(lambda k: k.mechanic_id.id == member.id)
            if member_kpis:
                monthly_target = member.monthly_target or 64000000.0
                adjusted_target = (monthly_target / 30) * days_in_range
                members.append({
                    'id': member.id,
                    'name': member.name,
                    'position': 'Mechanic',
                    'metrics': self._calculate_detailed_metrics(member_kpis, adjusted_target)
                })

        # Calculate team summary
        all_team_kpis = leader_kpis + team_kpis
        total_target = ((leader.monthly_target or 64000000.0) + 
                    sum(m.monthly_target or 64000000.0 for m in team_members))
        adjusted_team_target = (total_target / 30) * days_in_range

        return {
            'summary': self._calculate_detailed_metrics(all_team_kpis, adjusted_team_target),
            'members': members
        }

    def _get_team_metrics(self, leader, start_date_utc, end_date_utc):
        """Get team performance metrics for a team leader"""
        team_members = request.env['pitcar.mechanic.new'].search([
            ('leader_id', '=', leader.id)
        ])
        
        team_metrics = {
            'members': [],
            'summary': {
                'total_revenue': 0,
                'total_orders': 0,
                'average_rating': 0,
                'on_time_rate': 0,
                'target_achievement': 0
            }
        }

        # Get all team KPIs in one query
        all_team_kpis = request.env['mechanic.kpi'].search([
            ('mechanic_id', 'in', team_members.ids),
            ('date', '>=', start_date_utc.date()),
            ('date', '<=', end_date_utc.date())
        ])
        
        for member in team_members:
            member_kpis = all_team_kpis.filtered(lambda k: k.mechanic_id.id == member.id)
            
            if member_kpis:
                # Calculate member's adjusted target
                monthly_target = member.monthly_target or 64000000.0
                days_in_range = (end_date_utc - start_date_utc).days + 1
                adjusted_target = (monthly_target / 30) * days_in_range
                total_revenue = sum(member_kpis.mapped('total_revenue'))

                team_metrics['members'].append({
                    'id': member.id,
                    'name': member.name,
                    'metrics': {
                        'revenue': {
                            'total': total_revenue,
                            'target': adjusted_target,
                            'achievement': (total_revenue / adjusted_target * 100) if adjusted_target else 0
                        },
                        'orders': {
                            'total': len(member_kpis),
                            'average_value': total_revenue / len(member_kpis) if member_kpis else 0
                        },
                        'performance': {
                            'on_time_rate': sum(member_kpis.mapped('on_time_rate')) / len(member_kpis),
                            'rating': sum(member_kpis.mapped('average_rating')) / len(member_kpis),
                            'duration_accuracy': sum(member_kpis.mapped('duration_accuracy')) / len(member_kpis)
                        }
                    }
                })
        
        return team_metrics

    def _get_team_daily_trend(self, team_kpis):
        """Get daily trend data for team performance"""
        if not team_kpis:
            return []
            
        # Get unique dates and sort them
        dates = sorted(set(team_kpis.mapped('date')))
        trend_data = []
        
        for date in dates:
            day_kpis = team_kpis.filtered(lambda k: k.date == date)
            if day_kpis:
                trend_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'metrics': {
                        'revenue': sum(day_kpis.mapped('total_revenue')),
                        'orders': len(day_kpis),
                        'on_time_rate': sum(day_kpis.mapped('on_time_rate')) / len(day_kpis),
                        'rating': sum(day_kpis.mapped('average_rating')) / len(day_kpis)
                    }
                })
            
                return trend_data
            
                adjusted_target = (monthly_target / 30) * days_in_range
                total_revenue = sum(member_kpis.mapped('total_revenue'))

                member_metrics = {
                    'id': member.id,
                    'name': member.name,
                    'metrics': {
                        'revenue': {
                            'total': total_revenue,
                            'target': adjusted_target,
                            'achievement': (total_revenue / adjusted_target * 100) if adjusted_target else 0
                        },
                        'orders': len(member_kpis),
                        'performance': {
                            'on_time_rate': sum(member_kpis.mapped('on_time_rate')) / len(member_kpis),
                            'rating': sum(member_kpis.mapped('average_rating')) / len(member_kpis)
                        }
                    }
                }
                team_metrics['members'].append(member_metrics)
                
                # Update summary
                team_metrics['summary']['total_revenue'] += total_revenue
                team_metrics['summary']['total_orders'] += len(member_kpis)
                team_metrics['summary']['average_rating'] += member_metrics['metrics']['performance']['rating']
                team_metrics['summary']['on_time_rate'] += member_metrics['metrics']['performance']['on_time_rate']
                team_metrics['summary']['target_achievement'] += member_metrics['metrics']['revenue']['achievement']
        
        # Calculate averages for summary
        team_metrics = {
            'members': [],
            'summary': {
                'total_revenue': 0,
                'total_orders': 0,
                'average_rating': 0,
                'on_time_rate': 0,
                'target_achievement': 0
            }
        }

        member_count = len(team_metrics['members'])
        if member_count > 0:
            team_metrics['summary']['average_rating'] /= member_count
            team_metrics['summary']['on_time_rate'] /= member_count
            team_metrics['summary']['target_achievement'] /= member_count
        
        return team_metrics

    def _get_daily_stats(self, kpis):
        """Get daily statistics for KPIs"""
        daily_stats = []
        
        # Get unique dates and sort them
        dates = sorted(set(kpis.mapped('date')))
        
        for date in dates:
            day_kpis = kpis.filtered(lambda k: k.date == date)
            if day_kpis:
                stats = {
                    'date': date.strftime('%Y-%m-%d'),
                    'metrics': {
                        'revenue': sum(day_kpis.mapped('total_revenue')),
                        'orders': len(day_kpis),
                        'performance': {
                            'on_time_rate': sum(day_kpis.mapped('on_time_rate')) / len(day_kpis),
                            'rating': sum(day_kpis.mapped('average_rating')) / len(day_kpis),
                            'duration_accuracy': sum(day_kpis.mapped('duration_accuracy')) / len(day_kpis)
                        },
                        'timing': {
                            'early_starts': sum(day_kpis.mapped('early_starts')),
                            'late_starts': sum(day_kpis.mapped('late_starts')),
                            'early_completions': sum(day_kpis.mapped('early_completions')),
                            'late_completions': sum(day_kpis.mapped('late_completions'))
                        }
                    }
                }
                daily_stats.append(stats)
        
        return daily_stats

    @http.route('/web/v2/dashboard/mechanic/team-performance', type='json', auth='user', methods=['POST'], csrf=False)
    def get_team_performance(self, **kw):
        """Get comprehensive team performance metrics"""
        try:
            # Get date range
            date_range = kw.get('date_range', 'today')
            start_date, end_date = self._get_date_range(
                date_range, 
                kw.get('start_date'), 
                kw.get('end_date')
            )
            
            if not start_date or not end_date:
                return {'status': 'error', 'message': 'Invalid date range'}

            # Convert to UTC for database queries
            start_date_utc = start_date.astimezone(pytz.UTC)
            end_date_utc = end_date.astimezone(pytz.UTC)

            # Get all team leaders
            leaders = request.env['pitcar.mechanic.new'].search([
                ('position_code', '=', 'leader')
            ])

            # Get all KPIs in one query
            all_kpis = request.env['mechanic.kpi'].search([
                ('date', '>=', start_date_utc.date()),
                ('date', '<=', end_date_utc.date())
            ])

            teams = []
            for leader in leaders:
                team_members = request.env['pitcar.mechanic.new'].search([
                    ('leader_id', '=', leader.id)
                ])
                
                # Get leader and team KPIs
                leader_kpis = all_kpis.filtered(lambda k: k.mechanic_id.id == leader.id)
                team_kpis = all_kpis.filtered(lambda k: k.mechanic_id.id in team_members.ids)
                all_team_kpis = leader_kpis + team_kpis

                if all_team_kpis:
                    # Calculate team target
                    days_in_range = (end_date - start_date).days + 1
                    total_target = ((leader.monthly_target or 64000000.0) + 
                                sum(m.monthly_target or 64000000.0 for m in team_members))
                    adjusted_team_target = (total_target / 30) * days_in_range

                    teams.append({
                        'id': leader.id,
                        'name': leader.name,
                        'position': 'Team',
                        'member_count': len(team_members) + 1,  # Including leader
                        'metrics': self._calculate_detailed_metrics(all_team_kpis, adjusted_team_target),
                        'trends': self._get_daily_stats(all_team_kpis)
                    })

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start_date.strftime('%Y-%m-%d'),
                        'end': end_date.strftime('%Y-%m-%d')
                    },
                    'teams': teams
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_team_performance: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_member_performance(self, members, start_date_utc, end_date_utc, all_kpis=None):
        """Get detailed performance metrics for team members"""
        member_stats = []
        
        for member in members:
            # If all_kpis is provided, filter from it instead of making new query
            if all_kpis is not None:
                member_kpis = all_kpis.filtered(lambda k: k.mechanic_id.id == member.id)
            else:
                member_kpis = request.env['mechanic.kpi'].search([
                    ('mechanic_id', '=', member.id),
                    ('date', '>=', start_date_utc.date()),
                    ('date', '<=', end_date_utc.date())
                ])
            
            if member_kpis:
                # Calculate adjusted target
                monthly_target = member.monthly_target or 64000000.0
                days_in_range = (end_date_utc - start_date_utc).days + 1
                adjusted_target = (monthly_target / 30) * days_in_range
                total_revenue = sum(member_kpis.mapped('total_revenue'))

                member_stats.append({
                    'id': member.id,
                    'name': member.name,
                    'metrics': {
                        'revenue': {
                            'total': total_revenue,
                            'target': adjusted_target,
                            'achievement': (total_revenue / adjusted_target * 100) if adjusted_target else 0
                        },
                        'orders': {
                            'total': len(member_kpis),
                            'average_value': total_revenue / len(member_kpis) if member_kpis else 0
                        },
                        'performance': {
                            'on_time_rate': sum(member_kpis.mapped('on_time_rate')) / len(member_kpis),
                            'rating': sum(member_kpis.mapped('average_rating')) / len(member_kpis),
                            'duration_accuracy': sum(member_kpis.mapped('duration_accuracy')) / len(member_kpis)
                        }
                    }
                })
        
        return member_stats

    def _get_team_daily_trend(self, team_kpis):
        """Get daily trend data for team performance"""
        if not team_kpis:
            return []
            
        dates = sorted(set(team_kpis.mapped('date')))
        trend_data = []
        
        for date in dates:
            day_kpis = team_kpis.filtered(lambda k: k.date == date)
            trend_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'metrics': {
                    'revenue': sum(day_kpis.mapped('total_revenue')),
                    'orders': sum(day_kpis.mapped('total_orders')),
                    'on_time_rate': sum(day_kpis.mapped('on_time_rate')) / len(day_kpis),
                    'rating': sum(day_kpis.mapped('average_rating')) / len(day_kpis)
                }
            })
            
        return trend_data