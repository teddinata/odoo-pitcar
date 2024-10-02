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
