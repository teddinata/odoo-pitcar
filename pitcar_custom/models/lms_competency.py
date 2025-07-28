# models/lms_competency.py
from odoo import models, fields, api, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class LMSCompetency(models.Model):
    """Master competency/skill yang dapat dicapai melalui learning"""
    _name = 'lms.competency'
    _description = 'LMS Competency'
    _order = 'category, name'
    
    name = fields.Char('Competency Name', required=True, translate=True)
    code = fields.Char('Competency Code', required=True)
    description = fields.Html('Description', translate=True)
    
    # Categorization
    category = fields.Selection([
        ('technical', 'Technical Skill'),
        ('soft_skill', 'Soft Skill'),
        ('system', 'System Knowledge'),
        ('compliance', 'Compliance & Safety'),
        ('leadership', 'Leadership')
    ], string='Category', required=True, default='technical')
    
    # Competency Levels
    proficiency_levels = fields.Selection([
        ('beginner', 'Beginner'),
        ('competent', 'Competent'), 
        ('proficient', 'Proficient'),
        ('expert', 'Expert'),
        ('master', 'Master')
    ], string='Max Proficiency Level', default='competent')
    
    # Requirements
    required_course_ids = fields.Many2many(
        'lms.course',
        'competency_course_rel',
        'competency_id', 'course_id',
        string='Required Courses'
    )
    prerequisite_competency_ids = fields.Many2many(
        'lms.competency',
        'competency_prerequisite_rel', 
        'competency_id', 'prerequisite_id',
        string='Prerequisite Competencies'
    )
    
    # Validation Criteria
    min_score_required = fields.Float('Minimum Score Required (%)', default=80.0)
    validity_months = fields.Integer('Validity Period (Months)', default=12,
                                   help='How long this competency remains valid')
    requires_renewal = fields.Boolean('Requires Renewal', default=False)
    
    # Gamification
    completion_badge = fields.Char('Badge Name', help='Badge awarded upon competency achievement')
    points_awarded = fields.Integer('Points Awarded', default=50)
    
    # Stats
    user_competency_ids = fields.One2many('lms.user.competency', 'competency_id', 
                                         string='User Competencies')
    achiever_count = fields.Integer('Total Achievers', compute='_compute_achiever_stats')
    average_score = fields.Float('Average Achievement Score', compute='_compute_achiever_stats')
    
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Competency code must be unique!'),
    ]
    
    @api.depends('user_competency_ids', 'user_competency_ids.status', 'user_competency_ids.current_score')
    def _compute_achiever_stats(self):
        for competency in self:
            achieved = competency.user_competency_ids.filtered(lambda uc: uc.status == 'achieved')
            competency.achiever_count = len(achieved)
            
            if achieved:
                competency.average_score = sum(achieved.mapped('current_score')) / len(achieved)
            else:
                competency.average_score = 0.0

    def action_view_competency_achievers(self):
        """View users who achieved this competency"""
        self.ensure_one()
        return {
            'name': f'Achievers - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.user.competency',
            'view_mode': 'tree,form',
            'domain': [('competency_id', '=', self.id)],
            'context': {'default_competency_id': self.id}
        }



