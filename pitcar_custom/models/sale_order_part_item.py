
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import pytz
from datetime import datetime, timedelta

class SaleOrderPartItem(models.Model):
    _name = 'sale.order.part.item'
    _description = 'Sale Order Part Request Item'
    _rec_name = 'part_name'

    sale_order_id = fields.Many2one('sale.order', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    part_name = fields.Char('Nama Part', required=True)
    part_number = fields.Char('Nomor Part')
    quantity = fields.Integer('Jumlah', default=1)
    notes = fields.Text('Catatan Item')
    
     # Response fields
    is_fulfilled = fields.Boolean('Terpenuhi', default=False)
    response_time = fields.Datetime('Waktu Respon')
    response_deadline = fields.Datetime(
        compute='_compute_response_deadline',
        string='Batas Waktu Respon',
        store=True
    )
    alternative_part = fields.Char('Part Alternatif')
    estimated_cost = fields.Float('Estimated Cost')
    estimated_arrival = fields.Datetime('Estimasi Kedatangan')
    response_notes = fields.Text('Catatan Respon')
    is_response_late = fields.Boolean(
        compute='_compute_is_response_late',
        string='Respon Terlambat',
        store=True
    )

    # Tambahkan field untuk tracking approval
    approved_date = fields.Datetime('Tanggal Persetujuan')
    approved_by = fields.Many2one('res.users', string='Disetujui Oleh')
    rejection_reason = fields.Text('Alasan Penolakan')
    approve_message = fields.Text('Pesan Persetujuan')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('responded', 'Responded'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)

    def action_approve_part_response(self):
        """SA menyetujui estimasi dari tim part"""
        self.ensure_one()
        
        # Validasi
        if not self.response_time:
            raise UserError("Tidak dapat menyetujui. Tim Part belum memberikan respon.")
            
        # Tampilkan konfirmasi
        return {
            'name': 'Konfirmasi Persetujuan',
            'type': 'ir.actions.act_window',
            'res_model': 'part.response.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': { 'default_part_item_id': self.id }
        }

    def write(self, vals):
        # Jika ada response time dan state masih draft, update ke responded
        if vals.get('response_time') and self.state == 'draft':
            vals['state'] = 'responded'
        return super().write(vals)

    # Di SaleOrderPartItem
    @api.depends('state')
    def _compute_is_fulfilled(self):
        for item in self:
            item.is_fulfilled = item.state == 'approved'

    def _do_approve(self):
        """Internal method untuk proses approval setelah konfirmasi"""
        vals = {
            'state': 'approved',  # Update state dulu
            'approved_date': fields.Datetime.now(),
            'approved_by': self.env.user.id
        }
        self.write(vals)
        
        # is_fulfilled akan terupdate otomatis lewat compute
        # Dan akan trigger _compute_items_status di sale order
        
        msg = f"""
            <p><strong>Estimasi Tim Part Disetujui</strong></p>
            <ul>
                <li>Part: {self.part_name}</li>
                <li>Estimasi Biaya: {self.estimated_cost:,.2f}</li>
                <li>Estimasi Kedatangan: {self.estimated_arrival}</li>
                <li>Disetujui oleh: {self.env.user.name}</li>
            </ul>
        """
        self.sale_order_id.message_post(body=msg)


    def action_reject_part_response(self):
        """Method untuk membuka wizard penolakan estimasi part"""
        self.ensure_one()
        if not self.response_time:
            raise UserError("Tidak dapat menolak. Tim Part belum memberikan respon.")
            
        # Open wizard untuk input alasan penolakan
        return {
            'name': 'Alasan Penolakan',
            'type': 'ir.actions.act_window',
            'res_model': 'part.response.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_part_item_id': self.id}
        }


    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.part_name = self.product_id.get_product_multiline_description_sale()
            self.part_number = self.product_id.default_code

    @api.depends('sale_order_id.part_request_time')
    def _compute_response_deadline(self):
        for item in self:
            if item.sale_order_id.part_request_time:
                item.response_deadline = item.sale_order_id.part_request_time + timedelta(minutes=15)
            else:
                item.response_deadline = False

    @api.depends('response_deadline', 'response_time', 'state')
    def _compute_is_response_late(self):
        now = fields.Datetime.now()
        for item in self:
            if item.state in ['approved', 'rejected']:
                item.is_response_late = False
            elif item.response_deadline:
                if not item.response_time:
                    item.is_response_late = now > item.response_deadline
                else:
                    item.is_response_late = item.response_time > item.response_deadline
            else:
                item.is_response_late = False