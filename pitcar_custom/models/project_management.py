# models/team_project.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import datetime, timedelta
import re

_logger = logging.getLogger(__name__)

class TeamProject(models.Model):
    _name = 'team.project'
    _description = 'Team Project Management for All Divisions'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, priority desc'

    # Core Fields
    name = fields.Char(string='Project Name', required=True, tracking=True)
    code = fields.Char(string='Project Code', readonly=True, copy=False, 
                     default=lambda self: self.env['ir.sequence'].next_by_code('team.project'))
    department_id = fields.Many2one('hr.department', string='Department', required=True, tracking=True,
                                  help="Department responsible for this project")
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    description = fields.Html(string='Description', tracking=True)

    # Tambahkan field ini di model TeamProject
    project_type = fields.Selection([
        ('creation', 'Creation/Pembuatan'), 
        ('development', 'Development/Pengembangan'),
        ('training', 'Training/Pelatihan'),
        ('documentation', 'Documentation/Dokumentasi'),
        ('general', 'General/Umum'),
        ('weekly', 'Weekly/Mingguan'),
        ('monthly', 'Monthly/Bulanan')
    ], string='Tipe Proyek', default='general', required=True, tracking=True,
        help="Tipe proyek menentukan kategori dan proses bisnis yang berlaku")
    
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        'team_project_attachment_rel', 
        'project_id', 
        'attachment_id',
        string='Attachments'
    )
    attachment_count = fields.Integer(compute='_compute_attachment_count', string='Attachment Count')
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for project in self:
            project.attachment_count = len(project.attachment_ids)
            
    # Method untuk menambahkan attachment baru
    def add_attachment(self, attachment_data):
        """
        Menambahkan attachment ke project
        :param attachment_data: dictionary berisi name, datas (base64), dan type
        :return: attachment yang dibuat
        """
        self.ensure_one()
        vals = {
            'name': attachment_data.get('name', 'Untitled'),
            'datas': attachment_data.get('datas'),
            'res_model': 'team.project',
            'res_id': self.id,
            'type': attachment_data.get('type', 'binary'),
            'mimetype': attachment_data.get('mimetype', 'application/octet-stream'),
        }
        attachment = self.env['ir.attachment'].sudo().create(vals)
        self.attachment_ids = [(4, attachment.id)]
        return attachment
    
    # Team and Management
    project_manager_id = fields.Many2one('hr.employee', string='Project Manager', required=True, tracking=True)
    team_ids = fields.Many2many('hr.employee', string='Team Members', tracking=True)
    stakeholder_ids = fields.Many2many('hr.employee', 'project_stakeholder_rel', 'project_id', 'employee_id', 
                                     string='Stakeholders', tracking=True)
    
    # Tasks, Messages, and Activities
    task_ids = fields.One2many('team.project.task', 'project_id', string='Tasks')
    message_ids = fields.One2many('team.project.message', 'project_id', string='Messages')
    group_id = fields.Many2one('team.project.group', string='Collaboration Group')
    bau_ids = fields.One2many('team.project.bau', 'project_id', string='BAU Activities')
    meeting_ids = fields.One2many('team.project.meeting', 'project_id', string='Meetings')
    
    # Progress and Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('planning', 'Planning'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    progress = fields.Float(string='Progress %', compute='_compute_progress', store=True, tracking=True)
    planned_hours = fields.Float(string='Planned Hours', compute='_compute_planned_hours', store=True)
    actual_hours = fields.Float(string='Actual Hours', compute='_compute_actual_hours', store=True)
    
    # Additional Metadata
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Critical')
    ], string='Priority', default='1', tracking=True)
    
    color = fields.Integer(string='Color Index', default=0)
    tag_ids = fields.Many2many('team.project.tag', string='Tags')
    kanban_state = fields.Selection([
        ('normal', 'In Progress'),
        ('done', 'Ready for next stage'),
        ('blocked', 'Blocked')
    ], string='Kanban State', default='normal', tracking=True)
    
    # Display in Calendar
    calendar_visible = fields.Boolean('Show in Calendar', default=True)

    # Field baru untuk tracking waktu penyelesaian
    actual_date_end = fields.Date(string='Actual End Date', readonly=True, tracking=True)
    is_on_time = fields.Boolean(string='Completed On Time', compute='_compute_is_on_time', store=True)
    days_delayed = fields.Integer(string='Days Delayed', compute='_compute_days_delayed', store=True)

    @api.depends('date_end', 'actual_date_end', 'state')
    def _compute_is_on_time(self):
        for project in self:
            if project.state == 'completed' and project.actual_date_end and project.date_end:
                project.is_on_time = project.actual_date_end <= project.date_end
            else:
                project.is_on_time = False

    @api.depends('date_end', 'actual_date_end', 'is_on_time')
    def _compute_days_delayed(self):
        for project in self:
            if not project.is_on_time and project.actual_date_end and project.date_end:
                delta = project.actual_date_end - project.date_end
                project.days_delayed = delta.days if delta.days > 0 else 0
            else:
                project.days_delayed = 0

    # Tambahkan ke metode write
    def write(self, vals):
        if 'state' in vals and vals['state'] == 'completed':
            for project in self:
                if not project.actual_date_end:
                    vals['actual_date_end'] = fields.Date.today()
        return super(TeamProject, self).write(vals)

    
    # Constraints
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start > record.date_end:
                raise ValidationError(_('Start date must be before end date.'))

    # Computed Methods
    @api.depends('task_ids.progress', 'task_ids.state')
    def _compute_progress(self):
        for project in self:
            tasks = project.task_ids
            if not tasks:
                project.progress = 0.0
            else:
                total_tasks = len(tasks)
                completed_tasks = len(tasks.filtered(lambda t: t.state == 'done'))
                if total_tasks > 0:
                    # 50% weight on completion count, 50% on task progress
                    completion_ratio = completed_tasks / total_tasks
                    avg_progress = sum(task.progress for task in tasks) / total_tasks
                    project.progress = round((completion_ratio * 50 + avg_progress * 0.5), 2)
                else:
                    project.progress = 0.0

    @api.depends('task_ids.planned_hours')
    def _compute_planned_hours(self):
        for project in self:
            project.planned_hours = sum(project.task_ids.mapped('planned_hours'))

    @api.depends('task_ids.actual_hours')
    def _compute_actual_hours(self):
        for project in self:
            project.actual_hours = sum(project.task_ids.mapped('actual_hours'))

    # CRUD Methods
    @api.model
    def create(self, vals):
        if 'code' not in vals or not vals['code']:
            vals['code'] = self.env['ir.sequence'].next_by_code('team.project') or _('New')
        project = super(TeamProject, self).create(vals)
        
        # Create collaboration group automatically
        if not project.group_id:
            members = project.team_ids.ids + [project.project_manager_id.id]
            if project.stakeholder_ids:
                members += project.stakeholder_ids.ids
            
            group = self.env['team.project.group'].create({
                'name': f"Team: {project.name}",
                'project_id': project.id,
                'member_ids': [(6, 0, list(set(members)))]  # Use set to remove duplicates
            })
            project.group_id = group.id
        
        # Send notifications to team members
        self._send_project_notifications(project, 'created')
        return project

    def write(self, vals):
        res = super(TeamProject, self).write(vals)
        
        # Update group members if team changed
        if 'team_ids' in vals or 'project_manager_id' in vals or 'stakeholder_ids' in vals:
            for project in self:
                if project.group_id:
                    members = project.team_ids.ids + [project.project_manager_id.id]
                    if project.stakeholder_ids:
                        members += project.stakeholder_ids.ids
                    project.group_id.member_ids = [(6, 0, list(set(members)))]
        
        # Handle status changes
        if 'state' in vals:
            self._send_project_notifications(self, vals['state'])
            
        return res

    def unlink(self):
        for project in self:
            if project.state not in ('draft', 'cancelled'):
                raise ValidationError(_('Cannot delete a project that is in progress or completed.'))
        return super(TeamProject, self).unlink()
    
    # Helper Methods
    def _send_project_notifications(self, project, event_type):
        """Send notifications to relevant users based on project events"""
        if event_type == 'created':
            message = f"You have been added to project '{project.name}' starting on {project.date_start}."
            title = f"New Project: {project.name}"
        else:
            state_messages = {
                'planning': f"Project {project.name} is now in planning phase.",
                'in_progress': f"Project {project.name} has started.",
                'on_hold': f"Project {project.name} has been put on hold.",
                'completed': f"Project {project.name} has been completed.",
                'cancelled': f"Project {project.name} has been cancelled."
            }
            message = state_messages.get(event_type, f"Project {project.name} status updated.")
            title = f"Project Update: {project.name}"
        
        members = project.team_ids | project.project_manager_id
        if project.stakeholder_ids:
            members |= project.stakeholder_ids
            
        for member in members:
            if member.user_id:
                self.env['pitcar.notification'].create_or_update_notification(
                    model='team.project',
                    res_id=project.id,
                    type=f"project_{event_type}",
                    title=title,
                    message=message,
                    user_id=member.user_id.id,
                    data={'project_id': project.id, 'action': 'view_project'}
                )
    
    # UI Actions
    def action_start_project(self):
        self.write({'state': 'in_progress'})
    
    def action_complete_project(self):
        incomplete_tasks = self.task_ids.filtered(lambda t: t.state not in ('done', 'cancelled'))
        if incomplete_tasks:
            # Rather than error, mark incomplete tasks as cancelled
            incomplete_tasks.write({'state': 'cancelled'})
        
        self.write({'state': 'completed'})
    
    def action_hold_project(self):
        self.write({'state': 'on_hold'})
    
    def action_cancel_project(self):
        self.write({'state': 'cancelled'})
    
    def action_resume_project(self):
        self.write({'state': 'in_progress'})
    
    def action_view_calendar(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Project Calendar',
            'res_model': 'team.project',
            'view_mode': 'calendar',
            'domain': [('id', '=', self.id)],
        }
    
    def action_view_gantt(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Project Gantt',
            'res_model': 'team.project',
            'view_mode': 'gantt',
            'domain': [('id', '=', self.id)],
        }


