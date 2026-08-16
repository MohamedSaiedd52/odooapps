# -*- coding: utf-8 -*-
from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    secondary_uom_id = fields.Many2one(
        'uom.uom',
        string='Secondary UoM',
        related='product_id.secondary_uom_id',
        readonly=True,
    )
    
    secondary_uom_qty = fields.Float(
        string='Secondary Qty',
        digits='Product Unit of Measure',
        compute='_compute_secondary_uom_qty',
        store=True
    )

    @api.depends('product_id', 'quantity')
    def _compute_secondary_uom_qty(self):
        for line in self:
            conversion_factor = line.product_id.conversion_factor or 1.0
            if line.product_id.secondary_uom_id:
                line.secondary_uom_qty = line.quantity * conversion_factor
            else:
                line.secondary_uom_qty = 0.0