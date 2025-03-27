# models/kaizen_training.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import pytz
import logging

_logger = logging.getLogger(__name__)

class KaizenTrainingProgram(models.Model):
    _name = 'kaizen.training.program'
    _description = 'Program Pelatihan Tim Kaizen'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Nama Pelatihan', required=True, tracking=True)
    code = fields.Char('Kode Pelatihan', copy=False, readonly=True)
    description = fields.Text('Deskripsi', tracking=True)
    
    # Timestamps dengan timezone Jakarta
    date_start = fields.Datetime('Tanggal Mulai', required=True, tracking=True)
    date_end = fields.Datetime('Tanggal Selesai', required=True, tracking=True)
    
    # Orang-orang terkait
    creator_id = fields.Many2one('hr.employee', string='Pembuat/Perencana', required=True, 
                                tracking=True, default=lambda self: self.env.user.employee_id.id)
    instructor_id = fields.Many2one('hr.employee', string='Instruktur', required=True, tracking=True)
    verifier_id = fields.Many2one('hr.employee', string='Verifikator', required=True, tracking=True)
    
    # Status tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('planned', 'Direncanakan'),
        ('ongoing', 'Sedang Berjalan'),
        ('completed', 'Selesai'),
        ('cancelled', 'Dibatalkan')
    ], string='Status', default='draft', tracking=True)
    
    # Peserta (many2many langsung ke karyawan)
    attendee_ids = fields.Many2many('hr.employee', 'kaizen_training_attendee_rel', 
                                   'training_id', 'employee_id', string='Peserta')
    attendee_count = fields.Integer('Jumlah Peserta', compute='_compute_attendee_count', store=True)
    
    # Target dan pencapaian
    target_participants = fields.Integer('Target Peserta', required=True, tracking=True)
    
    # Material dan sumber daya
    training_material_ids = fields.One2many('kaizen.training.material', 'training_id', string='Materi Pelatihan')
    location = fields.Char('Lokasi Pelatihan', tracking=True)
    
    # Catatan kegiatan
    attendance_date = fields.Date('Tanggal Absensi')
    attendance_taken = fields.Boolean('Absensi Diambil', default=False)
    
    # Rating
    rating_ids = fields.One2many('kaizen.training.rating', 'training_id', string='Penilaian Peserta')
    
    # Metrik kinerja
    average_rating = fields.Float('Rating Rata-rata', compute='_compute_average_rating', store=True, digits=(2,1))
    success_rate = fields.Float('Tingkat Keberhasilan (%)', compute='_compute_success_rate', store=True)
    
    # Buat kode unik otomatis untuk setiap program pelatihan
    @api.model
    def create(self, vals):
        if not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('kaizen.training.program') or 'TRAIN-NEW'
        return super(KaizenTrainingProgram, self).create(vals)
    
    # Hitung jumlah peserta
    @api.depends('attendee_ids')
    def _compute_attendee_count(self):
        for record in self:
            record.attendee_count = len(record.attendee_ids)
    
    # Hitung rating rata-rata
    @api.depends('rating_ids.rating_value')
    def _compute_average_rating(self):
        for record in self:
            ratings = record.rating_ids.mapped('rating_value')
            record.average_rating = sum(ratings) / len(ratings) if ratings else 0.0
    
    # Hitung tingkat keberhasilan berdasarkan target peserta
    @api.depends('attendee_count', 'target_participants')
    def _compute_success_rate(self):
        for record in self:
            record.success_rate = (record.attendee_count / record.target_participants * 100) if record.target_participants else 0.0
    
    # Validasi bahwa tanggal akhir adalah setelah tanggal mulai
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_start > record.date_end:
                raise ValidationError(_("Tanggal akhir tidak boleh sebelum tanggal mulai."))
    
    # Metode perubahan status
    def action_set_to_planned(self):
        self.write({'state': 'planned'})
    
    def action_start_training(self):
        self.write({'state': 'ongoing'})
    
    def action_complete_training(self):
        self.write({'state': 'completed'})
    
    def action_cancel_training(self):
        self.write({'state': 'cancelled'})
    
    # Mengambil absensi peserta
    def action_take_attendance(self):
        self.write({
            'attendance_taken': True,
            'attendance_date': fields.Date.today()
        })


class KaizenTrainingRating(models.Model):
    _name = 'kaizen.training.rating'
    _description = 'Penilaian Pelatihan Kaizen'
    
    training_id = fields.Many2one('kaizen.training.program', string='Program Pelatihan', required=True, ondelete='cascade')
    attendee_id = fields.Many2one('hr.employee', string='Peserta', required=True, domain="[('id', 'in', training_attendee_ids)]")
    training_attendee_ids = fields.Many2many('hr.employee', related='training_id.attendee_ids')
    
    rater_id = fields.Many2one('hr.employee', string='Pemberi Nilai', required=True, help="Orang yang memberikan penilaian")
    
    rating_date = fields.Datetime('Tanggal Penilaian', default=fields.Datetime.now)
    rating_value = fields.Float('Nilai Rating', required=True, digits=(2,1))
    
    content_quality_rating = fields.Selection([
        ('1', 'Buruk'),
        ('2', 'Di Bawah Rata-rata'),
        ('3', 'Rata-rata'),
        ('4', 'Baik'),
        ('5', 'Sangat Baik')
    ], string='Kualitas Konten')
    
    instructor_rating = fields.Selection([
        ('1', 'Buruk'),
        ('2', 'Di Bawah Rata-rata'),
        ('3', 'Rata-rata'),
        ('4', 'Baik'),
        ('5', 'Sangat Baik')
    ], string='Kinerja Instruktur')
    
    material_rating = fields.Selection([
        ('1', 'Buruk'),
        ('2', 'Di Bawah Rata-rata'),
        ('3', 'Rata-rata'),
        ('4', 'Baik'),
        ('5', 'Sangat Baik')
    ], string='Materi')
    
    organization_rating = fields.Selection([
        ('1', 'Buruk'),
        ('2', 'Di Bawah Rata-rata'),
        ('3', 'Rata-rata'),
        ('4', 'Baik'),
        ('5', 'Sangat Baik')
    ], string='Organisasi')
    
    notes = fields.Text('Catatan Feedback')
    
    _sql_constraints = [
        ('unique_attendee_rating', 'UNIQUE(training_id, attendee_id)', 'Peserta ini sudah memberikan penilaian!')
    ]
    
    @api.constrains('rating_value')
    def _check_rating_value(self):
        for record in self:
            if record.rating_value < 1.0 or record.rating_value > 5.0:
                raise ValidationError(_("Nilai rating harus antara 1 dan 5."))


class KaizenTrainingMaterial(models.Model):
    _name = 'kaizen.training.material'
    _description = 'Materi Pelatihan Kaizen'
    
    training_id = fields.Many2one('kaizen.training.program', string='Program Pelatihan', required=True, ondelete='cascade')
    name = fields.Char('Nama Materi', required=True)
    description = fields.Text('Deskripsi')
    
    attachment_ids = fields.Many2many('ir.attachment', string='Lampiran')
    material_type = fields.Selection([
        ('document', 'Dokumen'),
        ('video', 'Video'),
        ('presentation', 'Presentasi'),
        ('exercise', 'Latihan'),
        ('other', 'Lainnya')
    ], string='Jenis Materi', default='document')
    
    sequence = fields.Integer('Urutan', default=10)
    is_mandatory = fields.Boolean('Wajib', default=True)