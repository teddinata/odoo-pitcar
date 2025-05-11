# pitcar_custom/models/service_booking.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import pytz
from odoo.tools import ormcache
import random
import string
import logging

# logger
_logger = logging.getLogger(__name__)

class ServiceBooking(models.Model):
    _name = 'pitcar.service.booking'
    _description = 'Service Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'booking_date desc, booking_time'
    @ormcache('self.id')
    def _get_booking_info(self):
        return {
            'name': self.name,
            'partner': self.partner_id.name,
            'formatted_time': self.formatted_time,
        }
    
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name),
                     ('partner_id.name', operator, name)]
        return self.search(domain + args, limit=limit).name_get()

    name = fields.Char(
        'Booking Reference', 
        required=True, 
        copy=False, 
        readonly=True, 
        default=lambda self: _('New'),
        tracking=True
    )

    # Tambahkan field untuk kode booking unik
    unique_code = fields.Char(
        'Kode Booking', 
        size=6, 
        readonly=True, 
        copy=False, 
        index=True,
        help='Kode unik 6 karakter untuk pencarian cepat'
    )
    
    partner_id = fields.Many2one(
        'res.partner', 
        string='Customer', 
        required=True,
        tracking=True,
        index=True
    )
    partner_car_id = fields.Many2one(
        'res.partner.car',
        string="Car to Service",
        domain="[('partner_id', '=', partner_id)]",
        required=True,
        tracking=True,
        index=True
    )
    partner_car_odometer = fields.Float(string="Odometer", tracking=True)
    
    service_category = fields.Selection([
        ('maintenance', 'Perawatan'),
        ('repair', 'Perbaikan')
    ], string="Kategori Servis", required=True, tracking=True)
    
    service_subcategory = fields.Selection([
        ('tune_up', 'Tune Up'),
        ('tune_up_addition', 'Tune Up + Addition'),
        ('periodic_service', 'Servis Berkala'),
        ('periodic_service_addition', 'Servis Berkala + Addition'),
        ('general_repair', 'General Repair'),
        ('oil_change', 'Ganti Oli'),
    ], string="Jenis Servis", required=True, tracking=True)

    # Convert booking_date to Char field with computed inverse
    booking_date_display = fields.Char(
        string='Fix Booking Date',
        compute='_compute_booking_date_display',
        inverse='_inverse_booking_date_display',
        store=True,
        readonly=True,
    )
    booking_date = fields.Date(string='Booking Date', tracking=True)

    @api.depends('booking_date')
    def _compute_booking_date_display(self):
        for record in self:
            if record.booking_date:
                record.booking_date_display = record.booking_date.strftime('%d/%m/%Y')
            else:
                record.booking_date_display = False

    def _inverse_booking_date_display(self):
        for record in self:
            if record.booking_date_display:
                try:
                    # Parse the date from dd/mm/yyyy format
                    record.booking_date = datetime.strptime(record.booking_date_display, '%d/%m/%Y').date()
                except ValueError:
                    record.booking_date = False
            else:
                record.booking_date = False


    booking_time = fields.Float('Booking Time', required=True, tracking=True)
    formatted_time = fields.Char('Formatted Time', compute='_compute_formatted_time', store=True)
    
    service_advisor_id = fields.Many2many('pitcar.service.advisor', string="Service Advisors", tracking=True)
    sale_order_id = fields.Many2one('sale.order', string='Related Sale Order', readonly=True)
    notes = fields.Text('Notes')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('converted', 'Converted to SO'),  # Langsung ke converted, tanpa arrived
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True, index=True)

    # Field untuk arsip dan analisis
    is_archived = fields.Boolean('Diarsipkan', default=False, index=True)
    is_completed = fields.Boolean('Selesai', compute='_compute_is_completed', store=True, index=True)
    completion_date = fields.Datetime('Tanggal Selesai', readonly=True)
    cancellation_reason = fields.Selection([
        ('customer', 'Dibatalkan oleh Pelanggan'),
        ('no_show', 'Pelanggan Tidak Hadir'),
        ('rescheduled', 'Dijadwalkan Ulang'),
        ('other', 'Alasan Lain')
    ], string='Alasan Pembatalan')
    cancellation_notes = fields.Text('Catatan Pembatalan')
    
    @api.depends('state')
    def _compute_is_completed(self):
        for booking in self:
            booking.is_completed = booking.state in ['converted', 'cancelled']

    # Tambahkan field date_stop
    date_stop = fields.Date(
        string='End Date', 
        compute='_compute_date_stop', 
        store=True
    )

    # Queue tracking fields
    queue_number = fields.Integer('Queue Number', readonly=True)
    display_queue_number = fields.Char('Display Queue Number', readonly=True)
    is_arrived = fields.Boolean('Has Arrived', readonly=True)
    arrival_time = fields.Datetime('Arrival Time', readonly=True)
    estimated_wait_minutes = fields.Integer('Estimated Wait (minutes)', readonly=True)
    estimated_service_time = fields.Datetime('Estimated Service Time', readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            # Format: BOOK/YYYYMM/XXXX
            vals['name'] = self.env['ir.sequence'].next_by_code('pitcar.service.booking') or _('New')
        
        # Generate kode booking unik 6 karakter (huruf kapital dan angka)
        if not vals.get('unique_code'):
            # Function untuk generate kode unik
            def generate_unique_code():
                chars = string.ascii_uppercase + string.digits
                return ''.join(random.choice(chars) for _ in range(6))
            
            # Pastikan kode unik tidak duplikat
            unique_code = generate_unique_code()
            while self.search_count([('unique_code', '=', unique_code)]) > 0:
                unique_code = generate_unique_code()
                
            vals['unique_code'] = unique_code
            
        return super().create(vals)
    
    # Tambahkan constraint untuk memastikan kode unik
    _sql_constraints = [
        ('unique_code_uniq', 'unique(unique_code)', 'Kode booking harus unik!')
    ]

    # Di bagian definisi fields model pitcar.service.booking
    is_online_booking = fields.Boolean(string='Online Booking', default=False, 
        help='Booking dilakukan melalui aplikasi online')
    online_booking_discount = fields.Float(string='Online Booking Discount (%)', default=10.0,
        help='Persentase diskon untuk booking online')
    total_before_discount = fields.Monetary(string='Total Before Discount',
        compute='_compute_amount', store=True, readonly=True)
    discount_amount = fields.Monetary(string='Discount Amount',
        compute='_compute_amount', store=True, readonly=True)

    # Perbarui fungsi compute amount untuk menghitung total sebelum dan sesudah diskon
    @api.depends('booking_line_ids.price_subtotal', 'booking_line_ids.price_before_discount')
    def _compute_amount(self):
        for booking in self:
            # Hitung total setelah diskon (yang sudah ada)
            amount_total = sum(line.price_subtotal for line in booking.booking_line_ids)
            
            # Hitung total sebelum diskon
            total_before_discount = sum(line.price_before_discount * line.quantity for line in booking.booking_line_ids)
            
            booking.amount_total = amount_total
            booking.total_before_discount = total_before_discount
            booking.discount_amount = total_before_discount - amount_total

    @api.depends('booking_date')
    def _compute_date_stop(self):
        for record in self:
            if record.booking_date:
                record.date_stop = record.booking_date

    def action_link_to_sale_order(self):
        """Link booking with existing sale order"""
        self.ensure_one()
        if self.state != 'confirmed':
            raise ValidationError(_('Only confirmed bookings can be linked to sale orders'))
            
        if self.sale_order_id:
            raise ValidationError(_('This booking is already linked to a sale order'))

        # Return wizard action
        return {
            'name': _('Link to Sale Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'booking.link.sale.order.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_booking_id': self.id,
                # Filter untuk SO hari ini
                'default_domain': [
                    ('create_date', '>=', fields.Date.today()),
                    ('create_date', '<', fields.Date.today() + timedelta(days=1)),
                    ('state', '!=', 'cancel')
                ]
            }
        }

    def action_convert_to_sale_order(self):
        self.ensure_one()
        if self.state not in ['confirmed', 'arrived']:
            raise ValidationError(_('Only confirmed or arrived bookings can be converted to sale orders'))
            
        if self.sale_order_id:
            raise ValidationError(_('This booking has already been converted to a sale order'))

        try:
            sale_order = self.env['sale.order'].create({
                'partner_id': self.partner_id.id,
                'partner_car_id': self.partner_car_id.id,
                'service_advisor_id': [(6, 0, self.service_advisor_id.ids)],
                'partner_car_odometer': self.partner_car_odometer,
                'service_category': self.service_category,
                'service_subcategory': self.service_subcategory,
                'is_booking': True,
                'booking_id': self.id,
                'origin': self.name,
                # Tambahkan informasi terkait diskon booking online jika perlu
                'is_online_booking': self.is_online_booking if hasattr(self, 'is_online_booking') else False,
            })

            # Convert booking lines dengan harga
            for line in self.booking_line_ids:
                if line.display_type:
                    # Handle section dan note
                    self.env['sale.order.line'].create({
                        'order_id': sale_order.id,
                        'display_type': line.display_type,
                        'name': line.name,
                        'sequence': line.sequence,
                    })
                    continue

                # Inisialisasi discount
                discount = 0.0
                price_unit = line.price_unit

                # Cek apakah ada online discount
                if hasattr(line, 'online_discount') and line.online_discount > 0:
                    # Jika kita memiliki price_before_discount dan online_discount, gunakan itu
                    if hasattr(line, 'price_before_discount') and line.price_before_discount > 0:
                        price_unit = line.price_before_discount  # Harga asli
                        discount = line.online_discount  # Persentase diskon
                    # Jika kita hanya memiliki price_unit yang sudah didiskon
                    else:
                        price_unit = line.price_unit  # Harga setelah diskon
                        discount = 0.0  # Tidak ada diskon karena sudah diterapkan ke price_unit
                else:
                    # Gunakan diskon yang ada jika ada (backward compatibility)
                    discount = line.discount * 100 if hasattr(line, 'discount') and line.discount else 0.0
                
                _logger.info(f"Converting line: price_unit={price_unit}, discount={discount}")

                line_values = {
                    'order_id': sale_order.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'service_duration': line.service_duration,
                    'name': line.name,
                    'price_unit': price_unit,  # Gunakan harga asli sebelum diskon
                    'discount': discount,  # Gunakan diskon (baik dari online_discount atau dari line.discount)
                    'tax_id': [(6, 0, line.tax_ids.ids)],
                    'sequence': line.sequence,
                }
                
                # Create sale order line dan log hasilnya
                sale_line = self.env['sale.order.line'].create(line_values)
                _logger.info("Created sale order line with price_unit: %s, discount: %s", sale_line.price_unit, sale_line.discount)

            # Update booking status
            self.write({
                'state': 'converted',
                'sale_order_id': sale_order.id
            })

            return {
                'type': 'ir.actions.act_window',
                'name': 'Sale Order',
                'res_model': 'sale.order',
                'res_id': sale_order.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            raise ValidationError(_('Error converting booking to sale order: %s') % str(e))

        
    def action_confirm(self):
        """Confirm booking"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_('Only draft bookings can be confirmed'))
            record.write({'state': 'confirmed'})
        return True

    def action_mark_arrived(self):
      """Mark customer as arrived by linking to existing sale order"""
      self.ensure_one()
      if self.state != 'confirmed':
          raise ValidationError(_('Only confirmed bookings can be marked as arrived'))
          
      return {
          'name': _('Select Sale Order'),
          'type': 'ir.actions.act_window',
          'res_model': 'booking.link.sale.order.wizard',
          'view_mode': 'form',
          'target': 'new',
          'context': {
              'default_booking_id': self.id,
              # Filter SO hari ini
              'default_domain': [
                  ('create_date', '>=', fields.Date.today()),
                  ('create_date', '<', fields.Date.today() + timedelta(days=1)),
                  ('state', '!=', 'cancel')
              ]
          }
      }

    def action_cancel(self):
        """Cancel booking"""
        for record in self:
            if record.state in ['converted']:
                raise ValidationError(_('Cannot cancel booking that has been converted to sale order'))
            record.write({'state': 'cancelled'})
        return True
    
    @api.depends('booking_time')
    def _compute_formatted_time(self):
        for record in self:
            if record.booking_time:
                hours = int(record.booking_time)
                minutes = int((record.booking_time - hours) * 60)
                record.formatted_time = f"{hours:02d}:{minutes:02d}"
            else:
                record.formatted_time = False

    @api.constrains('booking_date')
    def _check_booking_date(self):
        for record in self:
            if record.booking_date < fields.Date.today():
                raise ValidationError(_('Booking date cannot be in the past'))

    @api.constrains('booking_time')
    def _check_booking_time(self):
        for record in self:
            if not 8.0 <= record.booking_time <= 17.0:
                raise ValidationError(_('Booking time must be between 08:00 and 17:00'))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Clear car when customer changes"""
        if self.partner_id:
            self.partner_car_id = False

    booking_line_ids = fields.One2many(
      'pitcar.service.booking.line',
      'booking_id',
      string='Service Lines'
    )
    
    estimated_duration = fields.Float(
        string='Estimated Duration',
        compute='_compute_estimated_duration',
        store=True
    )

    @api.depends('booking_line_ids.service_duration')
    def _compute_estimated_duration(self):
        for booking in self:
            booking.estimated_duration = sum(booking.booking_line_ids.mapped('service_duration'))

     # Tambahkan fields untuk perhitungan total
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency',
        readonly=True,
        default=lambda self: self.env.company.currency_id
    )
    
    company_id = fields.Many2one(
        'res.company', 
        auto_join=True,  # Tambahkan auto_join untuk performa query
        default=lambda self: self.env.company
    )
    
    amount_untaxed = fields.Monetary(
        string='Untaxed Amount',
        store=True,
        compute='_compute_amounts',
        currency_field='currency_id'
    )
    
    amount_tax = fields.Monetary(
        string='Taxes',
        store=True,
        compute='_compute_amounts',
        currency_field='currency_id'
    )
    
    amount_total = fields.Monetary(
        string='Total',
        store=True,
        compute='_compute_amounts',
        currency_field='currency_id'
    )
    
    # Tambahan fields
    # stall_id = fields.Many2one('pitcar.service.stall', string='Assigned Stall', tracking=True)
    booking_end_time = fields.Float('Booking End Time', compute='_compute_end_time', store=True)
    booking_source = fields.Selection([
        ('internal', 'Internal'),
        ('web', 'Website'),
        ('whatsapp', 'WhatsApp'),
        ('phone', 'Phone'),
    ], string='Booking Source', default='internal')
    booking_link_token = fields.Char('Booking Link Token', copy=False)
    
    @api.depends('booking_time', 'estimated_duration')
    def _compute_end_time(self):
        for booking in self:
            if booking.booking_time and booking.estimated_duration:
                booking.booking_end_time = booking.booking_time + booking.estimated_duration
            else:
                booking.booking_end_time = booking.booking_time + 1.0 if booking.booking_time else 0.0

    @api.depends('booking_line_ids.price_subtotal', 'booking_line_ids.price_tax')
    def _compute_amounts(self):
        """Compute the total amounts of the booking."""
        # Prefetch related records
        self.mapped('booking_line_ids.tax_ids').mapped('amount')
        for booking in self:
            amount_untaxed = sum(booking.booking_line_ids.mapped('price_subtotal'))
            amount_tax = sum(booking.booking_line_ids.mapped('price_tax'))
            booking.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })

     # Gunakan sale.order.template yang sudah ada
    sale_order_template_id = fields.Many2one(
        'sale.order.template',
        string='Quotation Template',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        """Handle perubahan template"""
        if not self.sale_order_template_id:
            self.booking_line_ids = [(5, 0, 0)]  # Clear existing lines
            return
        
        lines_data = []
        
        # Get template lines
        for line in self.sale_order_template_id.sale_order_template_line_ids:
            if line.display_type:
                # Untuk section dan note
                lines_data.append((0, 0, {
                    'name': line.name,
                    'display_type': line.display_type,
                    'sequence': line.sequence,
                }))
                continue

            if not line.product_id:
                continue
            
            # Untuk product lines
            line_values = {
                'name': line.name,
                'product_id': line.product_id.id,
                'quantity': line.product_uom_qty,
                'sequence': line.sequence,
                'display_type': line.display_type,
            }

            # Add service duration if it's a service product
            if line.product_id.type == 'service':
                line_values['service_duration'] = line.service_duration

            # Get price dan taxes
            if line.product_id:
                line_values.update({
                    'price_unit': line.product_id.list_price,
                    'tax_ids': [(6, 0, line.product_id.taxes_id.filtered(
                        lambda t: t.company_id == self.company_id
                    ).ids)],
                })

            lines_data.append((0, 0, line_values))
        
        # Clear existing lines and set new ones
        self.booking_line_ids = [(5, 0, 0)]
        self.booking_line_ids = lines_data

        if self.sale_order_template_id.note:
            self.notes = self.sale_order_template_id.note

    def _compute_template_line_values(self, line):
        """Inherit untuk menambahkan service duration dari template"""
        vals = super()._compute_template_line_values(line)
        if line.product_id.type == 'service':
            vals['service_duration'] = line.service_duration
        return vals
    
    create_date = fields.Datetime(
        'Created on',
        readonly=True,
        index=True,
        copy=False
    )
    
    formatted_create_date = fields.Char(
        'Created Date',
        compute='_compute_formatted_create_date',
        store=True
    )

    @api.depends('create_date')
    def _compute_formatted_create_date(self):
        """Compute formatted create date in user's timezone"""
        for record in self:
            if record.create_date:
                # Convert to user timezone
                user_tz = self.env.user.tz or 'UTC'
                local_dt = pytz.UTC.localize(record.create_date).astimezone(pytz.timezone(user_tz))
                record.formatted_create_date = local_dt.strftime('%d/%m/%Y %H:%M:%S')

    def _get_date_display_name(self):
        """Format tanggal untuk display di group header"""
        self.ensure_one()
        if self.booking_date:
            # Format: "15 Jan" atau sesuai kebutuhan
            return self.booking_date.strftime('%d %b')
        return ''

    @api.model
    def _read_group_booking_date(self, booking_dates, domain, order):
        """Custom group by function untuk booking_date"""
        # Get dates from current search domain
        dates = self.search([('booking_date', '!=', False)] + domain).mapped('booking_date')
        
        if not dates:
            return [], {}

        # Sort tanggal
        dates = sorted(set(dates))
        
        # Return list of dates and their folded state
        date_groups = [
            (date.strftime('%Y-%m-%d'), date.strftime('%d %b')) 
            for date in dates
        ]
        
        return date_groups, {}
    
    # Tambahkan ke model pitcar.service.booking
    stall_id = fields.Many2one('pitcar.service.stall', string='Physical Stall',
                            tracking=True, index=True,
                            help="Physical stall where the service will be performed")

    stall_position = fields.Selection([
        ('stall1', 'STALL 1'),
        ('stall2', 'STALL 2'),
        ('stall3', 'STALL 3'),
        ('stall4', 'STALL 4'),
        ('stall5', 'STALL 5'),
        ('stall6', 'STALL 6'),
        ('stall7', 'STALL 7'),
        ('stall8', 'STALL 8'),
        ('stall9', 'STALL 9'),
        ('stall10', 'STALL 10'),
        ('unassigned', 'Unassigned'),
    ], string='Stall Position', default='unassigned', required=True, tracking=True,
    help="Position in the kanban view for visual management")

    @api.onchange('stall_id')
    def _onchange_stall_id(self):
        """Sinkronkan stall_position saat stall_id berubah"""
        if self.stall_id:
            # Extract number from stall name (assuming format "Stall X")
            stall_name = self.stall_id.name
            if "Stall " in stall_name:
                try:
                    stall_number = int(stall_name.replace("Stall ", ""))
                    if 1 <= stall_number <= 10:
                        self.stall_position = f'stall{stall_number}'
                        return
                except ValueError:
                    pass
            # Default fallback
            self.stall_position = 'unassigned'
        else:
            self.stall_position = 'unassigned'

    @api.onchange('stall_position')
    def _onchange_stall_position(self):
        """Sinkronkan stall_id saat stall_position berubah"""
        if self.stall_position and self.stall_position != 'unassigned':
            # Extract number from stall_position (stall1 -> 1)
            try:
                stall_number = int(self.stall_position.replace("stall", ""))
                stall = self.env['pitcar.service.stall'].search([
                    ('name', '=', f'Stall {stall_number}')
                ], limit=1)
                if stall:
                    self.stall_id = stall.id
                    return
            except ValueError:
                pass
            # Reset stall_id if no match
            self.stall_id = False
        else:
            self.stall_id = False

    # Override write method untuk memastikan sinkronisasi saat record disimpan
    def write(self, vals):
        # Sinkronisasi saat stall_id diubah
        if 'stall_id' in vals and vals['stall_id']:
            stall = self.env['pitcar.service.stall'].browse(vals['stall_id'])
            if stall.exists() and "Stall " in stall.name:
                try:
                    stall_number = int(stall.name.replace("Stall ", ""))
                    vals['stall_position'] = f'stall{stall_number}'
                except ValueError:
                    vals['stall_position'] = 'unassigned'
        elif 'stall_id' in vals and not vals['stall_id']:
            vals['stall_position'] = 'unassigned'
        
        # Sinkronisasi saat stall_position diubah
        if 'stall_position' in vals and vals['stall_position'] != 'unassigned':
            try:
                stall_number = int(vals['stall_position'].replace("stall", ""))
                stall = self.env['pitcar.service.stall'].search([
                    ('name', '=', f'Stall {stall_number}')
                ], limit=1)
                if stall:
                    vals['stall_id'] = stall.id
            except ValueError:
                vals['stall_id'] = False
        elif 'stall_position' in vals and vals['stall_position'] == 'unassigned':
            vals['stall_id'] = False
        
        return super(ServiceBooking, self).write(vals)

    @api.model
    def ensure_all_stall_positions_exist(self):
        """Pastikan semua stall ada di database"""
        # Pastikan semua physical stalls ada di DB
        stall_names = ['Stall 1', 'Stall 2', 'Stall 3', 'Stall 4', 'Stall 5', 
                    'Stall 6', 'Stall 7', 'Stall 8', 'Stall 9', 'Stall 10']
        
        for stall_name in stall_names:
            stall = self.env['pitcar.service.stall'].search([
                ('name', '=', stall_name)
            ], limit=1)
            
            if not stall:
                # Buat stall baru jika belum ada
                stall_number = int(stall_name.replace('Stall ', ''))
                self.env['pitcar.service.stall'].create({
                    'name': stall_name,
                    'code': f'S{stall_number:02d}',
                    'active': True
                })
        
        return True
    
    @api.model
    def _cron_update_booking_statuses(self):
        """Update status booking yang telah lewat tanggalnya (otomatis membatalkan booking yang tidak hadir)"""
        today = fields.Date.today()
        yesterday = today - timedelta(days=1)
        
        # Tandai booking yang tidak hadir sebagai cancelled
        missed_bookings = self.search([
            ('booking_date', '<', today),
            ('state', '=', 'confirmed'),
            ('is_archived', '=', False)
        ])
        
        if missed_bookings:
            # Batalkan dengan alasan tidak hadir
            missed_bookings.write({
                'state': 'cancelled',
                'cancellation_reason': 'no_show',
                'completion_date': fields.Datetime.now(),
                'cancellation_notes': 'Dibatalkan otomatis: Booking telah lewat dan pelanggan tidak hadir.'
            })
            
            # Log pesan di chatter untuk pelacakan
            for booking in missed_bookings:
                booking.message_post(
                    body=_('Booking dibatalkan otomatis: Pelanggan tidak hadir'),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )

    @api.model
    def _cron_archive_old_bookings(self):
        """Arsipkan booking lama untuk menjaga performa sistem"""
        archive_date = fields.Date.today() - timedelta(days=90)  # Arsipkan booking lebih dari 90 hari
        
        # Cari booking lama yang sudah selesai dan belum diarsipkan
        old_bookings = self.search([
            ('booking_date', '<', archive_date),
            ('is_completed', '=', True),  # Status converted atau cancelled
            ('is_archived', '=', False)
        ])
        
        if old_bookings:
            old_bookings.write({'is_archived': True})
            
            # Log jumlah booking yang diarsipkan
            _logger.info(f"Berhasil mengarsipkan {len(old_bookings)} booking lama.")

    def action_archive_booking(self):
        """Mengarsipkan booking secara manual"""
        self.ensure_one()
        if self.state not in ['converted', 'cancelled']:
            raise ValidationError(_('Only completed bookings can be archived'))
        
        return self.write({
            'is_archived': True,
            'completion_date': fields.Datetime.now() if not self.completion_date else self.completion_date
        })

    def action_unarchive_booking(self):
        """Mengembalikan booking dari arsip"""
        self.ensure_one()
        return self.write({
            'is_archived': False
        })

    # Tambahkan metode ini di kelas ServiceBooking untuk integrasi dengan frontend
    @api.model
    def get_frontend_booking_data(self, booking_id=None, unique_code=None):
        """Mendapatkan data booking untuk tampilan frontend"""
        domain = []
        
        if booking_id:
            domain.append(('id', '=', int(booking_id)))
        elif unique_code:
            domain.append(('unique_code', '=', unique_code))
        else:
            return False
        
        booking = self.search(domain, limit=1)
        if not booking:
            return False
        
        # Format data untuk frontend
        booking_data = {
            'id': booking.id,
            'name': booking.name,
            'unique_code': booking.unique_code,
            'date': fields.Date.to_string(booking.booking_date) if booking.booking_date else False,
            'time': booking.formatted_time,
            'customer': {
                'id': booking.partner_id.id,
                'name': booking.partner_id.name,
                'phone': booking.partner_id.phone,
                'email': booking.partner_id.email,
            },
            'car': {
                'id': booking.partner_car_id.id,
                'name': booking.partner_car_id.name,
                'plate_number': booking.partner_car_id.number_plate,
            },
            'services': [],
            'stall': booking.stall_id.name if booking.stall_id else 'Unassigned',
            'stall_position': booking.stall_position,
            'state': booking.state,
            'amount_total': booking.amount_total,
            'is_online_booking': booking.is_online_booking,
            'queue_info': {
                'is_arrived': booking.is_arrived,
                'queue_number': booking.queue_number,
                'display_queue_number': booking.display_queue_number,
                'estimated_wait_minutes': booking.estimated_wait_minutes,
            },
        }
        
        # Tambahkan informasi service
        for line in booking.booking_line_ids:
            if not line.display_type and line.product_id:
                booking_data['services'].append({
                    'id': line.product_id.id,
                    'name': line.name,
                    'quantity': line.quantity,
                    'price': line.price_unit,
                    'duration': line.service_duration,
                    'subtotal': line.price_subtotal,
                })
        
        return booking_data

    @api.model
    def process_frontend_checkin(self, unique_code):
        """Memproses checkin dari frontend"""
        booking = self.search([('unique_code', '=', unique_code)], limit=1)
        
        if not booking:
            return {'status': 'error', 'message': 'Booking not found'}
        
        if booking.state not in ['draft', 'confirmed']:
            return {'status': 'error', 'message': 'Booking cannot be checked in'}
        
        if booking.is_arrived:
            return {'status': 'warning', 'message': 'Already checked in', 'booking': self.get_frontend_booking_data(unique_code=unique_code)}
        
        # Auto confirm if in draft state
        if booking.state == 'draft':
            booking.action_confirm()
        
        # Update arrival info
        booking.write({
            'is_arrived': True,
            'arrival_time': fields.Datetime.now(),
        })
        
        # Calculate queue number if not set
        if not booking.queue_number:
            # Get today's confirmed/arrived bookings for the same stall
            same_stall_bookings = self.search([
                ('booking_date', '=', booking.booking_date),
                ('stall_id', '=', booking.stall_id.id),
                ('state', 'in', ['confirmed']),
                ('is_arrived', '=', True),
                ('id', '!=', booking.id)
            ], order='arrival_time')
            
            # Set queue number based on existing bookings
            booking.queue_number = len(same_stall_bookings) + 1
            booking.display_queue_number = f"{booking.stall_id.code}-{booking.queue_number:02d}"
            
            # Calculate estimated wait time (15 mins per booking in queue)
            booking.estimated_wait_minutes = len(same_stall_bookings) * 15
            
            # Calculate estimated service time
            current_time = fields.Datetime.now()
            wait_time = timedelta(minutes=booking.estimated_wait_minutes)
            booking.estimated_service_time = current_time + wait_time
        
        return {
            'status': 'success', 
            'message': 'Check-in successful',
            'booking': self.get_frontend_booking_data(unique_code=unique_code)
        }

    @api.model
    def update_booking_from_frontend(self, booking_id, values):
        """Update booking dari frontend app"""
        booking = self.browse(int(booking_id))
        
        if not booking.exists():
            return {'status': 'error', 'message': 'Booking not found'}
        
        try:
            updateable_fields = [
                'booking_date', 'booking_time', 'service_category', 
                'service_subcategory', 'stall_id', 'stall_position',
                'notes'
            ]
            
            update_vals = {}
            for field in updateable_fields:
                if field in values:
                    update_vals[field] = values[field]
            
            # Special case for stall_id - convert to int
            if 'stall_id' in update_vals and update_vals['stall_id']:
                update_vals['stall_id'] = int(update_vals['stall_id'])
            
            # Special case for date - convert to Date object
            if 'booking_date' in update_vals and update_vals['booking_date']:
                try:
                    update_vals['booking_date'] = fields.Date.from_string(update_vals['booking_date'])
                except ValueError:
                    return {'status': 'error', 'message': 'Invalid date format'}
            
            # Apply updates
            booking.write(update_vals)
            
            # Handle service changes if provided
            if 'service_ids' in values and values['service_ids']:
                # Clear existing lines that are not section or note
                booking.booking_line_ids.filtered(lambda l: not l.display_type).unlink()
                
                # Add new service lines
                service_ids = values['service_ids']
                for service_id in service_ids:
                    product = self.env['product.product'].browse(int(service_id))
                    if product.exists():
                        self.env['pitcar.service.booking.line'].create({
                            'booking_id': booking.id,
                            'product_id': product.id,
                            'name': product.name,
                            'quantity': 1.0,
                            'price_unit': product.list_price,
                            'service_duration': product.service_duration if hasattr(product, 'service_duration') else 1.0,
                            'tax_ids': [(6, 0, product.taxes_id.ids)],
                        })
            
            return {
                'status': 'success',
                'message': 'Booking updated successfully',
                'booking': self.get_frontend_booking_data(booking_id=booking.id)
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @api.model
    def get_dashboard_data(self, date=None):
        """Mendapatkan data dashboard untuk frontend"""
        if not date:
            date = fields.Date.today()
        else:
            date = fields.Date.from_string(date)
        
        # Get bookings for the date
        bookings = self.search([
            ('booking_date', '=', date),
            ('is_archived', '=', False)
        ])
        
        # Count bookings by state
        counts = {
            'total': len(bookings),
            'draft': len(bookings.filtered(lambda b: b.state == 'draft')),
            'confirmed': len(bookings.filtered(lambda b: b.state == 'confirmed')),
            'converted': len(bookings.filtered(lambda b: b.state == 'converted')),
            'cancelled': len(bookings.filtered(lambda b: b.state == 'cancelled')),
            'arrived': len(bookings.filtered(lambda b: b.is_arrived)),
        }
        
        # Group bookings by stall
        stalls_data = {}
        for booking in bookings:
            stall_key = booking.stall_id.id if booking.stall_id else 0
            stall_name = booking.stall_id.name if booking.stall_id else 'Unassigned'
            
            if stall_key not in stalls_data:
                stalls_data[stall_key] = {
                    'id': stall_key,
                    'name': stall_name,
                    'count': 0,
                    'bookings': []
                }
            
            stalls_data[stall_key]['count'] += 1
            stalls_data[stall_key]['bookings'].append({
                'id': booking.id,
                'name': booking.name,
                'time': booking.formatted_time,
                'customer': booking.partner_id.name,
                'state': booking.state,
                'is_arrived': booking.is_arrived,
            })
        
        # Get all stalls for complete view
        all_stalls = self.env['pitcar.service.stall'].search([])
        for stall in all_stalls:
            if stall.id not in stalls_data:
                stalls_data[stall.id] = {
                    'id': stall.id,
                    'name': stall.name,
                    'count': 0,
                    'bookings': []
                }
        
        # Calculate revenue and metrics
        total_revenue = sum(booking.amount_total for booking in bookings.filtered(lambda b: b.state == 'converted'))
        avg_booking_value = total_revenue / counts['converted'] if counts['converted'] else 0
        
        return {
            'date': fields.Date.to_string(date),
            'counts': counts,
            'stalls': list(stalls_data.values()),
            'metrics': {
                'total_revenue': total_revenue,
                'avg_booking_value': avg_booking_value,
                'conversion_rate': (counts['converted'] / counts['total']) * 100 if counts['total'] else 0,
                'arrival_rate': (counts['arrived'] / counts['confirmed']) * 100 if counts['confirmed'] else 0,
            }
        }

    def action_archive_booking(self):
        """Mengarsipkan booking secara manual"""
        for record in self:
            if record.state not in ['converted', 'cancelled']:
                raise ValidationError(_('Only completed bookings can be archived'))
            
            record.write({
                'is_archived': True,
                'completion_date': fields.Datetime.now() if not record.completion_date else record.completion_date
            })
        
        return True

    def action_unarchive_booking(self):
        """Mengembalikan booking dari arsip"""
        for record in self:
            record.write({
                'is_archived': False
            })
        
        return True

# pitcar_custom/models/service_booking.py
class ServiceBookingLine(models.Model):
    _name = 'pitcar.service.booking.line'
    _description = 'Service Booking Line'
    _order = 'sequence, id'

    booking_id = fields.Many2one('pitcar.service.booking', string='Booking Reference', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")
    ], default=False, help="Technical field for UX purpose.")
    
    product_id = fields.Many2one(
        'product.product', 
        string='Product/Service', 
        # domain=[('type', 'in', ['service', 'product'])],
        required=False  # Ubah jadi False, kita akan gunakan @api.constrains
    )
    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        digits='Product Unit of Measure',
        required=False  # Ubah jadi False, kita akan gunakan @api.constrains
    )
    service_duration = fields.Float(string='Service Duration')

    # Fields untuk perhitungan harga
    price_unit = fields.Float(
        'Unit Price',
        digits='Product Price',
        default=0.0
    )
    
    discount = fields.Float(
        string='Discount (%)',
        digits=(16, 2),  # Ubah precision menjadi lebih spesifik
        default=0.0
    )
    
    tax_ids = fields.Many2many(
        'account.tax',
        string='Taxes',
        domain=[('type_tax_use', '=', 'sale')]
    )
    
    price_subtotal = fields.Monetary(
        string='Subtotal',
        store=True,
        compute='_compute_amount',
        currency_field='currency_id'
    )
    
    price_tax = fields.Float(
        string='Total Tax',
        store=True,
        compute='_compute_amount'
    )
    
    price_total = fields.Monetary(
        string='Total',
        store=True,
        compute='_compute_amount',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        related='booking_id.currency_id',
        depends=['booking_id.currency_id'],
        store=True,
        string='Currency'
    )

    # Di bagian definisi fields model pitcar.service.booking.line
    price_before_discount = fields.Float(
        string='Price Before Discount',
        compute='_compute_price_before_discount',
        store=True,
        help='Harga original sebelum diskon booking online'
    )

    @api.depends('price_unit')
    def _compute_price_before_discount(self):
        for line in self:
            line.price_before_discount = line.price_unit

    online_discount = fields.Float(string='Online Discount (%)', default=0.0,
        help='Persentase diskon booking online yang diterapkan')

    @api.constrains('display_type', 'product_id', 'quantity')
    def _check_product_required(self):
        for line in self:
            if not line.display_type:  # Jika bukan section atau note
                if not line.product_id:
                    raise ValidationError(_('Please select a product for normal lines.'))
                if not line.quantity or line.quantity <= 0:
                    raise ValidationError(_('Quantity must be positive for normal lines.'))

    @api.onchange('display_type')
    def _onchange_display_type(self):
        if self.display_type:
            self.product_id = False
            self.quantity = 0
            self.price_unit = 0
            self.service_duration = 0
            self.tax_ids = [(5, 0, 0)]  # Clear taxes

    # Tambahkan fungsi untuk menghitung price_subtotal
    @api.depends('quantity', 'price_unit', 'tax_ids', 'online_discount')
    def _compute_amount(self):
        """Compute the amounts of the booking line."""
        for line in self:
            if line.display_type:
                line.update({
                    'price_subtotal': 0.0,
                    'price_total': 0.0,
                    'price_tax': 0.0,
                })
                continue

            # Gunakan online_discount (dalam persentase)
            discount_factor = 1 - (line.online_discount / 100.0)
            
            # Hitung price setelah diskon
            price_after_discount = line.price_unit * discount_factor
            
            # Pastikan price_before_discount memiliki nilai
            if not line.price_before_discount:
                line.price_before_discount = line.price_unit
            
            # Hitung subtotal
            subtotal = line.quantity * price_after_discount

            # Hitung pajak
            taxes = line.tax_ids.compute_all(
                price_after_discount,
                line.booking_id.currency_id,
                line.quantity,
                product=line.product_id,
                partner=line.booking_id.partner_id
            )

            # Lakukan update hanya sekali
            line.update({
                'price_subtotal': taxes['total_excluded'],
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included']
            })

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        # Force refresh product cache before search
        self.env['product.product'].flush()
        self.env['product.product'].invalidate_cache()
        
        return super(ServiceBookingLine, self).name_search(name=name, args=args, operator=operator, limit=limit)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id or self.display_type:
            return
            
        # Lazy loading
        values = {
            'name': self.product_id.get_product_multiline_description_sale(),
            'price_unit': self.product_id.list_price,
            'discount': 0.0,  # Reset discount saat product berubah
            'service_duration': self.product_id.service_duration if self.product_id.type == 'service' else 0.0,
            'tax_ids': [(6, 0, self.product_id.taxes_id.filtered(
                lambda t: t.company_id == self.booking_id.company_id
            ).ids)]
        }
            
        self.update(values)

    def _get_computed_name(self):
        self.ensure_one()
        if self.product_id and not self.display_type:
            if self.product_id.description_sale:
                return self.product_id.description_sale
            return self.product_id.name
        return self.name

