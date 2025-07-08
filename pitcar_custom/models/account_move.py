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

    # TAMBAHAN FIELD VENDOR DI HEADER - UNTUK LIST VIEW
    vendor_id = fields.Many2one(
        'res.partner', 
        string='Vendor',
        domain="[]",  # Tidak ada domain restriction, sama seperti partner
        help="Primary Vendor/Supplier for this journal entry",
        tracking=True,
        index=True,
        compute='_compute_vendor_from_lines',
        store=True,
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

    @api.depends('line_ids.vendor_id')
    def _compute_vendor_from_lines(self):
        """Compute vendor from journal lines - ambil vendor pertama yang ada"""
        for move in self:
            vendor_line = move.line_ids.filtered('vendor_id')
            move.vendor_id = vendor_line[0].vendor_id if vendor_line else False

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


# TAMBAHAN MODEL UNTUK ACCOUNT MOVE LINE - FIELD VENDOR DI JOURNAL ITEMS
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    vendor_id = fields.Many2one(
        'res.partner', 
        string='Vendor',
        domain="[]",  # Tidak ada domain restriction, sama seperti partner
        help="Vendor/Supplier for this journal item",
        tracking=True,
        index=True,
    )

    # FIELDS BARU UNTUK NOMOR HP DAN CUSTOMER SOURCE
    customer_phone = fields.Char(
        string='Customer Phone',
        compute='_compute_customer_info',
        store=True,
        help="Customer phone number from sale order or partner"
    )
    
    customer_source = fields.Selection([
        ('loyal', 'Loyal'),
        ('fb_ads', 'FB Ads'),
        ('referral', 'Referral'),
        ('all_b2b', 'All B2B'),
        ('ig_ads', 'IG Ads'),
        ('google_maps', 'Google Maps'),
        ('tiktok_ads', 'Tiktok Ads'),
        ('ig_organic', 'IG Organic'),
        ('beli_part', 'Beli Part'),
        ('web_paid_ads', 'Web - Paid Ads'),
        ('web_organic', 'Web - Organic'),
        ('workshop', 'Workshop'),
        ('relation', 'Relation'),
        ('youtube', 'Youtube'),
        ('tidak_dapat_info', 'Tidak Dapat Info'),
    ], 
    string='Customer Source',
    compute='_compute_customer_info',
    store=True,
    help="Customer source from sale order"
    )

    is_loyal_customer = fields.Boolean(
        string='Loyal Customer',
        compute='_compute_customer_info',
        store=True,
        help="Indicates if the customer has more than one transaction"
    )

    @api.depends('move_id.invoice_origin_sale_id', 'partner_id', 'move_id.partner_id')
    def _compute_customer_info(self):
        # Kumpulkan semua partner_id yang relevan
        partner_ids = set()
        for line in self:
            partner = (line.move_id.invoice_origin_sale_id.partner_id or
                    line.partner_id or
                    line.move_id.partner_id)
            if partner:
                partner_ids.add(partner.id)

        # Hitung transaction_count untuk semua partner sekaligus
        transaction_counts = {
            partner_id: self.env['account.move'].search_count([
                ('partner_id', '=', partner_id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted')
            ]) for partner_id in partner_ids
        }

        for line in self:
            line.customer_phone = False
            line.customer_source = False
            line.is_loyal_customer = False

            partner = False
            if line.move_id.invoice_origin_sale_id:
                sale_order = line.move_id.invoice_origin_sale_id
                if sale_order.partner_id:
                    line.customer_phone = sale_order.partner_id.phone or sale_order.partner_id.mobile
                    line.customer_source = sale_order.customer_sumber_info
                    partner = sale_order.partner_id
            elif line.partner_id:
                line.customer_phone = line.partner_id.phone or line.partner_id.mobile
                if line.partner_id.sumber_info_id:
                    line.customer_source = line.partner_id.sumber_info_id[0].sumber
                    partner = line.partner_id
            elif line.move_id.partner_id:
                line.customer_phone = line.move_id.partner_id.phone or line.move_id.partner_id.mobile
                if line.move_id.partner_id.sumber_info_id:
                    line.customer_source = line.move_id.partner_id.sumber_info_id[0].sumber
                    partner = line.move_id.partner_id

            if partner:
                line.is_loyal_customer = transaction_counts.get(partner.id, 0) > 1
                if line.is_loyal_customer and not line.customer_source:
                    line.customer_source = 'loyal'

    # @api.onchange('partner_id')
    # def _onchange_partner_id_vendor_line(self):
    #     """Auto-copy partner to vendor field (user bisa ubah manual jika perlu)"""
    #     if self.partner_id:
    #         self.vendor_id = self.partner_id

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger header vendor computation"""
        lines = super().create(vals_list)
        # Trigger recompute vendor di header
        moves = lines.mapped('move_id')
        moves._compute_vendor_from_lines()
        return lines

    def write(self, vals):
        """Override write to trigger header vendor computation"""
        result = super().write(vals)
        if 'vendor_id' in vals:
            # Trigger recompute vendor di header
            moves = self.mapped('move_id')
            moves._compute_vendor_from_lines()
        return result
