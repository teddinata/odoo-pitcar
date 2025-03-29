# models/it_system.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ITSystem(models.Model):
    _name = 'it.system'
    _description = 'IT System'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Nama Sistem', required=True, tracking=True)
    code = fields.Char('Kode Sistem', copy=False, readonly=True, 
                     default=lambda self: self.env['ir.sequence'].next_by_code('it.system'))
    description = fields.Text('Deskripsi', tracking=True)
    
    # Metadata
    creation_date = fields.Date('Tanggal Pembuatan', default=fields.Date.today, tracking=True)
    launch_date = fields.Date('Tanggal Launching', tracking=True)
    version = fields.Char('Versi', tracking=True, default='1.0')
    state = fields.Selection([
        ('development', 'Dalam Pengembangan'),
        ('testing', 'Dalam Pengujian'),
        ('production', 'Produksi'),
        ('maintenance', 'Pemeliharaan'),
        ('retired', 'Tidak Digunakan')
    ], string='Status', default='development', tracking=True)
    
    # Hubungan ke proyek - gunakan compute field untuk mencari project terkait
    project_id = fields.Many2one('team.project', string='Project Pengembangan',
                               compute='_compute_related_project', store=True)
    
    # Dokumentasi
    documentation_complete = fields.Boolean('Dokumentasi Lengkap', default=False, tracking=True)
    documentation_url = fields.Char('URL Dokumentasi')
    user_manual_attachment_id = fields.Many2one('ir.attachment', string='Manual Pengguna')
    technical_doc_attachment_id = fields.Many2one('ir.attachment', string='Dokumentasi Teknis')
    
    # Sosialisasi
    socialization_date = fields.Date('Tanggal Sosialisasi')
    socialization_complete = fields.Boolean('Sosialisasi Lengkap', default=False, tracking=True)
    
    # Fitur system
    feature_ids = fields.One2many('it.system.feature', 'system_id', string='Fitur')
    feature_count = fields.Integer('Jumlah Fitur', compute='_compute_feature_count')
    
    # Metrik kualitas
    error_report_ids = fields.One2many('it.error.report', 'system_id', string='Laporan Error')
    error_count = fields.Integer('Jumlah Error Dilaporkan', compute='_compute_error_count')
    error_free_days = fields.Integer('Hari Tanpa Error', compute='_compute_error_free_days')
    
    # Ratings
    rating_ids = fields.One2many('it.system.rating', 'system_id', string='Ratings')
    average_rating = fields.Float('Rating Rata-rata', compute='_compute_average_rating', store=True, digits=(2,1))

    # Ganti single attachment dengan many2many
    document_attachment_ids = fields.Many2many('ir.attachment', 'it_system_attachment_rel', 
                                            'system_id', 'attachment_id', string='Dokumen Sistem')
    
    # Compute methods
    @api.depends('name')
    def _compute_related_project(self):
        for system in self:
            project = self.env['team.project'].search([
                ('department_id.name', 'ilike', 'IT'),
                ('project_type', '=', 'development'),
                ('name', 'ilike', system.name)
            ], limit=1)
            
            if project:
                system.project_id = project.id
            else:
                system.project_id = False
    
    @api.depends('feature_ids')
    def _compute_feature_count(self):
        for system in self:
            system.feature_count = len(system.feature_ids)
    
    @api.depends('rating_ids.rating_value')
    def _compute_average_rating(self):
        for system in self:
            if system.rating_ids:
                system.average_rating = sum(system.rating_ids.mapped('rating_value')) / len(system.rating_ids)
            else:
                system.average_rating = 0.0
    
    def _compute_error_count(self):
        for system in self:
            system.error_count = len(system.error_report_ids)
    
    def _compute_error_free_days(self):
        for system in self:
            if system.error_count == 0:
                base_date = system.launch_date or system.creation_date or fields.Date.today()
                delta = fields.Date.today() - base_date
                system.error_free_days = delta.days
            else:
                last_error = self.env['it.error.report'].search([
                    ('system_id', '=', system.id),
                    ('reported_date', '!=', False)
                ], order='reported_date desc', limit=1)
                
                if last_error:
                    last_error_date = fields.Date.from_string(last_error.reported_date)
                    delta = fields.Date.today() - last_error_date
                    system.error_free_days = delta.days
                else:
                    system.error_free_days = 0