class LMSUserCompetency(models.Model):
    """Tracking competency achievement per user"""
    _name = 'lms.user.competency'
    _description = 'User Competency Achievement'
    _rec_name = 'display_name'
    
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', related='user_id.employee_id', store=True)
    competency_id = fields.Many2one('lms.competency', string='Competency', 
                                   required=True, ondelete='cascade')
    
    # Achievement Status
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('achieved', 'Achieved'),
        ('expired', 'Expired'),
        ('renewal_required', 'Renewal Required')
    ], string='Status', default='not_started', tracking=True)
    
    # Scoring & Progress
    current_score = fields.Float('Current Score (%)', default=0.0)
    proficiency_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('competent', 'Competent'),
        ('proficient', 'Proficient'), 
        ('expert', 'Expert'),
        ('master', 'Master')
    ], string='Achieved Level')
    
    # Timestamps
    start_date = fields.Datetime('Start Date')
    achieved_date = fields.Datetime('Achievement Date')
    expiry_date = fields.Datetime('Expiry Date', compute='_compute_expiry_date', store=True)
    last_updated = fields.Datetime('Last Updated', default=fields.Datetime.now)
    
    # Progress Tracking
    completed_courses = fields.Integer('Completed Courses', compute='_compute_progress')
    required_courses = fields.Integer('Required Courses', compute='_compute_progress')
    progress_percentage = fields.Float('Progress (%)', compute='_compute_progress')
    
    # Validation & Certification
    validated_by = fields.Many2one('res.users', string='Validated By')
    validation_date = fields.Datetime('Validation Date')
    certificate_number = fields.Char('Certificate Number')
    
    display_name = fields.Char('Display Name', compute='_compute_display_name')
    
    _sql_constraints = [
        ('user_competency_unique', 'unique(user_id, competency_id)',
         'User can only have one record per competency!'),
    ]
    
    @api.depends('user_id', 'competency_id')
    def _compute_display_name(self):
        for uc in self:
            uc.display_name = f"{uc.user_id.name} - {uc.competency_id.name}"
    
    @api.depends('achieved_date', 'competency_id.validity_months')
    def _compute_expiry_date(self):
        for uc in self:
            if uc.achieved_date and uc.competency_id.validity_months:
                uc.expiry_date = uc.achieved_date + timedelta(
                    days=uc.competency_id.validity_months * 30
                )
            else:
                uc.expiry_date = False
    
    @api.depends('user_id', 'competency_id.required_course_ids')
    def _compute_progress(self):
        for uc in self:
            required_courses = uc.competency_id.required_course_ids
            uc.required_courses = len(required_courses)
            
            if required_courses:
                # Count completed enrollments
                completed_enrollments = self.env['lms.enrollment'].search([
                    ('user_id', '=', uc.user_id.id),
                    ('course_id', 'in', required_courses.ids),
                    ('status', '=', 'completed')
                ])
                uc.completed_courses = len(completed_enrollments)
                uc.progress_percentage = (uc.completed_courses / uc.required_courses) * 100
            else:
                uc.completed_courses = 0
                uc.progress_percentage = 0
    
    def action_validate_competency(self):
        """Validate competency achievement"""
        self.ensure_one()
        
        # Check if all requirements are met
        if self.progress_percentage == 100 and self.current_score >= self.competency_id.min_score_required:
            self.status = 'achieved'
            self.achieved_date = fields.Datetime.now()
            self.validated_by = self.env.user
            self.validation_date = fields.Datetime.now()
            
            # Generate certificate number
            self.certificate_number = self._generate_certificate_number()
            
            # Award points and badge
            self.user_id.karma += self.competency_id.points_awarded
            
            # Log achievement
            _logger.info(f"User {self.user_id.name} achieved competency {self.competency_id.name}")
            
            return True
        return False
    
    def _generate_certificate_number(self):
        """Generate unique certificate number"""
        return f"CERT-{self.competency_id.code}-{self.user_id.id}-{datetime.now().strftime('%Y%m%d')}"


