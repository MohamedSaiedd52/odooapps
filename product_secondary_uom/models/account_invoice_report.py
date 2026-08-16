# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    _inherit = 'account.invoice.report'

    secondary_uom_id = fields.Many2one('uom.uom', string='Secondary UoM', readonly=True)
    secondary_uom_qty = fields.Float(string='Secondary Qty', readonly=True)

    # sign-corrected like the standard quantity column
    _SECONDARY_SELECT = (
        ", template.secondary_uom_id AS secondary_uom_id"
        ", line.secondary_uom_qty *"
        " (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt')"
        " THEN -1 ELSE 1 END) AS secondary_uom_qty"
    )

    @api.model
    def _select(self):
        res = super()._select()
        if isinstance(res, str):
            # Odoo 17: the query parts are plain strings composed with '%'
            return res + self._SECONDARY_SELECT
        # Odoo 18/19: the query parts are odoo.tools.SQL objects
        return SQL('%s' + self._SECONDARY_SELECT, res)
