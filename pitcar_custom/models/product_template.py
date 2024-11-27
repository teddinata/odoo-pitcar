from odoo import models, fields, api
# from dateutil.relativedelta import relativedelta
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    service_duration = fields.Float(
        string='Durasi Layanan (Jam)',
        help='Durasi estimasi untuk menyelesaikan layanan ini',
        default=0.0
    )

    oldest_stock_entry_date = fields.Datetime(string='Oldest Stock Entry Date', compute='_compute_oldest_stock_entry_date', store=True)
    inventory_age = fields.Char(string='Umur Persediaan', compute='_compute_inventory_age', store=True)
    inventory_age_days = fields.Integer(string='Lama Penyimpanan (hari)', compute='_compute_inventory_age', store=True)
    inventory_age_category = fields.Selection([
        ('new', 'Baru (< 30 hari)'),
        ('medium', 'Menengah (30-90 hari)'),
        ('old', 'Lama (90-180 hari)'),
        ('very_old', 'Sangat Lama (> 180 hari)')
    ], string='Kategori Umur Persediaan', compute='_compute_inventory_age', store=True)

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