from odoo import fields, models

class SaleReport(models.Model):
    _inherit = 'sale.report'

    secondary_uom_qty = fields.Float(string='Secondary Qty', readonly=True)

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        # ضفنا دالة التجميع SUM عشان الداتا بيز متضربش إيرور
        res['secondary_uom_qty'] = "SUM(l.secondary_uom_qty)" 
        return res