class PitcarServiceStall(models.Model):
    _name = 'pitcar.service.stall'
    _description = 'Service Stall Management'
    
    name = fields.Char('Stall Name', required=True)
    code = fields.Char('Stall Code', required=True)
    active = fields.Boolean('Active', default=True)
    mechanic_ids = fields.Many2many(
        'pitcar.mechanic.new', 
        string='Assigned Mechanics',
        help='Mechanics assigned to this stall'
    )
    is_quick_service = fields.Boolean(
        'Quick Service', 
        default=False,
        help='Check if this stall is dedicated for quick services'
    )
    max_capacity = fields.Integer(
        'Max Capacity', 
        default=1,
        help='Maximum number of cars that can be serviced simultaneously'
    )
    current_booking_id = fields.Many2one('pitcar.service.booking', 'Current Booking')
    next_available_time = fields.Datetime('Next Available Time', compute='_compute_next_available')
    
    # One2many untuk booking
    booking_ids = fields.One2many('pitcar.service.booking', 'stall_id', string='Bookings')
    
    @api.depends('booking_ids', 'booking_ids.state', 'booking_ids.booking_date', 'booking_ids.booking_time')
    def _compute_next_available(self):
        for stall in self:
            now = fields.Datetime.now()
            today = fields.Date.today()
            current_hour = now.hour + now.minute / 60.0
            
            # Cari booking aktif terdekat
            active_bookings = self.env['pitcar.service.booking'].search([
                ('stall_id', '=', stall.id),
                ('state', 'not in', ['cancelled']),
                '|',
                ('booking_date', '>', today),
                '&',
                ('booking_date', '=', today),
                ('booking_time', '>=', current_hour)
            ], order='booking_date, booking_time', limit=1)
            
            if active_bookings:
                booking = active_bookings[0]
                end_time = booking.booking_time + booking.estimated_duration
                # Konversi ke datetime
                end_datetime = datetime.combine(booking.booking_date, datetime.min.time()) + timedelta(hours=end_time)
                stall.next_available_time = end_datetime
            else:
                stall.next_available_time = now