class LMSLearningPath(models.Model):
    """Predefined learning paths untuk roles tertentu"""
    _name = 'lms.learning.path'
    _description = 'Learning Path'
    _order = 'sequence, name'
    
    name = fields.Char('Path Name', required=True, translate=True)
    code = fields.Char('Path Code', required=True)
    description = fields.Html('Description', translate=True)
    
    # Target & Requirements
    target_role_ids = fields.Many2many('hr.job', string='Target Job Positions')
    target_department_ids = fields.Many2many('hr.department', string='Target Departments')
    
    # Path Content
    course_ids = fields.Many2many(
        'lms.course',
        'learning_path_course_rel',
        'path_id', 'course_id',
        string='Courses in Path'
    )
    competency_ids = fields.Many2many(
        'lms.competency',
        string='Target Competencies'
    )
    
    # Path Properties
    estimated_duration_hours = fields.Float('Estimated Duration (Hours)', compute='_compute_duration')
    difficulty_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced')
    ], string='Overall Difficulty', default='beginner')
    
    # Completion Requirements
    min_completion_percentage = fields.Float('Minimum Completion %', default=100.0)
    min_average_score = fields.Float('Minimum Average Score %', default=70.0)
    
    # Settings
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    is_mandatory = fields.Boolean('Mandatory Path', default=False)
    
    # Gamification
    completion_badge = fields.Char('Completion Badge')
    completion_points = fields.Integer('Completion Points', default=100)
    certificate_template = fields.Html('Certificate Template')
    
    # Stats
    enrollment_ids = fields.One2many('lms.path.enrollment', 'path_id', string='Enrollments')
    enrollment_count = fields.Integer('Total Enrollments', compute='_compute_stats')
    completion_rate = fields.Float('Completion Rate (%)', compute='_compute_stats')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Learning path code must be unique!'),
    ]
    
    @api.depends('course_ids.duration_hours')
    def _compute_duration(self):
        for path in self:
            path.estimated_duration_hours = sum(path.course_ids.mapped('duration_hours'))
    
    @api.depends('enrollment_ids', 'enrollment_ids.status')
    def _compute_stats(self):
        for path in self:
            enrollments = path.enrollment_ids
            path.enrollment_count = len(enrollments)
            
            if enrollments:
                completed = enrollments.filtered(lambda e: e.status == 'completed')
                path.completion_rate = (len(completed) / len(enrollments)) * 100
            else:
                path.completion_rate = 0

    def action_view_path_enrollments(self):
        """View enrollments for this learning path"""
        self.ensure_one()
        return {
            'name': f'Enrollments - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.path.enrollment',
            'view_mode': 'tree,form',
            'domain': [('path_id', '=', self.id)],
            'context': {'default_path_id': self.id}
        }


class LMSPathEnrollment(models.Model):
    """Enrollment ke learning path"""
    _name = 'lms.path.enrollment'
    _description = 'Learning Path Enrollment'
    _rec_name = 'display_name'
    
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', related='user_id.employee_id', store=True)
    path_id = fields.Many2one('lms.learning.path', string='Learning Path', 
                             required=True, ondelete='cascade')
    
    # Enrollment Info
    enrollment_date = fields.Datetime('Enrollment Date', default=fields.Datetime.now)
    enrolled_by = fields.Many2one('res.users', string='Enrolled By', default=lambda self: self.env.user)
    
    # Progress
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='not_started', tracking=True)
    
    progress_percentage = fields.Float('Progress (%)', compute='_compute_progress')
    completion_date = fields.Datetime('Completion Date')
    
    # Performance
    average_score = fields.Float('Average Score (%)', compute='_compute_performance')
    total_points_earned = fields.Integer('Total Points Earned', default=0)
    
    display_name = fields.Char('Display Name', compute='_compute_display_name')
    
    @api.depends('user_id', 'path_id')
    def _compute_display_name(self):
        for enrollment in self:
            enrollment.display_name = f"{enrollment.user_id.name} - {enrollment.path_id.name}"
    
    @api.depends('user_id', 'path_id.course_ids')
    def _compute_progress(self):
        for enrollment in self:
            if enrollment.path_id.course_ids:
                # Get course enrollments for this user in this path
                course_enrollments = self.env['lms.enrollment'].search([
                    ('user_id', '=', enrollment.user_id.id),
                    ('course_id', 'in', enrollment.path_id.course_ids.ids)
                ])
                
                if course_enrollments:
                    completed = course_enrollments.filtered(lambda e: e.status == 'completed')
                    enrollment.progress_percentage = (len(completed) / len(enrollment.path_id.course_ids)) * 100
                else:
                    enrollment.progress_percentage = 0
            else:
                enrollment.progress_percentage = 0
            
            # Update status based on progress
            if enrollment.progress_percentage == 100:
                if enrollment.status != 'completed':
                    enrollment._handle_completion()
            elif enrollment.progress_percentage > 0:
                if enrollment.status == 'not_started':
                    enrollment.status = 'in_progress'
    
    @api.depends('user_id', 'path_id.course_ids')
    def _compute_performance(self):
        for enrollment in self:
            course_enrollments = self.env['lms.enrollment'].search([
                ('user_id', '=', enrollment.user_id.id),
                ('course_id', 'in', enrollment.path_id.course_ids.ids),
                ('status', '=', 'completed')
            ])
            
            if course_enrollments:
                scores = course_enrollments.mapped('final_score')
                enrollment.average_score = sum(scores) / len(scores)
            else:
                enrollment.average_score = 0
    
    def _handle_completion(self):
        """Handle path completion"""
        self.ensure_one()
        if self.status != 'completed':
            self.status = 'completed'
            self.completion_date = fields.Datetime.now()
            
            # Award completion points
            if not self.total_points_earned:
                self.total_points_earned = self.path_id.completion_points
                self.user_id.karma += self.total_points_earned
            
            _logger.info(f"User {self.user_id.name} completed learning path {self.path_id.name}")


