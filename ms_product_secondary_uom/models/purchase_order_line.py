# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    secondary_uom_id = fields.Many2one(
        'uom.uom',
        string='Secondary UoM',
        related='product_id.secondary_uom_id',
        readonly=True,
    )
    secondary_uom_qty = fields.Float(
        string='Secondary Qty',
        digits='Product Unit of Measure',
    )
