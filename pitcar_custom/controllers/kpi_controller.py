from odoo import http, fields
from odoo.http import request
import json
from datetime import datetime, timedelta, time
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

            # Initialize mechanics_data
            mechanics_data = {}
            for mechanic in mechanics:
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
                    'total_completions': 0,
                    'metrics': {
                        'utilization': {
                            'attendance_hours': 0,
                            'productive_hours': 0,
                            'utilization_rate': 0,
                            'target_rate': 85.0
                        }
                    }
                }

            # Process orders
            for order in orders:
                if not order.car_mechanic_id_new:
                    continue
                    
                for mechanic in order.car_mechanic_id_new:
                    if mechanic.id not in mechanics_data:
                        continue
                        
                    mech_data = mechanics_data[mechanic.id]
                    mechanic_count = len(order.car_mechanic_id_new)
                    
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

            # Calculate utilization for all mechanics
            # Bagian perhitungan utilization
            for mechanic_id, mech_data in mechanics_data.items():
                mechanic = mechanic_dict.get(mechanic_id)
                if not mechanic or not mechanic.employee_id:
                    continue

                # Get attendance records
                all_attendances = request.env['hr.attendance'].sudo().search([
                    ('employee_id', '=', mechanic.employee_id.id),
                    ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                    ('check_in', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                    ('check_out', '!=', False)
                ])

                total_attendance_hours = 0
                total_productive_hours = 0

                # Calculate attendance hours - PERLU DIUBAH
                for att in all_attendances:
                    check_in_local = pytz.utc.localize(fields.Datetime.from_string(att.check_in)).astimezone(tz)
                    check_out_local = pytz.utc.localize(fields.Datetime.from_string(att.check_out)).astimezone(tz)
                    
                    # Set work hours
                    work_start = check_in_local.replace(hour=8, minute=0, second=0)
                    
                    # Tidak perlu batasi sampai 17:00 jika ada overtime
                    effective_start = max(check_in_local, work_start)  # Tetap mulai jam 8 jika datang lebih awal
                    effective_end = check_out_local  # Gunakan actual check out untuk overtime
                    
                    if effective_end > effective_start:
                        # Handle break time
                        break_start = effective_start.replace(hour=12, minute=0, second=0)
                        break_end = effective_start.replace(hour=13, minute=0, second=0)
                        
                        if effective_start < break_end and effective_end > break_start:
                            morning_hours = (min(break_start, effective_end) - effective_start).total_seconds() / 3600
                            afternoon_hours = (effective_end - max(break_end, effective_start)).total_seconds() / 3600
                            total_attendance_hours += max(0, morning_hours) + max(0, afternoon_hours)
                        else:
                            total_attendance_hours += (effective_end - effective_start).total_seconds() / 3600

                # Calculate productive hours - PERLU DIUBAH 
                mechanic_orders = orders.filtered(lambda o: mechanic_id in o.car_mechanic_id_new.ids)
                for order in mechanic_orders:
                    if order.controller_mulai_servis and order.controller_selesai:
                        start_local = pytz.utc.localize(fields.Datetime.from_string(order.controller_mulai_servis)).astimezone(tz)
                        end_local = pytz.utc.localize(fields.Datetime.from_string(order.controller_selesai)).astimezone(tz)
                        
                        for att in all_attendances:
                            check_in_local = pytz.utc.localize(fields.Datetime.from_string(att.check_in)).astimezone(tz)
                            check_out_local = pytz.utc.localize(fields.Datetime.from_string(att.check_out)).astimezone(tz)
                            
                            # Set work hours with overtime handling
                            work_start = check_in_local.replace(hour=8, minute=0, second=0)
                            
                            start_overlap = max(start_local, check_in_local, work_start)
                            end_overlap = min(end_local, check_out_local)  # Allow overtime
                            
                            if end_overlap > start_overlap:
                                break_start = start_overlap.replace(hour=12, minute=0, second=0)
                                break_end = start_overlap.replace(hour=13, minute=0, second=0)
                                
                                if start_overlap < break_end and end_overlap > break_start:
                                    morning_prod = (min(break_start, end_overlap) - start_overlap).total_seconds() / 3600
                                    afternoon_prod = (end_overlap - max(break_end, start_overlap)).total_seconds() / 3600
                                    total_productive_hours += max(0, morning_prod) + max(0, afternoon_prod)
                                else:
                                    total_productive_hours += (end_overlap - start_overlap).total_seconds() / 3600

                # Update utilization metrics
                mech_data['metrics']['utilization'] = {
                    'attendance_hours': total_attendance_hours,
                    'productive_hours': total_productive_hours,
                    'utilization_rate': (total_productive_hours / total_attendance_hours * 100) if total_attendance_hours > 0 else 0,
                    'target_rate': 85.0
                }

                _logger.info(f"""
                    Mechanic: {mech_data['name']}
                    ID: {mechanic_id}
                    Attendance Hours: {total_attendance_hours:.2f}
                    Productive Hours: {total_productive_hours:.2f}
                    Rate: {(total_productive_hours / total_attendance_hours * 100) if total_attendance_hours > 0 else 0:.2f}%
                """)

            # Format active mechanics data
            active_mechanics = []
            for mechanic_id, data in mechanics_data.items():
                if data['orders'] > 0:
                    mechanic = mechanic_dict.get(mechanic_id)
                    if not mechanic:
                        continue

                    leader_info = None
                    if mechanic.leader_id:
                        leader_info = {
                            'id': mechanic.leader_id.id,
                            'name': mechanic.leader_id.name
                        }

                    metrics = {
                        'revenue': {
                            'total': data['revenue'],
                            'target': mechanic.monthly_target,
                            'achievement': (data['revenue'] / mechanic.monthly_target * 100) if mechanic.monthly_target else 0
                        },
                        'orders': {
                            'total': data['orders'],
                            'average_value': data['revenue'] / data['orders'] if data['orders'] else 0
                        },
                        'performance': {
                            'on_time_rate': (data['on_time_orders'] / data['orders'] * 100) if data['orders'] else 0,
                            'rating': min(data['total_rating'] / data['rated_orders'], 5.0) if data['rated_orders'] else 0,
                            'early_start_rate': (data['early_starts'] / data['total_completions'] * 100) if data['total_completions'] else 0,
                            'late_start_rate': (data['late_starts'] / data['total_completions'] * 100) if data['total_completions'] else 0,
                            'early_completion_rate': (data['early_completions'] / data['total_completions'] * 100) if data['total_completions'] else 0,
                            'late_completion_rate': (data['late_completions'] / data['total_completions'] * 100) if data['total_completions'] else 0
                        },
                        'utilization': data['metrics']['utilization']
                    }

                    active_mechanics.append({
                        'id': data['id'],
                        'name': data['name'],
                        'position': data['position'],
                        'leader': leader_info,
                        'metrics': metrics
                    })

            # Calculate team metrics
            teams_data = {}
            for mechanic_id, data in mechanics_data.items():
                mechanic = mechanic_dict.get(mechanic_id)
                if not mechanic:
                    continue
                    
                leader_id = mechanic.leader_id.id if mechanic.leader_id else (mechanic_id if mechanic.position_code == 'leader' else None)
                
                if leader_id:
                    if leader_id not in teams_data:
                        leader = mechanic_dict.get(leader_id)
                        if not leader:
                            continue
                            
                        leader_data = mechanics_data.get(leader_id, {})
                        teams_data[leader_id] = {
                            'id': leader_id,
                            'name': leader.name,
                            'position': 'Team',
                            'member_count': 0,
                            'total_rated_orders': 0,
                            'total_rating_sum': 0,
                            'metrics': {
                                'revenue': {
                                    # Lanjutan kode sebelumnya...

                                    'total': leader_data.get('revenue', 0),
                                    'target': 0,
                                    'achievement': 0
                                },
                                'orders': {
                                    'total': leader_data.get('orders', 0),
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
                    
                    if mechanic.position_code != 'leader':
                        team_data = teams_data[leader_id]
                        team_data['member_count'] += 1
                        team_data['metrics']['revenue']['total'] += data['revenue']
                        team_data['metrics']['orders']['total'] += data['orders']
                        
                        if data['rated_orders'] > 0:
                            team_data['total_rated_orders'] += data['rated_orders']
                            team_data['total_rating_sum'] += data['total_rating']
                        
                        if data['orders'] > 0:
                            team_data['metrics']['performance']['on_time_rate'] += (data['on_time_orders'] / data['orders'] * 100)
                        if data['total_completions'] > 0:
                            team_data['metrics']['performance']['early_completion_rate'] += (data['early_completions'] / data['total_completions'] * 100)
                            team_data['metrics']['performance']['late_completion_rate'] += (data['late_completions'] / data['total_completions'] * 100)

            # Calculate final team metrics
            for team in teams_data.values():
                if team['member_count'] > 0:
                    # Set target based on member count only (not including leader)
                    team['metrics']['revenue']['target'] = team['member_count'] * 64000000
                    
                    # Calculate achievement using total revenue (leader + members) against member-based target
                    team['metrics']['revenue']['achievement'] = (
                        team['metrics']['revenue']['total'] / team['metrics']['revenue']['target'] * 100
                    ) if team['metrics']['revenue']['target'] else 0
                    
                    # Calculate average value
                    team['metrics']['orders']['average_value'] = (
                        team['metrics']['revenue']['total'] / team['metrics']['orders']['total']
                    ) if team['metrics']['orders']['total'] else 0
                    
                    # Calculate proper team rating
                    team['metrics']['performance']['rating'] = (
                        team['total_rating_sum'] / team['total_rated_orders']
                        if team['total_rated_orders'] > 0 else 0
                    )
                    
                    # Average performance metrics by member count
                    team['metrics']['performance']['on_time_rate'] /= team['member_count']
                    team['metrics']['performance']['early_completion_rate'] /= team['member_count']
                    team['metrics']['performance']['late_completion_rate'] /= team['member_count']

            # Calculate overview metrics
            total_revenue = sum(order.amount_total for order in orders)
            total_orders = len(orders)
            total_completions = sum(1 for order in orders if order.controller_selesai)
            total_duration_accuracy = 0
            total_duration_orders = 0

            # Calculate time distribution metrics
            total_starts = 0
            early_starts = 0
            ontime_starts = 0
            late_starts = 0

            for order in orders:
                # Calculate duration accuracy
                if (order.controller_selesai and order.controller_estimasi_selesai and 
                    order.controller_mulai_servis and order.controller_estimasi_mulai):
                    try:
                        total_duration_orders += 1
                        estimated_duration = (fields.Datetime.from_string(order.controller_estimasi_selesai) - 
                                            fields.Datetime.from_string(order.controller_estimasi_mulai)).total_seconds() / 3600
                        actual_duration = (fields.Datetime.from_string(order.controller_selesai) - 
                                        fields.Datetime.from_string(order.controller_mulai_servis)).total_seconds() / 3600
                        if estimated_duration > 0:
                            accuracy = (1 - abs(actual_duration - estimated_duration) / estimated_duration) * 100
                            total_duration_accuracy += accuracy
                            
                        # Calculate start time distribution
                        total_starts += 1
                        est_start = fields.Datetime.from_string(order.controller_estimasi_mulai)
                        actual_start = fields.Datetime.from_string(order.controller_mulai_servis)
                        
                        if actual_start < est_start:
                            early_starts += 1
                        elif actual_start > est_start:
                            late_starts += 1
                        else:
                            ontime_starts += 1
                            
                    except Exception as e:
                        _logger.error(f"Error calculating metrics for order {order.id}: {str(e)}")
                        continue

            avg_duration_accuracy = total_duration_accuracy / total_duration_orders if total_duration_orders > 0 else 0

            # Calculate completion metrics
            total_completions = sum(1 for order in orders if order.controller_selesai)
            early_completions = sum(1 for order in orders if order.controller_selesai and 
                                order.controller_estimasi_selesai and 
                                order.controller_selesai <= order.controller_estimasi_selesai)
            late_completions = sum(1 for order in orders if order.controller_selesai and 
                                order.controller_estimasi_selesai and 
                                order.controller_selesai > order.controller_estimasi_selesai)

            # Calculate rating metrics
            rated_orders = orders.filtered(lambda o: o.customer_rating)
            total_rated_orders = len(rated_orders)
            average_rating = (
                sum(float(order.customer_rating) for order in rated_orders) / total_rated_orders
                if total_rated_orders else 0
            )

            complaints = len(orders.filtered(lambda o: o.customer_rating in ['1', '2']))

            overview = {
                'total_revenue': total_revenue,
                'total_orders': total_orders,
                'rating': {
                    'average': average_rating,
                    'total_rated_orders': total_rated_orders
                },
                'on_time_rate': (early_completions / total_completions * 100) if total_completions else 0,
                'complaints': {
                    'total': complaints,
                    'rate': (complaints / total_orders * 100) if total_orders else 0
                },
                'performance': {
                    'duration_accuracy': avg_duration_accuracy,
                    'early_completion_rate': (early_completions / total_completions * 100) if total_completions else 0,
                    'late_completion_rate': (late_completions / total_completions * 100) if total_completions else 0,
                    'early_start_rate': (early_starts / total_starts * 100) if total_starts else 0,
                    'ontime_start_rate': (ontime_starts / total_starts * 100) if total_starts else 0,
                    'late_start_rate': (late_starts / total_starts * 100) if total_starts else 0
                }
            }

            # Calculate daily trends
            trends = []
            current = start
            while current <= end:
                try:
                    current_end = min(current.replace(hour=23, minute=59, second=59), end)
                    current_start = current.replace(hour=0, minute=0, second=0)
                    trend_date = current.date()
                    
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
                        
                        # Get daily mechanics utilization
                        attendance_hours = 0
                        productive_hours = 0
                        
                        # Filter mechanics who worked on this day's orders
                        day_mechanics = set()
                        for order in day_orders:
                            if order.car_mechanic_id_new:
                                day_mechanics.update(order.car_mechanic_id_new.ids)
                        
                        # Get utilization data from mechanics_data
                        for mechanic_id in day_mechanics:
                            if mechanic_id in mechanics_data:
                                mech_data = mechanics_data[mechanic_id]
                                util_data = mech_data['metrics']['utilization']
                                attendance_hours += util_data['attendance_hours']
                                productive_hours += util_data['productive_hours']
                        
                        trends.append({
                            'date': current.strftime('%Y-%m-%d'),
                            'metrics': {
                                'revenue': daily_revenue,
                                'orders': len(day_orders),
                                'on_time_rate': (daily_early_completions / daily_completions * 100) if daily_completions else 0,
                                'rating': daily_rating,
                                'utilization': {
                                    'attendance_hours': attendance_hours,
                                    'productive_hours': productive_hours,
                                    'rate': (productive_hours / attendance_hours * 100) if attendance_hours > 0 else 0
                                }
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
                
            # Get mechanic data
            mechanic = request.env['pitcar.mechanic.new'].sudo().browse(mechanic_id)
            if not mechanic.exists():
                return {'status': 'error', 'message': 'Mechanic not found'}

            # Get orders in a single query
            domain = [
                ('date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', '=', 'sale'),
            ]
            all_orders = request.env['sale.order'].sudo().search(domain)

            # Filter orders for this mechanic
            mechanic_orders = all_orders.filtered(lambda o: mechanic_id in o.car_mechanic_id_new.ids)

            # Pre-process orders by date for trends
            orders_by_date = {}
            for order in mechanic_orders:
                order_date = pytz.utc.localize(fields.Datetime.from_string(order.date_completed)).astimezone(tz).date()
                if order_date not in orders_by_date:
                    orders_by_date[order_date] = []
                orders_by_date[order_date].append(order)

            # 1. Calculate basic metrics first
            total_revenue = 0
            total_orders = len(mechanic_orders)
            total_starts = 0
            early_starts = 0
            ontime_starts = 0
            late_starts = 0
            total_completions = 0
            early_completions = 0
            late_completions = 0
            total_duration_accuracy = 0
            total_duration_orders = 0
            total_rating = 0
            total_rated_orders = 0

            for order in mechanic_orders:
                # Calculate revenue considering multiple mechanics
                mechanic_count = len(order.car_mechanic_id_new)
                total_revenue += order.amount_total / mechanic_count

                # Calculate time-based metrics if all required fields exist
                if all([order.controller_estimasi_mulai, order.controller_mulai_servis,
                    order.controller_estimasi_selesai, order.controller_selesai]):
                    try:
                        # Convert timestamps once
                        est_start = fields.Datetime.from_string(order.controller_estimasi_mulai)
                        actual_start = fields.Datetime.from_string(order.controller_mulai_servis)
                        est_end = fields.Datetime.from_string(order.controller_estimasi_selesai)
                        actual_end = fields.Datetime.from_string(order.controller_selesai)

                        # Time distribution metrics
                        total_starts += 1
                        if actual_start < est_start:
                            early_starts += 1
                        elif actual_start > est_start:
                            late_starts += 1
                        else:
                            ontime_starts += 1

                        # Completion metrics
                        total_completions += 1
                        if actual_end <= est_end:
                            early_completions += 1
                        else:
                            late_completions += 1

                        # Duration accuracy
                        estimated_duration = (est_end - est_start).total_seconds() / 3600
                        actual_duration = (actual_end - actual_start).total_seconds() / 3600
                        if estimated_duration > 0:
                            total_duration_orders += 1
                            accuracy = (1 - abs(actual_duration - estimated_duration) / estimated_duration) * 100
                            total_duration_accuracy += accuracy

                    except Exception as e:
                        _logger.error(f"Error calculating time metrics for order {order.id}: {str(e)}")
                        continue

                # Rating metrics
                if order.customer_rating:
                    total_rated_orders += 1
                    total_rating += float(order.customer_rating)

            # 2. Initialize metrics dictionary with basic metrics
            metrics = {
                'revenue': {
                    'total': total_revenue,
                    'target': mechanic.monthly_target,
                    'achievement': (total_revenue / mechanic.monthly_target * 100) if mechanic.monthly_target else 0
                },
                'orders': {
                    'total': total_orders,
                    'average_value': total_revenue / total_orders if total_orders else 0
                },
                'performance': {
                    'duration_accuracy': total_duration_accuracy / total_duration_orders if total_duration_orders else 0,
                    'rating': total_rating / total_rated_orders if total_rated_orders else 0,
                    'early_start_rate': (early_starts / total_starts * 100) if total_starts else 0,
                    'ontime_start_rate': (ontime_starts / total_starts * 100) if total_starts else 0,
                    'late_start_rate': (late_starts / total_starts * 100) if total_starts else 0,
                    'early_completion_rate': (early_completions / total_completions * 100) if total_completions else 0,
                    'late_completion_rate': (late_completions / total_completions * 100) if total_completions else 0
                }
            }

            # 3. Calculate utilization metrics
            attendance_records = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', mechanic.employee_id.id),
                ('check_in', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_in', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('check_out', '!=', False)
            ])

            total_attendance_hours = 0
            total_productive_hours = 0

            # Calculate attendance hours
            for att in attendance_records:
                check_in_local = pytz.utc.localize(fields.Datetime.from_string(att.check_in)).astimezone(tz)
                check_out_local = pytz.utc.localize(fields.Datetime.from_string(att.check_out)).astimezone(tz)
                
                # Set work start (minimal jam 8)
                work_start = check_in_local.replace(hour=8, minute=0, second=0)
                
                # Effective time calculation
                effective_start = max(check_in_local, work_start)
                effective_end = check_out_local  # Allow overtime
                
                if effective_end > effective_start:
                    break_start = effective_start.replace(hour=12, minute=0, second=0)
                    break_end = effective_start.replace(hour=13, minute=0, second=0)
                    
                    if effective_start < break_end and effective_end > break_start:
                        morning_hours = (min(break_start, effective_end) - effective_start).total_seconds() / 3600
                        afternoon_hours = (effective_end - max(break_end, effective_start)).total_seconds() / 3600
                        total_attendance_hours += max(0, morning_hours) + max(0, afternoon_hours)
                    else:
                        total_attendance_hours += (effective_end - effective_start).total_seconds() / 3600

            # Calculate productive hours
            for order in mechanic_orders:
                if order.controller_mulai_servis and order.controller_selesai:
                    start_local = pytz.utc.localize(fields.Datetime.from_string(order.controller_mulai_servis)).astimezone(tz)
                    end_local = pytz.utc.localize(fields.Datetime.from_string(order.controller_selesai)).astimezone(tz)
                    
                    for att in attendance_records:
                        check_in_local = pytz.utc.localize(fields.Datetime.from_string(att.check_in)).astimezone(tz)
                        check_out_local = pytz.utc.localize(fields.Datetime.from_string(att.check_out)).astimezone(tz)
                        
                        work_start = check_in_local.replace(hour=8, minute=0, second=0)
                        
                        start_overlap = max(start_local, check_in_local, work_start)
                        end_overlap = min(end_local, check_out_local)  # Allow overtime
                        
                        if end_overlap > start_overlap:
                            break_start = start_overlap.replace(hour=12, minute=0, second=0)
                            break_end = start_overlap.replace(hour=13, minute=0, second=0)
                            
                            if start_overlap < break_end and end_overlap > break_start:
                                morning_prod = (min(break_start, end_overlap) - start_overlap).total_seconds() / 3600
                                afternoon_prod = (end_overlap - max(break_end, start_overlap)).total_seconds() / 3600
                                total_productive_hours += max(0, morning_prod) + max(0, afternoon_prod)
                            else:
                                total_productive_hours += (end_overlap - start_overlap).total_seconds() / 3600

            # 4. Update metrics with utilization data
            metrics['utilization'] = {
                'attendance_hours': total_attendance_hours,
                'productive_hours': total_productive_hours,
                'utilization_rate': (total_productive_hours / total_attendance_hours * 100) if total_attendance_hours > 0 else 0,
                'target_rate': 85.0
            }

            # 5. Calculate team data if mechanic is a leader
            team_data = None
            if mechanic.position_code == 'leader':
                team_members = request.env['pitcar.mechanic.new'].sudo().search([
                    ('leader_id', '=', mechanic.id)
                ])
                
                team_orders = all_orders.filtered(
                    lambda o: any(m.id in o.car_mechanic_id_new.ids for m in team_members)
                )

                if team_orders:
                    team_metrics = {
                        'revenue': 0,
                        'orders': len(team_orders),
                        'performance': {
                            'duration_accuracy': 0,
                            'rating': 0,
                            'early_start_rate': 0,
                            'ontime_start_rate': 0,
                            'late_start_rate': 0,
                            'early_completion_rate': 0,
                            'late_completion_rate': 0
                        }
                    }

                    # Add team metrics calculation here if needed...

            # 6. Calculate trends
            trends = []
            current = start
            while current <= end:
                try:
                    trend_date = current.date()
                    day_orders = orders_by_date.get(trend_date, [])
                    
                    if day_orders:
                        day_attendance = [att for att in attendance_records if 
                                        pytz.utc.localize(fields.Datetime.from_string(att.check_in)).astimezone(tz).date() == trend_date]
                        
                        day_attendance_hours = 0
                        day_productive_hours = 0
                        
                        # Calculate daily attendance hours
                        for att in day_attendance:
                            check_in_local = pytz.utc.localize(fields.Datetime.from_string(att.check_in)).astimezone(tz)
                            check_out_local = pytz.utc.localize(fields.Datetime.from_string(att.check_out)).astimezone(tz)
                            
                            work_start = check_in_local.replace(hour=8, minute=0, second=0)
                            
                            effective_start = max(check_in_local, work_start)
                            effective_end = check_out_local  # Allow overtime
                            
                            if effective_end > effective_start:
                                break_start = effective_start.replace(hour=12, minute=0, second=0)
                                break_end = effective_start.replace(hour=13, minute=0, second=0)
                                
                                if effective_start < break_end and effective_end > break_start:
                                    morning_hours = (min(break_start, effective_end) - effective_start).total_seconds() / 3600
                                    afternoon_hours = (effective_end - max(break_end, effective_start)).total_seconds() / 3600
                                    day_attendance_hours += max(0, morning_hours) + max(0, afternoon_hours)
                                else:
                                    day_attendance_hours += (effective_end - effective_start).total_seconds() / 3600
                        
                        # Calculate daily productive hours
                        for order in day_orders:
                            if order.controller_mulai_servis and order.controller_selesai:
                                service_start = pytz.utc.localize(fields.Datetime.from_string(order.controller_mulai_servis)).astimezone(tz)
                                service_end = pytz.utc.localize(fields.Datetime.from_string(order.controller_selesai)).astimezone(tz)
                                
                                for att in day_attendance:
                                    check_in_local = pytz.utc.localize(fields.Datetime.from_string(att.check_in)).astimezone(tz)
                                    check_out_local = pytz.utc.localize(fields.Datetime.from_string(att.check_out)).astimezone(tz)
                                    
                                    work_start = check_in_local.replace(hour=8, minute=0, second=0)
                                    
                                    start_overlap = max(service_start, check_in_local, work_start)
                                    end_overlap = min(service_end, check_out_local)  # Allow overtime
                                    
                                    if end_overlap > start_overlap:
                                        break_start = start_overlap.replace(hour=12, minute=0, second=0)
                                        break_end = start_overlap.replace(hour=13, minute=0, second=0)
                                        
                                        if start_overlap < break_end and end_overlap > break_start:
                                            morning_prod = (min(break_start, end_overlap) - start_overlap).total_seconds() / 3600
                                            afternoon_prod = (end_overlap - max(break_end, start_overlap)).total_seconds() / 3600
                                            day_productive_hours += max(0, morning_prod) + max(0, afternoon_prod)
                                        else:
                                            day_productive_hours += (end_overlap - start_overlap).total_seconds() / 3600

                        daily_metrics = {
                            'date': current.strftime('%Y-%m-%d'),
                            'metrics': {
                                'revenue': sum(order.amount_total / len(order.car_mechanic_id_new) for order in day_orders),
                                'orders': len(day_orders),
                                'on_time_rate': sum(
                                    1 for o in day_orders 
                                    if o.controller_selesai and o.controller_estimasi_selesai
                                    and fields.Datetime.from_string(o.controller_selesai) <= fields.Datetime.from_string(o.controller_estimasi_selesai)
                                ) / len(day_orders) * 100 if day_orders else 0,
                                'rating': (
                                    sum(float(o.customer_rating) for o in day_orders if o.customer_rating) /
                                    sum(1 for o in day_orders if o.customer_rating)
                                ) if any(o.customer_rating for o in day_orders) else 0,
                                'utilization': {
                                    'attendance_hours': day_attendance_hours,
                                    'productive_hours': day_productive_hours,
                                    'rate': (day_productive_hours / day_attendance_hours * 100) if day_attendance_hours > 0 else 0
                                }
                            }
                        }
                        trends.append(daily_metrics)
                    
                    current += timedelta(days=1)
                except Exception as e:
                    _logger.error(f"Error calculating trends for {current.strftime('%Y-%m-%d')}: {str(e)}")
                    continue

            # Get next and previous mechanic
            all_mechanics = request.env['pitcar.mechanic.new'].sudo().search([])
            mechanic_ids = all_mechanics.ids
            current_index = mechanic_ids.index(mechanic_id)

            next_mechanic = None
            prev_mechanic = None

            if current_index < len(mechanic_ids) - 1:
                next_id = mechanic_ids[current_index + 1]
                next_mech = request.env['pitcar.mechanic.new'].sudo().browse(next_id)
                next_mechanic = {
                    'id': next_mech.id,
                    'name': next_mech.name
                }

            if current_index > 0:
                prev_id = mechanic_ids[current_index - 1]
                prev_mech = request.env['pitcar.mechanic.new'].sudo().browse(prev_id)
                prev_mechanic = {
                    'id': prev_mech.id,
                    'name': prev_mech.name
                }

            # Return final response
            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
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
                    'metrics': metrics,
                    'team_data': team_data,
                    'trends': trends,
                    'navigation': {
                        'next': next_mechanic,
                        'previous': prev_mechanic
                    }
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

            # Get all team leaders in one query
            leaders = request.env['pitcar.mechanic.new'].sudo().search([
                ('position_code', '=', 'leader')
            ])

            # Get all relevant orders in one query to prevent multiple database hits
            base_domain = [
                ('date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', '=', 'sale'),
            ]
            all_orders = request.env['sale.order'].sudo().search(base_domain)

            teams = []
            for leader in leaders:
                # Get team members
                team_members = request.env['pitcar.mechanic.new'].sudo().search([
                    ('leader_id', '=', leader.id)
                ])

                # Filter orders for this team from the pre-fetched orders
                leader_orders = all_orders.filtered(lambda o: leader.id in o.car_mechanic_id_new.ids)
                member_orders = all_orders.filtered(lambda o: any(m.id in o.car_mechanic_id_new.ids for m in team_members))

                if member_orders or leader_orders:
                    all_team_orders = leader_orders | member_orders

                    # Initialize metrics counters
                    total_starts = 0
                    early_starts = 0
                    ontime_starts = 0
                    late_starts = 0
                    total_completions = 0
                    early_completions = 0
                    late_completions = 0
                    total_duration_accuracy = 0
                    total_duration_orders = 0
                    total_rating = 0
                    total_rated_orders = 0

                    # Pre-calculate team revenue
                    leader_revenue = sum(order.amount_total for order in leader_orders)
                    member_revenue = sum(order.amount_total for order in member_orders)
                    total_revenue = leader_revenue + member_revenue

                    # Group orders by date for trend calculation
                    orders_by_date = {}
                    for order in all_team_orders:
                        order_date = order.date_completed.date()
                        if order_date not in orders_by_date:
                            orders_by_date[order_date] = []
                        orders_by_date[order_date].append(order)

                    # Calculate detailed metrics in a single pass
                    for order in all_team_orders:
                        required_fields = [
                            order.controller_estimasi_mulai,
                            order.controller_mulai_servis,
                            order.controller_estimasi_selesai,
                            order.controller_selesai
                        ]
                        
                        if all(required_fields):
                            try:
                                # Convert strings to datetime only once
                                est_start = fields.Datetime.from_string(order.controller_estimasi_mulai)
                                actual_start = fields.Datetime.from_string(order.controller_mulai_servis)
                                est_end = fields.Datetime.from_string(order.controller_estimasi_selesai)
                                actual_end = fields.Datetime.from_string(order.controller_selesai)

                                # Time distribution
                                total_starts += 1
                                if actual_start < est_start:
                                    early_starts += 1
                                elif actual_start > est_start:
                                    late_starts += 1
                                else:
                                    ontime_starts += 1

                                # Completion metrics
                                total_completions += 1
                                if actual_end <= est_end:
                                    early_completions += 1
                                else:
                                    late_completions += 1

                                # Duration accuracy
                                estimated_duration = (est_end - est_start).total_seconds() / 3600
                                actual_duration = (actual_end - actual_start).total_seconds() / 3600
                                if estimated_duration > 0:
                                    total_duration_orders += 1
                                    accuracy = (1 - abs(actual_duration - estimated_duration) / estimated_duration) * 100
                                    total_duration_accuracy += accuracy

                            except Exception as e:
                                _logger.error(f"Error calculating metrics for order {order.id}: {str(e)}")
                                continue

                        if order.customer_rating:
                            total_rated_orders += 1
                            total_rating += float(order.customer_rating)

                    # Calculate trends using pre-grouped orders
                    trends = []
                    current = start
                    while current <= end:
                        current_date = current.date()
                        day_orders = orders_by_date.get(current_date, [])
                        
                        if day_orders:
                            daily_revenue = sum(o.amount_total for o in day_orders)
                            daily_count = len(day_orders)
                            daily_rated = [o for o in day_orders if o.customer_rating]
                            daily_rating = (
                                sum(float(o.customer_rating) for o in daily_rated) / len(daily_rated)
                                if daily_rated else 0
                            )
                            
                            daily_completed = [
                                o for o in day_orders 
                                if o.controller_selesai and o.controller_estimasi_selesai
                            ]
                            daily_ontime = sum(
                                1 for o in daily_completed 
                                if o.controller_selesai <= o.controller_estimasi_selesai
                            )
                            
                            trends.append({
                                'date': current_date.strftime('%Y-%m-%d'),
                                'metrics': {
                                    'revenue': daily_revenue,
                                    'orders': daily_count,
                                    'rating': daily_rating,
                                    'on_time_rate': (daily_ontime / len(daily_completed) * 100) 
                                                if daily_completed else 0
                                }
                            })
                        
                        current += timedelta(days=1)

                    # Calculate team metrics
                    team_target = len(team_members) * 64000000
                    metrics = {
                        'revenue': {
                            'total': total_revenue,
                            'target': team_target,
                            'achievement': (total_revenue / team_target * 100) if team_target else 0
                        },
                        'orders': {
                            'total': len(all_team_orders),
                            'average_value': total_revenue / len(all_team_orders) if all_team_orders else 0
                        },
                        'performance': {
                            'duration_accuracy': total_duration_accuracy / total_duration_orders if total_duration_orders else 0,
                            'rating': total_rating / total_rated_orders if total_rated_orders else 0,
                            'early_start_rate': (early_starts / total_starts * 100) if total_starts else 0,
                            'ontime_start_rate': (ontime_starts / total_starts * 100) if total_starts else 0,
                            'late_start_rate': (late_starts / total_starts * 100) if total_starts else 0,
                            'early_completion_rate': (early_completions / total_completions * 100) if total_completions else 0,
                            'late_completion_rate': (late_completions / total_completions * 100) if total_completions else 0
                        }
                    }

                    teams.append({
                        'id': leader.id,
                        'name': leader.name,
                        'position': 'Team',
                        'member_count': len(team_members),
                        'metrics': metrics,
                        'trends': trends
                    })

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
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
    
    # SERVICE ADVISOR
    @http.route('/web/v2/dashboard/service-advisor', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_service_advisor_kpi_dashboard(self, **kw):
        """Get dashboard KPI for service advisors with team metrics"""
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

            # Get all orders in one query
            domain = [
                ('date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', '=', 'sale')
            ]
            
            all_orders = request.env['sale.order'].sudo().search(domain)

            # Get all service advisors and create lookup dictionary
            advisors = request.env['pitcar.service.advisor'].sudo().search([])
            advisor_dict = {a.id: a for a in advisors}
            
            # Get position data for targets
            positions = request.env['pitcar.service.advisor.position'].sudo().search([])
            position_targets = {
                pos.code: pos.monthly_target for pos in positions
            }
            
            # Calculate advisor metrics
            advisors_data = {}
            total_revenue = 0
            total_orders = 0
            total_rating_sum = 0
            total_rated_orders = 0
            total_complaints = 0
            total_completed_services = 0
            total_on_time_services = 0
            total_confirmation_services = 0
            total_on_time_confirmations = 0
            total_service_time = 0
            total_confirmation_time = 0

            for order in all_orders:
                for advisor in order.service_advisor_id:
                    if advisor.id not in advisors_data:
                        advisors_data[advisor.id] = {
                            'id': advisor.id,
                            'name': advisor.name,
                            'position': 'Team Leader' if advisor.position_code == 'leader' else 'Service Advisor',
                            'position_code': advisor.position_code,
                            'monthly_target': advisor.monthly_target,
                            'revenue': 0,
                            'orders': 0,
                            'total_rating': 0,
                            'rated_orders': 0,
                            'completed_services': 0,
                            'on_time_services': 0,
                            'service_times': [],
                            'confirmation_services': 0,
                            'on_time_confirmations': 0,
                            'confirmation_times': [],
                            'complaints': 0,
                            'feedback_received': 0,
                            'google_reviews': 0,
                            'instagram_follows': 0
                        }
                    
                    advisor_data = advisors_data[advisor.id]
                    advisor_count = len(order.service_advisor_id)
                    
                    # Calculate revenue
                    # order_revenue = order.amount_total / advisor_count
                    order_revenue = order.amount_untaxed / advisor_count
                    advisor_data['revenue'] += order_revenue
                    advisor_data['orders'] += 1

                    # Calculate service time metrics
                    if order.sa_mulai_penerimaan and order.sa_cetak_pkb:
                        advisor_data['completed_services'] += 1
                        service_time = (order.sa_cetak_pkb - order.sa_mulai_penerimaan).total_seconds() / 60
                        advisor_data['service_times'].append(service_time)
                        
                        if service_time <= 15:  # 15 minutes target for service
                            advisor_data['on_time_services'] += 1
                            
                        total_completed_services += 1
                        total_service_time += service_time
                        if service_time <= 15:
                            total_on_time_services += 1

                    # Calculate confirmation time metrics
                    if order.controller_tunggu_konfirmasi_mulai and order.controller_tunggu_konfirmasi_selesai:
                        advisor_data['confirmation_services'] += 1
                        confirmation_time = (order.controller_tunggu_konfirmasi_selesai - 
                                        order.controller_tunggu_konfirmasi_mulai).total_seconds() / 60
                        advisor_data['confirmation_times'].append(confirmation_time)
                        
                        if confirmation_time <= 40:  # 40 minutes target for confirmation
                            advisor_data['on_time_confirmations'] += 1
                            
                        total_confirmation_services += 1
                        total_confirmation_time += confirmation_time
                        if confirmation_time <= 40:
                            total_on_time_confirmations += 1

                    # Rating and feedback metrics
                    if order.customer_rating:
                        advisor_data['rated_orders'] += 1
                        rating = float(order.customer_rating)
                        advisor_data['total_rating'] += rating
                        total_rating_sum += rating
                        total_rated_orders += 1

                    if order.customer_satisfaction in ['very_dissatisfied', 'dissatisfied']:
                        advisor_data['complaints'] += 1
                        total_complaints += 1

                    if order.is_willing_to_feedback == 'yes':
                        advisor_data['feedback_received'] += 1
                    if order.review_google == 'yes':
                        advisor_data['google_reviews'] += 1
                    if order.follow_instagram == 'yes':
                        advisor_data['instagram_follows'] += 1

                    total_revenue += order_revenue
                    total_orders += 1

            # Calculate team metrics
            teams_data = {}
            for advisor_id, data in advisors_data.items():
                advisor = advisor_dict.get(advisor_id)
                if not advisor:
                    continue
                    
                leader_id = advisor.leader_id.id if advisor.leader_id else (advisor_id if advisor.position_code == 'leader' else None)
                
                if leader_id:  # Process both leader and members
                    if leader_id not in teams_data:
                        leader = advisor_dict.get(leader_id)
                        leader_data = advisors_data.get(leader_id, {})
                        teams_data[leader_id] = {
                            'id': leader_id,
                            'name': leader.name,
                            'position': 'Team',
                            'member_count': 0,
                            'member_targets': 0,  # Track sum of member targets
                            'total_rated_orders': 0,
                            'total_rating_sum': 0,
                            'metrics': {
                                'revenue': {
                                    'total': leader_data.get('revenue', 0),
                                    'target': 0,
                                    'achievement': 0
                                },
                                'orders': {
                                    'total': leader_data.get('orders', 0),
                                    'average_value': 0
                                },
                                'performance': {
                                    'service': {
                                        'average_time': 0,
                                        'on_time_rate': 0,
                                        'total_services': 0,
                                        'on_time_services': 0
                                    },
                                    'confirmation': {
                                        'average_time': 0,
                                        'on_time_rate': 0,
                                        'total_services': 0,
                                        'on_time_services': 0
                                    },
                                    'rating': 0,
                                    'complaint_rate': 0
                                }
                            }
                        }
                    
                    if advisor.position_code != 'leader':  # Count and accumulate only for members
                        team_data = teams_data[leader_id]
                        team_data['member_count'] += 1
                        team_data['member_targets'] += advisor.monthly_target
                        
                        # Accumulate team metrics
                        team_data['metrics']['revenue']['total'] += data['revenue']
                        team_data['metrics']['orders']['total'] += data['orders']
                        
                        if data['rated_orders'] > 0:
                            team_data['total_rated_orders'] += data['rated_orders']
                            team_data['total_rating_sum'] += data['total_rating']
                        
                        # Service performance
                        team_data['metrics']['performance']['service']['total_services'] += data['completed_services']
                        team_data['metrics']['performance']['service']['on_time_services'] += data['on_time_services']
                        
                        # Confirmation performance
                        team_data['metrics']['performance']['confirmation']['total_services'] += data['confirmation_services']
                        team_data['metrics']['performance']['confirmation']['on_time_services'] += data['on_time_confirmations']

            # Calculate final team metrics
            for team in teams_data.values():
                if team['member_count'] > 0:
                    # Set target and calculate achievement
                    team['metrics']['revenue']['target'] = team['member_targets']
                    if team['metrics']['revenue']['target']:
                        team['metrics']['revenue']['achievement'] = (
                            team['metrics']['revenue']['total'] / team['metrics']['revenue']['target'] * 100
                        )
                    
                    # Calculate average order value
                    if team['metrics']['orders']['total']:
                        team['metrics']['orders']['average_value'] = (
                            team['metrics']['revenue']['total'] / team['metrics']['orders']['total']
                        )
                    
                    # Calculate service performance rates
                    service_total = team['metrics']['performance']['service']['total_services']
                    if service_total:
                        team['metrics']['performance']['service']['on_time_rate'] = (
                            team['metrics']['performance']['service']['on_time_services'] / service_total * 100
                        )
                    
                    # Calculate confirmation performance rates
                    conf_total = team['metrics']['performance']['confirmation']['total_services']
                    if conf_total:
                        team['metrics']['performance']['confirmation']['on_time_rate'] = (
                            team['metrics']['performance']['confirmation']['on_time_services'] / conf_total * 100
                        )
                    
                    # Calculate team rating
                    team['metrics']['performance']['rating'] = {
                        'average': (team['total_rating_sum'] / team['total_rated_orders']) if team['total_rated_orders'] else 0,
                        'total_rated_orders': team['total_rated_orders']
                    }


            # Format advisor data with proper targets
            active_advisors = []
            for data in advisors_data.values():
                if data['orders'] > 0:
                    advisor = advisor_dict.get(data['id'])
                    if not advisor:
                        continue

                    leader_info = None
                    if advisor.leader_id:
                        leader_info = {
                            'id': advisor.leader_id.id,
                            'name': advisor.leader_id.name
                        }

                    metrics = {
                        'revenue': {
                            'total': data['revenue'],
                            'target': data['monthly_target'],
                            'achievement': (data['revenue'] / data['monthly_target'] * 100) if data['monthly_target'] else 0
                        },
                        'orders': {
                            'total': data['orders'],
                            'average_value': data['revenue'] / data['orders'] if data['orders'] else 0
                        },
                        'performance': {
                            'service': {
                                'average_time': sum(data['service_times']) / len(data['service_times']) if data['service_times'] else 0,
                                'on_time_rate': (data['on_time_services'] / data['completed_services'] * 100) 
                                            if data['completed_services'] else 0,
                                'total_services': data['completed_services'],
                                'on_time_services': data['on_time_services']
                            },
                            'confirmation': {
                                'average_time': sum(data['confirmation_times']) / len(data['confirmation_times']) 
                                            if data['confirmation_times'] else 0,
                                'on_time_rate': (data['on_time_confirmations'] / data['confirmation_services'] * 100) 
                                            if data['confirmation_services'] else 0,
                                'total_services': data['confirmation_services'],
                                'on_time_services': data['on_time_confirmations']
                            },
                            'rating': {
                                'average': data['total_rating'] / data['rated_orders'] if data['rated_orders'] else 0,
                                'total_rated_orders': data['rated_orders']
                            },
                            'complaint_rate': (data['complaints'] / data['orders'] * 100) if data['orders'] else 0
                        },
                        'engagement': {
                            'feedback_rate': (data['feedback_received'] / data['orders'] * 100) if data['orders'] else 0,
                            'google_reviews': data['google_reviews'],
                            'instagram_follows': data['instagram_follows']
                        }
                    }

                    active_advisors.append({
                        'id': data['id'],
                        'name': data['name'],
                        'position': data['position'],
                        'leader': leader_info,
                        'metrics': metrics
                    })

            # Calculate overview metrics
            overview = {
                'total_revenue': total_revenue,
                'total_orders': total_orders,
                'rating': {
                    'average': total_rating_sum / total_rated_orders if total_rated_orders else 0,
                    'total_rated_orders': total_rated_orders
                },
                'service_performance': {
                    'average_time': total_service_time / total_completed_services if total_completed_services else 0,
                    'on_time_rate': (total_on_time_services / total_completed_services * 100) 
                                if total_completed_services else 0,
                    'total_services': total_completed_services,
                    'on_time_services': total_on_time_services
                },
                'confirmation_performance': {
                    'average_time': total_confirmation_time / total_confirmation_services 
                                if total_confirmation_services else 0,
                    'on_time_rate': (total_on_time_confirmations / total_confirmation_services * 100) 
                                if total_confirmation_services else 0,
                    'total_services': total_confirmation_services,
                    'on_time_services': total_on_time_confirmations
                },
                'complaints': {
                    'total': total_complaints,
                    'rate': (total_complaints / total_orders * 100) if total_orders else 0
                }
            }

            # Calculate daily trends
            trends = []
            current = start
            while current <= end:
                current_date = current.date()
                day_orders = [o for o in all_orders if o.date_completed.date() == current_date]
                
                if day_orders:
                    # Calculate daily metrics
                    daily_revenue = sum(o.amount_total for o in day_orders)
                    daily_count = len(day_orders)
                    
                    # Service time metrics
                    daily_completed_services = sum(1 for o in day_orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb)
                    daily_on_time_services = sum(1 for o in day_orders 
                        if o.sa_mulai_penerimaan and o.sa_cetak_pkb 
                        and (o.sa_cetak_pkb - o.sa_mulai_penerimaan).total_seconds() / 60 <= 15)
                    
                    # Confirmation time metrics
                    daily_confirmation_services = sum(1 for o in day_orders 
                        if o.controller_tunggu_konfirmasi_mulai and o.controller_tunggu_konfirmasi_selesai)
                    daily_on_time_confirmations = sum(1 for o in day_orders 
                        if o.controller_tunggu_konfirmasi_mulai and o.controller_tunggu_konfirmasi_selesai 
                        and (o.controller_tunggu_konfirmasi_selesai - o.controller_tunggu_konfirmasi_mulai).total_seconds() / 60 <= 40)
                    
                    # Rating metrics
                    daily_rated = [o for o in day_orders if o.customer_rating]
                    daily_rating = (sum(float(o.customer_rating) for o in daily_rated) / len(daily_rated)) if daily_rated else 0
                    
                    trends.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'metrics': {
                            'revenue': daily_revenue,
                            'orders': daily_count,
                            'service_performance': {
                                'on_time_rate': (daily_on_time_services / daily_completed_services * 100) 
                                            if daily_completed_services else 0,
                                'total_services': daily_completed_services,
                                'on_time_services': daily_on_time_services
                            },
                            'confirmation_performance': {
                                'on_time_rate': (daily_on_time_confirmations / daily_confirmation_services * 100) 
                                            if daily_confirmation_services else 0,
                                'total_services': daily_confirmation_services,
                                'on_time_services': daily_on_time_confirmations
                            },
                            'rating': daily_rating
                        }
                    })
                
                current += timedelta(days=1)

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
                    'advisors': active_advisors,
                    'trends': trends
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_service_advisor_kpi_dashboard: {str(e)}")
            return {'status': 'error', 'message': str(e)}

        
    @http.route('/web/v2/dashboard/service-advisor/<int:advisor_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_service_advisor_detail(self, advisor_id, **kw):
        """Get detailed KPIs for a specific service advisor"""
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
            
            # Get advisor data
            advisor = request.env['pitcar.service.advisor'].sudo().browse(advisor_id)
            if not advisor.exists():
                return {'status': 'error', 'message': 'Service Advisor not found'}

            # Get orders in a single query
            domain = [
                ('date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', '=', 'sale'),
                ('service_advisor_id', 'in', [advisor_id])
            ]

            orders = request.env['sale.order'].sudo().search(domain)

           # Initialize metrics counters [semua counter tetap sama]
            total_revenue = 0
            total_orders = len(orders)
            service_times = []
            completed_services = 0
            on_time_services = 0
            confirmation_times = []
            confirmation_services = 0
            on_time_confirmations = 0
            total_rating = 0
            rated_orders = 0
            complaints = 0
            feedback_received = 0
            google_reviews = 0
            instagram_follows = 0

            # Calculate daily performance
            orders_by_date = {}
            for order in orders:
                # Get order date
                order_date = order.date_completed.date()
                if order_date not in orders_by_date:
                    orders_by_date[order_date] = []
                orders_by_date[order_date].append(order)

                # Calculate revenue considering multiple advisors
                advisor_count = len(order.service_advisor_id)
                # order_revenue = order.amount_total / advisor_count
                order_revenue = order.amount_untaxed / advisor_count
                total_revenue += order_revenue

                # Service time metrics
                if order.sa_mulai_penerimaan and order.sa_cetak_pkb:
                    completed_services += 1
                    service_time = (order.sa_cetak_pkb - order.sa_mulai_penerimaan).total_seconds() / 60
                    service_times.append(service_time)
                    if service_time <= 15:  # 15 minutes target for service
                        on_time_services += 1

                # Confirmation time metrics
                if order.controller_tunggu_konfirmasi_mulai and order.controller_tunggu_konfirmasi_selesai:
                    confirmation_services += 1
                    confirmation_time = (order.controller_tunggu_konfirmasi_selesai - 
                                    order.controller_tunggu_konfirmasi_mulai).total_seconds() / 60
                    confirmation_times.append(confirmation_time)
                    if confirmation_time <= 40:  # 40 minutes target for confirmation
                        on_time_confirmations += 1

                # Rating and feedback metrics
                if order.customer_rating:
                    rated_orders += 1
                    total_rating += float(order.customer_rating)

                if order.customer_satisfaction in ['very_dissatisfied', 'dissatisfied']:
                    complaints += 1

                if order.is_willing_to_feedback == 'yes':
                    feedback_received += 1
                if order.review_google == 'yes':
                    google_reviews += 1
                if order.follow_instagram == 'yes':
                    instagram_follows += 1

            # Get next and previous advisors
            all_advisors = request.env['pitcar.service.advisor'].sudo().search([])
            advisor_ids = all_advisors.ids
            current_index = advisor_ids.index(advisor_id)

            next_advisor = None
            prev_advisor = None

            if current_index < len(advisor_ids) - 1:
                next_id = advisor_ids[current_index + 1]
                next_adv = request.env['pitcar.service.advisor'].sudo().browse(next_id)
                next_advisor = {
                    'id': next_adv.id,
                    'name': next_adv.name
                }

            if current_index > 0:
                prev_id = advisor_ids[current_index - 1]
                prev_adv = request.env['pitcar.service.advisor'].sudo().browse(prev_id)
                prev_advisor = {
                    'id': prev_adv.id,
                    'name': prev_adv.name
                }

            # Calculate trends
            trends = []
            current = start
            while current <= end:
                current_date = current.date()
                day_orders = orders_by_date.get(current_date, [])
                
                if day_orders:
                    # Calculate daily service metrics
                    daily_completed = sum(1 for o in day_orders if o.sa_mulai_penerimaan and o.sa_cetak_pkb)
                    daily_on_time = sum(1 for o in day_orders 
                        if o.sa_mulai_penerimaan and o.sa_cetak_pkb 
                        and (o.sa_cetak_pkb - o.sa_mulai_penerimaan).total_seconds() / 60 <= 15)

                    # Calculate daily confirmation metrics
                    daily_confirmations = sum(1 for o in day_orders 
                        if o.controller_tunggu_konfirmasi_mulai and o.controller_tunggu_konfirmasi_selesai)
                    daily_on_time_conf = sum(1 for o in day_orders 
                        if o.controller_tunggu_konfirmasi_mulai and o.controller_tunggu_konfirmasi_selesai 
                        and (o.controller_tunggu_konfirmasi_selesai - o.controller_tunggu_konfirmasi_mulai).total_seconds() / 60 <= 40)

                    # Calculate daily revenue and rating
                    daily_revenue = sum(o.amount_total / len(o.service_advisor_id) for o in day_orders)
                    daily_rated = [o for o in day_orders if o.customer_rating]
                    daily_rating = (
                        sum(float(o.customer_rating) for o in daily_rated) / len(daily_rated)
                        if daily_rated else 0
                    )

                    trends.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'metrics': {
                            'revenue': daily_revenue,
                            'orders': len(day_orders),
                            'service_performance': {
                                'on_time_rate': (daily_on_time / daily_completed * 100) if daily_completed else 0,
                                'total_services': daily_completed,
                                'on_time_services': daily_on_time
                            },
                            'confirmation_performance': {
                                'on_time_rate': (daily_on_time_conf / daily_confirmations * 100) if daily_confirmations else 0,
                                'total_services': daily_confirmations,
                                'on_time_services': daily_on_time_conf
                            },
                            'rating': daily_rating
                        }
                    })
                
                current += timedelta(days=1)

             # Compile final metrics dengan penambahan target dan achievement
            metrics = {
                'revenue': {
                    'total': total_revenue,
                    'average': total_revenue / total_orders if total_orders else 0,
                    'target': advisor.monthly_target,  # Tambahan target
                    'achievement': (total_revenue / advisor.monthly_target * 100) if advisor.monthly_target else 0  # Tambahan achievement
                },
                'orders': {
                    'total': total_orders
                },
                'performance': {
                    'service': {
                        'average_time': sum(service_times) / len(service_times) if service_times else 0,
                        'on_time_rate': (on_time_services / completed_services * 100) if completed_services else 0,
                        'total_services': completed_services,
                        'on_time_services': on_time_services
                    },
                    'confirmation': {
                        'average_time': sum(confirmation_times) / len(confirmation_times) if confirmation_times else 0,
                        'on_time_rate': (on_time_confirmations / confirmation_services * 100) if confirmation_services else 0,
                        'total_services': confirmation_services,
                        'on_time_services': on_time_confirmations
                    },
                    'rating': total_rating / rated_orders if rated_orders else 0,
                    'complaint_rate': (complaints / total_orders * 100) if total_orders else 0
                },
                'engagement': {
                    'feedback_rate': (feedback_received / total_orders * 100) if total_orders else 0,
                    'google_reviews': google_reviews,
                    'instagram_follows': instagram_follows
                }
            }

            # Tambahan informasi team
            team_info = {
                'leader': {
                    'id': advisor.leader_id.id,
                    'name': advisor.leader_id.name
                } if advisor.leader_id else None,
                'members': [{
                    'id': member.id,
                    'name': member.name
                } for member in advisor.team_member_ids] if advisor.position_code == 'leader' else []
            }

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'advisor': {
                        'id': advisor.id,
                        'name': advisor.name,
                        'position': 'Team Leader' if advisor.position_code == 'leader' else 'Service Advisor',
                        'team': team_info  # Tambahan informasi team
                    },
                    'metrics': metrics,
                    'trends': trends,
                    'navigation': {
                        'next': next_advisor,
                        'previous': prev_advisor
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_service_advisor_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # @http.route('/web/v2/statistics/overview', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    # def get_dashboard_overview(self, **kw):
    #     """Get comprehensive dashboard overview including cohort analysis"""
        # try:
    #         # Get date range parameters
    #         date_range = kw.get('date_range', 'today')
    #         start_date = kw.get('start_date')
    #         end_date = kw.get('end_date')
            
    #         # Set timezone
    #         tz = pytz.timezone('Asia/Jakarta')
    #         now = datetime.now(tz)
            
    #         # Calculate date range
    #         if start_date and end_date:
    #             try:
    #                 start = datetime.strptime(start_date, '%Y-%m-%d')
    #                 end = datetime.strptime(end_date, '%Y-%m-%d')
    #                 start = tz.localize(start.replace(hour=0, minute=0, second=0))
    #                 end = tz.localize(end.replace(hour=23, minute=59, second=59))
    #             except (ValueError, TypeError):
    #                 return {'status': 'error', 'message': 'Invalid date format'}
    #         else:
    #             if date_range == 'today':
    #                 start = now.replace(hour=0, minute=0, second=0)
    #                 end = now
    #             elif date_range == 'yesterday':
    #                 yesterday = now - timedelta(days=1)
    #                 start = yesterday.replace(hour=0, minute=0, second=0)
    #                 end = yesterday.replace(hour=23, minute=59, second=59)
    #             elif date_range == 'this_week':
    #                 start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    #                 end = now
    #             elif date_range == 'this_month':
    #                 start = now.replace(day=1, hour=0, minute=0, second=0)
    #                 end = now
    #             elif date_range == 'this_year':
    #                 start = now.replace(month=1, day=1, hour=0, minute=0, second=0)
    #                 end = now
    #             else:
    #                 start = now.replace(hour=0, minute=0, second=0)
    #                 end = now

    #         # Convert to UTC for database queries
    #         start_utc = start.astimezone(pytz.UTC)
    #         end_utc = end.astimezone(pytz.UTC)

    #         # Get previous period for comparison
    #         delta = end_utc - start_utc
    #         prev_end = start_utc - timedelta(microseconds=1)
    #         prev_start = prev_end - delta

    #         # Get current period orders dengan state='sale' dan menggunakan date_completed
    #         current_domain = [
    #             ('date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
    #             ('date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
    #             ('state', '=', 'sale')  # Hanya ambil confirmed sales
    #         ]

    #         # Get previous period orders
    #         prev_domain = [
    #             ('date_completed', '>=', prev_start.strftime('%Y-%m-%d %H:%M:%S')),
    #             ('date_completed', '<=', prev_end.strftime('%Y-%m-%d %H:%M:%S')),
    #             ('state', '=', 'sale')  # Hanya ambil confirmed sales
    #         ]

    #         # Get quotations
    #         current_quotations = request.env['sale.order'].sudo().search([
    #             *current_domain,
    #             ('state', '=', 'draft')
    #         ])
    #         prev_quotations = request.env['sale.order'].sudo().search([
    #             *prev_domain,
    #             ('state', '=', 'draft')
    #         ])

    #         # Get confirmed orders
    #         current_orders = request.env['sale.order'].sudo().search(current_domain)
    #         prev_orders = request.env['sale.order'].sudo().search(prev_domain)

    #         # Calculate overall metrics
    #         current_order_count = len(current_orders)
    #         prev_order_count = len(prev_orders)
    #         current_flat_rate_hours = sum(order.total_service_duration for order in current_orders)
    #         prev_flat_rate_hours = sum(order.total_service_duration for order in prev_orders)

    #         # Overall flat rate metrics
    #         flat_rate_overall = {
    #             'total_flat_rate_hours': {
    #                 'current': round(current_flat_rate_hours, 2),
    #                 'previous': round(prev_flat_rate_hours, 2),
    #                 'growth': round(
    #                     ((current_flat_rate_hours - prev_flat_rate_hours) / prev_flat_rate_hours * 100)
    #                     if prev_flat_rate_hours else 0,
    #                     2
    #                 ),
    #             },
    #             'average_flat_rate_per_order': {
    #                 'current': round(current_flat_rate_hours / current_order_count, 2) if current_order_count else 0,
    #                 'previous': round(prev_flat_rate_hours / prev_order_count, 2) if prev_order_count else 0,
    #                 'growth': round(
    #                     (((current_flat_rate_hours / current_order_count if current_order_count else 0) -
    #                     (prev_flat_rate_hours / prev_order_count if prev_order_count else 0)) /
    #                     (prev_flat_rate_hours / prev_order_count if prev_order_count else 1) * 100)
    #                     if prev_flat_rate_hours else 0,
    #                     2
    #                 ),
    #             },
    #         }

    #         # Calculate flat rate per mechanic
    #         def calculate_mechanic_flat_rate(orders):
    #             mechanic_data = {}
    #             for order in orders:
    #                 if order.car_mechanic_id_new:
    #                     mechanic_count = len(order.car_mechanic_id_new)
    #                     if mechanic_count > 0:
    #                         flat_rate_per_mechanic = order.total_service_duration / mechanic_count
    #                         for mechanic in order.car_mechanic_id_new:
    #                             if mechanic.id not in mechanic_data:
    #                                 mechanic_data[mechanic.id] = {
    #                                     'id': mechanic.id,
    #                                     'name': mechanic.name,
    #                                     'total_flat_rate_hours': 0.0,
    #                                     'order_count': 0,
    #                                 }
    #                             mechanic_data[mechanic.id]['total_flat_rate_hours'] += flat_rate_per_mechanic
    #                             mechanic_data[mechanic.id]['order_count'] += 1
    #             return mechanic_data

    #         current_mechanic_data = calculate_mechanic_flat_rate(current_orders)
    #         prev_mechanic_data = calculate_mechanic_flat_rate(prev_orders)

    #         # Combine mechanic data for current and previous periods
    #         mechanic_flat_rate_data = []
    #         all_mechanic_ids = set(current_mechanic_data.keys()) | set(prev_mechanic_data.keys())
    #         for mechanic_id in all_mechanic_ids:
    #             current = current_mechanic_data.get(mechanic_id, {'total_flat_rate_hours': 0, 'order_count': 0, 'name': ''})
    #             prev = prev_mechanic_data.get(mechanic_id, {'total_flat_rate_hours': 0, 'order_count': 0, 'name': ''})
    #             mechanic_flat_rate = {
    #                 'id': mechanic_id,
    #                 'name': current.get('name') or prev.get('name') or 'Unknown',
    #                 'current': {
    #                     'total_flat_rate_hours': round(current['total_flat_rate_hours'], 2),
    #                     'order_count': current['order_count'],
    #                     'average_flat_rate': round(
    #                         current['total_flat_rate_hours'] / current['order_count'], 2
    #                     ) if current['order_count'] else 0,
    #                 },
    #                 'previous': {
    #                     'total_flat_rate_hours': round(prev['total_flat_rate_hours'], 2),
    #                     'order_count': prev['order_count'],
    #                     'average_flat_rate': round(
    #                         prev['total_flat_rate_hours'] / prev['order_count'], 2
    #                     ) if prev['order_count'] else 0,
    #                 },
    #                 'growth': {
    #                     'total_flat_rate_hours': round(
    #                         ((current['total_flat_rate_hours'] - prev['total_flat_rate_hours']) /
    #                         prev['total_flat_rate_hours'] * 100)
    #                         if prev['total_flat_rate_hours'] else 0,
    #                         2
    #                     ),
    #                 },
    #             }
    #             mechanic_flat_rate_data.append(mechanic_flat_rate)

    #         # Sort by current total flat rate hours
    #         mechanic_flat_rate_data.sort(key=lambda x: x['current']['total_flat_rate_hours'], reverse=True)

    #         # Calculate basic metrics
    #         current_revenue = sum(order.amount_untaxed for order in current_orders)
    #         prev_revenue = sum(order.amount_untaxed for order in prev_orders)
            
    #         metrics = {
    #             'quotations': {
    #                 'current': len(current_quotations),
    #                 'previous': len(prev_quotations),
    #                 'growth': ((len(current_quotations) - len(prev_quotations)) / len(prev_quotations) * 100) 
    #                         if prev_quotations else 0
    #             },
    #             'orders': {
    #                 'current': len(current_orders),
    #                 'previous': len(prev_orders),
    #                 'growth': ((len(current_orders) - len(prev_orders)) / len(prev_orders) * 100) 
    #                         if prev_orders else 0
    #             },
    #             'revenue': {
    #                 'current': current_revenue,
    #                 'previous': prev_revenue,
    #                 'growth': ((current_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else 0
    #             },
    #             'average_order': {
    #                 'current': current_revenue / len(current_orders) if current_orders else 0,
    #                 'previous': prev_revenue / len(prev_orders) if prev_orders else 0,
    #                 'growth': (((current_revenue / len(current_orders) if current_orders else 0) - 
    #                         (prev_revenue / len(prev_orders) if prev_orders else 0)) / 
    #                         (prev_revenue / len(prev_orders) if prev_orders else 1) * 100)
    #                         if prev_orders else 0
    #             },
    #             'flat_rate': {
    #                 'overall': flat_rate_overall,
    #                 'per_mechanic': mechanic_flat_rate_data,
    #             },
    #         }

    #         # Calculate daily/monthly sales trend
    #         trends = []
    #         current = start
    #         while current <= end:
    #             current_end = min(current.replace(hour=23, minute=59, second=59), end)
    #             day_orders = request.env['sale.order'].sudo().search([
    #                 ('date_completed', '>=', current.strftime('%Y-%m-%d %H:%M:%S')),
    #                 ('date_completed', '<=', current_end.strftime('%Y-%m-%d %H:%M:%S')),
    #                 ('state', '=', 'sale')
    #             ])
                
    #             if day_orders:
    #                 trends.append({
    #                     'date': current.strftime('%Y-%m-%d'),
    #                     'revenue': sum(order.amount_total for order in day_orders),
    #                     'orders': len(day_orders)
    #                 })
                
    #             current += timedelta(days=1)

    #         # Get top products
    #         order_lines = request.env['sale.order.line'].sudo().search([
    #             ('order_id.state', '=', 'sale'),
    #             ('order_id.date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
    #             ('order_id.date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
    #         ])
            
    #         # Get top products separated by category
    #         service_products = {}
    #         physical_products = {}

    #         for line in order_lines:
    #             product = line.product_id
    #             # Check if product is a service
    #             is_service = product.type == 'service'  # or use your own criteria to determine service
                
    #             # Choose target dictionary based on product type
    #             target_dict = service_products if is_service else physical_products
                
    #             if product.id not in target_dict:
    #                 target_dict[product.id] = {
    #                     'id': product.id,
    #                     'name': product.name,
    #                     'orders': 0,
    #                     'revenue': 0
    #                 }
    #             target_dict[product.id]['orders'] += line.product_uom_qty
    #             target_dict[product.id]['revenue'] += line.price_subtotal

    #         # Sort and get top 10 for each category
    #         top_services = sorted(
    #             service_products.values(),
    #             key=lambda x: x['revenue'],
    #             reverse=True
    #         )[:10]

    #         top_physical_products = sorted(
    #             physical_products.values(),
    #             key=lambda x: x['revenue'],
    #             reverse=True
    #         )[:10]

    #         # Get top quotations
    #         top_quotations = [{
    #             'id': quot.id,
    #             'name': quot.name,
    #             'customer': quot.partner_id.name,
    #             'service_advisor': [sa.name for sa in quot.service_advisor_id],
    #             'amount': quot.amount_total
    #         } for quot in sorted(
    #             current_quotations,
    #             key=lambda x: x.amount_total,
    #             reverse=True
    #         )[:10]]

    #         # Get top sales orders
    #         top_sales = [{
    #             'id': order.id,
    #             'name': order.name,
    #             'customer': order.partner_id.name,
    #             'service_advisor': [sa.name for sa in order.service_advisor_id],
    #             'mechanic': [m.name for m in order.car_mechanic_id_new],
    #             'amount': order.amount_total
    #         } for order in sorted(
    #             current_orders,
    #             key=lambda x: x.amount_total,
    #             reverse=True
    #         )[:10]]

    #         # Get top customers
    #         customer_data = {}
    #         for order in current_orders:
    #             if order.partner_id.id not in customer_data:
    #                 customer_data[order.partner_id.id] = {
    #                     'id': order.partner_id.id,
    #                     'name': order.partner_id.name,
    #                     'orders': 0,
    #                     'revenue': 0
    #                 }
    #             customer_data[order.partner_id.id]['orders'] += 1
    #             customer_data[order.partner_id.id]['revenue'] += order.amount_total

    #         top_customers = sorted(
    #             customer_data.values(),
    #             key=lambda x: x['revenue'],
    #             reverse=True
    #         )[:10]

    #         # Get top service categories 
    #         subcategory_data = {key: {'name': label, 'orders': 0, 'revenue': 0}
    #                 for key, label in request.env['sale.order']._fields['service_subcategory'].selection}

    #         # Calculate subcategories data
    #         for order in current_orders:
    #             if order.service_subcategory:
    #                 subcategory_data[order.service_subcategory]['orders'] += 1
    #                 subcategory_data[order.service_subcategory]['revenue'] += order.amount_total

    #         # Format and sort categories (with empty list fallback)
    #         formatted_categories = []
    #         if current_orders:
    #             formatted_categories = [
    #                 {
    #                     'id': subcat_key,
    #                     'name': subcat['name'], 
    #                     'orders': subcat['orders'],
    #                     'revenue': subcat['revenue']
    #                 }
    #                 for subcat_key, subcat in subcategory_data.items() 
    #                 if subcat['orders'] > 0
    #             ]
    #             formatted_categories.sort(key=lambda x: x['revenue'], reverse=True)

    #         # Get top service advisors
    #         advisor_data = {}
    #         for order in current_orders:
    #             for advisor in order.service_advisor_id:
    #                 if advisor.id not in advisor_data:
    #                     advisor_data[advisor.id] = {
    #                         'id': advisor.id,
    #                         'name': advisor.name,
    #                         'orders': 0,
    #                         'revenue': 0
    #                     }
    #                 advisor_data[advisor.id]['orders'] += 1
    #                 advisor_data[advisor.id]['revenue'] += order.amount_total / len(order.service_advisor_id)

    #         top_advisors = sorted(
    #             advisor_data.values(),
    #             key=lambda x: x['revenue'],
    #             reverse=True
    #         )[:10]

    #         # Get top mechanics
    #         mechanic_data = {}
    #         for order in current_orders:
    #             for mechanic in order.car_mechanic_id_new:
    #                 if mechanic.id not in mechanic_data:
    #                     mechanic_data[mechanic.id] = {
    #                         'id': mechanic.id,
    #                         'name': mechanic.name,
    #                         'orders': 0,
    #                         'revenue': 0
    #                     }
    #                 mechanic_data[mechanic.id]['orders'] += 1
    #                 mechanic_data[mechanic.id]['revenue'] += order.amount_total / len(order.car_mechanic_id_new)

    #         top_mechanics = sorted(
    #             mechanic_data.values(),
    #             key=lambda x: x['revenue'],
    #             reverse=True
    #         )[:10]

    #         # Get cohort analysis data
    #         cohort_params = kw.get('cohort', {})
    #         cohort_depth = cohort_params.get('depth', 6)  # Default 6 bulan
    #         segment_by = cohort_params.get('segment_by')  # Optional segmentation parameter
    #         include_metrics = cohort_params.get('include_metrics', False)  # Optional additional metrics
            
    #         # Jika menggunakan enhanced cohort analysis
    #         if segment_by or include_metrics:
    #             # Get enhanced cohort data
    #             cohort_data = self.calculate_enhanced_customer_cohorts(
    #                 start_utc, 
    #                 end_utc, 
    #                 depth=cohort_depth,
    #                 segment_by=segment_by,
    #                 include_metrics=include_metrics
    #             )
    #         else:
    #             # Get basic cohort data (menggunakan fungsi yang sudah ada)
    #             basic_cohort_data = self.calculate_customer_cohorts(start_utc, end_utc, depth=cohort_depth)
    #             cohort_data = {
    #                 'segmented': False,
    #                 'cohorts': basic_cohort_data
    #             }

    #         return {
    #             'status': 'success',
    #             'data': {
    #                 'date_range': {
    #                     'type': date_range,
    #                     'start': start.strftime('%Y-%m-%d'),
    #                     'end': end.strftime('%Y-%m-%d')
    #                 },
    #                 'metrics': metrics,
    #                 'trends': trends,
    #                 'cohort_analysis': cohort_data,
    #                 'top_data': {
    #                     'products': {
    #                         'services': top_services,
    #                         'physical': top_physical_products
    #                     },
    #                     'quotations': top_quotations,
    #                     'sales': top_sales,
    #                     'customers': top_customers,
    #                     'categories': formatted_categories,
    #                     'advisors': top_advisors,
    #                     'mechanics': top_mechanics
    #                 }
    #             }
    #         }

        # except Exception as e:
    #         _logger.error(f"Error in get_dashboard_overview: {str(e)}")
    #         return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/statistics/overview', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_dashboard_overview(self, **kw):
        """Get comprehensive dashboard overview including cohort analysis"""
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
                elif date_range == 'last_year':
                    last_year = now.year - 1
                    start = now.replace(year=last_year, month=1, day=1, hour=0, minute=0, second=0)
                    end = now.replace(year=last_year, month=12, day=31, hour=23, minute=59, second=59)
                elif date_range == 'all_time':
                    # Use a far past date for start (e.g., 5 years ago)
                    start = now.replace(year=now.year-5, month=1, day=1, hour=0, minute=0, second=0)
                    end = now
                else:
                    start = now.replace(hour=0, minute=0, second=0)
                    end = now

            # Convert to UTC for database queries
            start_utc = start.astimezone(pytz.UTC)
            end_utc = end.astimezone(pytz.UTC)

            # Get previous period for comparison
            delta = end_utc - start_utc
            prev_end = start_utc - timedelta(microseconds=1)
            prev_start = prev_end - delta

            # Get current period orders dengan state='sale' dan menggunakan date_completed
            current_domain = [
                ('date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', '=', 'sale')  # Hanya ambil confirmed sales
            ]

            # Get previous period orders
            prev_domain = [
                ('date_completed', '>=', prev_start.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', prev_end.strftime('%Y-%m-%d %H:%M:%S')),
                ('state', '=', 'sale')  # Hanya ambil confirmed sales
            ]

            # Get quotations
            current_quotations = request.env['sale.order'].sudo().search([
                *current_domain,
                ('state', '=', 'draft')
            ])
            prev_quotations = request.env['sale.order'].sudo().search([
                *prev_domain,
                ('state', '=', 'draft')
            ])

            # Get confirmed orders
            current_orders = request.env['sale.order'].sudo().search(current_domain)
            prev_orders = request.env['sale.order'].sudo().search(prev_domain)

            # Calculate overall metrics
            current_order_count = len(current_orders)
            prev_order_count = len(prev_orders)
            current_flat_rate_hours = sum(order.total_service_duration for order in current_orders)
            prev_flat_rate_hours = sum(order.total_service_duration for order in prev_orders)

            # Overall flat rate metrics
            flat_rate_overall = {
                'total_flat_rate_hours': {
                    'current': round(current_flat_rate_hours, 2),
                    'previous': round(prev_flat_rate_hours, 2),
                    'growth': round(
                        ((current_flat_rate_hours - prev_flat_rate_hours) / prev_flat_rate_hours * 100)
                        if prev_flat_rate_hours else 0,
                        2
                    ),
                },
                'average_flat_rate_per_order': {
                    'current': round(current_flat_rate_hours / current_order_count, 2) if current_order_count else 0,
                    'previous': round(prev_flat_rate_hours / prev_order_count, 2) if prev_order_count else 0,
                    'growth': round(
                        (((current_flat_rate_hours / current_order_count if current_order_count else 0) -
                        (prev_flat_rate_hours / prev_order_count if prev_order_count else 0)) /
                        (prev_flat_rate_hours / prev_order_count if prev_order_count else 1) * 100)
                        if prev_flat_rate_hours else 0,
                        2
                    ),
                },
            }

            # Calculate flat rate per mechanic
            def calculate_mechanic_flat_rate(orders):
                mechanic_data = {}
                for order in orders:
                    if order.car_mechanic_id_new:
                        mechanic_count = len(order.car_mechanic_id_new)
                        if mechanic_count > 0:
                            flat_rate_per_mechanic = order.total_service_duration / mechanic_count
                            for mechanic in order.car_mechanic_id_new:
                                if mechanic.id not in mechanic_data:
                                    mechanic_data[mechanic.id] = {
                                        'id': mechanic.id,
                                        'name': mechanic.name,
                                        'total_flat_rate_hours': 0.0,
                                        'order_count': 0,
                                    }
                                mechanic_data[mechanic.id]['total_flat_rate_hours'] += flat_rate_per_mechanic
                                mechanic_data[mechanic.id]['order_count'] += 1
                return mechanic_data

            current_mechanic_data = calculate_mechanic_flat_rate(current_orders)
            prev_mechanic_data = calculate_mechanic_flat_rate(prev_orders)

            # Combine mechanic data for current and previous periods
            mechanic_flat_rate_data = []
            all_mechanic_ids = set(current_mechanic_data.keys()) | set(prev_mechanic_data.keys())
            for mechanic_id in all_mechanic_ids:
                current = current_mechanic_data.get(mechanic_id, {'total_flat_rate_hours': 0, 'order_count': 0, 'name': ''})
                prev = prev_mechanic_data.get(mechanic_id, {'total_flat_rate_hours': 0, 'order_count': 0, 'name': ''})
                mechanic_flat_rate = {
                    'id': mechanic_id,
                    'name': current.get('name') or prev.get('name') or 'Unknown',
                    'current': {
                        'total_flat_rate_hours': round(current['total_flat_rate_hours'], 2),
                        'order_count': current['order_count'],
                        'average_flat_rate': round(
                            current['total_flat_rate_hours'] / current['order_count'], 2
                        ) if current['order_count'] else 0,
                    },
                    'previous': {
                        'total_flat_rate_hours': round(prev['total_flat_rate_hours'], 2),
                        'order_count': prev['order_count'],
                        'average_flat_rate': round(
                            prev['total_flat_rate_hours'] / prev['order_count'], 2
                        ) if prev['order_count'] else 0,
                    },
                    'growth': {
                        'total_flat_rate_hours': round(
                            ((current['total_flat_rate_hours'] - prev['total_flat_rate_hours']) /
                            prev['total_flat_rate_hours'] * 100)
                            if prev['total_flat_rate_hours'] else 0,
                            2
                        ),
                    },
                }
                mechanic_flat_rate_data.append(mechanic_flat_rate)

            # Sort by current total flat rate hours
            mechanic_flat_rate_data.sort(key=lambda x: x['current']['total_flat_rate_hours'], reverse=True)

            # Calculate basic metrics
            current_revenue = sum(order.amount_untaxed for order in current_orders)
            prev_revenue = sum(order.amount_untaxed for order in prev_orders)
            
            metrics = {
                'quotations': {
                    'current': len(current_quotations),
                    'previous': len(prev_quotations),
                    'growth': ((len(current_quotations) - len(prev_quotations)) / len(prev_quotations) * 100) 
                            if prev_quotations else 0
                },
                'orders': {
                    'current': len(current_orders),
                    'previous': len(prev_orders),
                    'growth': ((len(current_orders) - len(prev_orders)) / len(prev_orders) * 100) 
                            if prev_orders else 0
                },
                'revenue': {
                    'current': current_revenue,
                    'previous': prev_revenue,
                    'growth': ((current_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else 0
                },
                'average_order': {
                    'current': current_revenue / len(current_orders) if current_orders else 0,
                    'previous': prev_revenue / len(prev_orders) if prev_orders else 0,
                    'growth': (((current_revenue / len(current_orders) if current_orders else 0) - 
                            (prev_revenue / len(prev_orders) if prev_orders else 0)) / 
                            (prev_revenue / len(prev_orders) if prev_orders else 1) * 100)
                            if prev_orders else 0
                },
                'flat_rate': {
                    'overall': flat_rate_overall,
                    'per_mechanic': mechanic_flat_rate_data,
                },
            }

            # Calculate daily/monthly sales trend
            trends = []
            current = start
            while current <= end:
                current_end = min(current.replace(hour=23, minute=59, second=59), end)
                day_orders = request.env['sale.order'].sudo().search([
                    ('date_completed', '>=', current.strftime('%Y-%m-%d %H:%M:%S')),
                    ('date_completed', '<=', current_end.strftime('%Y-%m-%d %H:%M:%S')),
                    ('state', '=', 'sale')
                ])
                
                if day_orders:
                    trends.append({
                        'date': current.strftime('%Y-%m-%d'),
                        'revenue': sum(order.amount_total for order in day_orders),
                        'orders': len(day_orders)
                    })
                
                current += timedelta(days=1)

            # Get top products
            order_lines = request.env['sale.order.line'].sudo().search([
                ('order_id.state', '=', 'sale'),
                ('order_id.date_completed', '>=', start_utc.strftime('%Y-%m-%d %H:%M:%S')),
                ('order_id.date_completed', '<=', end_utc.strftime('%Y-%m-%d %H:%M:%S'))
            ])
            
            # Get top products separated by category
            service_products = {}
            physical_products = {}

            for line in order_lines:
                product = line.product_id
                # Check if product is a service
                is_service = product.type == 'service'  # or use your own criteria to determine service
                
                # Choose target dictionary based on product type
                target_dict = service_products if is_service else physical_products
                
                if product.id not in target_dict:
                    target_dict[product.id] = {
                        'id': product.id,
                        'name': product.name,
                        'orders': 0,
                        'revenue': 0
                    }
                target_dict[product.id]['orders'] += line.product_uom_qty
                target_dict[product.id]['revenue'] += line.price_subtotal

            # Sort and get top 10 for each category
            top_services = sorted(
                service_products.values(),
                key=lambda x: x['revenue'],
                reverse=True
            )[:10]

            top_physical_products = sorted(
                physical_products.values(),
                key=lambda x: x['revenue'],
                reverse=True
            )[:10]

            # Get top quotations
            top_quotations = [{
                'id': quot.id,
                'name': quot.name,
                'customer': quot.partner_id.name,
                'service_advisor': [sa.name for sa in quot.service_advisor_id],
                'amount': quot.amount_total
            } for quot in sorted(
                current_quotations,
                key=lambda x: x.amount_total,
                reverse=True
            )[:10]]

            # Get top sales orders
            top_sales = [{
                'id': order.id,
                'name': order.name,
                'customer': order.partner_id.name,
                'service_advisor': [sa.name for sa in order.service_advisor_id],
                'mechanic': [m.name for m in order.car_mechanic_id_new],
                'amount': order.amount_total
            } for order in sorted(
                current_orders,
                key=lambda x: x.amount_total,
                reverse=True
            )[:10]]

            # Get top customers
            customer_data = {}
            for order in current_orders:
                if order.partner_id.id not in customer_data:
                    customer_data[order.partner_id.id] = {
                        'id': order.partner_id.id,
                        'name': order.partner_id.name,
                        'orders': 0,
                        'revenue': 0
                    }
                customer_data[order.partner_id.id]['orders'] += 1
                customer_data[order.partner_id.id]['revenue'] += order.amount_total

            top_customers = sorted(
                customer_data.values(),
                key=lambda x: x['revenue'],
                reverse=True
            )[:10]

            # Get top service categories 
            subcategory_data = {key: {'name': label, 'orders': 0, 'revenue': 0}
                    for key, label in request.env['sale.order']._fields['service_subcategory'].selection}

            # Calculate subcategories data
            for order in current_orders:
                if order.service_subcategory:
                    subcategory_data[order.service_subcategory]['orders'] += 1
                    subcategory_data[order.service_subcategory]['revenue'] += order.amount_total

            # Format and sort categories (with empty list fallback)
            formatted_categories = []
            if current_orders:
                formatted_categories = [
                    {
                        'id': subcat_key,
                        'name': subcat['name'], 
                        'orders': subcat['orders'],
                        'revenue': subcat['revenue']
                    }
                    for subcat_key, subcat in subcategory_data.items() 
                    if subcat['orders'] > 0
                ]
                formatted_categories.sort(key=lambda x: x['revenue'], reverse=True)

            # Get top service advisors
            advisor_data = {}
            for order in current_orders:
                for advisor in order.service_advisor_id:
                    if advisor.id not in advisor_data:
                        advisor_data[advisor.id] = {
                            'id': advisor.id,
                            'name': advisor.name,
                            'orders': 0,
                            'revenue': 0
                        }
                    advisor_data[advisor.id]['orders'] += 1
                    advisor_data[advisor.id]['revenue'] += order.amount_total / len(order.service_advisor_id)

            top_advisors = sorted(
                advisor_data.values(),
                key=lambda x: x['revenue'],
                reverse=True
            )[:10]

            # Get top mechanics
            mechanic_data = {}
            for order in current_orders:
                for mechanic in order.car_mechanic_id_new:
                    if mechanic.id not in mechanic_data:
                        mechanic_data[mechanic.id] = {
                            'id': mechanic.id,
                            'name': mechanic.name,
                            'orders': 0,
                            'revenue': 0
                        }
                    mechanic_data[mechanic.id]['orders'] += 1
                    mechanic_data[mechanic.id]['revenue'] += order.amount_total / len(order.car_mechanic_id_new)

            top_mechanics = sorted(
                mechanic_data.values(),
                key=lambda x: x['revenue'],
                reverse=True
            )[:10]

            # Get cohort analysis data - New Auto Service Cohort Implementation
            cohort_params = kw.get('cohort', {})
            cohort_depth = cohort_params.get('depth', 12)  # Default 12 periods
            segment_by = cohort_params.get('segment_by')  # Optional segmentation parameter
            include_metrics = cohort_params.get('include_metrics', False)  # Optional additional metrics
            interval_type = cohort_params.get('interval_type', '3_month')  # Default to 3-month interval for auto service
            
            # Get enhanced auto service cohort data
            cohort_data = self.calculate_auto_service_cohorts(
                start_utc, 
                end_utc, 
                interval_type=interval_type,
                depth=cohort_depth,
                segment_by=segment_by,
                include_metrics=include_metrics
            )

            return {
                'status': 'success',
                'data': {
                    'date_range': {
                        'type': date_range,
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    },
                    'metrics': metrics,
                    'trends': trends,
                    'cohort_analysis': cohort_data,
                    'top_data': {
                        'products': {
                            'services': top_services,
                            'physical': top_physical_products
                        },
                        'quotations': top_quotations,
                        'sales': top_sales,
                        'customers': top_customers,
                        'categories': formatted_categories,
                        'advisors': top_advisors,
                        'mechanics': top_mechanics
                    }
                }
            }
        
        except Exception as e:
            _logger.error(f"Error in get_dashboard_overview: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def calculate_customer_cohorts(self, start_date, end_date, depth=6):
        """
        Menghitung analisis cohort retensi pelanggan dasar.
        
        Args:
            start_date: Tanggal awal untuk analisis cohort (format: datetime UTC)
            end_date: Tanggal akhir untuk analisis cohort (format: datetime UTC)
            depth: Jumlah bulan yang akan dihitung untuk retensi (default: 6)
            
        Returns:
            List berisi data cohort
        """
        try:
            # Mengambil semua order dengan state 'sale' dalam periode yang ditentukan
            # dan sudah selesai (date_completed)
            all_orders = request.env['sale.order'].sudo().search([
                ('state', '=', 'sale'),
                ('date_completed', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
            ])
            
            if not all_orders:
                return []
                
            # Menggunakan defaultdict untuk mengorganisir pesanan berdasarkan pelanggan dan waktu
            from collections import defaultdict
            import calendar
            from dateutil.relativedelta import relativedelta
            
            # Dictionary untuk menyimpan bulan pertama order untuk setiap pelanggan
            customer_first_order = {}
            # Dictionary untuk menyimpan semua order berdasarkan pelanggan dan bulan
            customer_orders_by_month = defaultdict(lambda: defaultdict(list))
            
            # Kelompokkan orders berdasarkan pelanggan dan bulan
            for order in all_orders:
                customer_id = order.partner_id.id
                order_date = order.date_completed.replace(tzinfo=pytz.UTC)
                
                # Format bulan cohort sebagai 'YYYY-MM'
                order_month = order_date.strftime('%Y-%m')
                
                # Simpan order ke dalam dictionary berdasarkan pelanggan dan bulan
                customer_orders_by_month[customer_id][order_month].append(order)
                
                # Catat bulan pertama kali pelanggan order (jika belum ada)
                if customer_id not in customer_first_order or order_date < customer_first_order[customer_id]['date']:
                    customer_first_order[customer_id] = {
                        'date': order_date,
                        'month': order_month
                    }
            
            # Dictionary untuk menyimpan cohort
            cohort_data = defaultdict(lambda: defaultdict(int))
            # Dictionary untuk menyimpan total pelanggan per cohort
            cohort_sizes = defaultdict(int)
            
            # Hitung bulan tersedia dalam rentang
            start_month_date = start_date.replace(day=1, hour=0, minute=0, second=0)
            available_months = []
            current_month = start_month_date
            
            while current_month <= end_date:
                available_months.append(current_month.strftime('%Y-%m'))
                current_month += relativedelta(months=1)
            
            # Untuk setiap pelanggan, hitung aktivitas retensi
            for customer_id, first_order_info in customer_first_order.items():
                first_month = first_order_info['month']
                first_date = first_order_info['date']
                
                # Increment ukuran cohort
                cohort_sizes[first_month] += 1
                
                # Untuk setiap bulan dalam periode, hitung retensi
                for i, month in enumerate(available_months):
                    # Periksa apakah bulan lebih besar atau sama dengan first_month
                    if month >= first_month:
                        # Hitung selisih bulan antara bulan saat ini dan bulan pertama
                        month_date = datetime.strptime(month, '%Y-%m')
                        first_month_date = datetime.strptime(first_month, '%Y-%m')
                        month_diff = (month_date.year - first_month_date.year) * 12 + (month_date.month - first_month_date.month)
                        
                        # Jika pelanggan memiliki order di bulan ini, tandai sebagai retensi
                        if month in customer_orders_by_month[customer_id]:
                            cohort_data[first_month][month_diff] += 1
            
            # Format data cohort untuk output
            formatted_cohorts = []
            for cohort_month, retentions in cohort_data.items():
                cohort_size = cohort_sizes[cohort_month]
                
                # Buat entri cohort
                cohort_entry = {
                    'cohort': cohort_month,
                    'cohort_display': datetime.strptime(cohort_month, '%Y-%m').strftime('%b %Y'),
                    'total_customers': cohort_size
                }
                
                # Tambahkan data retensi untuk setiap bulan (hingga depth)
                for month_number in range(depth + 1):  # +1 karena kita juga ingin bulan 0
                    retention_count = retentions.get(month_number, 0)
                    retention_rate = (retention_count / cohort_size * 100) if cohort_size else 0
                    
                    # Format: 'month0', 'month1', dst. untuk retensi di bulan ke-n
                    cohort_entry[f'month{month_number}'] = round(retention_rate, 1)
                
                formatted_cohorts.append(cohort_entry)
            
            # Urutkan cohort berdasarkan bulan (terbaru ke terlama)
            formatted_cohorts.sort(key=lambda x: x['cohort'], reverse=True)
            
            return formatted_cohorts
            
        except Exception as e:
            _logger.error(f"Error in calculate_customer_cohorts: {str(e)}")
            return []

    def calculate_enhanced_customer_cohorts(self, start_date, end_date, depth=6, segment_by=None, include_metrics=False):
        """
        Menghitung analisis cohort retensi pelanggan dengan segmentasi dan metrik tambahan.
        
        Args:
            start_date: Tanggal awal untuk analisis cohort (format: datetime UTC)
            end_date: Tanggal akhir untuk analisis cohort (format: datetime UTC)
            depth: Jumlah bulan yang akan dihitung untuk retensi (default: 6)
            segment_by: Field untuk segmentasi ('car_brand', 'service_category', 'service_advisor', dll)
            include_metrics: Jika True, akan menyertakan metrik tambahan seperti rating, revenue, dll
            
        Returns:
            Dictionary berisi data cohort dengan segmentasi yang diminta
        """
        try:
            # Mengambil semua order dengan state 'sale' dalam periode yang ditentukan
            # dan sudah selesai (date_completed)
            all_orders = request.env['sale.order'].sudo().search([
                ('state', '=', 'sale'),
                ('date_completed', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
            ])
            
            if not all_orders:
                return []
                
            # Menggunakan defaultdict untuk mengorganisir pesanan berdasarkan pelanggan dan waktu
            from collections import defaultdict
            import calendar
            from dateutil.relativedelta import relativedelta
            
            # Dictionary untuk menyimpan bulan pertama order untuk setiap pelanggan
            customer_first_order = {}
            # Dictionary untuk menyimpan semua order berdasarkan pelanggan dan bulan
            customer_orders_by_month = defaultdict(lambda: defaultdict(list))
            
            # Kelompokkan orders berdasarkan pelanggan dan bulan
            for order in all_orders:
                customer_id = order.partner_id.id
                order_date = order.date_completed.replace(tzinfo=pytz.UTC)
                
                # Format bulan cohort sebagai 'YYYY-MM'
                order_month = order_date.strftime('%Y-%m')
                
                # Simpan order ke dalam dictionary berdasarkan pelanggan dan bulan
                customer_orders_by_month[customer_id][order_month].append(order)
                
                # Catat bulan pertama kali pelanggan order (jika belum ada)
                if customer_id not in customer_first_order or order_date < customer_first_order[customer_id]['date']:
                    customer_first_order[customer_id] = {
                        'date': order_date,
                        'month': order_month,
                        'order': order  # Simpan referensi ke order agar bisa mendapatkan data segmentasi
                    }
            
            # Hitung bulan tersedia dalam rentang
            start_month_date = start_date.replace(day=1, hour=0, minute=0, second=0)
            available_months = []
            current_month = start_month_date
            
            while current_month <= end_date:
                available_months.append(current_month.strftime('%Y-%m'))
                current_month += relativedelta(months=1)
                
            # Mempersiapkan data segmentasi jika diminta
            segment_data = {}
            if segment_by:
                if segment_by == 'car_brand':
                    # Segmentasi berdasarkan brand mobil
                    for customer_id, data in customer_first_order.items():
                        order = data['order']
                        brand = order.partner_car_brand.name if order.partner_car_brand else 'Unknown'
                        if brand not in segment_data:
                            segment_data[brand] = {
                                'cohort_data': defaultdict(lambda: defaultdict(int)),
                                'cohort_sizes': defaultdict(int),
                                'customers': set()
                            }
                        segment_data[brand]['customers'].add(customer_id)
                elif segment_by == 'service_category':
                    # Segmentasi berdasarkan kategori servis
                    for customer_id, data in customer_first_order.items():
                        order = data['order']
                        category = dict(order._fields['service_category'].selection).get(order.service_category, 'Unknown')
                        if category not in segment_data:
                            segment_data[category] = {
                                'cohort_data': defaultdict(lambda: defaultdict(int)),
                                'cohort_sizes': defaultdict(int),
                                'customers': set()
                            }
                        segment_data[category]['customers'].add(customer_id)
                elif segment_by == 'service_advisor':
                    # Segmentasi berdasarkan service advisor
                    for customer_id, data in customer_first_order.items():
                        order = data['order']
                        advisors = order.service_advisor_id
                        if not advisors:
                            advisor_name = 'No Advisor'
                        else:
                            advisor_name = ', '.join(advisor.name for advisor in advisors)
                        
                        if advisor_name not in segment_data:
                            segment_data[advisor_name] = {
                                'cohort_data': defaultdict(lambda: defaultdict(int)),
                                'cohort_sizes': defaultdict(int),
                                'customers': set()
                            }
                        segment_data[advisor_name]['customers'].add(customer_id)
                elif segment_by == 'customer_rating':
                    # Segmentasi berdasarkan rating pelanggan
                    for customer_id, data in customer_first_order.items():
                        order = data['order']
                        rating = order.customer_rating or 'No Rating'
                        if rating not in segment_data:
                            segment_data[rating] = {
                                'cohort_data': defaultdict(lambda: defaultdict(int)),
                                'cohort_sizes': defaultdict(int),
                                'customers': set()
                            }
                        segment_data[rating]['customers'].add(customer_id)
            
            # Hasil akan berbentuk berbeda tergantung apakah ada segmentasi
            if segment_by:
                # Proses untuk data tersegmentasi
                segment_result = {}
                
                for segment_key, segment_info in segment_data.items():
                    cohort_data = defaultdict(lambda: defaultdict(int))
                    cohort_sizes = defaultdict(int)
                    segment_customers = segment_info['customers']
                    
                    # Untuk setiap pelanggan dalam segmen ini, hitung retensi
                    for customer_id in segment_customers:
                        if customer_id in customer_first_order:
                            first_month = customer_first_order[customer_id]['month']
                            first_date = customer_first_order[customer_id]['date']
                            
                            # Increment ukuran cohort
                            cohort_sizes[first_month] += 1
                            
                            # Untuk setiap bulan dalam periode, hitung retensi
                            for i, month in enumerate(available_months):
                                # Periksa apakah bulan lebih besar atau sama dengan first_month
                                if month >= first_month:
                                    # Hitung selisih bulan antara bulan saat ini dan bulan pertama
                                    month_date = datetime.strptime(month, '%Y-%m')
                                    first_month_date = datetime.strptime(first_month, '%Y-%m')
                                    month_diff = (month_date.year - first_month_date.year) * 12 + (month_date.month - first_month_date.month)
                                    
                                    # Jika pelanggan memiliki order di bulan ini, tandai sebagai retensi
                                    if month in customer_orders_by_month[customer_id]:
                                        cohort_data[first_month][month_diff] += 1
                    
                    # Format data cohort untuk output
                    formatted_cohorts = []
                    for cohort_month, retentions in cohort_data.items():
                        cohort_size = cohort_sizes[cohort_month]
                        
                        # Buat entri cohort
                        cohort_entry = {
                            'cohort': cohort_month,
                            'cohort_display': datetime.strptime(cohort_month, '%Y-%m').strftime('%b %Y'),
                            'segment': segment_key,
                            'total_customers': cohort_size
                        }
                        
                        # Tambahkan data retensi untuk setiap bulan (hingga depth)
                        for month_number in range(depth + 1):  # +1 karena kita juga ingin bulan 0
                            retention_count = retentions.get(month_number, 0)
                            retention_rate = (retention_count / cohort_size * 100) if cohort_size else 0
                            
                            # Format: 'month0', 'month1', dst. untuk retensi di bulan ke-n
                            cohort_entry[f'month{month_number}'] = round(retention_rate, 1)
                        
                        formatted_cohorts.append(cohort_entry)
                    
                    # Urutkan cohort berdasarkan bulan (terbaru ke terlama)
                    formatted_cohorts.sort(key=lambda x: x['cohort'], reverse=True)
                    segment_result[segment_key] = formatted_cohorts
                
                return {
                    'segmented': True,
                    'segment_by': segment_by,
                    'segments': segment_result
                }
                
            else:
                # Proses tanpa segmentasi (original cohort analysis)
                cohort_data = defaultdict(lambda: defaultdict(int))
                cohort_sizes = defaultdict(int)
                
                # Untuk setiap pelanggan, hitung aktivitas retensi
                for customer_id, first_order_info in customer_first_order.items():
                    first_month = first_order_info['month']
                    first_date = first_order_info['date']
                    
                    # Increment ukuran cohort
                    cohort_sizes[first_month] += 1
                    
                    # Untuk setiap bulan dalam periode, hitung retensi
                    for i, month in enumerate(available_months):
                        # Periksa apakah bulan lebih besar atau sama dengan first_month
                        if month >= first_month:
                            # Hitung selisih bulan antara bulan saat ini dan bulan pertama
                            month_date = datetime.strptime(month, '%Y-%m')
                            first_month_date = datetime.strptime(first_month, '%Y-%m')
                            month_diff = (month_date.year - first_month_date.year) * 12 + (month_date.month - first_month_date.month)
                            
                            # Jika pelanggan memiliki order di bulan ini, tandai sebagai retensi
                            if month in customer_orders_by_month[customer_id]:
                                cohort_data[first_month][month_diff] += 1
                
                # Format data cohort untuk output
                formatted_cohorts = []
                
                # Dictionary untuk metrik tambahan jika diperlukan
                cohort_metrics = defaultdict(lambda: {
                    'avg_rating': [],
                    'total_revenue': 0,
                    'booking_rate': {'yes': 0, 'no': 0},
                    'feedback_rate': {'yes': 0, 'no': 0}
                }) if include_metrics else None
                
                for cohort_month, retentions in cohort_data.items():
                    cohort_size = cohort_sizes[cohort_month]
                    
                    # Buat entri cohort
                    cohort_entry = {
                        'cohort': cohort_month,
                        'cohort_display': datetime.strptime(cohort_month, '%Y-%m').strftime('%b %Y'),
                        'total_customers': cohort_size
                    }
                    
                    # Tambahkan data retensi untuk setiap bulan (hingga depth)
                    for month_number in range(depth + 1):  # +1 karena kita juga ingin bulan 0
                        retention_count = retentions.get(month_number, 0)
                        retention_rate = (retention_count / cohort_size * 100) if cohort_size else 0
                        
                        # Format: 'month0', 'month1', dst. untuk retensi di bulan ke-n
                        cohort_entry[f'month{month_number}'] = round(retention_rate, 1)
                    
                    # Tambahkan metrik tambahan jika diperlukan
                    if include_metrics:
                        # Ambil semua pelanggan dalam cohort ini
                        cohort_customers = [
                            cust_id for cust_id, info in customer_first_order.items()
                            if info['month'] == cohort_month
                        ]
                        
                        # Metrik untuk cohort ini
                        all_orders_in_cohort = []
                        for cust_id in cohort_customers:
                            cust_orders = []
                            for month_orders in customer_orders_by_month[cust_id].values():
                                cust_orders.extend(month_orders)
                            all_orders_in_cohort.extend(cust_orders)
                        
                        # Calculate metrics
                        ratings = [float(o.customer_rating) for o in all_orders_in_cohort if o.customer_rating and o.customer_rating.isdigit()]
                        avg_rating = sum(ratings) / len(ratings) if ratings else 0
                        
                        total_revenue = sum(o.amount_total for o in all_orders_in_cohort)
                        
                        booking_yes = sum(1 for o in all_orders_in_cohort if o.is_booking)
                        booking_rate = (booking_yes / len(all_orders_in_cohort) * 100) if all_orders_in_cohort else 0
                        
                        feedback_yes = sum(1 for o in all_orders_in_cohort if o.is_willing_to_feedback == 'yes')
                        feedback_rate = (feedback_yes / len(all_orders_in_cohort) * 100) if all_orders_in_cohort else 0
                        
                        cohort_entry.update({
                            'avg_rating': round(avg_rating, 1),
                            'total_revenue': round(total_revenue, 2),
                            'booking_rate': round(booking_rate, 1),
                            'feedback_rate': round(feedback_rate, 1)
                        })
                    
                    formatted_cohorts.append(cohort_entry)
                
                # Urutkan cohort berdasarkan bulan (terbaru ke terlama)
                formatted_cohorts.sort(key=lambda x: x['cohort'], reverse=True)
                
                result = {
                    'segmented': False,
                    'cohorts': formatted_cohorts
                }
                
                return result
            
        except Exception as e:
            _logger.error(f"Error in calculate_enhanced_customer_cohorts: {str(e)}")
            return {'error': str(e)}

    def calculate_auto_service_cohorts(self, start_date, end_date, interval_type='monthly', depth=12, segment_by=None, include_metrics=False):
        """
        Menghitung analisis cohort retensi pelanggan khusus untuk bengkel mobil dengan pendekatan interval servis.
        
        Args:
            start_date: Tanggal awal untuk analisis cohort (format: datetime UTC)
            end_date: Tanggal akhir untuk analisis cohort (format: datetime UTC)
            interval_type: Tipe interval cohort ('monthly', '3_month', '6_month', '12_month')
            depth: Jumlah interval yang akan dihitung (default: 12)
            segment_by: Field untuk segmentasi ('car_brand', 'service_category', 'service_advisor', dll)
            include_metrics: Jika True, akan menyertakan metrik tambahan
            
        Returns:
            Dictionary berisi data cohort dengan pola retensi servis mobil
        """
        try:
            # Mengambil semua order dalam rentang waktu
            all_orders = request.env['sale.order'].sudo().search([
                ('state', '=', 'sale'),
                ('date_completed', '>=', start_date.strftime('%Y-%m-%d %H:%M:%S')),
                ('date_completed', '<=', end_date.strftime('%Y-%m-%d %H:%M:%S'))
            ])
            
            if not all_orders:
                return {'segmented': False, 'cohorts': []}
                
            # Import libraries
            from collections import defaultdict
            from dateutil.relativedelta import relativedelta
            
            # Tentukan interval dalam bulan berdasarkan tipe yang dipilih
            interval_months = {
                'monthly': 1,
                '3_month': 3,
                '6_month': 6,
                '12_month': 12
            }.get(interval_type, 1)
            
            # Tentukan window toleransi (seberapa jauh dari tanggal ekspektasi servis berikutnya)
            # Misal: Untuk interval 3 bulan, berikan window 1 bulan (sebulan sebelum dan sesudah)
            window_months = max(1, interval_months // 3)
            
            # Dictionary untuk menyimpan semua order per pelanggan dan tanggal 
            customer_orders = defaultdict(list)
            # Dictionary untuk menyimpan mobil yang dimiliki pelanggan
            customer_cars = defaultdict(set)
            # Dictionary untuk menyimpan order pertama per pelanggan
            first_orders = {}
            # Dictionary untuk track bulan pertama servis per cohort
            cohort_first_months = defaultdict(list)
            
            # Proses semua order
            for order in all_orders:
                customer_id = order.partner_id.id
                car_id = order.partner_car_id.id if order.partner_car_id else None
                
                if car_id:
                    customer_cars[customer_id].add(car_id)
                
                # Simpan order dengan data lengkap
                customer_orders[customer_id].append({
                    'id': order.id,
                    'date': order.date_completed,
                    'car_id': car_id,
                    'car_brand': order.partner_car_brand.name if order.partner_car_brand else None,
                    'service_category': order.service_category,
                    'service_subcategory': order.service_subcategory,
                    'service_advisor': order.service_advisor_id[0].name if order.service_advisor_id else None,
                    'customer_rating': order.customer_rating,
                    'is_booking': order.is_booking,
                    'is_willing_to_feedback': order.is_willing_to_feedback,
                    'revenue': order.amount_total,
                    'order': order
                })
            
            # Urutkan order untuk setiap pelanggan berdasarkan tanggal
            for customer_id, orders in customer_orders.items():
                orders.sort(key=lambda o: o['date'])
                
                # Catat order pertama untuk setiap pelanggan
                if orders:
                    first_orders[customer_id] = orders[0]
                    
                    # Tentukan bulan cohort berdasarkan tanggal order pertama
                    first_date = orders[0]['date']
                    # Format cohort berdasarkan interval
                    if interval_type == 'monthly':
                        cohort_key = first_date.strftime('%Y-%m')  # YYYY-MM
                    elif interval_type == '3_month':
                        # Quarter (Q1, Q2, Q3, Q4)
                        quarter = ((first_date.month - 1) // 3) + 1
                        cohort_key = f"{first_date.year}-Q{quarter}"
                    elif interval_type == '6_month':
                        # Semester (S1, S2)
                        semester = ((first_date.month - 1) // 6) + 1
                        cohort_key = f"{first_date.year}-S{semester}"
                    else:  # 12_month
                        cohort_key = f"{first_date.year}"
                    
                    # Tambahkan ke cohort yang sesuai
                    cohort_first_months[cohort_key].append({
                        'customer_id': customer_id,
                        'first_date': first_date,
                        'order': orders[0]
                    })
            
            # Jika ada segmentasi, proses data segmentasi
            segment_data = {}
            if segment_by:
                # Inisialisasi segment data
                for customer_info in first_orders.values():
                    # Tentukan nilai segment berdasarkan parameter segment_by
                    if segment_by == 'car_brand':
                        segment_value = customer_info['car_brand'] or 'Unknown'
                    elif segment_by == 'service_category':
                        segment_value = dict(all_orders._fields['service_category'].selection).get(
                            customer_info['service_category'], 'Unknown')
                    elif segment_by == 'service_advisor':
                        segment_value = customer_info['service_advisor'] or 'No Advisor'
                    elif segment_by == 'customer_rating':
                        segment_value = customer_info['customer_rating'] or 'No Rating'
                    else:
                        segment_value = 'Default'
                    
                    # Inisialisasi segment jika belum ada
                    if segment_value not in segment_data:
                        segment_data[segment_value] = {
                            'cohorts': defaultdict(list),
                            'retention_data': defaultdict(lambda: defaultdict(int))
                        }
                    
                    # Tambahkan customer ke segment
                    customer_id = customer_info['order']['partner_id'].id
                    first_date = customer_info['date']
                    
                    # Tentukan cohort key seperti sebelumnya
                    if interval_type == 'monthly':
                        cohort_key = first_date.strftime('%Y-%m')
                    elif interval_type == '3_month':
                        quarter = ((first_date.month - 1) // 3) + 1
                        cohort_key = f"{first_date.year}-Q{quarter}"
                    elif interval_type == '6_month':
                        semester = ((first_date.month - 1) // 6) + 1
                        cohort_key = f"{first_date.year}-S{semester}"
                    else:  # 12_month
                        cohort_key = f"{first_date.year}"
                    
                    segment_data[segment_value]['cohorts'][cohort_key].append(customer_id)
            
            # Proses data retensi untuk setiap cohort
            def process_cohort_retention(cohort_key, customer_infos, segment=None):
                # Struktur untuk menyimpan data retensi cohort tertentu
                retention_data = defaultdict(int)
                cohort_size = len(customer_infos)
                
                # Untuk setiap pelanggan dalam cohort, cek retensi di interval berikutnya
                for customer_info in customer_infos:
                    customer_id = customer_info['customer_id']
                    first_date = customer_info['first_date']
                    
                    # Dapatkan semua order untuk pelanggan ini
                    orders = customer_orders[customer_id]
                    
                    # Untuk setiap interval berikutnya, cek apakah ada servis
                    for interval in range(depth + 1):  # +1 karena kita ingin termasuk interval 0 (awal)
                        # Interval 0 selalu 100% (semua pelanggan ada di bulan pertama)
                        if interval == 0:
                            retention_data[0] += 1
                            continue
                        
                        # Hitung tanggal ekspektasi untuk interval ini
                        expected_date = first_date + relativedelta(months=interval * interval_months)
                        
                        # Tentukan window toleransi
                        window_start = expected_date - relativedelta(months=window_months)
                        window_end = expected_date + relativedelta(months=window_months)
                        
                        # Cek apakah ada servis dalam window
                        has_service = False
                        for order in orders:
                            if window_start <= order['date'] <= window_end:
                                # Jika pelanggan servis dalam window, tandai sebagai retensi
                                has_service = True
                                break
                        
                        if has_service:
                            retention_data[interval] += 1
                
                # Hitung persentase retensi
                retention_percent = {}
                for interval, count in retention_data.items():
                    retention_percent[interval] = round((count / cohort_size * 100) if cohort_size else 0, 1)
                
                # Format data untuk output
                result = {
                    'cohort': cohort_key,
                    'cohort_display': format_cohort_display(cohort_key, interval_type),
                    'total_customers': cohort_size,
                }
                
                # Tambahkan persentase retensi untuk setiap interval
                for interval in range(depth + 1):
                    result[f'month{interval}'] = retention_percent.get(interval, 0)
                
                # Jika segment ditentukan
                if segment:
                    result['segment'] = segment
                
                # Jika metrics diminta, tambahkan metrik lainnya
                if include_metrics:
                    # Ambil semua order untuk cohort ini
                    all_cohort_orders = []
                    for customer_info in customer_infos:
                        all_cohort_orders.extend([o['order'] for o in customer_orders[customer_info['customer_id']]])
                    
                    # Hitung metrik tambahan
                    if all_cohort_orders:
                        # Average rating
                        ratings = [float(o.customer_rating) for o in all_cohort_orders 
                                if o.customer_rating and o.customer_rating.isdigit()]
                        avg_rating = sum(ratings) / len(ratings) if ratings else 0
                        
                        # Booking rate
                        booking_count = sum(1 for o in all_cohort_orders if o.is_booking)
                        booking_rate = (booking_count / len(all_cohort_orders) * 100)
                        
                        # Feedback rate
                        feedback_count = sum(1 for o in all_cohort_orders if o.is_willing_to_feedback == 'yes')
                        feedback_rate = (feedback_count / len(all_cohort_orders) * 100)
                        
                        # Total revenue
                        total_revenue = sum(o.amount_total for o in all_cohort_orders)
                        
                        # Cars per customer
                        cars_per_customer = sum(len(customer_cars[info['customer_id']]) 
                                                for info in customer_infos) / cohort_size
                        
                        # Tambahkan metrik ke result
                        result.update({
                            'avg_rating': round(avg_rating, 1),
                            'booking_rate': round(booking_rate, 1),
                            'feedback_rate': round(feedback_rate, 1),
                            'total_revenue': round(total_revenue, 2),
                            'cars_per_customer': round(cars_per_customer, 1)
                        })
                
                return result
            
            # Helper untuk format cohort display
            def format_cohort_display(cohort_key, interval_type):
                """Format cohort key menjadi tampilan yang lebih user friendly"""
                if interval_type == 'monthly':
                    # YYYY-MM format to Month Year (e.g., Jan 2023)
                    try:
                        year, month = cohort_key.split('-')
                        return datetime(int(year), int(month), 1).strftime('%b %Y')
                    except:
                        return cohort_key
                elif interval_type == '3_month':
                    # YYYY-Q# format to Q# YYYY (e.g., Q1 2023)
                    try:
                        year, quarter = cohort_key.split('-')
                        return f"{quarter} {year}"
                    except:
                        return cohort_key
                elif interval_type == '6_month':
                    # YYYY-S# format to H# YYYY (e.g., H1 2023)
                    try:
                        year, semester = cohort_key.split('-')
                        return f"{semester} {year}"
                    except:
                        return cohort_key
                else:  # yearly
                    # YYYY format to Year YYYY (e.g., Year 2023)
                    return f"Year {cohort_key}"
            
            # Proses hasil akhir
            if segment_by:
                # Result dengan segmentasi
                segment_result = {}
                
                for segment_value, data in segment_data.items():
                    segment_cohorts = []
                    
                    for cohort_key, customer_ids in data['cohorts'].items():
                        # Dapatkan info pelanggan untuk cohort ini
                        customer_infos = [
                            {'customer_id': cust_id, 'first_date': first_orders[cust_id]['date']}
                            for cust_id in customer_ids if cust_id in first_orders
                        ]
                        
                        if customer_infos:
                            # Proses data retensi untuk segment dan cohort ini
                            cohort_data = process_cohort_retention(
                                cohort_key, customer_infos, segment_value
                            )
                            segment_cohorts.append(cohort_data)
                    
                    # Sort cohorts dalam segment dan simpan
                    if segment_cohorts:
                        segment_cohorts.sort(key=lambda x: x['cohort'], reverse=True)
                        segment_result[segment_value] = segment_cohorts
                
                return {
                    'segmented': True,
                    'segment_by': segment_by,
                    'interval_type': interval_type,
                    'segments': segment_result
                }
                
            else:
                # Result tanpa segmentasi
                formatted_cohorts = []
                
                for cohort_key, customer_infos in cohort_first_months.items():
                    cohort_data = process_cohort_retention(cohort_key, customer_infos)
                    formatted_cohorts.append(cohort_data)
                
                # Sort cohorts
                formatted_cohorts.sort(key=lambda x: x['cohort'], reverse=True)
                
                return {
                    'segmented': False,
                    'interval_type': interval_type,
                    'cohorts': formatted_cohorts
                }
                
        except Exception as e:
            _logger.error(f"Error in calculate_auto_service_cohorts: {str(e)}")
            return {'error': str(e), 'segmented': False, 'cohorts': []}