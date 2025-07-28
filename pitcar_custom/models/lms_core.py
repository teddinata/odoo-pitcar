# models/lms_core.py
from odoo import models, fields, api, _
from datetime import datetime, timedelta
import logging


_logger = logging.getLogger(__name__)

class LMSCategory(models.Model):
    """Kategori untuk mengelompokkan course"""
    _name = 'lms.category'
    _description = 'LMS Course Category'
    _order = 'sequence, name'
    _parent_store = True
    
    name = fields.Char('Category Name', required=True, translate=True)
    parent_id = fields.Many2one('lms.category', string='Parent Category', ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('lms.category', 'parent_id', string='Child Categories')
    color = fields.Integer('Color', default=1)
    icon = fields.Char('Icon Class', help='CSS icon class for UI display')
    description = fields.Text('Description', translate=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Stats fields
    course_count = fields.Integer('Course Count', compute='_compute_course_count')
    
    @api.depends('child_ids')
    def _compute_course_count(self):
        for category in self:
            # Count courses in this category and all child categories
            categories = category.search([('id', 'child_of', category.id)])
            category.course_count = self.env['lms.course'].search_count([
                ('category_id', 'in', categories.ids)
            ])
    
    def action_view_category_courses(self):
        """View courses in this category"""
        self.ensure_one()
        return {
            'name': f'Courses - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.course',
            'view_mode': 'kanban,tree,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id}
        }

class LMSCourse(models.Model):
    """Master data untuk course/kursus"""
    _name = 'lms.course'
    _description = 'LMS Course'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Course Name', required=True, tracking=True, translate=True)
    code = fields.Char('Course Code', required=True, copy=False, tracking=True)
    category_id = fields.Many2one('lms.category', string='Category', required=True)
    description = fields.Html('Description', translate=True)
    short_description = fields.Text('Short Description', translate=True)
    
    # Course Properties
    duration_hours = fields.Float('Estimated Duration (Hours)', default=1.0)
    difficulty_level = fields.Selection([
        ('basic', 'Basic'),
        ('intermediate', 'Intermediate'), 
        ('advanced', 'Advanced')
    ], string='Difficulty Level', default='basic', required=True)
    
    # Prerequisites & Requirements
    prerequisite_course_ids = fields.Many2many(
        'lms.course',
        'course_prerequisite_rel',
        'course_id', 'prerequisite_id',
        string='Prerequisite Courses'
    )
    target_role_ids = fields.Many2many(
        'hr.job',
        string='Target Job Positions',
        help='Job positions that should take this course'
    )
    
    # Course Settings
    is_mandatory = fields.Boolean('Mandatory Course', default=False, tracking=True)
    is_published = fields.Boolean('Published', default=False, tracking=True)
    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer('Sequence', default=10)
    
    # Gamification Settings
    completion_points = fields.Integer('Completion Points', default=10, 
                                     help='Points awarded upon course completion')
    certificate_template = fields.Html('Certificate Template')
    
    # Course Content
    module_ids = fields.One2many('lms.module', 'course_id', string='Modules')
    module_count = fields.Integer('Module Count', compute='_compute_module_count')
    
    # Enrollment & Progress
    enrollment_ids = fields.One2many('lms.enrollment', 'course_id', string='Enrollments')
    enrollment_count = fields.Integer('Enrolled Users', compute='_compute_enrollment_stats')
    completion_rate = fields.Float('Completion Rate (%)', compute='_compute_enrollment_stats')
    average_score = fields.Float('Average Score', compute='_compute_enrollment_stats')
    
    # Timestamps
    create_date = fields.Datetime('Created Date', readonly=True)
    write_date = fields.Datetime('Last Updated', readonly=True)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Course code must be unique!'),
    ]
    
    @api.depends('module_ids')
    def _compute_module_count(self):
        for course in self:
            course.module_count = len(course.module_ids)
    
    @api.depends('enrollment_ids', 'enrollment_ids.status', 'enrollment_ids.final_score')
    def _compute_enrollment_stats(self):
        for course in self:
            enrollments = course.enrollment_ids
            course.enrollment_count = len(enrollments)
            
            if enrollments:
                completed = enrollments.filtered(lambda e: e.status == 'completed')
                course.completion_rate = (len(completed) / len(enrollments)) * 100
                
                scores = completed.mapped('final_score')
                course.average_score = sum(scores) / len(scores) if scores else 0
            else:
                course.completion_rate = 0
                course.average_score = 0
    
    def action_publish(self):
        """Publish course untuk mulai enrollment"""
        self.is_published = True
        self.message_post(body="Course has been published and is now available for enrollment.")
    
    def action_unpublish(self):
        """Unpublish course"""
        self.is_published = False
        self.message_post(body="Course has been unpublished.")
    
    def action_view_course_enrollments(self):
        """View enrollments for this course"""
        self.ensure_one()
        return {
            'name': f'Enrollments - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.enrollment',
            'view_mode': 'tree,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id}
        }
    
    def action_view_course_modules(self):
        """View modules for this course"""
        self.ensure_one()
        return {
            'name': f'Modules - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.module',
            'view_mode': 'tree,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id}
        }


class LMSModule(models.Model):
    """Sub-module dalam course (seperti chapter)"""
    _name = 'lms.module'
    _description = 'LMS Course Module'
    _order = 'course_id, sequence'
    
    name = fields.Char('Module Name', required=True, translate=True)
    course_id = fields.Many2one('lms.course', string='Course', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    
    # Content
    description = fields.Html('Description', translate=True)
    content_type = fields.Selection([
        ('video', 'Video'),
        ('document', 'Document/PDF'),
        ('interactive', 'Interactive Content'),
        ('assessment', 'Assessment/Quiz'),
        ('external_link', 'External Link')
    ], string='Content Type', required=True, default='document')
    
    # Content Files/Links
    content_file = fields.Binary('Content File', attachment=True)
    content_filename = fields.Char('Filename')
    content_url = fields.Char('Content URL', help='External link or video URL')
    
    # Module Properties
    duration_minutes = fields.Integer('Duration (Minutes)', default=15)
    is_mandatory = fields.Boolean('Mandatory Module', default=True)
    learning_objectives = fields.Text('Learning Objectives', translate=True)
    
    # Assessment Properties (jika content_type = assessment)
    is_assessment = fields.Boolean('Is Assessment', compute='_compute_is_assessment', store=True)
    passing_score = fields.Float('Passing Score (%)', default=70.0,
                                help='Minimum score required to pass this assessment')
    max_attempts = fields.Integer('Maximum Attempts', default=3)
    time_limit_minutes = fields.Integer('Time Limit (Minutes)', default=0,
                                       help='0 means no time limit')
    
    # Status
    active = fields.Boolean('Active', default=True)
    
    @api.depends('content_type')
    def _compute_is_assessment(self):
        for module in self:
            module.is_assessment = module.content_type == 'assessment'


class LMSEnrollment(models.Model):
    """Record enrollment user ke course"""
    _name = 'lms.enrollment'
    _description = 'LMS Course Enrollment'
    _rec_name = 'display_name'
    
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', 
                                 related='user_id.employee_id', store=True)
    course_id = fields.Many2one('lms.course', string='Course', required=True, ondelete='cascade')
    
    # Enrollment Info
    enrollment_date = fields.Datetime('Enrollment Date', default=fields.Datetime.now)
    enrolled_by = fields.Many2one('res.users', string='Enrolled By', 
                                 default=lambda self: self.env.user)
    enrollment_type = fields.Selection([
        ('self', 'Self Enrollment'),
        ('mandatory', 'Mandatory Assignment'),
        ('manager', 'Manager Assignment'),
        ('bulk', 'Bulk Assignment')
    ], string='Enrollment Type', default='self')
    
    # Progress Tracking
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='not_started', tracking=True)
    
    progress_percentage = fields.Float('Progress (%)', compute='_compute_progress', store=True)
    start_date = fields.Datetime('Start Date')
    completion_date = fields.Datetime('Completion Date')
    
    # Scoring
    final_score = fields.Float('Final Score (%)', default=0.0)
    passed = fields.Boolean('Passed', compute='_compute_passed', store=True)
    
    # Gamification
    points_earned = fields.Integer('Points Earned', default=0)
    certificate_generated = fields.Boolean('Certificate Generated', default=False)
    
    # Related Progress Records
    progress_ids = fields.One2many('lms.progress', 'enrollment_id', string='Module Progress')
    
    # Display name for better UX
    display_name = fields.Char('Display Name', compute='_compute_display_name')
    
    _sql_constraints = [
        ('user_course_unique', 'unique(user_id, course_id)', 
         'User can only be enrolled once per course!'),
    ]
    
    @api.depends('user_id', 'course_id')
    def _compute_display_name(self):
        for enrollment in self:
            enrollment.display_name = f"{enrollment.user_id.name} - {enrollment.course_id.name}"
    
    @api.depends('progress_ids', 'progress_ids.completion_percentage')
    def _compute_progress(self):
        for enrollment in self:
            if enrollment.progress_ids:
                total_progress = sum(enrollment.progress_ids.mapped('completion_percentage'))
                enrollment.progress_percentage = total_progress / len(enrollment.progress_ids)
            else:
                enrollment.progress_percentage = 0.0
            
            # Update status based on progress
            if enrollment.progress_percentage == 100:
                if enrollment.status != 'completed':
                    enrollment._handle_completion()
            elif enrollment.progress_percentage > 0:
                if enrollment.status == 'not_started':
                    enrollment.status = 'in_progress'
                    enrollment.start_date = fields.Datetime.now()
    
    @api.depends('final_score', 'course_id')
    def _compute_passed(self):
        for enrollment in self:
            # Minimum passing score could be configured per course
            min_score = 70.0  # Default minimum score
            enrollment.passed = enrollment.final_score >= min_score
    
    def _handle_completion(self):
        """Handle course completion logic"""
        self.ensure_one()
        if self.status != 'completed':
            self.status = 'completed'
            self.completion_date = fields.Datetime.now()
            
            # Award points
            if not self.points_earned:
                self.points_earned = self.course_id.completion_points
                # Update user karma
                self.user_id.karma += self.points_earned
            
            # Log completion
            _logger.info(f"User {self.user_id.name} completed course {self.course_id.name}")
    
    def action_start_course(self):
        """Start the course - create progress records for all modules"""
        self.ensure_one()
        if self.status == 'not_started':
            self.status = 'in_progress'
            self.start_date = fields.Datetime.now()
            
            # Create progress records for all modules
            for module in self.course_id.module_ids:
                self.env['lms.progress'].create({
                    'enrollment_id': self.id,
                    'module_id': module.id,
                    'status': 'not_started'
                })
    
    def action_reset_progress(self):
        """Reset course progress"""
        self.ensure_one()
        self.progress_ids.unlink()
        self.status = 'not_started'
        self.start_date = False
        self.completion_date = False
        self.final_score = 0.0
        self.points_earned = 0


