from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # === COST SECURITY ===
    standard_price = fields.Float(
        'Cost',
        company_dependent=True,
        digits='Product Price',
        groups="base.group_system,stock.group_stock_manager",
        help="Cost price - visible only to administrators and stock managers"
    )

    service_duration = fields.Float(
        string='Durasi Layanan (Jam)',
        help='Durasi estimasi untuk menyelesaikan layanan ini',
        default=0.0
    )

    flat_rate = fields.Float(
        string='Flat Rate (Jam)',
        help='Jam flat rate untuk layanan ini',
        default=0.0,
        tracking=True
    )

    flat_rate_value = fields.Float(
        string='Nilai Flat Rate',
        default=211000,
        help='Nilai flat rate per jam (default: 210.671)'
    )

    def calculate_flat_rate(self):
        for product in self:
            if product.list_price > 0 and product.flat_rate_value > 0:
                product.flat_rate = product.list_price / product.flat_rate_value
        return True
    
    # Metode untuk menghitung flat rate untuk semua produk service
    @api.model
    def action_calculate_all_flat_rates(self):
        service_products = self.search([('type', '=', 'service')])
        service_products.calculate_flat_rate()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sukses',
                'message': f'Flat rate untuk {len(service_products)} produk layanan telah diperbarui.',
                'sticky': False,
            }
        }

    def write(self, vals):
        res = super().write(vals)
        # Update template lines ketika service duration berubah
        if 'service_duration' in vals:
            template_lines = self.env['sale.order.template.line'].search([
                ('product_id.product_tmpl_id', 'in', self.ids)
            ])
            if template_lines:
                template_lines.write({'service_duration': vals['service_duration']})
        return res

    oldest_stock_entry_date = fields.Datetime(string='Oldest Stock Entry Date', compute='_compute_oldest_stock_entry_date', store=True)
    inventory_age = fields.Char(string='Umur Persediaan', compute='_compute_inventory_age', store=True)
    inventory_age_days = fields.Integer(string='Lama Penyimpanan (hari)', compute='_compute_inventory_age', store=True)
    inventory_age_category = fields.Selection([
        ('new', 'Baru (< 30 hari)'),
        ('medium', 'Menengah (30-90 hari)'),
        ('old', 'Lama (90-180 hari)'),
        ('very_old', 'Sangat Lama (> 180 hari)')
    ], string='Kategori Umur Persediaan', compute='_compute_inventory_age', store=True)

     # Tambah field untuk mandatory stock
    is_mandatory_stock = fields.Boolean(
        string='Wajib Ready Stock',
        default=False,
        help='Centang jika part ini wajib selalu tersedia di stock',
        tracking=True
    )
    min_mandatory_stock = fields.Float(
        string='Minimum Stock Wajib',
        default=0.0,
        help='Jumlah minimum yang harus selalu tersedia untuk part wajib stock',
        tracking=True
    )
    
    is_below_mandatory_level = fields.Boolean(
        string='Di Bawah Level Minimum',
        compute='_compute_is_below_mandatory_level',
        store=True,
        help='True jika stok saat ini di bawah level minimum yang diwajibkan'
    )

    @api.depends('qty_available', 'min_mandatory_stock', 'is_mandatory_stock')
    def _compute_is_below_mandatory_level(self):
        for product in self:
            if product.is_mandatory_stock and product.min_mandatory_stock > 0:
                current_qty = product.with_context(company_owned=True).qty_available
                product.is_below_mandatory_level = current_qty < product.min_mandatory_stock
                
                # Jika di bawah minimum, create record stockout
                if product.is_below_mandatory_level:
                    # Check if stockout record already exists today
                    existing_stockout = self.env['stock.mandatory.stockout'].search([
                        ('date', '=', fields.Date.today()),
                        ('product_tmpl_id', '=', product.id)
                    ], limit=1)
                    
                    if not existing_stockout:
                        self.env['stock.mandatory.stockout'].sudo().create({
                            'date': fields.Date.today(),
                            'product_tmpl_id': product.id,
                            'available_qty': current_qty,
                            'min_required': product.min_mandatory_stock
                        })
            else:
                product.is_below_mandatory_level = False

     # Tambahkan method baru untuk menghitung stockout mandatory parts
    def check_mandatory_stock_status(self):
        """
        Check status stok untuk parts yang wajib ready
        Returns dict dengan informasi stockout jika ada
        """
        self.ensure_one()
        if not self.is_mandatory_stock:
            return None

        available_qty = self.with_context(company_owned=True).qty_available
        if available_qty < self.min_mandatory_stock:
            return {
                'product_id': self.id,
                'name': self.name,
                'available_qty': available_qty,
                'min_required': self.min_mandatory_stock,
                'shortage': self.min_mandatory_stock - available_qty
            }
        return None

    @api.depends('product_variant_ids.stock_move_ids.state', 'product_variant_ids.stock_quant_ids.quantity')
    def _compute_oldest_stock_entry_date(self):
        for product in self:
            _logger.info(f"Computing oldest stock entry date for product: {product.name}")
            
            current_stock = sum(product.with_context(company_owned=True).product_variant_ids.mapped('qty_available'))
            _logger.info(f"Current stock: {current_stock}")

            if current_stock <= 0:
                product.oldest_stock_entry_date = False
                _logger.info("No stock available, set oldest_stock_entry_date to False")
                continue

            moves = self.env['stock.move'].search([
                ('product_id', 'in', product.product_variant_ids.ids),
                ('state', '=', 'done')
            ], order='date asc')

            stock_entries = []
            for move in moves:
                if move.location_dest_id.usage == 'internal' and move.location_id.usage != 'internal':
                    # Incoming move
                    stock_entries.append((move.date, move.product_uom_qty, 'in'))
                elif move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
                    # Outgoing move
                    qty_to_remove = move.product_uom_qty
                    while qty_to_remove > 0 and stock_entries:
                        if stock_entries[0][1] <= qty_to_remove:
                            qty_to_remove -= stock_entries[0][1]
                            stock_entries.pop(0)
                        else:
                            stock_entries[0] = (stock_entries[0][0], stock_entries[0][1] - qty_to_remove, 'in')
                            qty_to_remove = 0

            if stock_entries:
                product.oldest_stock_entry_date = stock_entries[0][0]
                _logger.info(f"Set oldest_stock_entry_date to {product.oldest_stock_entry_date}")
            else:
                product.oldest_stock_entry_date = False
                _logger.info("No stock entries found, set oldest_stock_entry_date to False")

    @api.depends('oldest_stock_entry_date')
    def _compute_inventory_age(self):
        now = fields.Datetime.now()
        for product in self:
            if product.oldest_stock_entry_date:
                delta = now - product.oldest_stock_entry_date
                days = delta.days
                product.inventory_age = f"{days // 365}t {(days % 365) // 30}b {days % 30}h"
                product.inventory_age_days = days
                if days < 30:
                    product.inventory_age_category = 'new'
                elif 30 <= days < 90:
                    product.inventory_age_category = 'medium'
                elif 90 <= days < 180:
                    product.inventory_age_category = 'old'
                else:
                    product.inventory_age_category = 'very_old'
            else:
                product.inventory_age = "0t 0b 0h"
                product.inventory_age_days = 0
                product.inventory_age_category = 'new'

    def action_update_inventory_age(self):
        self._compute_oldest_stock_entry_date()
        self._compute_inventory_age()
        return True

    def force_recompute_inventory_age(self):
        self._compute_inventory_age()
        self.env.cr.commit()

    @api.model
    def action_update_all_inventory_age(self):
        products = self.search([])
        products.action_update_inventory_age()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sukses',
                'message': 'Semua umur persediaan telah diperbarui.',
                'sticky': False,
            }
        }