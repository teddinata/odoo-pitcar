from odoo import models, fields, api
from datetime import date

class ProjectTask(models.Model):
    _inherit = 'project.task'

    entry_date = fields.Date(string='Entry Date', default=fields.Date.today)
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Quotation/Order',
        domain="[('partner_id', '=', partner_id), ('state', 'in', ['draft', 'sent', 'sale'])]",
        options="{'no_create': True}",
        context="{'display_sale_order_origin': True}",
        readonly=False,  # Explicitly set readonly to False
        states={'done': [('readonly', True)]},  # Only readonly when task is done
    )
    # Add the missing order_total field
    order_total = fields.Monetary(string='Order Total', compute='_compute_order_total', store=True)

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    color = fields.Integer(string='Color Index')
    days_until_deadline = fields.Integer(string='Days Until Deadline', compute='_compute_days_until_deadline')
    deadline_status = fields.Char(string='Deadline Status', compute='_compute_days_until_deadline')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done')
    ], string='Status', default='draft', tracking=True)
    
    @api.depends('sale_order_id', 'sale_order_id.amount_total')
    def _compute_order_total(self):
        for task in self:
            try:
                if task.sale_order_id and task.sale_order_id.amount_total:
                    task.order_total = task.sale_order_id.amount_total
                else:
                    task.order_total = 0
            except Exception as e:
                task.order_total = 0
                _logger.error(f"Error computing order_total for task {task.id}: {str(e)}")

    @api.depends('entry_date', 'date_deadline')
    def _compute_days_until_deadline(self):
        for task in self:
            if task.entry_date and task.date_deadline:
                duration = (task.date_deadline - task.entry_date).days
                task.days_until_deadline = duration
                task.deadline_status = f"Task duration: {duration} days"
            else:
                task.days_until_deadline = 0
                task.deadline_status = ""

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if not self.partner_id:
            self.sale_order_id = False
        else:
            # This will help refresh the domain
            return {'domain': {'sale_order_id': [
                ('partner_id', '=', self.partner_id.id),
                ('state', 'in', ['draft', 'sent', 'sale'])
            ]}}