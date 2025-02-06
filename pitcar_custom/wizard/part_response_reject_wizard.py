# Part of 'pitcar_custom' module.
from odoo import models, fields, api

class PartResponseRejectWizard(models.TransientModel):
    _name = 'part.response.reject.wizard'
    _description = 'Wizard Penolakan Estimasi Part'

    part_item_id = fields.Many2one('sale.order.part.item', string='Part Item')
    reason = fields.Text('Alasan Penolakan', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.part_item_id:
            return
            
        self.part_item_id.write({
            'is_fulfilled': False,
            'rejection_reason': self.reason,
            'approved_date': fields.Datetime.now(),
            'approved_by': self.env.user.id,
            'state': 'rejected'  # Update state
        })

        
        # Post message to chatter
        msg = f"""
            <p><strong>Estimasi Tim Part Ditolak</strong></p>
            <ul>
                <li>Part: {self.part_item_id.part_name}</li>
                <li>Alasan: {self.reason}</li>
                <li>Ditolak oleh: {self.env.user.name}</li>
            </ul>
        """
        self.part_item_id.sale_order_id.message_post(body=msg)