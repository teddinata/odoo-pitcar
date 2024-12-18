from odoo import models, fields, api, _, exceptions

class AccountMove(models.Model):
    _inherit = 'account.move'

    # Field baru untuk Service Advisor yang merujuk ke model 'pitcar.service.advisor'
    service_advisor_id = fields.Many2many(
        'pitcar.service.advisor',
        string="Service Advisors",
        help="Select multiple Service Advisors for this sales order"
    )

    partner_car_id = fields.Many2one(
        'res.partner.car',
        string="Serviced Car",
        domain="[('partner_id','=',partner_id)]",
        tracking=True,
        index=True,
    )
    partner_car_brand = fields.Many2one(
        string="Car Brand",
        related="partner_car_id.brand",
        store=True,
    )
    partner_car_brand_type = fields.Many2one(
        string="Car Brand Type",
        related="partner_car_id.brand_type",
        store=True,
    )
    partner_car_year = fields.Char(
        string="Car Year",
        related="partner_car_id.year",
        store=True,
    )
    partner_car_odometer = fields.Float(
        string="Odometer",
    )
    car_mechanic_id = fields.Many2one(
        'pitcar.mechanic',
        string="Mechanic (Old Input)",
        tracking=True,
        index=True,
    )
    car_mechanic_id_new = fields.Many2many(
        'pitcar.mechanic.new',
        string="Mechanic (New input)",
        index=True,
        readonly=True,
    )
    generated_mechanic_team = fields.Char(
        string="Mechanic",
        compute="_compute_generated_mechanic_team",
        store=True,
    )
    date_sale_completed = fields.Datetime(
        string="Sale Completed Date",
        readonly=True,
        help="Date when the sale is completed"
    )
    date_sale_quotation = fields.Datetime(
        string="Sale Quotation Date",
        readonly=True,
        help="Date when the sale is quoted"
    )
    car_arrival_time = fields.Datetime(
        string="Car Arrival Time",
        help="Record the time when the car arrived."
    )
    
    @api.depends('car_mechanic_id_new')
    def _compute_generated_mechanic_team(self):
        for account in self:
            account.generated_mechanic_team = ', '.join(account.car_mechanic_id_new.mapped('name'))

    # Method untuk menandai service advisor yang terlibat dalam transaksi
    def action_mark_service_advisor(self):
        for account in self:
            account.service_advisor_id = [(6, 0, account.partner_id.service_advisor_ids.ids)]
        return True
    
    # def _post(self, soft=True):
    #     res = super()._post(soft=soft)
    #     self._update_mechanic_kpi()
    #     return res

    # def action_register_payment(self):
    #     res = super().action_register_payment()
    #     self._update_mechanic_kpi()
    #     return res

    invoice_origin_sale_id = fields.Many2one(
        'sale.order', 
        string='Source Sale Order',
        compute='_compute_invoice_origin_sale'
    )

    recommendation_ids = fields.One2many(
        'sale.order.recommendation',
        related='invoice_origin_sale_id.recommendation_ids',
        string='Service Recommendations',
        readonly=True
    )

    @api.depends('invoice_origin')
    def _compute_invoice_origin_sale(self):
        for move in self:
            # Get sale order from invoice origin
            if move.invoice_origin:
                sale_order = self.env['sale.order'].search([
                    ('name', '=', move.invoice_origin)
                ], limit=1)
                move.invoice_origin_sale_id = sale_order.id
            else:
                move.invoice_origin_sale_id = False