class LMSProgress(models.Model):
    """Progress tracking per module per user"""
    _name = 'lms.progress'
    _description = 'LMS Module Progress'
    _rec_name = 'display_name'
    
    enrollment_id = fields.Many2one('lms.enrollment', string='Enrollment', 
                                   required=True, ondelete='cascade')
    module_id = fields.Many2one('lms.module', string='Module', required=True)
    user_id = fields.Many2one('res.users', related='enrollment_id.user_id', store=True)
    course_id = fields.Many2one('lms.course', related='enrollment_id.course_id', store=True)
    
    # Progress Status
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped')
    ], string='Status', default='not_started')
    
    completion_percentage = fields.Float('Completion %', default=0.0)
    
    # Timestamps
    start_date = fields.Datetime('Start Date')
    completion_date = fields.Datetime('Completion Date')
    last_accessed = fields.Datetime('Last Accessed')
    time_spent_minutes = fields.Integer('Time Spent (Minutes)', default=0)
    
    # Assessment Results (for assessment modules)
    attempts = fields.Integer('Attempts', default=0)
    best_score = fields.Float('Best Score', default=0.0)
    last_score = fields.Float('Last Score', default=0.0)
    
    display_name = fields.Char('Display Name', compute='_compute_display_name')
    
    @api.depends('user_id', 'module_id')
    def _compute_display_name(self):
        for progress in self:
            progress.display_name = f"{progress.user_id.name} - {progress.module_id.name}"
    
    def action_mark_completed(self):
        """Mark module as completed"""
        self.ensure_one()
        self.status = 'completed'
        self.completion_percentage = 100.0
        self.completion_date = fields.Datetime.now()
        
        # Trigger enrollment progress recalculation
        self.enrollment_id._compute_progress()
    
    def action_start_module(self):
        """Start module"""
        self.ensure_one()
        if self.status == 'not_started':
            self.status = 'in_progress'
            self.start_date = fields.Datetime.now()
        self.last_accessed = fields.Datetime.now()
        
    module_id = fields.Many2one('lms.module', string='Module', required=True)
    user_id = fields.Many2one('res.users', related='enrollment_id.user_id', store=True)
    course_id = fields.Many2one('lms.course', related='enrollment_id.course_id', store=True)
    
    # Progress Status
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped')
    ], string='Status', default='not_started')
    
    completion_percentage = fields.Float('Completion %', default=0.0)
    
    # Timestamps
    start_date = fields.Datetime('Start Date')
    completion_date = fields.Datetime('Completion Date')
    last_accessed = fields.Datetime('Last Accessed')
    time_spent_minutes = fields.Integer('Time Spent (Minutes)', default=0)
    
    # Assessment Results (for assessment modules)
    attempts = fields.Integer('Attempts', default=0)
    best_score = fields.Float('Best Score', default=0.0)
    last_score = fields.Float('Last Score', default=0.0)
    
    display_name = fields.Char('Display Name', compute='_compute_display_name')
    
    @api.depends('user_id', 'module_id')
    def _compute_display_name(self):
        for progress in self:
            progress.display_name = f"{progress.user_id.name} - {progress.module_id.name}"
    
    def action_mark_completed(self):
        """Mark module as completed"""
        self.ensure_one()
        self.status = 'completed'
        self.completion_percentage = 100.0
        self.completion_date = fields.Datetime.now()
        
        # Trigger enrollment progress recalculation
        self.enrollment_id._compute_progress()
    
    def action_start_module(self):
        """Start module"""
        self.ensure_one()
        if self.status == 'not_started':
            self.status = 'in_progress'
            self.start_date = fields.Datetime.now()
        self.last_accessed = fields.Datetime.now()