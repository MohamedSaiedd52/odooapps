# -*- coding: utf-8 -*-
from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

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
        store=True, # ضروري جداً عشان يسمّع في التقارير
    )

    @api.depends('product_uom_qty', 'product_id.conversion_factor')
    def _compute_secondary_uom_qty(self):
        for line in self:
            # لو الصنف ليه معامل تحويل، اضرب الكمية الأساسية في المعامل
            if line.product_id and line.product_id.conversion_factor:
                line.secondary_uom_qty = line.product_uom_qty * line.product_id.conversion_factor
            else:
                line.secondary_uom_qty = 0.0