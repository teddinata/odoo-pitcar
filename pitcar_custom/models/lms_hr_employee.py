# models/lms_hr_employee.py - Update dari file yang sudah ada di documents
from odoo import models, fields, api, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    # LMS Related Fields - safely defined
    lms_enrollments = fields.One2many('lms.enrollment', 'employee_id', string='LMS Enrollments')
    lms_competencies = fields.One2many('lms.user.competency', 'employee_id', string='Competencies')
    lms_badges = fields.One2many('lms.user.badge', 'employee_id', string='Badges')
    lms_path_enrollments = fields.One2many('lms.path.enrollment', 'employee_id', string='Learning Paths')
    
    # Learning Statistics - computed fields yang safe
    total_courses_completed = fields.Integer('Courses Completed', compute='_compute_lms_stats')
    total_learning_hours = fields.Float('Learning Hours', compute='_compute_lms_stats')
    average_assessment_score = fields.Float('Average Score (%)', compute='_compute_lms_stats')
    competencies_achieved = fields.Integer('Competencies Achieved', compute='_compute_lms_stats')
    badges_earned = fields.Integer('Badges Earned', compute='_compute_lms_stats')
    
    # Learning Profile - simple fields
    learning_style = fields.Selection([
        ('visual', 'Visual Learner'),
        ('auditory', 'Auditory Learner'),
        ('kinesthetic', 'Kinesthetic Learner'),
        ('reading', 'Reading/Writing Learner')
    ], string='Learning Style')
    
    preferred_learning_time = fields.Selection([
        ('morning', 'Morning (6-12)'),
        ('afternoon', 'Afternoon (12-18)'),
        ('evening', 'Evening (18-24)')
    ], string='Preferred Learning Time')
    
    # Mandatory Training Status
    mandatory_training_compliance = fields.Float('Mandatory Training Compliance (%)', 
                                                compute='_compute_compliance')
    overdue_trainings = fields.Integer('Overdue Trainings', compute='_compute_compliance')
    
    @api.depends('lms_enrollments', 'lms_enrollments.status', 'lms_enrollments.final_score',
                 'lms_competencies', 'lms_badges')
    def _compute_lms_stats(self):
        for employee in self:
            try:
                completed_enrollments = employee.lms_enrollments.filtered(lambda e: e.status == 'completed')
                
                employee.total_courses_completed = len(completed_enrollments)
                employee.total_learning_hours = sum(completed_enrollments.mapped('course_id.duration_hours'))
                
                if completed_enrollments:
                    scores = completed_enrollments.mapped('final_score')
                    employee.average_assessment_score = sum(scores) / len(scores) if scores else 0
                else:
                    employee.average_assessment_score = 0
                
                employee.competencies_achieved = len(employee.lms_competencies.filtered(
                    lambda c: c.status == 'achieved'
                ))
                employee.badges_earned = len(employee.lms_badges)
            except Exception as e:
                _logger.error(f"Error computing LMS stats for employee {employee.id}: {e}")
                # Set safe defaults
                employee.total_courses_completed = 0
                employee.total_learning_hours = 0
                employee.average_assessment_score = 0
                employee.competencies_achieved = 0
                employee.badges_earned = 0
    
    @api.depends('lms_enrollments', 'job_id')
    def _compute_compliance(self):
        for employee in self:
            try:
                if not employee.job_id:
                    employee.mandatory_training_compliance = 100
                    employee.overdue_trainings = 0
                    continue
                
                # Get mandatory courses for this job position
                mandatory_courses = self.env['lms.course'].search([
                    ('is_mandatory', '=', True),
                    ('target_role_ids', 'in', [employee.job_id.id])
                ])
                
                if not mandatory_courses:
                    employee.mandatory_training_compliance = 100
                    employee.overdue_trainings = 0
                    continue
                
                # Check completion status
                completed_mandatory = employee.lms_enrollments.filtered(
                    lambda e: e.course_id.id in mandatory_courses.ids and e.status == 'completed'
                )
                
                employee.mandatory_training_compliance = (
                    len(completed_mandatory) / len(mandatory_courses) * 100
                )
                employee.overdue_trainings = len(mandatory_courses) - len(completed_mandatory)
            except Exception as e:
                _logger.error(f"Error computing compliance for employee {employee.id}: {e}")
                employee.mandatory_training_compliance = 100
                employee.overdue_trainings = 0
    
    def action_auto_enroll_mandatory_courses(self):
        """Auto-enroll employee to mandatory courses based on job position"""
        self.ensure_one()
        
        try:
            if not self.job_id or not self.user_id:
                return 0
            
            # Get mandatory courses for this position
            mandatory_courses = self.env['lms.course'].search([
                ('is_mandatory', '=', True),
                ('target_role_ids', 'in', [self.job_id.id]),
                ('is_published', '=', True)
            ])
            
            # Check existing enrollments
            existing_enrollments = self.lms_enrollments.mapped('course_id')
            courses_to_enroll = mandatory_courses - existing_enrollments
            
            enrolled_count = 0
            for course in courses_to_enroll:
                try:
                    self.env['lms.enrollment'].create({
                        'user_id': self.user_id.id,
                        'course_id': course.id,
                        'enrollment_type': 'mandatory',
                        'enrolled_by': self.env.user.id
                    })
                    enrolled_count += 1
                except Exception as e:
                    _logger.error(f"Error enrolling employee {self.id} in course {course.id}: {e}")
            
            return enrolled_count
        except Exception as e:
            _logger.error(f"Error in auto-enroll for employee {self.id}: {e}")
            return 0
    
    def action_view_learning_dashboard(self):
        """Open employee learning dashboard"""
        return {
            'name': f'Learning Dashboard - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.employee.dashboard',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_employee_id': self.id}
        }

