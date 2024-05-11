from odoo import models, fields, api, _, exceptions

READONLY_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'sale', 'done', 'cancel'}
}

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_car_id = fields.Many2one(
        'res.partner.car',
        string="Serviced Car",
        tracking=True,
        index=True,
        readonly=False,
        states=READONLY_FIELD_STATES,
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
        tracking=True,
    )
    partner_car_transmission = fields.Many2one(
        'res.partner.car.transmission',
        string="Transmission",
        related="partner_car_id.transmission",
        store=True,
    )
    partner_car_engine_type = fields.Selection(
        string="Engine Type",
        related="partner_car_id.engine_type",
        store=True,
    )
    partner_car_engine_number = fields.Char(
        string="Engine Number",
        related="partner_car_id.engine_number",
        store=True,
    )
    partner_car_frame_number = fields.Char(
        string="Frame Number",
        related="partner_car_id.frame_number",
        store=True,
    )
    partner_car_color = fields.Char(
        string="Color",
        related="partner_car_id.color",
        store=True,
    )
    car_mechanic_id = fields.Many2one(
        'pitcar.mechanic',
        string="Mechanic (Old Input)",
        tracking=True,
        index=True,
        readonly=True,
    )
    car_mechanic_id_new = fields.Many2many(
        'pitcar.mechanic.new',
        string="Mechanic",
        tracking=True,
        index=True,
    )
    
    @api.onchange('partner_car_id')
    def _onchange_partner_car_id(self):
        for order in self:
            order.partner_id = order.partner_car_id.partner_id.id
            
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for order in self:
            if order.partner_id:
                return {
                    'domain': {
                        'partner_car_id': [
                            ('partner_id', '=', order.partner_id.id)
                        ]
                    }
                }
            return 
    
    # Copying car information from sales order to delivery data when sales confirmed
    # model : stock.picking
    def _action_confirm(self):
        res = super(SaleOrder, self)._action_confirm()
        for order in self:
            if hasattr(order, 'picking_ids'):
                for picking in order.picking_ids:
                    picking.partner_car_id = order.partner_car_id
                    picking.partner_car_odometer = order.partner_car_odometer
                    picking.car_mechanic_id = order.car_mechanic_id
        return res

    # Copying car information from sales order to invoice data when invoice created
    # model : account.move
    def _create_invoices(self, grouped=False, final=False):
        res = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
        for order in self:
            for invoice in order.invoice_ids:
                invoice.partner_car_id = order.partner_car_id
                invoice.partner_car_odometer = order.partner_car_odometer
                invoice.car_mechanic_id = order.car_mechanic_id
        return res
    