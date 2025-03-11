# models/content_management.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ContentProject(models.Model):
    _name = 'content.project'
    _description = 'Content Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Project Name', required=True, tracking=True)
    code = fields.Char('Project Code', readonly=True, copy=False)
    date_start = fields.Date('Start Date', required=True, tracking=True)
    date_end = fields.Date('End Date', required=True, tracking=True)
    
    # Project Details
    description = fields.Html('Description')
    # Ubah ke hr.employee
    project_manager_id = fields.Many2one('hr.employee', 'Project Manager', required=True, tracking=True)
    team_ids = fields.Many2many('hr.employee', string='Team Members', tracking=True)
    
    # Content Plan
    planned_video_count = fields.Integer('Planned Video Content', tracking=True)
    planned_design_count = fields.Integer('Planned Design Content', tracking=True)
    
    # Content Tasks
    task_ids = fields.One2many('content.task', 'project_id', 'Tasks')
    
    # BAU Tracking
    bau_ids = fields.One2many('content.bau', 'project_id', 'BAU Activities')
    
    # Status and Progress
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    progress = fields.Float('Progress %', compute='_compute_progress', tracking=True)
    
    @api.model
    def create(self, vals):
        if not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('content.project')
        return super().create(vals)
    
    @api.depends('task_ids.progress', 'task_ids.state')
    def _compute_progress(self):
        for project in self:
            if not project.task_ids:
                project.progress = 0.0
                continue
                
            completed_tasks = project.task_ids.filtered(lambda t: t.state == 'done')
            total_tasks = len(project.task_ids)
            
            if total_tasks > 0:
                # Calculate basic progress based on completed tasks
                completion_progress = (len(completed_tasks) / total_tasks) * 100
                
                # Calculate weighted progress based on individual task progress
                task_progress = sum(task.progress for task in project.task_ids) / total_tasks
                
                # Final progress is average of completion and task progress
                project.progress = round((completion_progress + task_progress) / 2, 2)
            else:
                project.progress = 0.0

    # Di ContentProject
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end:
                if record.date_start > record.date_end:
                    raise ValidationError('Start date must be before end date')

    @api.constrains('planned_video_count', 'planned_design_count')
    def _check_planned_counts(self):
        for record in self:
            if record.planned_video_count < 0:
                raise ValidationError('Planned video count cannot be negative')
            if record.planned_design_count < 0:
                raise ValidationError('Planned design count cannot be negative')

    # Di ContentTask
    @api.constrains('planned_date_start', 'planned_date_end')
    def _check_planned_dates(self):
        for record in self:
            if record.planned_date_start and record.planned_date_end:
                if record.planned_date_start > record.planned_date_end:
                    raise ValidationError('Planned start date must be before planned end date')

    @api.constrains('actual_date_start', 'actual_date_end')
    def _check_actual_dates(self):
        for record in self:
            if record.actual_date_start and record.actual_date_end:
                if record.actual_date_start > record.actual_date_end:
                    raise ValidationError('Actual start date must be before actual end date')

    @api.constrains('planned_hours')
    def _check_planned_hours(self):
        for record in self:
            if record.planned_hours < 0:
                raise ValidationError('Planned hours cannot be negative')
class ContentTask(models.Model):
    _name = 'content.task'
    _description = 'Content Task'
    _inherit = ['mail.thread']
    
    name = fields.Char('Task Name', required=True, tracking=True)
    project_id = fields.Many2one('content.project', 'Project', required=True)
    
    # Task Details
    content_type = fields.Selection([
        ('video', 'Video Content'),
        ('design', 'Design Content')
    ], string='Content Type', required=True)
    
    # Ubah ke hr.employee
    assigned_to = fields.Many2many(
        'hr.employee', 
        'task_employee_rel',
        'task_id',
        'employee_id',
        string='Assigned To',
        required=True,
        tracking=True
    )
    reviewer_id = fields.Many2one('hr.employee', 'Reviewer', tracking=True)
    
    # Dates and Duration
    planned_date_start = fields.Datetime('Planned Start', tracking=True)
    planned_date_end = fields.Datetime('Planned End', tracking=True)
    actual_date_start = fields.Datetime('Actual Start')
    actual_date_end = fields.Datetime('Actual End')
    
    # Time Tracking
    planned_hours = fields.Float('Planned Hours')
    actual_hours = fields.Float('Actual Hours', compute='_compute_hours')
    
    # Revision Tracking
    revision_count = fields.Integer(compute='_compute_revision_count', store=True)
    revision_ids = fields.One2many('content.revision', 'task_id', 'Revisions')
    has_excessive_revisions = fields.Boolean(compute='_compute_excessive_revisions')
    max_allowed_revisions = fields.Integer(default=5)  # config untuk max revisi
    
    # Progress and Status
    progress = fields.Float('Progress %', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('revision', 'In Revision'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    description = fields.Text('Task Description')
    
    @api.depends('revision_ids')
    def _compute_revision_count(self):
        for task in self:
            task.revision_count = len(task.revision_ids)

    @api.depends('revision_count')
    def _compute_excessive_revisions(self):
        for task in self:
            task.has_excessive_revisions = task.revision_count > task.max_allowed_revisions

    @api.depends('actual_date_start', 'actual_date_end')
    def _compute_hours(self):
        for task in self:
            if task.actual_date_start and task.actual_date_end:
                # Convert datetime difference to hours
                delta = task.actual_date_end - task.actual_date_start
                task.actual_hours = round(delta.total_seconds() / 3600.0, 2)
            else:
                task.actual_hours = 0.0

class ContentRevision(models.Model):
    _name = 'content.revision'
    _description = 'Content Revision'
    
    task_id = fields.Many2one('content.task', 'Task', required=True, tracking=True)
    revision_number = fields.Integer('Revision #', required=True)
    requested_by = fields.Many2one('hr.employee', 'Requested By', tracking=True)
    date_requested = fields.Datetime('Date Requested', tracking=True)
    feedback = fields.Text(required=True)
    revision_points = fields.Text("Points to Revise")
    deadline = fields.Datetime()
    
    description = fields.Text('Revision Notes')
    status = fields.Selection([
        ('requested', 'Requested'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], string='Status', default='requested', tracking=True)

class ContentBAU(models.Model):
    _name = 'content.bau'
    _description = 'BAU Activity'
    _inherit = ['mail.thread']
    
    name = fields.Char('Activity Name', required=True, tracking=True)
    project_id = fields.Many2one('content.project', 'Related Project', tracking=True)
    creator_id = fields.Many2one('hr.employee', 'Creator', required=True, tracking=True)
    date = fields.Date('Date', required=True)
    hours_spent = fields.Float('Hours Spent', default=0.0, help="Optional: Record hours spent if applicable")
    activity_type = fields.Selection([
        ('video', 'Video Related'),
        ('design', 'Design Related'),
        ('other', 'Other BAU')
    ], string='Activity Type', required=True, tracking=True)
    description = fields.Text('Description')
    impact_on_delivery = fields.Text('Impact on Deliverables')
    state = fields.Selection([
        ('planned', 'Planned'),
        ('done', 'Done'),
        ('not_done', 'Not Done')
    ], string='Status', default='planned', required=True, tracking=True)
    verified_by = fields.Many2one('hr.employee', 'Verified By', readonly=True)
    verification_date = fields.Datetime('Verification Date', readonly=True)
    verification_reason = fields.Text('Verification Reason', help="Required if verified on H+1")
    
    @api.constrains('hours_spent')
    def _check_hours_spent(self):
        for record in self:
            if record.hours_spent < 0:
                raise ValidationError('Hours spent cannot be negative')