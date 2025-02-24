from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import pytz
import logging as _logger
from dateutil.relativedelta import relativedelta

class QueueManagement(models.Model):
    _name = 'queue.management'
    _description = 'Queue Management'

    date = fields.Date(required=True, index=True)
    last_number = fields.Integer(default=0)
    last_priority_number = fields.Integer(default=0)  # Nomor khusus untuk priority
    current_number = fields.Integer(default=0)
    average_service_time = fields.Float(
        string='Average Service Time (minutes)', 
        default=15,
        help='Average time to serve one customer'
    )
    queue_start_time = fields.Datetime()
    max_priority_slot = fields.Integer(
        string='Slot Antrean Prioritas',
        default=30,
        help='Maksimum slot untuk antrian prioritas per hari'
    )
    
    # Statistics fields
    total_served = fields.Integer(default=0)
    total_priority_served = fields.Integer(default=0)
    total_service_time = fields.Float(default=0)
    active_order_id = fields.Many2one('sale.order', string='Current Active Order')
    
    # Queue records
    queue_line_ids = fields.One2many('queue.management.line', 'queue_id', string='Queue Lines')

    def write(self, vals):
        res = super().write(vals)
        # Trigger update metrics setiap kali data queue management berubah
        self.env['queue.metric'].refresh_metrics()
        self._broadcast_queue_update()
        return res
    
    def _broadcast_queue_update(self):
        self.ensure_one()
        try:
            message = {
                'type': 'refresh_dashboard',
                'payload': {
                    'timestamp': fields.Datetime.now(),
                    'message': 'refresh'
                }
            }
            self.env['bus.bus']._sendone('queue_dashboard', message)
            _logger.info('Queue update broadcast sent: %s', message)
        except Exception as e:
            _logger.error('Failed to broadcast queue update: %s', str(e))
    
    def assign_queue_number(self, order_id, is_booking=False):
        """Assign queue number to an order with priority handling"""
        self.ensure_one()

        tz = pytz.timezone('Asia/Jakarta')
        utc_dt = fields.Datetime.now()
        local_dt = pytz.utc.localize(utc_dt).astimezone(tz)
        # Convert back to naive datetime in local timezone
        local_time = fields.Datetime.to_string(local_dt.replace(tzinfo=None))
        
        # Check if order already has queue number
        existing_line = self.queue_line_ids.filtered(lambda l: l.order_id.id == order_id)
        if existing_line:
            return self._prepare_queue_info(existing_line.queue_number, existing_line.is_priority)
        
        if is_booking:
            # Check priority slot availability
            priority_count = len(self.queue_line_ids.filtered(lambda l: l.is_priority))
            if priority_count >= self.max_priority_slot:
                raise ValidationError(
                    f'Slot antrian prioritas hari ini sudah penuh (maksimal {self.max_priority_slot} slot)'
                )
            
            # Generate priority number (P-xxx format)
            self.last_priority_number += 1
            queue_number = self.last_priority_number
            is_priority = True
        else:
            # Generate regular number
            self.last_number += 1
            queue_number = self.last_number
            is_priority = False
        
        # Create queue line
        queue_line = self.env['queue.management.line'].create({
            'queue_id': self.id,
            'order_id': order_id,
            'queue_number': queue_number,
            'is_priority': is_priority,
            'status': 'waiting',
            'assigned_time': local_time
        })
        
        # Update sale order with queue_line_id
        sale_order = self.env['sale.order'].browse(order_id)
        sale_order.write({
            'queue_line_id': queue_line.id,
            'car_arrival_time': local_time,
            'sa_jam_masuk': local_time
        })
        
        # Auto-start queue if first number
        if not self.queue_start_time:
            self.queue_start_time = local_time
            
        return self._prepare_queue_info(queue_number, is_priority)

    def _prepare_queue_info(self, queue_number, is_priority):
        """Prepare queue information considering priority"""
        self.ensure_one()
        
        next_queue = self.get_next_queue()
        if next_queue:
            self.current_number = next_queue.queue_number
        else:
            self.current_number = 0
            
        # if not self.current_number:
        #     self.current_number = 1

        # Get all waiting queue lines in service order
        waiting_lines = self.queue_line_ids.filtered(
            lambda l: l.status == 'waiting'
        ).sorted(lambda l: (not l.is_priority, l.queue_number))
        
        # Find position in queue
        current_line = waiting_lines.filtered(
            lambda l: l.queue_number == queue_number and l.is_priority == is_priority
        )
        if not current_line:
            return {'status': 'not_found'}
            
        position = waiting_lines.ids.index(current_line.id)
        numbers_ahead = position
        
        # Calculate estimated wait time
        estimated_wait_time = numbers_ahead * self.average_service_time
        if self.total_served > 0:
            actual_average = self.total_service_time / self.total_served
            estimated_wait_time = numbers_ahead * actual_average

        # Format queue number for display
        display_number = f"P{queue_number:03d}" if is_priority else f"{queue_number:03d}"

        return {
            'queue_number': queue_number,
            'display_number': display_number,
            'is_priority': is_priority,
            'current_number': self.current_number,
            'numbers_ahead': numbers_ahead,
            'estimated_wait_minutes': round(estimated_wait_time),
            'estimated_service_time': fields.Datetime.now() + timedelta(minutes=estimated_wait_time),
            'total_served': self.total_served,
            'average_service_time': round(self.average_service_time, 1)
        }

    def get_next_queue(self):
        """Get next queue number considering priority"""
        self.ensure_one()
        
        # Pisahkan antrian priority dan regular yang sedang menunggu
        waiting_priority = self.queue_line_ids.filtered(
            lambda l: l.status == 'waiting' and l.is_priority
        ).sorted('queue_number')
        
        waiting_regular = self.queue_line_ids.filtered(
            lambda l: l.status == 'waiting' and not l.is_priority
        ).sorted('queue_number')
        
        # Jika ada antrian priority yang menunggu, ambil itu dulu
        if waiting_priority:
            return waiting_priority[0]
        # Jika tidak ada priority, ambil regular
        elif waiting_regular:
            return waiting_regular[0]
        return False
        
        return waiting_lines[0] if waiting_lines else False

    def start_service(self, order_id):
        """Start service for an order"""
        self.ensure_one()
        queue_line = self.queue_line_ids.filtered(lambda l: l.order_id.id == order_id)
        
        # if not queue_line:
        #     raise UserError('Order tidak memiliki nomor antrian')
            
        # Validate if this is the next queue to be served
        next_queue = self.get_next_queue()
        if not next_queue or next_queue.id != queue_line.id:
            raise UserError(
                f'Tidak dapat memulai pelayanan. Silakan layani antrian nomor {next_queue.display_number if next_queue else "N/A"}'
            )
        
        # Update queue line status
        queue_line.write({
            'status': 'in_progress',
            'start_time': fields.Datetime.now()
        })
        
        # Update active order
        self.write({
            'active_order_id': order_id,
            'current_number': queue_line.queue_number
        })
        
        return True
    
    def complete_service(self, order_id):
        """Complete service and update statistics with priority handling"""
        self.ensure_one()
        queue_line = self.queue_line_ids.filtered(lambda l: l.order_id.id == order_id)
        
        if not queue_line or queue_line.status != 'in_progress':
            return False
            
        end_time = fields.Datetime.now()
        service_duration = (end_time - queue_line.start_time).total_seconds() / 60
        
        queue_line.write({
            'status': 'completed',
            'end_time': end_time,
            'service_duration': service_duration
        })
        
        # Update statistics
        self.total_served += 1
        if queue_line.is_priority:
            self.total_priority_served += 1
        self.total_service_time += service_duration
        self.average_service_time = self.total_service_time / self.total_served
        
        # Get and set next queue
        next_queue = self.get_next_queue()
        if next_queue:
            self.current_number = next_queue.queue_number
        self.active_order_id = False
        
        return True
    
    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    current_number = fields.Integer(string='Nomor Saat Ini', readonly=True)
    active_order_id = fields.Many2one('sale.order', string='Sedang Dilayani', readonly=True)
    total_served = fields.Integer(string='Total Selesai', readonly=True)
    last_number = fields.Integer(string='Total Regular', readonly=True)
    last_priority_number = fields.Integer(string='Total Prioritas', readonly=True)
    waiting_count = fields.Integer(compute='_compute_waiting_count', store=True, string='Jumlah Menunggu')
    queue_line_ids = fields.One2many('queue.management.line', 'queue_id', string='Queue Lines')

    @api.depends('date')
    def _compute_name(self):
        for record in self:
            record.name = f'QUE/{record.date or fields.Date.today()}'

    @api.depends('queue_line_ids', 'queue_line_ids.status')
    def _compute_waiting_count(self):
        for record in self:
            record.waiting_count = len(record.queue_line_ids.filtered(lambda l: l.status == 'waiting'))
    
    @api.depends('queue_line_ids.service_duration')
    def _compute_service_stats(self):
        for record in self:
            completed_lines = record.queue_line_ids.filtered(lambda l: l.status == 'completed')
            total_duration = sum(completed_lines.mapped('service_duration'))
            count_completed = len(completed_lines)
            
            record.total_service_duration = total_duration
            record.average_service_time = total_duration / count_completed if count_completed > 0 else 0

    total_service_duration = fields.Float(
        'Total Service Duration',
        compute='_compute_service_stats',
        store=True,
        help='Total durasi pelayanan dalam menit'
    )
    
    def action_view_detail(self):
        self.ensure_one()
        return {
            'name': f'Detail Antrean - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'queue.management.line',
            'view_mode': 'tree,form',
            'domain': [('queue_id', '=', self.id)],
            'context': {'default_queue_id': self.id},
        }
    
    def init(self):
        super(QueueManagement, self).init()
        # Create index on date field for better performance
        tools.create_index(self._cr, 'queue_management_date_index',
                         self._table, ['date'])

    @api.model
    def action_view_last_7_days(self):
        action = self.env.ref('queue_management.action_queue_management_report').read()[0]
        action['domain'] = [
            ('date', '>=', fields.Date.today() - timedelta(days=6))
        ]
        return action

    @api.model
    def action_view_last_30_days(self):
        action = self.env.ref('queue_management.action_queue_management_report').read()[0]
        action['domain'] = [
            ('date', '>=', fields.Date.today() - timedelta(days=29))
        ]
        return action

