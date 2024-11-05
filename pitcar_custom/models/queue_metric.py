from odoo import models, fields, api
from datetime import datetime
import pytz

class QueueMetric(models.Model):
    _name = 'queue.metric'
    _description = 'Queue Metric'
    _order = 'sequence'

    name = fields.Char('Name', required=True)
    value = fields.Char('Value', required=True)
    icon = fields.Char('Icon', default='circle')  # Default icon
    color_class = fields.Char('Color Class')
    sequence = fields.Integer('Sequence', default=10)
    metric_type = fields.Selection([
        ('summary', 'Overall Summary'),
        ('current', 'Nomor Saat Ini'),
        ('active', 'Sedang Dilayani'),
        ('completed', 'Selesai'),
        ('waiting', 'Menunggu'),
        ('regular', 'Regular'),
        ('priority', 'Prioritas')
    ], string='Tipe Metrik', required=True)
    date = fields.Date('Date', default=fields.Date.context_today)
    subtitle = fields.Char('Subtitle')  # Untuk informasi tambahan
    last_update = fields.Datetime('Last Updated', default=fields.Datetime.now)

    @api.model
    def refresh_metrics(self):
        """Update metrics from queue management"""
        queue_mgmt = self.env['queue.management'].search([
            ('date', '=', fields.Date.today())
        ], limit=1)

        if queue_mgmt:
             # Dapatkan next queue number
            next_queue = queue_mgmt.get_next_queue()
            next_number = next_queue.display_number if next_queue else '-'
            next_subtitle = f'Nomor selanjutnya yang akan dipanggil' if next_queue else 'Tidak ada antrian menunggu'

            # Calculate average service time
            avg_time = queue_mgmt.average_service_time
            time_str = f"{int(avg_time)} menit" if avg_time else "N/A"

            tz = pytz.timezone('Asia/Jakarta')
            local_dt = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
            last_update_str = local_dt.strftime('%H:%M:%S WIB')
            
            # Hitung total antrian (termasuk yang sudah selesai dan sedang menunggu)
            total_queues = queue_mgmt.last_number + queue_mgmt.last_priority_number
            active_number = queue_mgmt.active_order_id.queue_line_id.display_number if queue_mgmt.active_order_id and queue_mgmt.active_order_id.queue_line_id else '-'

            metrics = {
                'summary': {
                'name': 'Overall Summary',
                'value': fields.Date.today().strftime('%d %B %Y'),
                'subtitle': f'Rata-rata waktu pelayanan: {time_str}\nTerakhir diperbarui: {last_update_str}',
                'icon': 'calendar',
                'color_class': 'bg-purple',
                'sequence': 0,
              },
              'current': {
                  'name': 'Nomor Antrean Saat Ini',
                  'value': active_number,  # Menggunakan display_number dari active order
                  'subtitle': f'Dari total {total_queues} antrian',
                  'icon': 'list-ol',
                  'color_class': 'bg-primary',
                  'sequence': 1,
              },
              'active': {
                  'name': 'Nomor Selanjutnya',
                  'value': next_number,
                  'subtitle': next_subtitle,
                  'icon': 'users',
                  'color_class': 'bg-info',
                  'sequence': 2,
              },
              'completed': {
                  'name': 'Selesai',
                  'value': str(queue_mgmt.total_served),
                  'subtitle': f'Dari total {total_queues} antrian',
                  'icon': 'check-circle',
                  'color_class': 'bg-success',
                  'sequence': 3,
              },
              'waiting': {
                  'name': 'Menunggu',
                  'value': str(queue_mgmt.waiting_count),
                  'subtitle': f'Dari total {total_queues} antrian',
                  'icon': 'hourglass-half',
                  'color_class': 'bg-warning',
                  'sequence': 4,
              },
              'regular': {
                  'name': 'Regular',
                  'value': str(queue_mgmt.last_number),
                  'subtitle': 'Total Antrean Regular',
                  'icon': 'user',
                  'color_class': 'bg-secondary',
                  'sequence': 5,
              },
              'priority': {
                  'name': 'Prioritas',
                  'value': str(queue_mgmt.last_priority_number),
                  'subtitle': 'Total Antrean Booking',
                  'icon': 'star',
                  'color_class': 'bg-primary',
                  'sequence': 6,
              }
            }

            # Update or create metrics
            for metric_type, data in metrics.items():
                metric = self.search([
                    ('metric_type', '=', metric_type),
                    ('date', '=', fields.Date.today())
                ], limit=1)
                
                vals = {
                    'name': data['name'],
                    'value': data['value'],
                    'subtitle': data['subtitle'],
                    'icon': data['icon'],
                    'color_class': data['color_class'],
                    'sequence': data['sequence'],
                    'last_update': fields.Datetime.now(),
                }

                if metric:
                    metric.write(vals)
                else:
                    vals['metric_type'] = metric_type
                    vals['date'] = fields.Date.today()
                    self.create(vals)