from odoo import models, fields, api, _, exceptions

class ProductTag(models.Model):
	_inherit = 'product.tag'

	product_ids_count = fields.Integer(string="Product Count", compute='_compute_product_ids_count')

	@api.depends('product_template_ids', 'product_product_ids')
	def _compute_product_ids_count(self):
		for tag in self:
			tag.product_ids_count = len(tag.product_template_ids) + len(tag.product_product_ids)