class HrJob(models.Model):
    _inherit = 'hr.job'
    
    # LMS Integration - simple Many2many fields
    required_course_ids = fields.Many2many('lms.course', string='Required Courses')
    required_competency_ids = fields.Many2many('lms.competency', string='Required Competencies')
    learning_path_id = fields.Many2one('lms.learning.path', string='Default Learning Path')
    
    # Training Requirements
    onboarding_duration_days = fields.Integer('Onboarding Duration (Days)', default=30)
    mandatory_refresh_months = fields.Integer('Mandatory Training Refresh (Months)', default=12)
    
    def action_bulk_enroll_employees(self):
        """Bulk enroll all employees in this position to required courses"""
        try:
            employees = self.env['hr.employee'].search([('job_id', '=', self.id)])
            
            enrolled_count = 0
            for employee in employees:
                enrolled_count += employee.action_auto_enroll_mandatory_courses()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Successfully enrolled {enrolled_count} courses to {len(employees)} employees',
                    'type': 'success'
                }
            }
        except Exception as e:
            _logger.error(f"Error in bulk enrollment: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error during bulk enrollment: {str(e)}',
                    'type': 'danger'
                }
            }

# Safe extension of res.users - HANYA method dan computed fields
class ResUsersLMSExtension(models.Model):
    _inherit = 'res.users'
    
    # NO STORED FIELDS - hanya computed/method fields yang safe
    
    def get_lms_level(self):
        """Get LMS level based on karma - method call, not field"""
        try:
            if self.karma >= 1000:
                return 'master'
            elif self.karma >= 500:
                return 'expert'
            elif self.karma >= 200:
                return 'achiever'
            elif self.karma >= 50:
                return 'learner'
            else:
                return 'novice'
        except:
            return 'novice'
    
    def get_active_enrollments_count(self):
        """Get count of active enrollments - method call"""
        try:
            if not self.employee_id:
                return 0
            enrollments = self.env['lms.enrollment'].search([
                ('user_id', '=', self.id),
                ('status', '=', 'in_progress')
            ])
            return len(enrollments)
        except:
            return 0
    
    def update_learning_streak(self):
        """Update learning streak - will be enhanced by separate LMS module"""
        try:
            # Basic implementation that doesn't depend on stored fields
            today = fields.Date.today()
            # Simple success return - detailed implementation can be added later
            return True
        except Exception as e:
            _logger.error(f"Error updating learning streak: {e}")
            return False
    
    def action_my_learning_dashboard(self):
        """Open user's personal learning dashboard"""
        return {
            'name': 'My Learning Dashboard', 
            'type': 'ir.actions.act_window',
            'res_model': 'lms.user.dashboard',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_user_id': self.id}
        }