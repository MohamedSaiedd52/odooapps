# -*- coding: utf-8 -*-
from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    secondary_uom_id = fields.Many2one(
        'uom.uom',
        string='Secondary Unit of Measure',
        help="Alternative unit of measure for this product. Independent from the primary UoM."
    )

    conversion_factor = fields.Float(
        string='معامل التحويل',
        default=1.0,
        help="المعامل لضرب الكمية الأساسية وتحويلها للوحدة الثانوية"
    )