class TeamProjectTag(models.Model):
    _name = 'team.project.tag'
    _description = 'Project Tags'
    
    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index')


class TeamProjectTask(models.Model):
    _name = 'team.project.task'
    _description = 'Team Project Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, sequence, id desc'

    # Core Fields
    name = fields.Char(string='Task Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)
    project_id = fields.Many2one('team.project', string='Project', required=True, ondelete='cascade')
    department_id = fields.Many2one('hr.department', string='Department', related='project_id.department_id', store=True)
    user_id = fields.Many2one('res.users', string='Assigned User', tracking=True)
    
    # Assignments
    assigned_to = fields.Many2many('hr.employee', string='Assigned To', required=True, tracking=True)
    reviewer_id = fields.Many2one('hr.employee', string='Reviewer', tracking=True)
    follower_ids = fields.Many2many('hr.employee', 'task_follower_rel', 'task_id', 'employee_id', 
                                  string='Followers')
    
    # Timing
    planned_date_start = fields.Datetime(string='Planned Start', tracking=True)
    planned_date_end = fields.Datetime(string='Planned End', tracking=True)
    actual_date_start = fields.Datetime(string='Actual Start', readonly=True)
    actual_date_end = fields.Datetime(string='Actual End', readonly=True)
    planned_hours = fields.Float(string='Planned Hours', default=0.0, tracking=True)
    actual_hours = fields.Float(string='Actual Hours', compute='_compute_actual_hours', store=True)
    duration = fields.Float(string='Duration (Days)', compute='_compute_duration', store=True)
    
    # Content
    description = fields.Html(string='Description', tracking=True)
    checklist_ids = fields.One2many('team.project.task.checklist', 'task_id', string='Checklist Items')
    checklist_progress = fields.Float(string='Checklist Progress', compute='_compute_checklist_progress', store=True)

    # Pastikan attachment_ids didefinisikan dengan benar dan domain yang tepat
    attachment_ids = fields.One2many(
        'ir.attachment', 
        'res_id', 
        string='Attachments',
        domain=[('res_model', '=', 'team.project.task')]
    )
    attachment_count = fields.Integer(compute='_compute_attachment_count', string='Attachment Count')
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for task in self:
            task.attachment_count = len(task.attachment_ids)
    
    # Method untuk menambahkan attachment baru
    def add_attachment(self, attachment_data):
        """
        Menambahkan attachment ke task
        :param attachment_data: dictionary berisi name, datas (base64), dan type
        :return: attachment yang dibuat
        """
        self.ensure_one()
        vals = {
            'name': attachment_data.get('name', 'Untitled'),
            'datas': attachment_data.get('datas'),
            'res_model': 'team.project.task',
            'res_id': self.id,
            'type': attachment_data.get('type', 'binary'),
            'mimetype': attachment_data.get('mimetype', 'application/octet-stream'),
        }
        attachment = self.env['ir.attachment'].sudo().create(vals)
        return attachment
    
    # Status and Progress
    state = fields.Selection([
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    progress = fields.Float(string='Progress %', default=0.0, tracking=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Critical')
    ], string='Priority', default='1', tracking=True)
    
    color = fields.Integer(string='Color', default=0)
    tag_ids = fields.Many2many('team.project.task.tag', string='Tags')
    
    # Dependencies
    # Di model TeamProjectTask
    depends_on_ids = fields.Many2many(
        'team.project.task', 
        'team_task_dependency_rel',  # Nama tabel relasi yang unik
        'task_id',                   # Nama kolom task_id
        'dependency_task_id',        # Nama kolom dependency_task_id
        string='Depends On'
    )
    blocked_by_id = fields.Many2one('team.project.task', string='Blocked By')
    
    # Display in Kanban
    kanban_state = fields.Selection([
        ('normal', 'In Progress'),
        ('done', 'Ready for next stage'),
        ('blocked', 'Blocked')
    ], string='Kanban State', default='normal', tracking=True)
    
    # Attachments
    attachment_ids = fields.One2many('ir.attachment', 'res_id', string='Attachments',
                                   domain=[('res_model', '=', 'team.project.task')])
    attachment_count = fields.Integer(compute='_compute_attachment_count', string='Attachment Count')
    
    # Comments and History
    comment_ids = fields.One2many('team.project.task.comment', 'task_id', string='Comments')
    
    # Time Tracking
    timesheet_ids = fields.One2many('team.project.timesheet', 'task_id', string='Timesheets')
    
    # Task Type
    type_id = fields.Many2one('team.project.task.type', string='Task Type')

     # Tambahkan field untuk tracking status sebelumnya dan timestamp
    previous_state = fields.Char(string='Previous State', readonly=True, copy=False)
    state_change_time = fields.Datetime(string='Last State Change', readonly=True, copy=False)
    time_in_progress = fields.Float(string='Time in Progress', readonly=True, copy=False, default=0.0)
    auto_timesheet = fields.Boolean(string='Auto Timesheet', default=True, 
                                  help="Automatically create timesheet entries on state change") 
    
    # Constraints
    @api.constrains('planned_date_start', 'planned_date_end')
    def _check_planned_dates(self):
        for task in self:
            if task.planned_date_start and task.planned_date_end:
                if task.planned_date_start > task.planned_date_end:
                    raise ValidationError(_('Planned start date must be before planned end date.'))

    @api.constrains('planned_hours')
    def _check_planned_hours(self):
        for task in self:
            if task.planned_hours < 0:
                raise ValidationError(_('Planned hours cannot be negative.'))
    
    # Computed Methods
    @api.depends('checklist_ids', 'checklist_ids.is_done')
    def _compute_checklist_progress(self):
        for task in self:
            checklist_items = task.checklist_ids
            if not checklist_items:
                task.checklist_progress = 0.0
            else:
                done_items = len(checklist_items.filtered(lambda c: c.is_done))
                progress = (done_items / len(checklist_items)) * 100
                task.checklist_progress = progress
                
                # Opsional: Update task progress berdasarkan checklist
                # Tambahkan hanya jika Anda ingin progress task otomatis diupdate
                if hasattr(task, 'progress_based_on_checklist') and task.progress_based_on_checklist:
                    task.progress = progress

    @api.depends('timesheet_ids.hours')
    def _compute_actual_hours(self):
        for task in self:
            task.actual_hours = sum(task.timesheet_ids.mapped('hours'))

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for task in self:
            task.attachment_count = len(task.attachment_ids)
    
    @api.depends('planned_date_start', 'planned_date_end')
    def _compute_duration(self):
        for task in self:
            if task.planned_date_start and task.planned_date_end:
                # Calculate duration in days
                delta = task.planned_date_end - task.planned_date_start
                task.duration = delta.total_seconds() / (24 * 60 * 60)
            else:
                task.duration = 0.0
    
    # CRUD Methods
    # Di model team.project.task - tambahkan ke method create
    @api.model
    def create(self, vals):
        task = super(TeamProjectTask, self).create(vals)
        
        # Notifikasi untuk penugasan baru
        if task.assigned_to:
            for assignee in task.assigned_to:
                if assignee.user_id:
                    self.env['team.project.notification'].create_project_notification(
                        model='team.project.task',
                        res_id=task.id,
                        type='task_assigned',
                        title=f"Tugas Baru: {task.name}",
                        message=f"Anda ditugaskan ke tugas '{task.name}' dalam proyek {task.project_id.name}.",
                        project_id=task.project_id.id,
                        sender_id=self.env.user.employee_id.id,
                        # recipient_id=assignee.id,
                        user_id=assignee.user_id.id,  # Tambahkan user_id eksplisit
                        category='task_assigned',
                        data={
                            'task_id': task.id, 
                            'project_id': task.project_id.id,
                            'action': 'view_task'
                        },
                        priority='high' if task.priority in ['2', '3'] else 'normal'
                    )
        
        return task

    def write(self, vals):
        # Simpan nilai lama untuk perbandingan
        old_states = {}
        if 'state' in vals:
            for task in self:
                old_states[task.id] = task.state
        
        # Untuk setiap task yang diupdate
        for task in self:
            # Jika terjadi perubahan status
            if 'state' in vals and task.state != vals['state']:
                now = fields.Datetime.now()
                
                # Jika fitur auto timesheet diaktifkan
                if task.auto_timesheet:
                    # Jika status sebelumnya adalah in_progress, catat timesheet
                    if task.state == 'in_progress' and task.state_change_time:
                        # Hitung total durasi dalam jam
                        total_duration_hours = (now - task.state_change_time).total_seconds() / 3600
                        
                        # Hanya proses jika durasinya signifikan (>= 6 menit)
                        if total_duration_hours >= 0.1:
                            # Ambil tanggal mulai dan selesai
                            start_date = task.state_change_time.date()
                            end_date = now.date()
                            
                            # Hitung jumlah hari kerja di antara kedua tanggal
                            current_date = start_date
                            remaining_hours = total_duration_hours
                            
                            # Definisikan jam kerja maksimum per hari (8 jam)
                            work_hours_per_day = 8.0
                            
                            while current_date <= end_date and remaining_hours > 0:
                                # Tentukan jam untuk hari ini
                                hours_today = min(remaining_hours, work_hours_per_day)
                                
                                # Hanya buat entri jika ada jam yang signifikan
                                if hours_today >= 0.1:
                                    # Buat entri timesheet dengan jam kerja standar
                                    self.env['team.project.timesheet'].sudo().create({
                                        'task_id': task.id,
                                        'employee_id': self.env.user.employee_id.id,
                                        'date': current_date,
                                        'hours': round(hours_today, 2),
                                        'description': f"Waktu yang dihabiskan saat task dalam status '{task.state}' (jam kerja 08:00-17:00)"
                                    })
                                
                                # Kurangi jam yang tersisa dan pindah ke hari berikutnya
                                remaining_hours -= hours_today
                                current_date = current_date + timedelta(days=1)
                                
                                # Lewati akhir pekan jika diinginkan
                                while current_date.weekday() >= 6:  # 5=Sabtu, 6=Minggu
                                    current_date = current_date + timedelta(days=1)
                
                # Catat status sebelumnya dan waktu perubahan
                vals.update({
                    'previous_state': task.state,
                    'state_change_time': fields.Datetime.now()
                })
                
                # Jika status berubah ke in_progress
                if vals['state'] == 'in_progress' and not task.actual_date_start:
                    vals['actual_date_start'] = fields.Datetime.now()
                # Jika status berubah ke done
                elif vals['state'] == 'done' and not task.actual_date_end:
                    vals['actual_date_end'] = fields.Datetime.now()
        
        # Panggil write asli
        result = super(TeamProjectTask, self).write(vals)
        
        # Proses notifikasi setelah write
        for task in self:
            # Notifikasi perubahan status
            # Di model team.project.task dalam method write
            if 'state' in vals and task.id in old_states and old_states[task.id] != task.state:
                # Pesan untuk setiap status
                state_messages = {
                    'in_progress': f"Tugas {task.name} sekarang sedang dikerjakan.",
                    'review': f"Tugas {task.name} perlu ditinjau.",
                    'done': f"Tugas {task.name} telah selesai.",
                    'cancelled': f"Tugas {task.name} telah dibatalkan."
                }
                
                # Tentukan tipe dan pesan berdasarkan status baru
                current_state = task.state
                if current_state in state_messages:
                    # Beri notifikasi kepada penanggung jawab tugas
                    for assignee in task.assigned_to:
                        if assignee.user_id:
                            self.env['team.project.notification'].create_project_notification(
                                model='team.project.task',
                                res_id=task.id,
                                type=f"task_{current_state}",
                                title=f"Pembaruan Tugas: {task.name}",
                                message=state_messages[current_state],
                                project_id=task.project_id.id,
                                sender_id=self.env.user.employee_id.id,
                                # recipient_id=assignee.id,
                                user_id=assignee.user_id.id,  # Tambahkan user_id eksplisit
                                category='task_updated',
                                data={
                                    'task_id': task.id, 
                                    'project_id': task.project_id.id,
                                    'action': 'view_task'
                                }
                            )
                    
                    # Beri notifikasi kepada manajer proyek
                    if task.project_id.project_manager_id and task.project_id.project_manager_id.user_id:
                        self.env['team.project.notification'].create_project_notification(
                            model='team.project.task',
                            res_id=task.id,
                            type=f"task_{current_state}",
                            title=f"Pembaruan Tugas: {task.name}",
                            message=state_messages[current_state],
                            project_id=task.project_id.id,
                            sender_id=self.env.user.employee_id.id,
                            # recipient_id=task.project_id.project_manager_id.id,
                            user_id=task.project_id.project_manager_id.user_id.id,  # Tambahkan user_id eksplisit
                            category='task_updated',
                            data={
                                'task_id': task.id, 
                                'project_id': task.project_id.id,
                                'action': 'view_task'
                            }
                        )
                
                # Perbarui progres proyek saat tugas berubah
                task.project_id._compute_progress()

        return result
    
    # UI Actions
    def action_start_task(self):
        self.write({'state': 'in_progress'})
    
    def action_mark_done(self):
        self.write({'state': 'done', 'progress': 100.0})
    
    def action_send_for_review(self):
        self.write({'state': 'review'})
    
    def action_reset_to_draft(self):
        self.write({'state': 'draft', 'actual_date_start': False, 'actual_date_end': False})


class TeamProjectTaskChecklist(models.Model):
    _name = 'team.project.task.checklist'
    _description = 'Task Checklist Item'
    _order = 'sequence, id'
    
    name = fields.Char(string='Item Description', required=True)
    task_id = fields.Many2one('team.project.task', string='Task', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    is_done = fields.Boolean(string='Done', default=False)
    assigned_to = fields.Many2one('hr.employee', string='Assigned To')
    deadline = fields.Date(string='Deadline')
    notes = fields.Text(string='Notes')


class TeamProjectTaskTag(models.Model):
    _name = 'team.project.task.tag'
    _description = 'Task Tags'
    
    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index')


class TeamProjectTaskType(models.Model):
    _name = 'team.project.task.type'
    _description = 'Task Types'
    
    name = fields.Char(string='Type Name', required=True)
    description = fields.Text(string='Description')
    color = fields.Integer(string='Color')
    default_planned_hours = fields.Float(string='Default Planned Hours')


class TeamProjectTaskComment(models.Model):
    _name = 'team.project.task.comment'
    _description = 'Task Comment'
    _order = 'date desc, id desc'
    
    task_id = fields.Many2one('team.project.task', string='Task', required=True, ondelete='cascade')
    author_id = fields.Many2one('hr.employee', string='Author', required=True,
                              default=lambda self: self.env.user.employee_id.id)
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    content = fields.Html(string='Comment', required=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')


class TeamProjectGroup(models.Model):
    _name = 'team.project.group'
    _description = 'Collaboration Group'
    _inherit = ['mail.thread']
    
    name = fields.Char(string='Group Name', required=True)
    description = fields.Text(string='Description')
    project_id = fields.Many2one('team.project', string='Related Project', ondelete='cascade')
    member_ids = fields.Many2many('hr.employee', string='Members', required=True)
    message_ids = fields.One2many('team.project.message', 'group_id', string='Messages')
    is_archived = fields.Boolean(string='Archived', default=False)
    
    def action_archive(self):
        self.write({'is_archived': True})
    
    def action_unarchive(self):
        self.write({'is_archived': False})


class TeamProjectMessage(models.Model):
    _name = 'team.project.message'
    _description = 'Group Message'
    _order = 'date desc, id desc'
    
    group_id = fields.Many2one('team.project.group', string='Group', ondelete='cascade')
    project_id = fields.Many2one('team.project', string='Project', ondelete='cascade')
    author_id = fields.Many2one('hr.employee', string='Author', required=True,
                              default=lambda self: self.env.user.employee_id.id)
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    content = fields.Html(string='Message', required=True)

    # Perbaikan field attachment
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        'team_message_attachment_rel', 
        'message_id', 
        'attachment_id',
        string='Attachments'
    )
    
    # Hitung jumlah attachment untuk tampilan
    attachment_count = fields.Integer(compute='_compute_attachment_count', string='Attachment Count')
    
    parent_id = fields.Many2one('team.project.message', string='Parent Message')
    is_pinned = fields.Boolean(string='Pinned', default=False)

    # Add this field
    message_type = fields.Selection([
        ('regular', 'Regular'),
        ('mention', 'Mention'),
        ('announcement', 'Announcement')
    ], string='Message Type', default='regular')
    
    # Either project_id or group_id must be set
    @api.constrains('group_id', 'project_id')
    def _check_message_parent(self):
        for message in self:
            if not message.group_id and not message.project_id:
                raise ValidationError(_('Message must be linked to either a group or a project.'))
    
    def action_pin(self):
        self.write({'is_pinned': True})
    
    def action_unpin(self):
        self.write({'is_pinned': False})

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for message in self:
            message.attachment_count = len(message.attachment_ids)
            
    # Method untuk menambahkan attachment baru
    def add_attachment(self, attachment_data):
        """
        Menambahkan attachment ke pesan
        :param attachment_data: dictionary berisi name, datas (base64), dan type
        :return: attachment yang dibuat
        """
        self.ensure_one()
        vals = {
            'name': attachment_data.get('name', 'Untitled'),
            'datas': attachment_data.get('datas'),
            'res_model': 'team.project.message',
            'res_id': self.id,
            'type': attachment_data.get('type', 'binary'),
            'mimetype': attachment_data.get('mimetype', 'application/octet-stream'),
        }
        attachment = self.env['ir.attachment'].sudo().create(vals)
        self.attachment_ids = [(4, attachment.id)]
        return attachment
    
    def _process_mentions(self):
        """Mendeteksi dan memproses mention di pesan dan membuat notifikasi"""
        if not self.content:
            return

        # Mencari pola mention (@[...])
        mention_pattern = r'@\[(.*?)\]'
        mentions = re.findall(mention_pattern, self.content)
        
        if not mentions:
            return
        
        # Memproses setiap mention yang ditemukan
        for mention in mentions:
            try:
                # Periksa format @[id:name]
                if ':' in mention:
                    parts = mention.split(':', 1)
                    
                    # Coba ekstrak ID dari format @[id:name]
                    try:
                        user_id = int(parts[0])
                        user = self.env['res.users'].sudo().browse(user_id)
                        
                        # Jika tidak ditemukan, coba format @[name:id]
                        if not user.exists():
                            user_id = int(parts[1])
                            user = self.env['res.users'].sudo().browse(user_id)
                    except (ValueError, IndexError):
                        continue
                        
                    # Validasi user dan employee
                    if not user.exists() or not user.employee_id:
                        continue
                        
                    # PENTING: Skip jika self-mention (user yang ditagged adalah pengirim pesan)
                    if user.id == self.env.user.id or user.employee_id.id == self.author_id.id:
                        continue
                        
                    # Siapkan data notifikasi
                    mention_data = {
                        'message_id': self.id,
                        'group_id': self.group_id.id,
                        'action': 'view_group_chat'
                    }
                    
                    # Buat notifikasi dengan sudo() untuk melewati batasan izin
                    self.env['team.project.notification'].sudo().create_project_notification(
                        model='team.project.message',
                        res_id=self.id,
                        type='mention',
                        title=f"Anda disebut oleh {self.author_id.name}",
                        message=f"Anda disebut dalam pesan: '{self.content[:100]}...'",
                        project_id=self.project_id.id if self.project_id else False,
                        sender_id=self.author_id.id,
                        # recipient_id=user.employee_id.id,
                        user_id=user.id,  # Tambahkan user_id eksplisit
                        category='mention',
                        data=mention_data,
                        priority='medium'
                    )
                
            except Exception as e:
                _logger.error(f"Error processing mention: {str(e)}")
                import traceback
                _logger.error(traceback.format_exc())

    @api.model
    def create(self, vals):
        """Override create untuk memproses mention saat pesan dibuat"""
        message = super(TeamProjectMessage, self).create(vals)
        
        # Proses mention jika fitur aktif
        message._process_mentions()
        
        # Kirim notifikasi umum ke semua anggota grup jika ini grup kolaborasi
        if message.group_id:
            message._notify_group_members()
        
        return message

    def _notify_group_members(self):
        """Mengirim notifikasi ke semua anggota grup"""
        if not self.group_id or not self.group_id.member_ids:
            return
            
        # Jangan kirim notifikasi ke pengirim pesan
        members = self.group_id.member_ids.filtered(lambda m: m.id != self.author_id.id)
        
        # Ekstrak ID yang di-mention
        mentioned_ids = set()
        mention_pattern = r'@\[(\d+)'
        
        if self.content:
            mentions = re.findall(mention_pattern, self.content)
            for id_str in mentions:
                try:
                    user_id = int(id_str)
                    user = self.env['res.users'].sudo().browse(user_id)
                    if user.exists() and user.employee_id:
                        mentioned_ids.add(user.employee_id.id)
                except (ValueError, Exception):
                    continue
        
        for member in members:
            # Skip notifikasi untuk anggota yang sudah di-mention
            if member.id in mentioned_ids:
                continue
                
            if not member.user_id:
                continue
                
            # PENTING: Cek apakah pengguna berada di departemen yang sama dengan project
            if self.project_id and self.project_id.department_id:
                if member.department_id.id != self.project_id.department_id.id:
                    # Opsi 1: Skip notifikasi untuk departemen berbeda
                    # continue
                    
                    # Opsi 2: Hanya buat notifikasi untuk pesan penting
                    if self.message_type != 'announcement':
                        continue
                    
            # Tentukan jenis notifikasi
            if self.message_type == 'announcement':
                title = f"Pengumuman di {self.group_id.name}"
                priority = 'high'
                category = 'announcement'
            else:
                title = f"Pesan baru di {self.group_id.name}"
                priority = 'normal'
                category = 'new_message'
                
            # Siapkan data notifikasi
            message_data = {
                'message_id': self.id,
                'group_id': self.group_id.id,
                'action': 'view_group_chat',
                'author_id': self.author_id.id
            }

            # Buat notifikasi untuk anggota grup
            self.env['team.project.notification'].sudo().create_project_notification(
                model='team.project.message',
                res_id=self.id,
                type='new_message',
                title=title,
                message=f"{self.author_id.name}: {self.content[:100]}...",
                project_id=self.project_id.id if self.project_id else False,
                sender_id=self.author_id.id,
                user_id=member.user_id.id,
                category=category,
                data=message_data,
                priority=priority
            )
class TeamProjectBAU(models.Model):
    _name = 'team.project.bau'
    _description = 'Business As Usual Activity'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Activity Name', required=True, tracking=True)
    project_id = fields.Many2one('team.project', string='Related Project', tracking=True)
    creator_id = fields.Many2one('hr.employee', string='Creator', required=True, tracking=True,
                             default=lambda self: self.env.user.employee_id.id)
    date = fields.Date(string='Date', required=True)
    
    # Add time fields
    time_start = fields.Float(string='Start Time', required=True, default=9.0,
                              help="Start time in 24-hour format (e.g., 9.5 = 9:30 AM)")
    time_end = fields.Float(string='End Time', required=True, default=10.0,
                            help="End time in 24-hour format (e.g., 17.5 = 5:30 PM)")
    
    hours_spent = fields.Float(string='Hours Spent', compute='_compute_hours_spent', store=True, readonly=False)
    
    activity_type = fields.Selection([
        ('meeting', 'Meeting'),
        ('training', 'Training'),
        ('support', 'Support'),
        ('admin', 'Administrative'),
        ('other', 'Other')
    ], string='Activity Type', required=True, tracking=True)
    
    description = fields.Text(string='Description')
    state = fields.Selection([
        ('planned', 'Planned'),
        ('done', 'Done'),
        ('not_done', 'Not Done')
    ], string='Status', default='planned', required=True, tracking=True)
    
    # Verification fields
    verified_by = fields.Many2one('hr.employee', string='Verified By', readonly=True)
    verification_date = fields.Datetime(string='Verification Date', readonly=True)
    verification_reason = fields.Text(string='Verification Reason', help="Reason for H+1 verification")
    
    @api.depends('time_start', 'time_end')
    def _compute_hours_spent(self):
        """Compute hours spent based on start and end time"""
        for record in self:
            if record.time_start is not False and record.time_end is not False:
                if record.time_end >= record.time_start:
                    record.hours_spent = record.time_end - record.time_start
                else:
                    # Handle overnight activities (end time is on next day)
                    record.hours_spent = (24.0 - record.time_start) + record.time_end
            else:
                record.hours_spent = 0.0
    
    @api.constrains('time_start', 'time_end', 'hours_spent')
    def _check_time_validity(self):
        """Validate time inputs"""
        for record in self:
            if record.time_start < 0 or record.time_start >= 24:
                raise ValidationError(_('Start time must be between 0:00 and 23:59.'))
            if record.time_end < 0 or record.time_end >= 24:
                raise ValidationError(_('End time must be between 0:00 and 23:59.'))
            
            # If end time is less than start time, assume overnight and allow
            if record.time_end < record.time_start and (record.time_start - record.time_end) > 16:
                # Prevent unrealistic time spans (over 16 hours)
                raise ValidationError(_('The time span between start and end time is too long.'))
            
            if record.hours_spent < 0:
                raise ValidationError(_('Hours spent cannot be negative.'))
            if record.hours_spent > 24:
                raise ValidationError(_('Hours spent cannot exceed 24 hours.'))
    

class TeamProjectTimesheet(models.Model):
    _name = 'team.project.timesheet'
    _description = 'Task Timesheet'
    _order = 'date desc, id desc'
    
    task_id = fields.Many2one('team.project.task', string='Task', required=True, ondelete='cascade')
    project_id = fields.Many2one('team.project', string='Project', related='task_id.project_id', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                default=lambda self: self.env.user.employee_id.id)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    hours = fields.Float(string='Hours Spent', required=True)
    description = fields.Text(string='Description')
    session_id = fields.Char(string='Session ID', copy=False, 
                       help="Identifies timesheet entries from the same work session")
    
    @api.model
    def get_auto_timesheet_summary(self, employee_id, date_from, date_to):
        """Get summary of automatically generated timesheets"""
        domain = [
            ('employee_id', '=', employee_id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            # Tambahkan filter untuk membedakan timesheet otomatis vs manual
        ]
        
        timesheets = self.env['team.project.timesheet'].search(domain)
        
        # Kelompokkan berdasarkan task dan project
        result = {}
        for ts in timesheets:
            task_key = ts.task_id.id
            if task_key not in result:
                result[task_key] = {
                    'task': ts.task_id.name,
                    'project': ts.project_id.name,
                    'total_hours': 0,
                    'entries': []
                }
            
            result[task_key]['total_hours'] += ts.hours
            result[task_key]['entries'].append({
                'date': ts.date,
                'hours': ts.hours,
                'description': ts.description
            })
        
        return list(result.values())

        
    
    @api.constrains('hours')
    def _check_hours(self):
        for record in self:
            if record.hours <= 0:
                raise ValidationError(_('Hours must be positive.'))
            if record.hours > 24:
                raise ValidationError(_('You cannot log more than 24 hours per day.'))
            
    # Add these methods to the TeamProjectTimesheet model class in models/team_project.py
    # Extension for the TeamProjectTimesheet model
    def _check_employee_availability(self):
        """Check if employee has already logged too many hours on a given date."""
        for timesheet in self:
            # Get all other timesheets from the same employee on the same date
            other_timesheets = self.env['team.project.timesheet'].search([
                ('employee_id', '=', timesheet.employee_id.id),
                ('date', '=', timesheet.date),
                ('id', '!=', timesheet.id)
            ])
            
            # Calculate total hours logged for that day
            total_hours = sum(other_timesheets.mapped('hours')) + timesheet.hours
            
            # Check against the maximum allowed per day (8 or configurable)
            # This is a soft warning - doesn't prevent saving but logs a warning
            max_hours_per_day = 8  # Could be made configurable
            if total_hours > max_hours_per_day:
                _logger.warning(
                    f"Employee {timesheet.employee_id.name} has logged {total_hours} hours "
                    f"on {timesheet.date}, which exceeds the recommended {max_hours_per_day} hours."
                )

    # Add an SQL constraint to ensure hours are positive
    _sql_constraints = [
        ('check_timesheet_hours_positive', 'CHECK(hours > 0)', 'Hours must be greater than zero.'),
    ]

    # Add this method to get available employees for a task
    @api.model
    def get_available_employees_for_task(self, task_id):
        """Get employees available for logging time on a specific task."""
        if not task_id:
            return []
            
        task = self.env['team.project.task'].browse(int(task_id))
        if not task.exists():
            return []
            
        # Get assigned employees plus project team members
        available_employees = task.assigned_to
        if task.project_id:
            available_employees |= task.project_id.team_ids
            available_employees |= task.project_id.project_manager_id
            
        return available_employees.mapped(lambda e: {'id': e.id, 'name': e.name})

    # Add this method to analyze timesheet efficiency
    @api.model
    def analyze_timesheet_efficiency(self, domain=None):
        """Analyze timesheet efficiency for reporting."""
        if domain is None:
            domain = []
            
        timesheets = self.search(domain)
        
        # Group timesheets by task
        task_efficiency = {}
        for timesheet in timesheets:
            task_id = timesheet.task_id.id
            if task_id not in task_efficiency:
                task = timesheet.task_id
                task_efficiency[task_id] = {
                    'task_name': task.name,
                    'planned_hours': task.planned_hours,
                    'actual_hours': 0,
                    'progress': task.progress,
                    'efficiency': 0
                }
            task_efficiency[task_id]['actual_hours'] += timesheet.hours
            
        # Calculate efficiency
        for task_id, data in task_efficiency.items():
            if data['planned_hours'] > 0:
                # Calculate hours efficiency (planned vs actual)
                hours_ratio = data['planned_hours'] / max(data['actual_hours'], 0.1)
                # Calculate progress efficiency (progress vs expected based on hours)
                expected_progress = min(100, (data['actual_hours'] / data['planned_hours']) * 100)
                progress_ratio = data['progress'] / max(expected_progress, 0.1)
                
                # Combined efficiency score (0-100%)
                data['efficiency'] = min(100, (hours_ratio * 0.5 + progress_ratio * 0.5) * 100)
            else:
                data['efficiency'] = 0
                
        return list(task_efficiency.values())


class TeamProjectMeeting(models.Model):
    _name = 'team.project.meeting'
    _description = 'Project Meeting'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'
    
    name = fields.Char(string='Meeting Title', required=True, tracking=True)
    project_id = fields.Many2one('team.project', string='Related Project', tracking=True)
    organizer_id = fields.Many2one('hr.employee', string='Organizer', required=True, tracking=True,
                                 default=lambda self: self.env.user.employee_id.id)
    attendee_ids = fields.Many2many('hr.employee', string='Attendees', tracking=True)
    
    start_datetime = fields.Datetime(string='Start Time', required=True, tracking=True)
    end_datetime = fields.Datetime(string='End Time', required=True, tracking=True)
    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)
    
    location = fields.Char(string='Location')
    virtual_location = fields.Char(string='Virtual Meeting Link')
    agenda = fields.Html(string='Agenda')
    notes = fields.Html(string='Meeting Notes')
    action_items = fields.One2many('team.project.meeting.action', 'meeting_id', string='Action Items')
    
    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='planned', tracking=True)
    
    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        for meeting in self:
            if meeting.start_datetime and meeting.end_datetime:
                delta = meeting.end_datetime - meeting.start_datetime
                meeting.duration = delta.total_seconds() / 3600
            else:
                meeting.duration = 0.0
    
    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime(self):
        for record in self:
            if record.start_datetime and record.end_datetime:
                if record.start_datetime > record.end_datetime:
                    raise ValidationError(_('Start time must be before end time.'))
    
    # Methods for calendar integration
    def action_notify_attendees(self):
        """Send meeting invitation to attendees"""
        for meeting in self:
            for attendee in meeting.attendee_ids:
                if attendee.user_id:
                    self.env['team.project.notification'].create_project_notification(
                        model='team.project.meeting',
                        res_id=meeting.id,
                        type='meeting_scheduled',
                        title=f"Undangan Rapat: {meeting.name}",
                        message=f"""
                            Anda diundang ke rapat:
                            {meeting.name}
                            Tanggal: {meeting.start_datetime.strftime('%Y-%m-%d %H:%M')} sampai {meeting.end_datetime.strftime('%H:%M')}
                            Lokasi: {meeting.location or 'Belum ditentukan'}
                            Penyelenggara: {meeting.organizer_id.name}
                        """,
                        project_id=meeting.project_id.id if meeting.project_id else False,
                        sender_id=meeting.organizer_id.id,
                        # recipient_id=attendee.id,
                        user_id=attendee.user_id.id,  # Tambahkan user_id eksplisit
                        category='meeting_scheduled',
                        data={
                            'meeting_id': meeting.id,
                            'project_id': meeting.project_id.id if meeting.project_id else False,
                            'action': 'view_meeting'
                        },
                        # priority='medium'
                    )
    
    def action_start_meeting(self):
        self.write({'state': 'in_progress'})
    
    def action_end_meeting(self):
        self.write({'state': 'done'})
    
    def action_cancel_meeting(self):
        self.write({'state': 'cancelled'})
        
        # Notify attendees of cancellation
        for meeting in self:
            for attendee in meeting.attendee_ids:
                if attendee.user_id:
                    self.env['team.project.notification'].create_project_notification(
                        model='team.project.meeting',
                        res_id=meeting.id,
                        type='meeting_cancelled',
                        title=f"Rapat Dibatalkan: {meeting.name}",
                        message=f"Rapat {meeting.name} yang dijadwalkan pada {meeting.start_datetime.strftime('%Y-%m-%d %H:%M')} telah dibatalkan.",
                        project_id=meeting.project_id.id if meeting.project_id else False,
                        sender_id=self.env.user.employee_id.id,
                        # recipient_id=attendee.id,
                        user_id=attendee.user_id.id,  # Tambahkan user_id eksplisit
                        category='meeting_scheduled',
                        data={
                            'meeting_id': meeting.id,
                            'project_id': meeting.project_id.id if meeting.project_id else False,
                            'action': 'view_meeting'
                        },
                        # priority='high'
                    )

class TeamProjectMeetingAction(models.Model):
    _name = 'team.project.meeting.action'
    _description = 'Meeting Action Item'
    _order = 'due_date, id'
    
    name = fields.Char(string='Action Item', required=True)
    meeting_id = fields.Many2one('team.project.meeting', string='Meeting', required=True, ondelete='cascade')
    assigned_to = fields.Many2one('hr.employee', string='Assigned To', required=True)
    due_date = fields.Date(string='Due Date')
    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='todo')
    notes = fields.Text(string='Notes')
    
    def action_mark_done(self):
        self.write({'state': 'done'})
    
    def action_mark_in_progress(self):
        self.write({'state': 'in_progress'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})