# models/res_users.py - Replace your current file
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Existing fields from your original file
    pitcar_role = fields.Selection([
        ('service_advisor', 'Service Advisor'),
        ('controller', 'Controller'),
        ('user', 'User')
    ], string='PitCar Role', default='user', tracking=True)

    # Keep karma as simple Integer - no fancy description that might reference LMS
    karma = fields.Integer(string='Karma', default=0)

    @api.model
    def create(self, vals):
        user = super(ResUsers, self).create(vals)
        try:
            self._update_pitcar_role(user)
        except Exception as e:
            _logger.error(f"Error updating pitcar role: {str(e)}")
        return user

    def write(self, vals):
        # Jika pitcar_role diubah, update groups
        if 'pitcar_role' in vals:
            try:
                self._update_groups_for_role(vals['pitcar_role'])
            except Exception as e:
                _logger.error(f"Error updating groups for role: {str(e)}")
            
        # Jika groups diubah, update role    
        if 'groups_id' in vals:
            res = super(ResUsers, self).write(vals)
            for user in self:
                try:
                    self._update_pitcar_role(user)
                except Exception as e:
                    _logger.error(f"Error updating pitcar role: {str(e)}")
            return res
            
        return super(ResUsers, self).write(vals)

    @api.model 
    def _update_pitcar_role(self, user):
        try:
            sa_group = self.env.ref('pitcar_custom.group_service_advisor', raise_if_not_found=False)
            controller_group = self.env.ref('pitcar_custom.group_controller', raise_if_not_found=False)
            
            if sa_group and sa_group in user.groups_id:
                user.sudo().write({'pitcar_role': 'service_advisor'})
            elif controller_group and controller_group in user.groups_id:
                user.sudo().write({'pitcar_role': 'controller'})
            else:
                user.sudo().write({'pitcar_role': 'user'})
        except Exception as e:
            _logger.error(f"Error updating pitcar role: {str(e)}")

    def _update_groups_for_role(self, new_role):
        try:
            sa_group = self.env.ref('pitcar_custom.group_service_advisor', raise_if_not_found=False)
            controller_group = self.env.ref('pitcar_custom.group_controller', raise_if_not_found=False)
            
            if not sa_group or not controller_group:
                _logger.warning("LMS groups not found, skipping group update")
                return
            
            # Prepare commands based on new role
            if new_role == 'service_advisor':
                commands = [(4, sa_group.id), (3, controller_group.id)]
            elif new_role == 'controller':
                commands = [(4, controller_group.id), (3, sa_group.id)]
            else:  # user
                commands = [(3, sa_group.id), (3, controller_group.id)]
            
            # Update groups
            self.sudo().write({'groups_id': commands})
        except Exception as e:
            _logger.error(f"Error updating groups: {str(e)}")
            # Don't raise UserError in basic model operations