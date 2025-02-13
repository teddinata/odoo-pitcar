from odoo import models, fields, api

class StockMandatoryStockout(models.Model):
    _name = 'stock.mandatory.stockout'
    _description = 'Mandatory Stock Part Stockout Records'
    _order = 'date desc'

    date = fields.Date(
        string='Tanggal',
        required=True,
        default=fields.Date.context_today
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Part',
        required=True,
        domain=[('is_mandatory_stock', '=', True)]
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order'
    )
    available_qty = fields.Float(
        string='Qty Tersedia',
        required=True
    )
    min_required = fields.Float(
        string='Minimum Required',
        required=True
    )
    shortage_qty = fields.Float(
        string='Kekurangan',
        compute='_compute_shortage',
        store=True
    )

    @api.depends('available_qty', 'min_required')
    def _compute_shortage(self):
        for record in self:
            record.shortage_qty = record.min_required - record.available_qty