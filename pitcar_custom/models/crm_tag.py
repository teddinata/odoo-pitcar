from odoo import models, fields, api, _, exceptions

class CrmTag(models.Model):
	_inherit = 'crm.tag'

	crm_lead_ids = fields.Many2many('crm.lead', 'crm_tag_rel', 'tag_id', 'lead_id', string='Leads')
	sale_order_ids = fields.Many2many('sale.order', 'sale_order_tag_rel', 'tag_id', 'order_id', string='Sales Orders')
	crm_lead_ids_count = fields.Integer(string="Lead Count", compute='_compute_crm_lead_ids_count')

	@api.depends('crm_lead_ids', 'sale_order_ids')
	def _compute_crm_lead_ids_count(self):
		for tag in self:
			tag.crm_lead_ids_count = len(tag.crm_lead_ids) + len(tag.sale_order_ids)