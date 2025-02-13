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

    is_stock_audit = fields.Boolean(
        'Is Stock Audit',
        help='Centang jika jurnal ini untuk pencatatan selisih audit'
    )
    audit_type = fields.Selection([
        ('part', 'Part'),
        ('tool', 'Tool')
    ], string='Audit Type',
    help='Pilih tipe audit: Part atau Tool')
    audit_difference = fields.Float(
        'Selisih Audit', 
        compute='_compute_audit_difference',
        store=True,
        help='Selisih antara nilai sistem dan aktual'
    )

    is_within_tolerance = fields.Boolean(
        'Within Tolerance',
        compute='_compute_is_within_tolerance',
        store=True
    )

    @api.onchange('is_stock_audit')
    def _onchange_is_stock_audit(self):
        if self.is_stock_audit:
            self.ref = 'Selisih audit stock '
        else:
            self.audit_type = False
            
    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_audit_difference(self):
        for move in self:
            if move.is_stock_audit:
                # Ambil selisih dari line pertama
                line = move.line_ids[0] if move.line_ids else False
                if line:
                    move.audit_difference = line.debit - line.credit
            else:
                move.audit_difference = 0

    @api.depends('audit_difference')
    def _compute_is_within_tolerance(self):
        for move in self:
            if move.is_stock_audit:
                move.is_within_tolerance = abs(move.audit_difference) < 200000 
            else:
                move.is_within_tolerance = False

    # Override untuk memastikan referensi selisih audit terformat benar
    @api.onchange('is_stock_audit', 'audit_type', 'date')
    def _onchange_audit_fields(self):
        if self.is_stock_audit and self.audit_type and self.date:
            type_text = 'Part' if self.audit_type == 'part' else 'Tools'
            self.ref = f'Selisih audit stock {type_text} {self.date.strftime("%d/%m/%Y")}'


    
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
