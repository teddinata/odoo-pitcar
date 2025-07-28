# models/lms_config.py
from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # LMS General Settings
    lms_auto_enroll_new_employees = fields.Boolean(
        string='Auto-enroll New Employees',
        config_parameter='lms.auto_enroll_new_employees',
        help='Automatically enroll new employees in mandatory courses'
    )
    
    lms_default_passing_score = fields.Float(
        string='Default Passing Score (%)',
        config_parameter='lms.default_passing_score',
        default=70.0,
        help='Default minimum score to pass assessments'
    )
    
    lms_max_attempts_default = fields.Integer(
        string='Default Maximum Attempts',
        config_parameter='lms.max_attempts_default',
        default=3,
        help='Default maximum attempts for assessments'
    )
    
    lms_completion_points_default = fields.Integer(
        string='Default Completion Points',
        config_parameter='lms.completion_points_default',
        default=10,
        help='Default points awarded for course completion'
    )
    
    # Gamification Settings
    lms_enable_gamification = fields.Boolean(
        string='Enable Gamification',
        config_parameter='lms.enable_gamification',
        default=True,
        help='Enable points, badges, and leaderboards'
    )
    
    lms_enable_certificates = fields.Boolean(
        string='Enable Certificates',
        config_parameter='lms.enable_certificates',
        default=True,
        help='Generate certificates upon course completion'
    )
    
    lms_enable_learning_paths = fields.Boolean(
        string='Enable Learning Paths',
        config_parameter='lms.enable_learning_paths',
        default=True,
        help='Enable structured learning paths for roles'
    )
    
    # Notification Settings
    lms_send_enrollment_emails = fields.Boolean(
        string='Send Enrollment Emails',
        config_parameter='lms.send_enrollment_emails',
        default=True,
        help='Send email notifications for new enrollments'
    )
    
    lms_send_completion_emails = fields.Boolean(
        string='Send Completion Emails',
        config_parameter='lms.send_completion_emails',
        default=True,
        help='Send email notifications for course completions'
    )
    
    lms_send_reminder_emails = fields.Boolean(
        string='Send Reminder Emails',
        config_parameter='lms.send_reminder_emails',
        default=True,
        help='Send email reminders for overdue courses'
    )
    
    lms_reminder_days = fields.Integer(
        string='Reminder Days',
        config_parameter='lms.reminder_days',
        default=7,
        help='Send reminders after X days of inactivity'
    )
    
    # Content Settings
    lms_max_file_size_mb = fields.Integer(
        string='Maximum File Size (MB)',
        config_parameter='lms.max_file_size_mb',
        default=100,
        help='Maximum file size for course content uploads'
    )
    
    lms_allowed_file_types = fields.Char(
        string='Allowed File Types',
        config_parameter='lms.allowed_file_types',
        default='pdf,mp4,pptx,docx,xlsx',
        help='Comma-separated list of allowed file extensions'
    )
    
    # Integration Settings
    lms_odoo_training_category_id = fields.Many2one(
        'lms.category',
        string='Odoo Training Category',
        config_parameter='lms.odoo_training_category_id',
        help='Default category for Odoo system training courses'
    )
    
    # API Settings untuk Vue.js integration
    lms_api_enabled = fields.Boolean(
        string='Enable LMS API',
        config_parameter='lms.api_enabled',
        default=True,
        help='Enable REST API for frontend integration'
    )
    
    lms_api_rate_limit = fields.Integer(
        string='API Rate Limit (requests/minute)',
        config_parameter='lms.api_rate_limit',
        default=100,
        help='Rate limit for API requests per user per minute'
    )

class LMSSystemParameter(models.Model):
    """Extended system parameters for LMS"""
    _name = 'lms.system.parameter'
    _description = 'LMS System Parameters'
    
    key = fields.Char('Parameter Key', required=True)
    value = fields.Text('Parameter Value')
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('key_unique', 'unique(key)', 'Parameter key must be unique!'),
    ]
    
    @api.model
    def get_param(self, key, default=None):
        """Get system parameter value"""
        param = self.search([('key', '=', key), ('active', '=', True)], limit=1)
        return param.value if param else default
    
    @api.model
    def set_param(self, key, value, description=None):
        """Set system parameter value"""
        param = self.search([('key', '=', key)], limit=1)
        if param:
            param.value = value
            if description:
                param.description = description
        else:
            self.create({
                'key': key,
                'value': value,
                'description': description or key
            })

