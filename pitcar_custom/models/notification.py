from odoo import models, fields, api, _
import json
from datetime import datetime, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)

class Notification(models.Model):
    _name = 'pitcar.notification'
    _description = 'Global Notification'
    _order = 'create_date desc'

    # Field generik untuk referensi ke model apa pun
    model = fields.Char(string='Model', required=True)  # Nama model, misalnya 'sale.order'
    res_id = fields.Integer(string='Record ID', required=True)  # ID record di model tersebut
    name = fields.Char(string='Name', compute='_compute_name', store=True)  # Nama record terkait
    
    # Field notifikasi
    type = fields.Char(string='Type', required=True)  # Jenis notifikasi, misalnya 'new_request'
    title = fields.Char(string='Title', required=True)
    message = fields.Char(string='Message', required=True)
    data = fields.Text(string='Data', help='Additional data in JSON format')  # Untuk menyimpan informasi spesifik
    is_read = fields.Boolean(string='Is Read', default=False)
    create_date = fields.Datetime(string='Created On', readonly=True)
    request_time = fields.Datetime(string='Request Time', required=True)  # Waktu kejadian

    @api.depends('model', 'res_id')
    def _compute_name(self):
        for record in self:
            if record.model and record.res_id:
                try:
                    model_obj = self.env[record.model].browse(record.res_id)
                    record.name = model_obj.name if model_obj.exists() else 'Record Not Found'
                except Exception as e:
                    _logger.warning(f"Error computing name for {record.model}/{record.res_id}: {e}")
                    record.name = 'Unknown'
            else:
                record.name = 'Unknown'

    @api.model
    def create_or_update_notification(self, model, res_id, type, title, message, request_time=None, data=None):
        """Create or update a notification for any model"""
        existing = self.search([('model', '=', model), ('res_id', '=', res_id), ('type', '=', type)], limit=1)
        values = {
            'model': model,
            'res_id': res_id,
            'type': type,
            'title': title,
            'message': message,
            'request_time': request_time or fields.Datetime.now(),
            'data': json.dumps(data) if data else False,
            'is_read': False if not existing else existing.is_read
        }
        if existing:
            existing.write(values)
            return existing
        return self.create(values)