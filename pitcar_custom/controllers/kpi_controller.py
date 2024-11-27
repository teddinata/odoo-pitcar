from odoo import http, fields
from odoo.http import request
import json
from datetime import datetime, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)

class KPIController(http.Controller):
    def _get_date_range(self, range_type='today', start_date=None, end_date=None):
        """Helper to get date range based on type"""
        tz = pytz.timezone('Asia/Jakarta')
        now = datetime.now(tz)
        
        if start_date and end_date:
            return start_date, end_date
            
        if range_type == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif range_type == 'yesterday':
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(hour=23, minute=59, second=59)
        elif range_type == 'this_week':
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif range_type == 'this_month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif range_type == 'last_month':
            last_month = now.replace(day=1) - timedelta(days=1)
            start = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = last_month.replace(day=last_month.day, hour=23, minute=59, second=59)
        elif range_type == 'this_year':
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        else:  # default to today
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
            
        return start, end

    @http.route('/web/smart/dashboard/mechanic', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_dashboard_overview(self, **kw):
        try:
            data = request.get_json_data()
            date_range = data.get('date_range', 'today')  # today, this_week, this_month, custom
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            if start_date and end_date:
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d')
                    end_date = datetime.strptime(end_date, '%Y-%m-%d')
                except ValueError:
                    return {'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD'}
                    
            start_date, end_date = self._get_date_range(date_range, start_date, end_date)
            
            # Get all mechanics with their hierarchy info
            mechanics = request.env['pitcar.mechanic.new'].search([])
            mechanic_data = []
            team_data = {}

            for mech in mechanics:
                # Get KPIs for the date range
                kpis = request.env['mechanic.kpi'].search([
                    ('mechanic_id', '=', mech.id),
                    ('date', '>=', start_date.date()),
                    ('date', '<=', end_date.date())
                ])

                # Calculate metrics
                total_revenue = sum(kpis.mapped('total_revenue'))
                monthly_target = mech.monthly_target or 64000000.0
                achievement = (total_revenue / monthly_target * 100) if monthly_target else 0

                mechanic_info = {
                    'id': mech.id,
                    'name': mech.name,
                    'position': 'Team Leader' if mech.position_code == 'leader' else 'Mechanic',
                    'metrics': {
                        'revenue': {
                            'total': total_revenue,
                            'target': monthly_target,
                            'achievement': achievement
                        },
                        'orders': {
                            'total': sum(kpis.mapped('total_orders')),
                            'average_value': sum(kpis.mapped('average_order_value')) / len(kpis) if kpis else 0
                        },
                        'performance': {
                            'on_time_rate': sum(kpis.mapped('on_time_rate')) / len(kpis) if kpis else 0,
                            'average_rating': sum(kpis.mapped('average_rating')) / len(kpis) if kpis else 0,
                            'duration_accuracy': sum(kpis.mapped('duration_accuracy')) / len(kpis) if kpis else 0
                        }
                    },
                    'leader_id': mech.leader_id.id if mech.leader_id else None,
                    'team_members': []
                }

                # Group by team
                if mech.position_code == 'leader':
                    team_data[mech.id] = mechanic_info
                else:
                    mechanic_data.append(mechanic_info)
                    if mech.leader_id:
                        if mech.leader_id.id in team_data:
                            team_data[mech.leader_id.id]['team_members'].append(mechanic_info)

            # Aggregate performance metrics
            all_kpis = request.env['mechanic.kpi'].search([
                ('date', '>=', start_date.date()),
                ('date', '<=', end_date.date())
            ])

            performance_metrics = {
                'duration': {
                    'total_estimated': sum(all_kpis.mapped('total_estimated_duration')),
                    'total_actual': sum(all_kpis.mapped('total_actual_duration')),
                    'accuracy': sum(all_kpis.mapped('duration_accuracy')) / len(all_kpis) if all_kpis else 0,
                    'average_deviation': sum(all_kpis.mapped('average_duration_deviation')) / len(all_kpis) if all_kpis else 0
                },
                'timing': {
                    'early_starts': sum(all_kpis.mapped('early_starts')),
                    'late_starts': sum(all_kpis.mapped('late_starts')),
                    'early_completions': sum(all_kpis.mapped('early_completions')),
                    'late_completions': sum(all_kpis.mapped('late_completions')),
                    'average_delay': sum(all_kpis.mapped('average_delay')) / len(all_kpis) if all_kpis else 0
                },
                'quality': {
                    'average_rating': sum(all_kpis.mapped('average_rating')) / len(all_kpis) if all_kpis else 0,
                    'total_complaints': sum(all_kpis.mapped('total_complaints')),
                    'complaint_rate': sum(all_kpis.mapped('complaint_rate')) / len(all_kpis) if all_kpis else 0
                }
            }

            # Get trend data
            trend_data = self._get_trend_data(start_date.date(), end_date.date(), all_kpis)

            # Calculate team summaries
            team_summaries = []
            for team_id, team_info in team_data.items():
                team_members = team_info['team_members']
                team_revenue = sum(m['metrics']['revenue']['total'] for m in team_members)
                team_target = sum(m['metrics']['revenue']['target'] for m in team_members)
                
                team_summaries.append({
                    'team_id': team_id,
                    'leader_name': team_info['name'],
                    'member_count': len(team_members),
                    'total_revenue': team_revenue,
                    'target_revenue': team_target,
                    'achievement': (team_revenue / team_target * 100) if team_target else 0,
                    'average_performance': {
                        'on_time_rate': sum(m['metrics']['performance']['on_time_rate'] for m in team_members) / len(team_members) if team_members else 0,
                        'rating': sum(m['metrics']['performance']['average_rating'] for m in team_members) / len(team_members) if team_members else 0
                    }
                })

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start_date.strftime('%Y-%m-%d'),
                        'end': end_date.strftime('%Y-%m-%d')
                    },
                    'overview': {
                        'total_revenue': sum(m['metrics']['revenue']['total'] for m in mechanic_data),
                        'total_orders': sum(m['metrics']['orders']['total'] for m in mechanic_data),
                        'average_rating': performance_metrics['quality']['average_rating'],
                        'on_time_rate': sum(m['metrics']['performance']['on_time_rate'] for m in mechanic_data) / len(mechanic_data) if mechanic_data else 0
                    },
                    'teams': team_summaries,
                    'mechanics': mechanic_data,
                    'performance': performance_metrics,
                    'trends': trend_data
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_dashboard_overview: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_trend_data(self, start_date, end_date, kpis):
        """Helper method to generate trend data"""
        trend_data = []
        current_date = start_date
        
        while current_date <= end_date:
            day_kpis = kpis.filtered(lambda k: k.date == current_date)
            
            if day_kpis:
                trend_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'metrics': {
                        'revenue': sum(day_kpis.mapped('total_revenue')),
                        'orders': sum(day_kpis.mapped('total_orders')),
                        'on_time_rate': sum(day_kpis.mapped('on_time_rate')) / len(day_kpis),
                        'rating': sum(day_kpis.mapped('average_rating')) / len(day_kpis)
                    }
                })
            
            current_date += timedelta(days=1)
            
        return trend_data

    @http.route('/web/smart/dashboard/mechanic/detail/<int:mechanic_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_mechanic_detail(self, mechanic_id, **kw):
        """Get detailed KPIs for a specific mechanic"""
        try:
            data = request.get_json_data()
            date_range = data.get('date_range', 'today')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            start_date, end_date = self._get_date_range(date_range, start_date, end_date)
            
            mechanic = request.env['pitcar.mechanic.new'].browse(mechanic_id)
            if not mechanic.exists():
                return {'status': 'error', 'message': 'Mechanic not found'}

            kpis = request.env['mechanic.kpi'].search([
                ('mechanic_id', '=', mechanic_id),
                ('date', '>=', start_date.date()),
                ('date', '<=', end_date.date())
            ])

            # Get team metrics if leader
            team_metrics = None
            if mechanic.position_code == 'leader':
                team_metrics = self._get_team_metrics(mechanic, start_date, end_date)

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
                    'metrics': {
                        'revenue': {
                            'total': sum(kpis.mapped('total_revenue')),
                            'target': mechanic.monthly_target,
                            'achievement': sum(kpis.mapped('revenue_achievement')) / len(kpis) if kpis else 0
                        },
                        'orders': {
                            'total': sum(kpis.mapped('total_orders')),
                            'average_value': sum(kpis.mapped('average_order_value')) / len(kpis) if kpis else 0
                        },
                        'performance': {
                            'on_time_rate': sum(kpis.mapped('on_time_rate')) / len(kpis) if kpis else 0,
                            'rating': sum(kpis.mapped('average_rating')) / len(kpis) if kpis else 0,
                            'complaints': sum(kpis.mapped('total_complaints')),
                            'complaint_rate': sum(kpis.mapped('complaint_rate')) / len(kpis) if kpis else 0
                        },
                        'timing': {
                            'early_starts': sum(kpis.mapped('early_starts')),
                            'late_starts': sum(kpis.mapped('late_starts')),
                            'early_completions': sum(kpis.mapped('early_completions')),
                            'late_completions': sum(kpis.mapped('late_completions')),
                            'average_delay': sum(kpis.mapped('average_delay')) / len(kpis) if kpis else 0
                        },
                        'duration': {
                            'total_estimated': sum(kpis.mapped('total_estimated_duration')),
                            'total_actual': sum(kpis.mapped('total_actual_duration')),
                            'accuracy': sum(kpis.mapped('duration_accuracy')) / len(kpis) if kpis else 0,
                            'average_deviation': sum(kpis.mapped('average_duration_deviation')) / len(kpis) if kpis else 0
                        }
                    },
                    'team_metrics': team_metrics,
                    'daily_stats': self._get_daily_stats(kpis)
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_mechanic_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_team_metrics(self, leader, start_date, end_date):
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
        
        for member in team_members:
            member_kpis = request.env['mechanic.kpi'].search([
                ('mechanic_id', '=', member.id),
                ('date', '>=', start_date.date()),
                ('date', '<=', end_date.date())
            ])
            
            if member_kpis:
                member_metrics = {
                    'id': member.id,
                    'name': member.name,
                    'metrics': {
                        'revenue': {
                            'total': sum(member_kpis.mapped('total_revenue')),
                            'target': member.monthly_target,
                            'achievement': sum(member_kpis.mapped('revenue_achievement')) / len(member_kpis)
                        },
                        'orders': sum(member_kpis.mapped('total_orders')),
                        'performance': {
                            'on_time_rate': sum(member_kpis.mapped('on_time_rate')) / len(member_kpis),
                            'rating': sum(member_kpis.mapped('average_rating')) / len(member_kpis)
                        }
                    }
                }
                team_metrics['members'].append(member_metrics)
                
                # Update summary
                team_metrics['summary']['total_revenue'] += member_metrics['metrics']['revenue']['total']
                team_metrics['summary']['total_orders'] += member_metrics['metrics']['orders']
                team_metrics['summary']['average_rating'] += member_metrics['metrics']['performance']['rating']
                team_metrics['summary']['on_time_rate'] += member_metrics['metrics']['performance']['on_time_rate']
                team_metrics['summary']['target_achievement'] += member_metrics['metrics']['revenue']['achievement']
        
        # Calculate averages for summary
        member_count = len(team_metrics['members'])
        if member_count > 0:
            team_metrics['summary']['average_rating'] /= member_count
            team_metrics['summary']['on_time_rate'] /= member_count
            team_metrics['summary']['target_achievement'] /= member_count
        
        return team_metrics

    def _get_daily_stats(self, kpis):
        """Get daily statistics for KPIs"""
        daily_stats = []
        
        for kpi in kpis.sorted(key=lambda k: k.date):
            stats = {
                'date': kpi.date.strftime('%Y-%m-%d'),
                'metrics': {
                    'revenue': kpi.total_revenue,
                    'orders': kpi.total_orders,
                    'performance': {
                        'on_time_rate': kpi.on_time_rate,
                        'rating': kpi.average_rating,
                        'duration_accuracy': kpi.duration_accuracy
                    },
                    'timing': {
                        'early_starts': kpi.early_starts,
                        'late_starts': kpi.late_starts,
                        'early_completions': kpi.early_completions,
                        'late_completions': kpi.late_completions
                    }
                }
            }
            daily_stats.append(stats)
        
        return daily_stats

    @http.route('/web/smart/dashboard/mechanic/team-performance', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_team_performance(self, **kw):
        """Get comprehensive team performance metrics"""
        try:
            data = request.get_json_data()
            date_range = data.get('date_range', 'today')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            start_date, end_date = self._get_date_range(date_range, start_date, end_date)
            
            # Get all team leaders
            leaders = request.env['pitcar.mechanic.new'].search([
                ('position_code', '=', 'leader')
            ])
            
            teams_data = {}
            for leader in leaders:
                team_members = request.env['pitcar.mechanic.new'].search([
                    ('leader_id', '=', leader.id)
                ])
                
                # Get KPIs for leader and team members
                team_kpis = request.env['mechanic.kpi'].search([
                    ('mechanic_id', 'in', [leader.id] + team_members.ids),
                    ('date', '>=', start_date.date()),
                    ('date', '<=', end_date.date())
                ])
                
                # Calculate team metrics
                total_revenue = sum(team_kpis.mapped('total_revenue'))
                total_orders = sum(team_kpis.mapped('total_orders'))
                team_target = len(team_members) * 64000000  # Base target per member
                
                teams_data[leader.id] = {
                    'leader': {
                        'id': leader.id,
                        'name': leader.name
                    },
                    'metrics': {
                        'revenue': {
                            'total': total_revenue,
                            'target': team_target,
                            'achievement': (total_revenue / team_target * 100) if team_target else 0
                        },
                        'orders': {
                            'total': total_orders,
                            'average_per_member': total_orders / len(team_members) if team_members else 0
                        },
                        'performance': {
                            'on_time_rate': sum(team_kpis.mapped('on_time_rate')) / len(team_kpis) if team_kpis else 0,
                            'average_rating': sum(team_kpis.mapped('average_rating')) / len(team_kpis) if team_kpis else 0,
                            'complaint_rate': sum(team_kpis.mapped('complaint_rate')) / len(team_kpis) if team_kpis else 0
                        }
                    },
                    'members': self._get_member_performance(team_members, start_date, end_date),
                    'daily_trend': self._get_team_daily_trend(team_kpis)
                }
            
            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start_date.strftime('%Y-%m-%d'),
                        'end': end_date.strftime('%Y-%m-%d')
                    },
                    'teams': teams_data
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_team_performance: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_member_performance(self, members, start_date, end_date):
        """Get detailed performance metrics for team members"""
        member_stats = []
        
        for member in members:
            member_kpis = request.env['mechanic.kpi'].search([
                ('mechanic_id', '=', member.id),
                ('date', '>=', start_date.date()),
                ('date', '<=', end_date.date())
            ])
            
            if member_kpis:
                member_stats.append({
                    'id': member.id,
                    'name': member.name,
                    'metrics': {
                        'revenue': {
                            'total': sum(member_kpis.mapped('total_revenue')),
                            'target': member.monthly_target,
                            'achievement': sum(member_kpis.mapped('revenue_achievement')) / len(member_kpis)
                        },
                        'orders': {
                            'total': sum(member_kpis.mapped('total_orders')),
                            'average_value': sum(member_kpis.mapped('average_order_value')) / len(member_kpis)
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