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
        # Tambahkan log untuk debugging
        _logger.info(f"Creating/updating notification: model={model}, res_id={res_id}, type={type}")
        
        # Jika model atau res_id tidak valid, log error dan return False
        if not model or not res_id:
            _logger.error(f"Invalid model({model}) or res_id({res_id})")
            return False
        
        # Cari notifikasi yang sudah ada untuk model, res_id, dan type tertentu
        existing = self.search([
            ('model', '=', model), 
            ('res_id', '=', res_id), 
            ('type', '=', type)
        ], limit=1)
        
        # Jika data adalah dictionary, konversi ke JSON string
        data_str = False
        if data:
            if isinstance(data, dict):
                data_str = json.dumps(data)
            else:
                data_str = data
        
        values = {
            'model': model,
            'res_id': res_id,
            'type': type,
            'title': title,
            'message': message,
            'request_time': request_time or fields.Datetime.now(),
            'data': data_str,
            'is_read': False if not existing else existing.is_read  
        }
        
        try:
            if existing:
                # Update existing notification
                existing.write(values)
                _logger.info(f"Updated existing notification ID {existing.id} for {model}/{res_id}")
                return existing
            else:
                # Create new notification
                new_notif = self.create(values)
                _logger.info(f"Created new notification ID {new_notif.id} for {model}/{res_id}")
                return new_notif
        except Exception as e:
            _logger.error(f"Error in create_or_update_notification: {str(e)}")
            return False