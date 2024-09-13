from odoo import models, fields, api, _, exceptions

class StockPicking(models.Model):
    _inherit = 'stock.picking'

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
    partner_car_odometer = fields.Float(string="Odometer", tracking=True)
    car_mechanic_id = fields.Many2one('pitcar.mechanic', string="Mechanic (Old Input)", index=True)
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
    
    @api.depends('car_mechanic_id_new')
    def _compute_generated_mechanic_team(self):
        for order in self:
            order.generated_mechanic_team = ', '.join(order.car_mechanic_id_new.mapped('name'))

    # Method untuk menandai service advisor yang terlibat dalam transaksi    