# Default data untuk system parameters
class LMSDataDefault(models.Model):
    _name = 'lms.data.default'
    _description = 'LMS Default Data Handler'
    
    @api.model
    def create_default_categories(self):
        """Create default course categories"""
        categories = [
            {
                'name': 'Odoo System Training',
                'code': 'odoo',
                'icon': 'fa fa-desktop',
                'color': '#875A7B'
            },
            {
                'name': 'Technical Skills',
                'code': 'technical',
                'icon': 'fa fa-wrench',
                'color': '#2E8B57'
            },
            {
                'name': 'Soft Skills',
                'code': 'soft_skills', 
                'icon': 'fa fa-users',
                'color': '#4169E1'
            },
            {
                'name': 'Compliance & Safety',
                'code': 'compliance',
                'icon': 'fa fa-shield',
                'color': '#DC143C'
            },
            {
                'name': 'Leadership Development',
                'code': 'leadership',
                'icon': 'fa fa-star',
                'color': '#FF8C00'
            }
        ]
        
        for cat_data in categories:
            existing = self.env['lms.category'].search([('name', '=', cat_data['name'])])
            if not existing:
                self.env['lms.category'].create(cat_data)
    
    @api.model
    def create_default_badges(self):
        """Create default badges"""
        badges = [
            {
                'name': 'First Course Completed',
                'code': 'first_course',
                'badge_type': 'course_completion',
                'description': 'Awarded for completing your first course',
                'points_awarded': 25,
                'color': '#4CAF50'
            },
            {
                'name': 'Fast Learner',
                'code': 'fast_learner',
                'badge_type': 'special',
                'description': 'Completed a course in record time',
                'points_awarded': 30,
                'color': '#FF9800'
            },
            {
                'name': 'Perfect Score',
                'code': 'perfect_score',
                'badge_type': 'assessment_excellence',
                'description': 'Achieved 100% on an assessment',
                'points_awarded': 50,
                'color': '#9C27B0'
            },
            {
                'name': 'Odoo Expert',
                'code': 'odoo_expert',
                'badge_type': 'competency_achievement',
                'description': 'Mastered all Odoo system modules',
                'points_awarded': 100,
                'color': '#875A7B'
            },
            {
                'name': 'Learning Streak',
                'code': 'learning_streak',
                'badge_type': 'participation',
                'description': 'Learned something new for 7 consecutive days',
                'points_awarded': 40,
                'color': '#03A9F4'
            }
        ]
        
        for badge_data in badges:
            existing = self.env['lms.badge'].search([('code', '=', badge_data['code'])])
            if not existing:
                self.env['lms.badge'].create(badge_data)
    
    @api.model
    def create_default_competencies(self):
        """Create default competencies for bengkel context"""
        competencies = [
            {
                'name': 'Odoo Sales Management',
                'code': 'odoo_sales',
                'category': 'system',
                'description': 'Proficient in using Odoo Sales module',
                'min_score_required': 80.0,
                'points_awarded': 75
            },
            {
                'name': 'Odoo Inventory Management', 
                'code': 'odoo_inventory',
                'category': 'system',
                'description': 'Proficient in using Odoo Inventory module',
                'min_score_required': 80.0,
                'points_awarded': 75
            },
            {
                'name': 'Customer Service Excellence',
                'code': 'customer_service',
                'category': 'soft_skill',
                'description': 'Excellence in customer service delivery',
                'min_score_required': 85.0,
                'points_awarded': 60
            },
            {
                'name': 'Workshop Safety Compliance',
                'code': 'safety_compliance',
                'category': 'compliance',
                'description': 'Complete understanding of workshop safety protocols',
                'min_score_required': 90.0,
                'points_awarded': 100,
                'requires_renewal': True,
                'validity_months': 6
            },
            {
                'name': 'Team Leadership',
                'code': 'team_leadership',
                'category': 'leadership', 
                'description': 'Demonstrated team leadership capabilities',
                'min_score_required': 80.0,
                'points_awarded': 120
            }
        ]
        
        for comp_data in competencies:
            existing = self.env['lms.competency'].search([('code', '=', comp_data['code'])])
            if not existing:
                self.env['lms.competency'].create(comp_data)
    
    @api.model
    def setup_default_learning_paths(self):
        """Create default learning paths for different roles"""
        
        # Get categories and courses (assuming they exist)
        odoo_category = self.env['lms.category'].search([('name', '=', 'Odoo System Training')], limit=1)
        
        learning_paths = [
            {
                'name': 'New Employee Onboarding',
                'code': 'new_employee',
                'description': 'Complete onboarding program for new employees',
                'difficulty_level': 'beginner',
                'completion_points': 200,
                'is_mandatory': True
            },
            {
                'name': 'Service Advisor Excellence Program',
                'code': 'service_advisor',
                'description': 'Comprehensive training for Service Advisors',
                'difficulty_level': 'intermediate',
                'completion_points': 300
            },
            {
                'name': 'Mechanic Technical Certification',
                'code': 'mechanic_cert',
                'description': 'Technical certification program for mechanics',
                'difficulty_level': 'advanced',
                'completion_points': 400
            },
            {
                'name': 'Odoo Power User Track',
                'code': 'odoo_power_user',
                'description': 'Advanced Odoo system usage training',
                'difficulty_level': 'advanced',
                'completion_points': 350
            }
        ]
        
        for path_data in learning_paths:
            existing = self.env['lms.learning.path'].search([('code', '=', path_data['code'])])
            if not existing:
                self.env['lms.learning.path'].create(path_data)
    
    @api.model
    def initialize_lms_data(self):
        """Initialize all default LMS data"""
        try:
            self.create_default_categories()
            self.create_default_badges()
            self.create_default_competencies()
            self.setup_default_learning_paths()
            
            # Set default system parameters
            self.env['lms.system.parameter'].set_param(
                'lms.initialized', 'true', 'LMS system initialization status'
            )
            
            return True
        except Exception as e:
            _logger.error(f"Error initializing LMS data: {e}")
            return False

