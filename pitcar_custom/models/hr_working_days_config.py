import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class WorkingDaysConfig(models.Model):
    _name = 'hr.working.days.config'
    _description = 'Working Days Configuration'
    _order = 'year desc, month desc'

    name = fields.Char('Name', required=True)
    month = fields.Integer('Month', required=True)
    year = fields.Integer('Year', required=True)
    working_days = fields.Integer('Working Days', required=True)
    notes = fields.Text('Notes')

     # Tracking fields
    create_uid = fields.Many2one('res.users', string='Created by', readonly=True)
    create_date = fields.Datetime(string='Created on', readonly=True)
    write_uid = fields.Many2one('res.users', string='Last Updated by', readonly=True)
    write_date = fields.Datetime(string='Last Updated on', readonly=True)
    
    @api.constrains('working_days')
    def _check_working_days(self):
        for record in self:
            if record.working_days < 1 or record.working_days > 31:
                raise ValidationError('Working days must be between 1 and 31')
    
    @api.constrains('month')
    def _check_month(self):
        for record in self:
            if record.month < 1 or record.month > 12:
                raise ValidationError('Month must be between 1 and 12')
    
    _sql_constraints = [
        ('month_year_unique', 
         'unique(month, year)', 
         'Working days configuration already exists for this month and year!')
    ]