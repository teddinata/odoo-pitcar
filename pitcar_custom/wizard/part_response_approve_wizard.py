from odoo import models, fields, api, _
import logging

class PartResponseApproveWizard(models.TransientModel):
    _name = 'part.response.approve.wizard'
    _description = 'Wizard Konfirmasi Approval Response Part'

    part_item_id = fields.Many2one('sale.order.part.item', string='Part Item', required=True)
    approve_message = fields.Text('Pesan Konfirmasi')

    def action_confirm(self):
        self.ensure_one()
        if not self.part_item_id:
            return
            
        self.part_item_id.write({
            'is_fulfilled': True,
            'approve_message': self.approve_message,
            'approved_date': fields.Datetime.now(),
            'approved_by': self.env.user.id,
            'state': 'approved'  # Update state
        })

        
        # Post message to chatter
        msg = f"""
            <p><strong>Estimasi Tim Part Disetujui</strong></p>
            <ul>
                <li>Part: {self.part_item_id.part_name}</li>
                <li>Alasan: {self.approve_message}</li>
                <li>Disetujui oleh: {self.env.user.name}</li>
            </ul>
        """
        self.part_item_id.sale_order_id.message_post(body=msg)