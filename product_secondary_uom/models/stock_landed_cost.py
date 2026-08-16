from odoo import models, fields, api

class StockValuationAdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'

    secondary_uom_id = fields.Many2one(
        'uom.uom', 
        related='product_id.secondary_uom_id', 
        string='Secondary UoM', 
        store=True,
        readonly=True
    )
    
    # حولنا الحقل لـ Compute عشان لو الداتا قديمة وفيها أصفار، يحسبها هو أوتوماتيك
    secondary_uom_qty = fields.Float(
        string='Secondary Quantity', 
        compute='_compute_secondary_qty',
        store=True
    )

    # هنا نفذنا فكرة المدير: ربطنا حقل الوزن الافتراضي بالكمية التانية بتاعتنا
    weight = fields.Float(
        string='Weight',
        compute='_compute_weight_from_secondary',
        store=True
    )

    @api.depends('move_id.secondary_uom_qty', 'quantity', 'product_id.conversion_factor')
    def _compute_secondary_qty(self):
        for line in self:
            # لو الحركة فيها كمية تانية أكبر من صفر، اسحبها
            if line.move_id and line.move_id.secondary_uom_qty > 0:
                line.secondary_uom_qty = line.move_id.secondary_uom_qty
            # لو بصفر (حركات قديمة)، اضرب الكمية الأصلية في معامل التحويل
            else:
                conversion = line.product_id.conversion_factor or 1.0
                line.secondary_uom_qty = line.quantity * conversion

    @api.depends('secondary_uom_qty')
    def _compute_weight_from_secondary(self):
        for line in self:
            # تغذية حقل الوزن بالكمية التانية عشان أودو يحسب التوزيع أوتوماتيك
            line.weight = line.secondary_uom_qty