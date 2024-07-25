from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # حقل مخفي لعرض المنتجات المرتبطة بالمورد
    vendor_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_vendor_products',
        string='Products from Vendor',
        store=False
    )

    @api.depends('partner_id')
    def _compute_vendor_products(self):
        for order in self:
            if order.partner_id:
                # البحث عن جميع المنتجات المرتبطة بالمورد المحدد
                products = self.env['product.product'].search([('seller_ids.partner_id', '=', order.partner_id.id)])
                order.vendor_product_ids = products

                # حذف المنتجات القديمة المرتبطة بالمورد السابق
                order.order_line = [(5, 0, 0)]

                # إضافة المنتجات الجديدة إلى خطوط الطلب
                order.order_line = [(0, 0, {'product_id': product.id, 'name': product.name, 'product_qty': 1,
                                            'price_unit': product.list_price}) for product in products]
            else:
                order.vendor_product_ids = False
