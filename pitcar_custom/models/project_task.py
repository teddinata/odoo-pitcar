from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'

    entry_date = fields.Date(string='Entry Date')
    # invoice_id = fields.Many2one('account.move', string='Invoice')
    invoice_id = fields.Many2one('account.move', string='Invoice', domain="[('partner_id', '=', partner_id), ('state', '=', 'posted'), ('move_type', '=', 'out_invoice')]")
    invoice_total = fields.Monetary(string='Invoice Total', compute='_compute_invoice_total', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    @api.depends('invoice_id', 'invoice_id.amount_total')
    def _compute_invoice_total(self):
        for task in self:
            try:
                if task.invoice_id and task.invoice_id.amount_total:
                    task.invoice_total = task.invoice_id.amount_total
                else:
                    task.invoice_total = 0
            except Exception as e:
                task.invoice_total = 0
                # Log the error for debugging
                _logger.error(f"Error computing invoice_total for task {task.id}: {str(e)}")

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        self.invoice_id = False

    