# pitcar_custom/models/service_booking.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import pytz
from odoo.tools import ormcache
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
        return super().create(vals)

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

                # Handle product lines dengan diskon yang benar
                # Kompensasi pembagian 100 yang dilakukan oleh Odoo
                actual_discount = line.discount * 100 if line.discount else 0.0
                
                _logger.info(f"Original discount: {line.discount}")
                _logger.info(f"Compensated discount: {actual_discount}")

                line_values = {
                    'order_id': sale_order.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'service_duration': line.service_duration,
                    'name': line.name,
                    'price_unit': line.price_unit,
                    'discount': actual_discount,  # Gunakan nilai yang sudah dikompensasi
                    'tax_id': [(6, 0, line.tax_ids.ids)],
                    'sequence': line.sequence,
                }
                
                # Create sale order line dan log hasilnya
                sale_line = self.env['sale.order.line'].create(line_values)
                _logger.info("Created sale order line with discount: %s", sale_line.discount)
                # new_line = self.env['sale.order.line'].create(line_values)
                # _logger.info(f"Created sale order line with discount: {new_line.discount}")

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
    stall_id = fields.Many2one('pitcar.service.stall', string='Assigned Stall', tracking=True)
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
    
    stall_position = fields.Selection([
        ('stall1', 'STALL 1'),
        ('stall2', 'STALL 2'),
        ('stall3', 'STALL 3'),
        ('stall4', 'STALL 4'),
        ('stall5', 'STALL 5'),
        ('stall6', 'STALL 6'),
        ('unassigned', 'Unassigned'),
    ], string='Pilih Stall', default='stall1', required=True, tracking=True)

    def write(self, vals):
        """Override write untuk menangani perubahan stall via drag & drop"""
        if 'stall_position' in vals:
            # Log perubahan stall di chatter
            for record in self:
                old_stall = dict(self._fields['stall_position'].selection).get(record.stall_position, 'Unassigned')
                new_stall = dict(self._fields['stall_position'].selection).get(vals['stall_position'], 'Unassigned')
                msg = _(f"Booking dipindahkan dari {old_stall} ke {new_stall} oleh {self.env.user.name}")
                record.message_post(body=msg)
        
        return super().write(vals)

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
        domain=[('type', 'in', ['service', 'product'])],
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

    @api.depends('quantity', 'price_unit', 'tax_ids', 'discount')
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

            # Hitung price setelah diskon
            price = line.price_unit * (1 - (line.discount / 100.0))  # Konversi diskon ke desimal
            
            # Hitung subtotal
            subtotal = line.quantity * price

            # Hitung pajak
            taxes = line.tax_ids.compute_all(
                price,
                line.booking_id.currency_id,
                line.quantity,
                product=line.product_id,
                partner=line.booking_id.partner_id
            )

            line.update({
                'price_subtotal': taxes['total_excluded'],
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included']
            })


            # Hitung price setelah 
            price = line.price_unit * (1 - line.discount)  # Hapus pembagian dengan 100
            # Hitung subtotal sebelum pajak
            subtotal = line.quantity * price

            # Hitung pajak
            taxes = line.tax_ids.compute_all(
                price,  # Gunakan harga per unit yang sudah didiskon
                line.booking_id.currency_id,
                line.quantity,
                product=line.product_id,
                partner=line.booking_id.partner_id
            )

            line.update({
                'price_subtotal': taxes['total_excluded'],
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included']
            })

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
