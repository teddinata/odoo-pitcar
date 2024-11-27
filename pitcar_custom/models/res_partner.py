from odoo import models, fields, api, _, exceptions
from random import randint

class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    partner_count = fields.Integer(string="Partner Count", compute='_compute_partner_count')

    @api.depends('partner_ids')
    def _compute_partner_count(self):
        for category in self:
            category.partner_count = len(category.partner_ids)


class ResPartnerSource(models.Model):
    _name = 'res.partner.source'
    _description = 'Source of partner'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

class ResPartner(models.Model):
    _inherit = ['res.partner']

    gender = fields.Selection(
        [('male', 'Male'), 
         ('female', 'Female'),
        ], string="Gender"
    )
    source = fields.Many2one('res.partner.source', string="Source")
    dob = fields.Date(string="Date of Birth")
    car_ids = fields.One2many('res.partner.car', 'partner_id', string="Cars")
    category_id = fields.Many2many('res.partner.category', column1='partner_id',
                                    column2='category_id', string='Tags', required=True)
    phone = fields.Char(unaccent=False, required=True)

class PitcarMechanic(models.Model):
    _name = 'pitcar.mechanic'
    _description = 'Mechanic'
    _order = 'name'

    name = fields.Char(string="Name", required=True)
    
class PitcarMechanicNew(models.Model):
    _name = 'pitcar.mechanic.new'
    _description = 'Mechanic'
    _order = 'name'
    
    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string="Name", required=True, tracking=True)
    color = fields.Integer('Color', default=_get_default_color)
    position_id = fields.Many2one('pitcar.position', string="Position", required=True)
    position_code = fields.Selection(
        related='position_id.code',
        string='Position Code',
        store=True
    )
    leader_id = fields.Many2one(
        'pitcar.mechanic.new',
        string='Team Leader',
        domain="[('position_code', '=', 'leader')]"
    )
    team_member_ids = fields.One2many(
        'pitcar.mechanic.new',
        'leader_id',
        string='Team Members'
    )
    monthly_target = fields.Float(
        string='Monthly Target',
        compute='_compute_monthly_target',
        store=True
    )
    current_revenue = fields.Float(
        string='Current Revenue',
        compute='_compute_revenue_metrics'
    )
    target_achievement = fields.Float(
        string='Target Achievement (%)',
        compute='_compute_revenue_metrics'
    )

    @api.depends('position_id', 'team_member_ids')
    def _compute_monthly_target(self):
        for mechanic in self:
            if mechanic.position_code == 'leader':
                mechanic.monthly_target = len(mechanic.team_member_ids) * 64000000
            else:
                mechanic.monthly_target = 64000000

    @api.depends('monthly_target')
    def _compute_revenue_metrics(self):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        
        for mechanic in self:
            # Calculate revenue
            if mechanic.position_code == 'leader':
                domain = [
                    ('car_mechanic_id_new', 'in', mechanic.team_member_ids.ids),
                    ('date_order', '>=', first_day),
                    ('date_order', '<=', today),
                    ('state', '=', 'sale')
                ]
            else:
                domain = [
                    ('car_mechanic_id_new', '=', mechanic.id),
                    ('date_order', '>=', first_day),
                    ('date_order', '<=', today),
                    ('state', '=', 'sale')
                ]

            orders = self.env['sale.order'].search(domain)
            mechanic.current_revenue = sum(orders.mapped('amount_total'))
            
            # Calculate achievement percentage
            if mechanic.monthly_target:
                mechanic.target_achievement = (mechanic.current_revenue / mechanic.monthly_target) * 100
            else:
                mechanic.target_achievement = 0
    
    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Mechanic name already exists !"),
    ]

