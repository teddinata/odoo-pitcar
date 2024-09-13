from odoo import models, fields, api

class ServiceAdvisor(models.Model):
    _name = 'pitcar.service.advisor'
    _description = 'Service Advisor'

    user_id = fields.Many2one('res.users', string="Service Advisor", required=True)
    color = fields.Integer(string="Color", default=0)

    # Tambahkan computed field untuk nama
    name = fields.Char(string="Service Advisor Name", compute='_compute_name', store=True)

    @api.depends('user_id')
    def _compute_name(self):
        for record in self:
            record.name = record.user_id.name if record.user_id else ''
