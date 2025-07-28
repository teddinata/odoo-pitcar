# models/existing_model_updates.py
# Update untuk model yang sudah ada

from odoo import models, fields, api, _

class PitcarMechanicNew(models.Model):
    _inherit = 'pitcar.mechanic.new'
    
    # LMS Integration fields
    lms_competencies = fields.One2many(
        'lms.user.competency', 
        related='employee_id.lms_competencies',
        string='LMS Competencies'
    )
    
    technical_certification_level = fields.Selection([
        ('basic', 'Basic Mechanic'),
        ('intermediate', 'Skilled Mechanic'),
        ('advanced', 'Senior Mechanic'),
        ('expert', 'Master Mechanic')
    ], string='Technical Level', compute='_compute_technical_level', store=True)
    
    required_training_compliance = fields.Float(
        'Required Training Compliance (%)',
        related='employee_id.mandatory_training_compliance'
    )
    
    @api.depends('lms_competencies', 'lms_competencies.status')
    def _compute_technical_level(self):
        """Compute technical level based on achieved competencies"""
        for mechanic in self:
            achieved_comps = mechanic.lms_competencies.filtered(
                lambda c: c.status == 'achieved' and c.competency_id.category == 'technical'
            )
            
            comp_count = len(achieved_comps)
            if comp_count >= 10:
                mechanic.technical_certification_level = 'expert'
            elif comp_count >= 7:
                mechanic.technical_certification_level = 'advanced'
            elif comp_count >= 4:
                mechanic.technical_certification_level = 'intermediate'
            else:
                mechanic.technical_certification_level = 'basic'
    
    def action_view_lms_progress(self):
        """View mechanic's LMS progress"""
        return {
            'name': f'Learning Progress - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.enrollment',
            'view_mode': 'tree,form',
            'domain': [('user_id', '=', self.user_id.id)],
            'context': {'create': False}
        }

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Extend customer model untuk training purposes
    # Jika customer juga bisa akses LMS untuk training produk/layanan
    customer_training_level = fields.Selection([
        ('basic', 'Basic User'),
        ('intermediate', 'Intermediate User'),
        ('advanced', 'Advanced User')
    ], string='Training Level')
    
    last_training_date = fields.Date('Last Training Date')
    
    def action_customer_training_portal(self):
        """Redirect to customer training portal (if implemented)"""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/lms/customer/{self.id}',
            'target': 'new'
        }

# Model untuk menghubungkan LMS dengan Performance Management
class HrEmployeePerformance(models.Model):
    _name = 'hr.employee.performance'
    _description = 'Employee Performance Integration with LMS'
    
    employee_id = fields.Many2one('hr.employee', required=True)
    period_start = fields.Date('Period Start', required=True)
    period_end = fields.Date('Period End', required=True)
    
    # Learning KPIs
    learning_hours_target = fields.Float('Learning Hours Target', default=40.0)
    learning_hours_actual = fields.Float('Actual Learning Hours', compute='_compute_learning_kpis')
    learning_courses_target = fields.Integer('Courses Target', default=4)
    learning_courses_actual = fields.Integer('Actual Courses', compute='_compute_learning_kpis')
    
    # Performance Scores
    learning_performance_score = fields.Float('Learning Performance (%)', 
                                            compute='_compute_learning_performance')
    overall_performance_impact = fields.Float('Performance Impact from Learning (%)',
                                            help='Improvement in overall performance attributed to learning')
    
    @api.depends('employee_id', 'period_start', 'period_end')
    def _compute_learning_kpis(self):
        for record in self:
            # Get enrollments in the period
            enrollments = self.env['lms.enrollment'].search([
                ('user_id', '=', record.employee_id.user_id.id),
                ('enrollment_date', '>=', record.period_start),
                ('enrollment_date', '<=', record.period_end)
            ])
            
            completed = enrollments.filtered(lambda e: e.status == 'completed')
            record.learning_courses_actual = len(completed)
            record.learning_hours_actual = sum(completed.mapped('course_id.duration_hours'))
    
    @api.depends('learning_hours_actual', 'learning_hours_target', 
                 'learning_courses_actual', 'learning_courses_target')
    def _compute_learning_performance(self):
        for record in self:
            if record.learning_hours_target > 0 and record.learning_courses_target > 0:
                hours_score = min(record.learning_hours_actual / record.learning_hours_target * 100, 100)
                courses_score = min(record.learning_courses_actual / record.learning_courses_target * 100, 100)
                record.learning_performance_score = (hours_score + courses_score) / 2
            else:
                record.learning_performance_score = 0

