from odoo import api, fields, models

class StockMove(models.Model):
    _inherit = 'stock.move'

    secondary_uom_id = fields.Many2one(
        'uom.uom',
        string='Secondary UoM',
        related='product_id.secondary_uom_id',
        readonly=True,
    )

    secondary_uom_qty = fields.Float(
        string='Secondary Qty',
        compute='_compute_secondary_uom_qty',
        store=True
    )

    # "Sec. Done": mirrors the done quantity in the secondary UoM
    secondary_quantity = fields.Float(
        string='Secondary Done Qty',
        compute='_compute_secondary_quantity',
        store=True
    )

    @api.depends('product_id', 'product_uom_qty')
    def _compute_secondary_uom_qty(self):
        for move in self:
            conversion_factor = move.product_id.conversion_factor or 1.0
            if move.product_id.secondary_uom_id:
                move.secondary_uom_qty = move.product_uom_qty * conversion_factor
            else:
                move.secondary_uom_qty = 0.0

    @api.depends('product_id', 'quantity')
    def _compute_secondary_quantity(self):
        for move in self:
            conversion_factor = move.product_id.conversion_factor or 1.0
            if move.product_id.secondary_uom_id:
                move.secondary_quantity = move.quantity * conversion_factor
            else:
                move.secondary_quantity = 0.0

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # بنسحب الحقل من الحركة الرئيسية مباشرة عشان يظهر في الـ Moves History
    secondary_uom_qty = fields.Float(
        string='Secondary Qty',
        related='move_id.secondary_uom_qty',
        store=True
    )