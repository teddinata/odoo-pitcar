from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from datetime import datetime
import logging
class ProductProduct(models.Model):
    _inherit = 'product.product'

    # === EXISTING FIELDS ===
    template_categ_id = fields.Many2one(
        string="Category",
        related="product_tmpl_id.categ_id",
        store=True,
        index=True,
    )

    # === COST SECURITY FOR PRODUCT.PRODUCT ===
    standard_price = fields.Float(
        'Cost',
        company_dependent=True,
        digits='Product Price',
        groups="base.group_system,stock.group_stock_manager",
        help="Cost used for stock valuation in standard price and as a first price to set in average/fifo."
    )

    def read(self, fields=None, load='_classic_read'):
        """Override read method untuk product.product"""
        # Cek apakah user bukan admin
        if not self.env.user.has_group('base.group_system') and \
           not self.env.user.has_group('stock.group_stock_manager'):
            if fields and 'standard_price' in fields:
                fields = [f for f in fields if f != 'standard_price']
            elif not fields:
                all_fields = list(self._fields.keys())
                fields = [f for f in all_fields if f not in ['standard_price']]
        
        result = super(ProductProduct, self).read(fields, load)
        
        # Set cost ke 0 untuk non-admin
        if not self.env.user.has_group('base.group_system') and \
           not self.env.user.has_group('stock.group_stock_manager'):
            for record in result:
                if 'standard_price' in record:
                    record['standard_price'] = 0.0
                    
        return result

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Override fields_get untuk product.product"""
        res = super(ProductProduct, self).fields_get(allfields, attributes)
        
        if not self.env.user.has_group('base.group_system') and \
           not self.env.user.has_group('stock.group_stock_manager'):
            cost_fields = ['standard_price', 'cost']
            for field in cost_fields:
                if field in res:
                    res[field]['readonly'] = True
                    res[field]['invisible'] = True
        
        return res

    # === EXISTING METHOD ===
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        # Adding total_value field to show in group by
        if 'total_value' in fields:
            fields.append('total_value')
            
        return super(ProductProduct, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)