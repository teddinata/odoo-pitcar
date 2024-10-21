from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Tambahkan satu field dahulu
    pitcar_role = fields.Selection([
        ('service_advisor', 'Service Advisor'),
        ('controller', 'Controller'),
        ('other', 'Other')
    ], string='PitCar Role', default='other')

    @api.model
    def create(self, vals):
        user = super(ResUsers, self).create(vals)
        self._update_pitcar_role(user)
        return user

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        if 'groups_id' in vals:
            for user in self:
                self._update_pitcar_role(user)
        return res

    @api.model
    def _update_pitcar_role(self, user):
        sa_group = self.env.ref('pitcar_custom.group_service_advisor')
        controller_group = self.env.ref('pitcar_custom.group_controller')
        
        if sa_group in user.groups_id:
            user.pitcar_role = 'service_advisor'
        elif controller_group in user.groups_id:
            user.pitcar_role = 'controller'
        else:
            user.pitcar_role = 'other'

    @api.onchange('pitcar_role')
    def _onchange_pitcar_role(self):
        sa_group = self.env.ref('pitcar_custom.group_service_advisor')
        controller_group = self.env.ref('pitcar_custom.group_controller')
        
        if self.pitcar_role == 'service_advisor':
            self.groups_id = [(4, sa_group.id), (3, controller_group.id)]
        elif self.pitcar_role == 'controller':
            self.groups_id = [(4, controller_group.id), (3, sa_group.id)]
        else:
            self.groups_id = [(3, sa_group.id), (3, controller_group.id)]

    # Jangan gunakan onchange untuk mengubah groups_id, gunakan write method sebagai gantinya
    # def write(self, vals):
    #     res = super(ResUsers, self).write(vals)
    #     if 'pitcar_role' in vals:
    #         self.sudo()._update_groups_for_role()
    #     return res

    # def _update_groups_for_role(self):
    #     sa_group = self.env.ref('pitcar_custom.group_service_advisor')
    #     controller_group = self.env.ref('pitcar_custom.group_controller')
    #     for user in self:
    #         if user.pitcar_role == 'service_advisor':
    #             user.groups_id = [(4, sa_group.id), (3, controller_group.id)]
    #         elif user.pitcar_role == 'controller':
    #             user.groups_id = [(4, controller_group.id), (3, sa_group.id)]
    #         else:
    #             user.groups_id = [(3, sa_group.id), (3, controller_group.id)]
