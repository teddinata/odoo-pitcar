from odoo import models, fields, tools

class StockAuditReport(models.Model):
    _name = 'stock.audit.report'
    _description = 'Stock Audit Report'
    _auto = False

    date = fields.Date('Audit Date')
    audit_type = fields.Selection([
        ('part', 'Part'),
        ('tool', 'Tool')
    ], string='Type')
    total_audits = fields.Integer('Total Audits')
    within_tolerance = fields.Integer('Within Tolerance')
    success_rate = fields.Float('Success Rate (%)')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    MIN(id) as id,
                    date as date,
                    audit_type,
                    COUNT(*) as total_audits,
                    SUM(CASE WHEN is_within_tolerance THEN 1 ELSE 0 END) as within_tolerance,
                    (SUM(CASE WHEN is_within_tolerance THEN 1 ELSE 0 END)::float / COUNT(*)::float * 100) as success_rate
                FROM account_move
                WHERE is_stock_audit = true
                GROUP BY date, audit_type
            )
        """ % self._table)