# Model untuk LMS Analytics dan Reporting
class LMSAnalytics(models.Model):
    _name = 'lms.analytics'
    _description = 'LMS Analytics and Reporting'
    _auto = False
    
    # Dimensions
    user_id = fields.Many2one('res.users', string='User')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    course_id = fields.Many2one('lms.course', string='Course')
    department_id = fields.Many2one('hr.department', string='Department')
    job_id = fields.Many2one('hr.job', string='Job Position')
    
    # Date dimensions
    enrollment_date = fields.Date('Enrollment Date')
    completion_date = fields.Date('Completion Date')
    year = fields.Char('Year')
    month = fields.Char('Month')
    quarter = fields.Char('Quarter')
    
    # Measures
    total_enrollments = fields.Integer('Total Enrollments')
    completed_courses = fields.Integer('Completed Courses')
    total_learning_hours = fields.Float('Total Learning Hours')
    average_score = fields.Float('Average Score')
    completion_rate = fields.Float('Completion Rate')
    time_to_complete = fields.Float('Average Time to Complete (Days)')
    
    def init(self):
        """Create the view for analytics"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER() AS id,
                    e.user_id,
                    u.employee_id,
                    e.course_id,
                    emp.department_id,
                    emp.job_id,
                    DATE(e.enrollment_date) as enrollment_date,
                    DATE(e.completion_date) as completion_date,
                    EXTRACT(YEAR FROM e.enrollment_date) as year,
                    TO_CHAR(e.enrollment_date, 'YYYY-MM') as month,
                    CONCAT('Q', EXTRACT(QUARTER FROM e.enrollment_date), '-', EXTRACT(YEAR FROM e.enrollment_date)) as quarter,
                    COUNT(*) as total_enrollments,
                    COUNT(CASE WHEN e.status = 'completed' THEN 1 END) as completed_courses,
                    SUM(CASE WHEN e.status = 'completed' THEN c.duration_hours ELSE 0 END) as total_learning_hours,
                    AVG(CASE WHEN e.status = 'completed' THEN e.final_score ELSE NULL END) as average_score,
                    (COUNT(CASE WHEN e.status = 'completed' THEN 1 END) * 100.0 / COUNT(*)) as completion_rate,
                    AVG(CASE WHEN e.completion_date IS NOT NULL THEN 
                        EXTRACT(EPOCH FROM (e.completion_date - e.enrollment_date))/86400 
                        ELSE NULL END) as time_to_complete
                FROM lms_enrollment e
                JOIN res_users u ON e.user_id = u.id
                LEFT JOIN hr_employee emp ON u.employee_id = emp.id
                JOIN lms_course c ON e.course_id = c.id
                GROUP BY 
                    e.user_id, u.employee_id, e.course_id, emp.department_id, emp.job_id,
                    DATE(e.enrollment_date), DATE(e.completion_date),
                    EXTRACT(YEAR FROM e.enrollment_date),
                    TO_CHAR(e.enrollment_date, 'YYYY-MM'),
                    CONCAT('Q', EXTRACT(QUARTER FROM e.enrollment_date), '-', EXTRACT(YEAR FROM e.enrollment_date))
            )
        """ % self._table)

# Model untuk Automated Learning Path Assignment
class LMSLearningPathAssignment(models.Model):
    _name = 'lms.learning.path.assignment'
    _description = 'Automated Learning Path Assignment'
    
    name = fields.Char('Assignment Rule Name', required=True)
    active = fields.Boolean('Active', default=True)
    
    # Trigger Conditions
    trigger_on_hire = fields.Boolean('Trigger on New Hire', default=True)
    trigger_on_promotion = fields.Boolean('Trigger on Job Change', default=True)
    trigger_on_department_change = fields.Boolean('Trigger on Department Change', default=False)
    
    # Assignment Criteria
    job_ids = fields.Many2many('hr.job', string='Target Job Positions')
    department_ids = fields.Many2many('hr.department', string='Target Departments')
    learning_path_id = fields.Many2one('lms.learning.path', string='Learning Path to Assign', required=True)
    
    # Assignment Settings
    auto_start = fields.Boolean('Auto Start Courses', default=True,
                               help='Automatically start the first course in the path')
    deadline_days = fields.Integer('Completion Deadline (Days)', default=90,
                                  help='Days from assignment to complete the path')
    
    @api.model
    def process_assignment_rules(self, employee_id, trigger_type):
        """Process assignment rules for given employee and trigger"""
        employee = self.env['hr.employee'].browse(employee_id)
        
        rules = self.search([
            ('active', '=', True),
            (f'trigger_{trigger_type}', '=', True)
        ])
        
        for rule in rules:
            # Check if employee matches criteria
            job_match = not rule.job_ids or employee.job_id in rule.job_ids
            dept_match = not rule.department_ids or employee.department_id in rule.department_ids
            
            if job_match and dept_match:
                # Check if already enrolled in this path
                existing = self.env['lms.path.enrollment'].search([
                    ('user_id', '=', employee.user_id.id),
                    ('path_id', '=', rule.learning_path_id.id)
                ])
                
                if not existing:
                    # Create path enrollment
                    enrollment = self.env['lms.path.enrollment'].create({
                        'user_id': employee.user_id.id,
                        'path_id': rule.learning_path_id.id,
                        'enrolled_by': self.env.ref('base.user_admin').id,
                        'enrollment_date': fields.Datetime.now()
                    })
                    
                    # Auto-enroll in first course if enabled
                    if rule.auto_start and rule.learning_path_id.course_ids:
                        first_course = rule.learning_path_id.course_ids[0]
                        self.env['lms.enrollment'].create({
                            'user_id': employee.user_id.id,
                            'course_id': first_course.id,
                            'enrollment_type': 'mandatory'
                        })
                    
                    _logger.info(f"Auto-assigned learning path {rule.learning_path_id.name} to {employee.name}")

# Extend existing hr.employee create/write methods
class HrEmployeeExtended(models.Model):
    _inherit = 'hr.employee'
    
    @api.model
    def create(self, vals):
        """Override create to trigger LMS assignments"""
        employee = super().create(vals)
        
        # Trigger learning path assignment for new hire
        if employee.user_id:
            self.env['lms.learning.path.assignment'].process_assignment_rules(
                employee.id, 'on_hire'
            )
        
        return employee
    
    def write(self, vals):
        """Override write to trigger LMS assignments on job/department change"""
        result = super().write(vals)
        
        if 'job_id' in vals:
            for employee in self:
                if employee.user_id:
                    self.env['lms.learning.path.assignment'].process_assignment_rules(
                        employee.id, 'on_promotion'
                    )
        
        if 'department_id' in vals:
            for employee in self:
                if employee.user_id:
                    self.env['lms.learning.path.assignment'].process_assignment_rules(
                        employee.id, 'on_department_change'
                    )
        
        return result