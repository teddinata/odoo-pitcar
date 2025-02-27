from odoo import models, fields, api, _
import json
from datetime import datetime, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)

class Notification(models.Model):
    _name = 'pitcar.notification'
    _description = 'Global Notification'
    _order = 'request_time desc'

    model = fields.Char(string='Model', required=True)
    res_id = fields.Integer(string='Record ID', required=True)
    name = fields.Char(string='Name', compute='_compute_name', store=True)
    type = fields.Char(string='Type', required=True)
    title = fields.Char(string='Title', required=True)
    message = fields.Char(string='Message', required=True)
    data = fields.Text(string='Data')
    is_read = fields.Boolean(string='Is Read', default=False)
    create_date = fields.Datetime(string='Created On', readonly=True)
    request_time = fields.Datetime(string='Request Time', required=True)

    @api.depends('model', 'res_id')
    def _compute_name(self):
        for record in self:
            if record.model and record.res_id:
                try:
                    model_obj = self.env[record.model].sudo().browse(record.res_id)
                    if model_obj.exists() and hasattr(model_obj, 'name'):
                        record.name = model_obj.name
                    else:
                        record.name = f"{record.model} #{record.res_id} (Not Found)"
                except Exception as e:
                    _logger.warning(f"Error computing name for {record.model}/{record.res_id}: {e}")
                    record.name = f"{record.model} #{record.res_id} (Error)"
            else:
                record.name = 'Unknown'

    @api.model
    def create_or_update_notification(self, model, res_id, type, title, message, request_time=None, data=None):
        # Cari notifikasi yang sudah ada untuk model dan res_id tertentu
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
            _logger.info(f"Updated existing notification for {model}/{res_id}")
            return existing
        new_notif = self.create(values)
        _logger.info(f"Created new notification for {model}/{res_id}")
        return new_notif