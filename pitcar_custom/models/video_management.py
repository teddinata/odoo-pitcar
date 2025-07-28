from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import base64
import os
import mimetypes

class VideoManagement(models.Model):
    _name = 'video.management'
    _description = 'Video Management for Dashboard'
    _order = 'sequence, create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Video Title', required=True, tracking=True)
    description = fields.Text('Description', tracking=True)
    
    # Video file
    video_file = fields.Binary('Video File', required=True, tracking=True)
    video_filename = fields.Char('Video Filename')
    video_url = fields.Char('Video URL', compute='_compute_video_url', store=True)
    video_size = fields.Float('File Size (MB)', compute='_compute_video_size', store=True)
    video_duration = fields.Float('Duration (minutes)', help="Video duration in minutes")
    
    # Video metadata
    video_format = fields.Char('Video Format', compute='_compute_video_format', store=True)
    resolution = fields.Char('Resolution', help="e.g., 1920x1080")
    aspect_ratio = fields.Selection([
        ('16:9', '16:9 (Widescreen)'),
        ('4:3', '4:3 (Standard)'),
        ('1:1', '1:1 (Square)'),
        ('9:16', '9:16 (Vertical)'),
    ], string='Aspect Ratio')
    
    # Display settings
    sequence = fields.Integer('Sequence', default=10, help="Order of video in playlist")
    active = fields.Boolean('Active', default=True, tracking=True)
    is_featured = fields.Boolean('Featured Video', help="Show as featured in dashboard")
    
    # Status and scheduling
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True)
    
    publish_date = fields.Datetime('Publish Date', tracking=True)
    expire_date = fields.Datetime('Expire Date', tracking=True)
    
    # Categories and tags
    category_id = fields.Many2one('video.category', string='Category')
    tag_ids = fields.Many2many('video.tag', string='Tags')
    
    # Analytics
    view_count = fields.Integer('View Count', default=0)
    last_viewed = fields.Datetime('Last Viewed')
    
    # Display preferences
    autoplay = fields.Boolean('Auto Play', default=True)
    loop_video = fields.Boolean('Loop Video', default=True)
    show_controls = fields.Boolean('Show Controls', default=True)
    muted = fields.Boolean('Start Muted', default=True, 
                          help="Start video muted (recommended for autoplay)")
    
    # Company
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company)

    @api.depends('video_file')
    def _compute_video_size(self):
        for record in self:
            if record.video_file:
                # Calculate size in MB
                size_bytes = len(base64.b64decode(record.video_file))
                record.video_size = round(size_bytes / (1024 * 1024), 2)
            else:
                record.video_size = 0

    @api.depends('video_filename')
    def _compute_video_format(self):
        for record in self:
            if record.video_filename:
                _, ext = os.path.splitext(record.video_filename)
                record.video_format = ext.upper().replace('.', '') if ext else ''
            else:
                record.video_format = ''

    @api.depends('video_file', 'video_filename')
    def _compute_video_url(self):
        for record in self:
            if record.video_file and record.id:
                # Generate URL for video access
                record.video_url = f'/web/content/video.management/{record.id}/video_file/{record.video_filename or "video"}'
            else:
                record.video_url = ''

    @api.constrains('video_file', 'video_filename')
    def _check_video_file(self):
        for record in self:
            if record.video_file:
                # Check file size (max 100MB)
                if record.video_size > 100:
                    raise ValidationError(_("Video file size cannot exceed 100MB. Current size: %.2f MB") % record.video_size)
                
                # Check file format
                if record.video_filename:
                    allowed_formats = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv']
                    _, ext = os.path.splitext(record.video_filename.lower())
                    if ext not in allowed_formats:
                        raise ValidationError(_("Only video files are allowed: %s") % ', '.join(allowed_formats))

    @api.constrains('publish_date', 'expire_date')
    def _check_dates(self):
        for record in self:
            if record.publish_date and record.expire_date:
                if record.expire_date <= record.publish_date:
                    raise ValidationError(_("Expire date must be after publish date"))

    def action_publish(self):
        """Publish video"""
        self.ensure_one()
        if not self.video_file:
            raise UserError(_("Cannot publish video without file"))
        
        self.write({
            'state': 'published',
            'publish_date': fields.Datetime.now()
        })

    def action_archive(self):
        """Archive video"""
        self.write({'state': 'archived'})

    def action_reset_to_draft(self):
        """Reset to draft"""
        self.write({
            'state': 'draft',
            'publish_date': False
        })

    def action_increment_view(self):
        """Increment view count"""
        self.sudo().write({
            'view_count': self.view_count + 1,
            'last_viewed': fields.Datetime.now()
        })

    @api.model
    def get_dashboard_videos(self):
        """Get videos for dashboard display"""
        domain = [
            ('state', '=', 'published'),
            ('active', '=', True),
            '|',
            ('expire_date', '=', False),
            ('expire_date', '>', fields.Datetime.now())
        ]
        
        videos = self.search(domain, order='sequence, create_date desc')
        
        return [{
            'id': video.id,
            'name': video.name,
            'description': video.description,
            'url': video.video_url,
            'sequence': video.sequence,
            'duration': video.video_duration,
            'autoplay': video.autoplay,
            'loop': video.loop_video,
            'controls': video.show_controls,
            'muted': video.muted,
            'category': video.category_id.name if video.category_id else None,
            'tags': [tag.name for tag in video.tag_ids],
            'is_featured': video.is_featured
        } for video in videos]

    @api.model
    def get_featured_video(self):
        """Get featured video for dashboard"""
        video = self.search([
            ('state', '=', 'published'),
            ('active', '=', True),
            ('is_featured', '=', True),
            '|',
            ('expire_date', '=', False),
            ('expire_date', '>', fields.Datetime.now())
        ], limit=1)
        
        if video:
            video.action_increment_view()
            return {
                'id': video.id,
                'name': video.name,
                'url': video.video_url,
                'autoplay': video.autoplay,
                'loop': video.loop_video,
                'muted': video.muted
            }
        return None


class VideoCategory(models.Model):
    _name = 'video.category'
    _description = 'Video Category'
    _order = 'name'

    name = fields.Char('Category Name', required=True)
    description = fields.Text('Description')
    color = fields.Integer('Color Index')
    video_count = fields.Integer('Video Count', compute='_compute_video_count')

    @api.depends('name')
    def _compute_video_count(self):
        for category in self:
            category.video_count = self.env['video.management'].search_count([
                ('category_id', '=', category.id)
            ])


class VideoTag(models.Model):
    _name = 'video.tag'
    _description = 'Video Tag'
    _order = 'name'

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer('Color Index')
    video_count = fields.Integer('Video Count', compute='_compute_video_count')

    @api.depends('name')
    def _compute_video_count(self):
        for tag in self:
            tag.video_count = self.env['video.management'].search_count([
                ('tag_ids', 'in', tag.id)
            ])