class QueueManagementLine(models.Model):
    _name = 'queue.management.line'
    _description = 'Queue Line'
    _order = 'is_priority desc, queue_number'

    queue_id = fields.Many2one('queue.management', required=True, ondelete='cascade')
    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade')
    queue_number = fields.Integer(required=True)
    is_priority = fields.Boolean(string='Is Priority Queue', default=False)
    display_number = fields.Char(compute='_compute_display_number', store=True)
    status = fields.Selection([
        ('waiting', 'Menunggu'),
        ('in_progress', 'Sedang Dilayani'),
        ('completed', 'Selesai'),
        ('cancelled', 'Dibatalkan')
    ], default='waiting', required=True)
    
    # Timing fields
    assigned_time = fields.Datetime(required=True)
    start_time = fields.Datetime()
    end_time = fields.Datetime()
    service_duration = fields.Float(compute='_compute_service_duration', store=True)
    estimated_service_time = fields.Datetime(compute='_compute_estimated_service_time', store=True)
    
    # Service type and duration
    service_type = fields.Selection(related='order_id.service_category')
    base_duration = fields.Float(compute='_compute_base_duration')

    def write(self, vals):
        res = super().write(vals)
        if 'status' in vals:  # Jika status berubah
            self.queue_id._broadcast_queue_update()
        return res
    
    def get_numbers_ahead(self):
        """Get number of queues ahead of current queue"""
        self.ensure_one()
        if not self.queue_id or self.status != 'waiting':
            return 0
            
        domain = [
            ('queue_id', '=', self.queue_id.id),
            ('status', '=', 'waiting'),
            '|',
                '&',
                    ('is_priority', '=', self.is_priority),
                    ('queue_number', '<', self.queue_number),
                '&',
                    ('is_priority', '=', True),
                    ('is_priority', '!=', self.is_priority),
        ]
        
        return len(self.env['queue.management.line'].search(domain))
    
    def get_queue_info(self):
        """Get comprehensive queue information"""
        self.ensure_one()
        numbers_ahead = self.get_numbers_ahead()
        
        return {
            'queue_number': self.display_number,
            'is_priority': self.is_priority,
            'current_number': self.queue_id.current_number,
            'numbers_ahead': numbers_ahead,
            'estimated_wait_minutes': round(numbers_ahead * self.base_duration),
            'estimated_service_time': self.estimated_service_time,
            'status': self.status
        }

    @api.depends('service_type')
    def _compute_base_duration(self):
        """Compute base duration based on service type"""
        for record in self:
            if record.service_type == 'maintenance':
                record.base_duration = 30  # 30 minutes for maintenance
            elif record.service_type == 'repair':
                record.base_duration = 60  # 60 minutes for repair
            else:
                record.base_duration = 45  # default duration

    @api.depends('queue_number', 'is_priority')
    def _compute_display_number(self):
        for record in self:
            if record.is_priority:
                record.display_number = f"P{record.queue_number:03d}"
            else:
                record.display_number = f"{record.queue_number:03d}"

    @api.depends('start_time', 'end_time')
    def _compute_service_duration(self):
        """Compute actual service duration"""
        for record in self:
            if record.start_time and record.end_time:
                duration = (record.end_time - record.start_time).total_seconds() / 60
                record.service_duration = round(duration, 2)
            else:
                record.service_duration = 0

    @api.depends('queue_id.current_number', 'queue_number', 'base_duration', 'is_priority')
    def _compute_estimated_service_time(self):
        """Compute estimated service time based on queue position and service type"""
        for record in self:
            if not record.queue_id or not record.queue_number:
                record.estimated_service_time = False
                continue

            queue_lines = record.queue_id.queue_line_ids.filtered(
                lambda l: l.status == 'waiting' and 
                         ((l.is_priority and record.is_priority and l.queue_number <= record.queue_number) or
                          (not l.is_priority and not record.is_priority and l.queue_number <= record.queue_number) or
                          (not record.is_priority and l.is_priority))
            )

            total_wait_time = sum(l.base_duration for l in queue_lines)
            record.estimated_service_time = fields.Datetime.now() + timedelta(minutes=total_wait_time)

    def mark_started(self):
        """Mark service as started"""
        self.ensure_one()
        if self.status != 'waiting':
            return False
            
        self.write({
            'status': 'in_progress',
            'start_time': fields.Datetime.now()
        })
        return True

    def mark_completed(self):
        """Mark service as completed"""
        self.ensure_one()
        if self.status != 'in_progress':
            return False
            
        self.write({
            'status': 'completed',
            'end_time': fields.Datetime.now()
        })
        return True


        