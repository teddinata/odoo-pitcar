from odoo import models, fields

class FeedbackClassification(models.Model):
    _name = 'feedback.classification'
    _description = 'Feedback Classification'

    name = fields.Char(string='Name', required=True)
