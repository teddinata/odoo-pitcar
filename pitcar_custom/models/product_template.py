from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from datetime import datetime

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    entry_date = fields.Datetime(string='Entry Date', readonly=True)
    inventory_age = fields.Char(string='Inventory Age', compute='_compute_inventory_age', store=True)
    inventory_age_days = fields.Integer(string='Days in Inventory', compute='_compute_inventory_age', store=True)
    inventory_age_category = fields.Selection([
        ('new', 'New (< 30 hari)'),
        ('medium', 'Medium (30-90 hari)'),
        ('old', 'Slow Moving (90-180 hari)'),
        ('very_old', 'Very Slow Moving (> 180 hari)')
    ], string='Inventory Age Category', compute='_compute_inventory_age', store=True)

    @api.depends('entry_date')
    def _compute_inventory_age(self):
        now = fields.Datetime.now()
        for product in self:
            if product.entry_date:
                delta = now - product.entry_date
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

    def update_entry_date(self, date=None):
        if date is None:
            date = fields.Datetime.now()
        for product in self:
            # Selalu update entry_date dengan tanggal terbaru
            if not product.entry_date or date > product.entry_date:
                product.entry_date = date
        self._compute_inventory_age()  # Recalculate inventory age
        return True

    def force_recompute_inventory_age(self):
        self._compute_inventory_age()
        self.env.cr.commit()
    
    def action_update_inventory_age(self):
        self._compute_inventory_age()
        return True

    @api.model
    def action_update_all_inventory_age(self):
        products = self.search([])
        products._compute_inventory_age()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'All inventory ages have been updated.',
                'sticky': False,
            }
        }