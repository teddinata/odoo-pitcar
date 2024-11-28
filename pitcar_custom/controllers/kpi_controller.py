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

            # Get KPIs with strict date filtering
            kpi_domain = [
                ('date', '>=', start_date_utc.date()),
                ('date', '<=', end_date_utc.date())
            ]
            
            kpis = request.env['mechanic.kpi'].search(kpi_domain)
            
            # Filter KPIs by date and verify the data
            kpis = kpis.filtered(lambda k: 
                k.date >= start_date_utc.date() and 
                k.date <= end_date_utc.date() and
                k.total_revenue > 0  # Only include KPIs with valid revenue
            )

            # Calculate dashboard metrics
            dashboard_data = self._calculate_dashboard_metrics(kpis)
            teams_data = self._get_team_performance(kpis)
            mechanics_data = self._get_mechanic_performance(kpis)
            
            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start_date.strftime('%Y-%m-%d'),
                        'end': end_date.strftime('%Y-%m-%d')
                    },
                    'overview': dashboard_data,
                    'teams': teams_data,
                    'mechanics': mechanics_data,
                    'trends': self._calculate_trends(kpis)
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_mechanic_kpi_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    def _calculate_revenue_for_period(self, kpis):
        """Calculate accurate revenue for the given period"""
        if not kpis:
            return 0
            
        return sum(kpis.mapped('total_revenue'))

    def _calculate_dashboard_metrics(self, kpis):
        """Calculate overall dashboard metrics with accurate filtering"""
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

        # Calculate accurate revenue
        total_revenue = self._calculate_revenue_for_period(kpis)
        total_orders = len(kpis)

        return {
            'total_revenue': total_revenue,
            'total_orders': total_orders,
            'average_rating': sum(kpis.mapped('average_rating')) / len(kpis) if kpis else 0,
            'on_time_rate': sum(kpis.mapped('on_time_rate')) / len(kpis) if kpis else 0,
            'complaints': {
                'total': sum(kpis.mapped('total_complaints')),
                'rate': (sum(kpis.mapped('total_complaints')) / total_orders * 100) if total_orders else 0
            },
            'performance': {
                'duration_accuracy': sum(kpis.mapped('duration_accuracy')) / len(kpis) if kpis else 0,
                'early_completion_rate': sum(kpis.mapped('early_completions')) / total_orders * 100 if total_orders else 0,
                'late_completion_rate': sum(kpis.mapped('late_completions')) / total_orders * 100 if total_orders else 0
            }
        }

    def _get_team_performance(self, kpis):
        """Calculate team performance metrics"""
        team_list = []
        
        # Get all team leaders
        team_leaders = request.env['pitcar.mechanic.new'].search([
            ('position_code', '=', 'leader')
        ])
        
        for leader in team_leaders:
            # Get team members
            team_members = request.env['pitcar.mechanic.new'].search([
                ('leader_id', '=', leader.id)
            ])
            
            # Include leader in member count
            member_count = len(team_members) + 1
            team_member_ids = team_members.ids + [leader.id]
            
            # Get KPIs for the entire team
            team_kpis = kpis.filtered(lambda k: k.mechanic_id.id in team_member_ids)
            
            if not team_kpis:
                continue

            total_revenue = sum(team_kpis.mapped('total_revenue'))
            total_orders = sum(team_kpis.mapped('total_orders'))
            monthly_target = member_count * 64000000  # Base target per mechanic
            
            team_list.append({
                'id': leader.id,
                'name': leader.name,
                'position': 'Team',
                'member_count': member_count,
                'metrics': {
                    'revenue': {
                        'total': total_revenue,
                        'target': monthly_target,
                        'achievement': (total_revenue / monthly_target * 100) if monthly_target else 0
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

    def _get_mechanic_performance(self, kpis):
        """Calculate individual mechanic performance"""
        mechanic_data = {}
        
        for kpi in kpis:
            mechanic_id = kpi.mechanic_id.id
            if mechanic_id not in mechanic_data:
                mechanic_data[mechanic_id] = {
                    'id': mechanic_id,
                    'name': kpi.mechanic_id.name,
                    'position': 'Team Leader' if kpi.mechanic_id.position_code == 'leader' else 'Mechanic',
                    'metrics': {
                        'revenue': {
                            'total': 0,
                            'target': kpi.monthly_target,
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
                }
            
            data = mechanic_data[mechanic_id]
            data['metrics']['revenue']['total'] += kpi.total_revenue
            data['metrics']['orders']['total'] += kpi.total_orders
            
            # Update averages
            kpi_count = len(kpis.filtered(lambda k: k.mechanic_id.id == mechanic_id))
            if kpi_count:
                data['metrics']['performance']['on_time_rate'] = sum(
                    kpis.filtered(lambda k: k.mechanic_id.id == mechanic_id).mapped('on_time_rate')
                ) / kpi_count
                data['metrics']['performance']['rating'] = sum(
                    kpis.filtered(lambda k: k.mechanic_id.id == mechanic_id).mapped('average_rating')
                ) / kpi_count
                data['metrics']['performance']['duration_accuracy'] = sum(
                    kpis.filtered(lambda k: k.mechanic_id.id == mechanic_id).mapped('duration_accuracy')
                ) / kpi_count
            
            # Calculate achievement and average order value
            if data['metrics']['revenue']['target']:
                data['metrics']['revenue']['achievement'] = (
                    data['metrics']['revenue']['total'] / data['metrics']['revenue']['target'] * 100
                )
            if data['metrics']['orders']['total']:
                data['metrics']['orders']['average_value'] = (
                    data['metrics']['revenue']['total'] / data['metrics']['orders']['total']
                )

        return list(mechanic_data.values())

    def _calculate_trends(self, kpis):
        """Calculate trend data for the dashboard"""
        if not kpis:
            return []

        dates = sorted(set(kpis.mapped('date')))
        trends = []

        for date in dates:
            day_kpis = kpis.filtered(lambda k: k.date == date)
            if day_kpis:
                trends.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'metrics': {
                        'revenue': sum(day_kpis.mapped('total_revenue')),
                        'orders': sum(day_kpis.mapped('total_orders')),
                        'on_time_rate': sum(day_kpis.mapped('on_time_rate')) / len(day_kpis),
                        'rating': sum(day_kpis.mapped('average_rating')) / len(day_kpis)
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