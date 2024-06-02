from odoo import models, fields, api, _, exceptions

class AccountMove(models.Model):
    _inherit = 'account.move'

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
    
    @api.depends('car_mechanic_id_new')
    def _compute_generated_mechanic_team(self):
        for account in self:
            account.generated_mechanic_team = ', '.join(account.car_mechanic_id_new.mapped('name'))