class ITSystemFeature(models.Model):
    _name = 'it.system.feature'
    _description = 'Fitur Sistem IT'
    _order = 'sequence, name'
    
    name = fields.Char('Nama Fitur', required=True)
    sequence = fields.Integer('Urutan', default=10)
    system_id = fields.Many2one('it.system', string='Sistem', required=True, ondelete='cascade')
    description = fields.Text('Deskripsi Fitur')
    
    # Status implementasi
    state = fields.Selection([
        ('planned', 'Direncanakan'),
        ('in_progress', 'Dalam Pengembangan'),
        ('completed', 'Selesai'),
        ('deferred', 'Ditunda')
    ], string='Status', default='planned', tracking=True)
    
    # Dokumentasi
    has_documentation = fields.Boolean('Memiliki Dokumentasi', default=False)
    documentation_url = fields.Char('URL Dokumentasi Fitur')
    # Ganti single attachment dengan many2many
    document_attachment_ids = fields.Many2many('ir.attachment', 'it_system_feature_attachment_rel', 
                                            'feature_id', 'attachment_id', string='Dokumen Fitur')

    
    # Sub-fitur
    parent_id = fields.Many2one('it.system.feature', string='Fitur Induk')
    child_ids = fields.One2many('it.system.feature', 'parent_id', string='Sub-Fitur')
    
    # Pengguna yang bertanggung jawab
    responsible_id = fields.Many2one('hr.employee', string='Penanggung Jawab')

class ITSystemRating(models.Model):
    _name = 'it.system.rating'
    _description = 'Rating Sistem IT'
    
    system_id = fields.Many2one('it.system', string='Sistem', required=True, ondelete='cascade')
    rater_id = fields.Many2one('hr.employee', string='Penilai', required=True)
    department_id = fields.Many2one(related='rater_id.department_id', string='Departemen')
    
    rating_date = fields.Date('Tanggal Penilaian', default=fields.Date.today)
    
    # Rating
    rating_value = fields.Float('Nilai Rating', required=True, digits=(2,1))
    
    # Kriteria penilaian (skala 1-5)
    usability_rating = fields.Selection([
        ('1', 'Sangat Buruk'),
        ('2', 'Buruk'),
        ('3', 'Cukup'),
        ('4', 'Baik'),
        ('5', 'Sangat Baik')
    ], string='Kemudahan Penggunaan')
    
    performance_rating = fields.Selection([
        ('1', 'Sangat Buruk'),
        ('2', 'Buruk'),
        ('3', 'Cukup'),
        ('4', 'Baik'),
        ('5', 'Sangat Baik')
    ], string='Performa')
    
    reliability_rating = fields.Selection([
        ('1', 'Sangat Buruk'),
        ('2', 'Buruk'),
        ('3', 'Cukup'),
        ('4', 'Baik'),
        ('5', 'Sangat Baik')
    ], string='Keandalan')
    
    feedback = fields.Text('Umpan Balik / Saran')
    
    _sql_constraints = [
        ('unique_system_rater', 'UNIQUE(system_id, rater_id)', 
         'Pengguna ini sudah memberikan penilaian untuk sistem ini!')
    ]
    
    @api.constrains('rating_value')
    def _check_rating_value(self):
        for record in self:
            if record.rating_value < 1.0 or record.rating_value > 5.0:
                raise ValidationError(_("Nilai rating harus antara 1 dan 5."))

class ITErrorReport(models.Model):
    _name = 'it.error.report'
    _description = 'Laporan Error Sistem IT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reported_date desc, id desc'
    
    name = fields.Char('Judul Error', required=True, tracking=True)
    system_id = fields.Many2one('it.system', string='Sistem', required=True, tracking=True)
    reported_by_id = fields.Many2one('hr.employee', string='Dilaporkan Oleh', 
                                   default=lambda self: self.env.user.employee_id.id, tracking=True)
    reported_date = fields.Datetime('Tanggal Dilaporkan', default=fields.Datetime.now, tracking=True)
    
    severity = fields.Selection([
        ('critical', 'Kritis'),
        ('high', 'Tinggi'),
        ('medium', 'Sedang'),
        ('low', 'Rendah')
    ], string='Tingkat Keparahan', default='medium', tracking=True)
    
    description = fields.Text('Deskripsi Error', required=True)
    steps_to_reproduce = fields.Text('Langkah Reproduksi')
    
    assigned_to_id = fields.Many2one('hr.employee', string='Ditugaskan Kepada', tracking=True)
    resolution_date = fields.Datetime('Tanggal Penyelesaian', tracking=True)
    resolution = fields.Text('Penyelesaian')
    
    state = fields.Selection([
        ('new', 'Baru'),
        ('in_progress', 'Sedang Ditangani'),
        ('resolved', 'Terselesaikan'),
        ('closed', 'Ditutup'),
        ('reopened', 'Dibuka Kembali')
    ], string='Status', default='new', tracking=True)
    
    # Untuk melacak berapa lama penyelesaian
    resolution_time = fields.Float('Waktu Penyelesaian (Jam)', compute='_compute_resolution_time', store=True)
    
    @api.depends('reported_date', 'resolution_date', 'state')
    def _compute_resolution_time(self):
        for error in self:
            if error.reported_date and error.resolution_date and error.state in ['resolved', 'closed']:
                delta = error.resolution_date - error.reported_date
                # Konversi ke jam
                error.resolution_time = delta.total_seconds() / 3600
            else:
                error.resolution_time = 0.0

  