# Model untuk Dashboard dan Reporting
class LMSDashboard(models.Model):
    _name = 'lms.dashboard'
    _description = 'LMS Dashboard Data'
    
    @api.model
    def get_user_dashboard_data(self, user_id=None):
        """Get dashboard data for specific user"""
        if not user_id:
            user_id = self.env.user.id
        
        user = self.env['res.users'].browse(user_id)
        employee = user.employee_id
        
        if not employee:
            return {'error': 'No employee record found'}
        
        # Get enrollments
        enrollments = employee.lms_enrollments
        active_enrollments = enrollments.filtered(lambda e: e.status == 'in_progress')
        completed_enrollments = enrollments.filtered(lambda e: e.status == 'completed')
        
        # Get competencies
        competencies = employee.lms_competencies
        achieved_competencies = competencies.filtered(lambda c: c.status == 'achieved')
        
        # Get recent activity
        recent_progress = self.env['lms.progress'].search([
            ('user_id', '=', user_id),
            ('last_accessed', '!=', False)
        ], order='last_accessed desc', limit=5)
        
        return {
            'user': {
                'name': user.name,
                'karma': user.karma,
                # 'lms_level': user.lms_level,
                'learning_streak_days': user.learning_streak_days,
                'avatar': user.image_128
            },
            'stats': {
                'active_courses': len(active_enrollments),
                'completed_courses': len(completed_enrollments),
                'total_learning_hours': employee.total_learning_hours,
                'competencies_achieved': len(achieved_competencies),
                'badges_earned': len(employee.lms_badges),
                'average_score': employee.average_assessment_score,
                'compliance_rate': employee.mandatory_training_compliance
            },
            'recent_activity': [{
                'module_name': p.module_id.name,
                'course_name': p.course_id.name,
                'last_accessed': p.last_accessed,
                'completion_percentage': p.completion_percentage,
                'status': p.status
            } for p in recent_progress],
            'pending_assessments': self._get_pending_assessments(user_id),
            'recommended_courses': self._get_recommended_courses(user_id)
        }
    
    @api.model
    def get_manager_dashboard_data(self, manager_id=None):
        """Get dashboard data for managers"""
        if not manager_id:
            manager_id = self.env.user.id
        
        manager = self.env['res.users'].browse(manager_id)
        
        # Get team members (employees reporting to this manager)
        team_employees = self.env['hr.employee'].search([
            ('parent_id', '=', manager.employee_id.id)
        ])
        
        if not team_employees:
            # If no direct reports, show company-wide data for HR managers
            team_employees = self.env['hr.employee'].search([])
        
        team_stats = []
        for employee in team_employees:
            team_stats.append({
                'employee_id': employee.id,
                'name': employee.name,
                'job_title': employee.job_id.name if employee.job_id else '',
                'completed_courses': employee.total_courses_completed,
                'learning_hours': employee.total_learning_hours,
                'compliance_rate': employee.mandatory_training_compliance,
                'overdue_trainings': employee.overdue_trainings,
                'last_activity': self._get_last_learning_activity(employee.user_id.id)
            })
        
        return {
            'team_overview': {
                'total_team_members': len(team_employees),
                'average_compliance': sum(emp.mandatory_training_compliance for emp in team_employees) / len(team_employees) if team_employees else 0,
                'total_overdue': sum(emp.overdue_trainings for emp in team_employees),
                'active_learners': len([emp for emp in team_employees if emp.total_courses_completed > 0])
            },
            'team_stats': team_stats,
            'trending_courses': self._get_trending_courses(),
            'completion_trends': self._get_completion_trends()
        }
    
    def _get_pending_assessments(self, user_id):
        """Get pending assessments for user"""
        # Get in-progress enrollments with assessment modules
        enrollments = self.env['lms.enrollment'].search([
            ('user_id', '=', user_id),
            ('status', '=', 'in_progress')
        ])
        
        pending = []
        for enrollment in enrollments:
            for module in enrollment.course_id.module_ids:
                if module.content_type == 'assessment':
                    # Check if already completed
                    progress = self.env['lms.progress'].search([
                        ('enrollment_id', '=', enrollment.id),
                        ('module_id', '=', module.id)
                    ], limit=1)
                    
                    if not progress or progress.status != 'completed':
                        pending.append({
                            'course_name': enrollment.course_id.name,
                            'module_name': module.name,
                            'enrollment_id': enrollment.id,
                            'module_id': module.id
                        })
        
        return pending
    
    def _get_recommended_courses(self, user_id):
        """Get recommended courses for user"""
        user = self.env['res.users'].browse(user_id)
        employee = user.employee_id
        
        if not employee or not employee.job_id:
            return []
        
        # Get courses for user's job position that they haven't enrolled in
        job_courses = self.env['lms.course'].search([
            ('target_role_ids', 'in', [employee.job_id.id]),
            ('is_published', '=', True)
        ])
        
        enrolled_courses = employee.lms_enrollments.mapped('course_id')
        recommended = job_courses - enrolled_courses
        
        return [{
            'id': course.id,
            'name': course.name,
            'description': course.short_description,
            'duration_hours': course.duration_hours,
            'difficulty_level': course.difficulty_level,
            'completion_points': course.completion_points
        } for course in recommended[:5]]  # Limit to 5 recommendations
    
    def _get_last_learning_activity(self, user_id):
        """Get last learning activity date for user"""
        last_progress = self.env['lms.progress'].search([
            ('user_id', '=', user_id),
            ('last_accessed', '!=', False)
        ], order='last_accessed desc', limit=1)
        
        return last_progress.last_accessed if last_progress else None
    
    def _get_trending_courses(self):
        """Get trending courses based on recent enrollments"""
        # Get courses with most enrollments in last 30 days
        thirty_days_ago = fields.Date.today() - timedelta(days=30)
        
        recent_enrollments = self.env['lms.enrollment'].search([
            ('enrollment_date', '>=', thirty_days_ago)
        ])
        
        course_counts = {}
        for enrollment in recent_enrollments:
            course_id = enrollment.course_id.id
            course_counts[course_id] = course_counts.get(course_id, 0) + 1
        
        # Sort by enrollment count
        sorted_courses = sorted(course_counts.items(), key=lambda x: x[1], reverse=True)
        
        trending = []
        for course_id, count in sorted_courses[:5]:
            course = self.env['lms.course'].browse(course_id)
            trending.append({
                'id': course.id,
                'name': course.name,
                'enrollment_count': count,
                'completion_rate': course.completion_rate
            })
        
        return trending
    
    def _get_completion_trends(self):
        """Get completion trends over time"""
        # Get completion data for last 6 months
        trends = []
        for i in range(6):
            month_start = (fields.Date.today().replace(day=1) - timedelta(days=30*i))
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            completions = self.env['lms.enrollment'].search_count([
                ('completion_date', '>=', month_start),
                ('completion_date', '<=', month_end),
                ('status', '=', 'completed')
            ])
            
            trends.append({
                'month': month_start.strftime('%Y-%m'),
                'completions': completions
            })
        
        return list(reversed(trends))