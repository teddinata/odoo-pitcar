from odoo import models, fields, api, _

class ProductProduct(models.Model):
    _inherit = 'product.product'

    # category_id will be used as a filter in the product list view by connecting it to the product.template model
    template_categ_id = fields.Many2one(
        string="Category",
        related="product_tmpl_id.categ_id",
        store=True,
        index=True,
    )
    
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        # Adding total_value field to show in group by
        if 'total_value' in fields:
            fields.append('total_value')
            
        return super(ProductProduct, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)