class LMSBadge(models.Model):
    """Badge system untuk gamification"""
    _name = 'lms.badge'
    _description = 'LMS Badge'
    
    name = fields.Char('Badge Name', required=True, translate=True)
    code = fields.Char('Badge Code', required=True)
    description = fields.Html('Description', translate=True)
    
    # Badge Properties
    badge_type = fields.Selection([
        ('course_completion', 'Course Completion'),
        ('competency_achievement', 'Competency Achievement'),
        ('path_completion', 'Learning Path Completion'),
        ('assessment_excellence', 'Assessment Excellence'),
        ('participation', 'Participation'),
        ('special', 'Special Achievement')
    ], string='Badge Type', required=True)
    
    # Visual
    icon = fields.Binary('Badge Icon', attachment=True)
    icon_filename = fields.Char('Icon Filename')
    color = fields.Char('Badge Color', default='#4CAF50')
    
    # Requirements
    points_required = fields.Integer('Points Required', default=0)
    courses_required = fields.Integer('Courses Required', default=0)
    min_score_required = fields.Float('Minimum Score Required (%)', default=0)
    
    # Awards
    points_awarded = fields.Integer('Points Awarded', default=10)
    
    # Stats
    user_badge_ids = fields.One2many('lms.user.badge', 'badge_id', string='User Badges')
    awarded_count = fields.Integer('Times Awarded', compute='_compute_awarded_count')
    
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Badge code must be unique!'),
    ]
    
    @api.depends('user_badge_ids')
    def _compute_awarded_count(self):
        for badge in self:
            badge.awarded_count = len(badge.user_badge_ids)

    def action_view_badge_recipients(self):
        """View users who earned this badge"""
        self.ensure_one()
        return {
            'name': f'Recipients - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.user.badge',
            'view_mode': 'tree,form',
            'domain': [('badge_id', '=', self.id)],
            'context': {'default_badge_id': self.id}
        }



class LMSUserBadge(models.Model):
    """Badge yang diraih user"""
    _name = 'lms.user.badge'
    _description = 'User Badge Achievement'
    _rec_name = 'display_name'
    
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', related='user_id.employee_id', store=True)
    badge_id = fields.Many2one('lms.badge', string='Badge', required=True, ondelete='cascade')
    
    # Achievement Info
    earned_date = fields.Datetime('Earned Date', default=fields.Datetime.now)
    awarded_by = fields.Many2one('res.users', string='Awarded By')
    reason = fields.Text('Reason/Achievement Details')
    
    # Related Records
    course_id = fields.Many2one('lms.course', string='Related Course')
    competency_id = fields.Many2one('lms.competency', string='Related Competency')
    path_id = fields.Many2one('lms.learning.path', string='Related Learning Path')
    
    display_name = fields.Char('Display Name', compute='_compute_display_name')
    
    _sql_constraints = [
        ('user_badge_unique', 'unique(user_id, badge_id, course_id, competency_id, path_id)',
         'User cannot earn the same badge multiple times for the same achievement!'),
    ]
    
    @api.depends('user_id', 'badge_id')
    def _compute_display_name(self):
        for ub in self:
            ub.display_name = f"{ub.user_id.name} - {ub.badge_id.name}"