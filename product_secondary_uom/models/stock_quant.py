# -*- coding: utf-8 -*-
from odoo import api, fields, models

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    secondary_uom_id = fields.Many2one(
        'uom.uom',
        string='Secondary UoM',
        related='product_id.secondary_uom_id',
        readonly=True,
    )

    # شيلنا store=True عشان الرقم يتحدث لحظياً
    secondary_uom_qty = fields.Float(
        string='Secondary Qty',
        compute='_compute_secondary_uom_qty'
    )

    # ربطنا المعادلة بالكمية ومعامل التحويل عشان تتحدث أوتوماتيك
    @api.depends('quantity', 'product_id.conversion_factor', 'product_id.secondary_uom_id')
    def _compute_secondary_uom_qty(self):
        for quant in self:
            # لو معامل التحويل بصفر أو مش مكتوب، بنعتبره 1 عشان ميضربش إيرور
            factor = quant.product_id.conversion_factor if quant.product_id.conversion_factor else 1.0
            
            if quant.product_id.secondary_uom_id:
                quant.secondary_uom_qty = quant.quantity * factor
            else:
                quant.secondary_uom_qty = 0.0