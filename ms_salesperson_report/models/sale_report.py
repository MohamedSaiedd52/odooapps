# -*- coding: utf-8 -*-
"""
MS Salesperson Report
========================
Problem:
    تقرير المبيعات الافتراضي في Odoo يعرض المندوب (user_id) بناءً على
    أمر البيع (sale.order) فقط. لكن في بعض الحالات يكون المندوب على
    الفاتورة (invoice_user_id) مختلفاً، أو يريد المدير مقارنة الاثنين.

Fix:
    - إضافة حقل invoice_user_id في sale.report يجيب المندوب من
      أول فاتورة مرتبطة بأمر البيع.
    - يتم ذلك عبر subquery (correlated subquery) على account_move
      مرتبطة بـ sale.order عبر حقل invoice_ids.
"""

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    # ─── الحقل الجديد: مندوب المبيعات بحسب الفاتورة ───────────────────
    invoice_user_id = fields.Many2one(
        comodel_name='res.users',
        string='مندوب المبيعات (الفاتورة)',
        readonly=True,
        help=(
            'مندوب المبيعات المسجّل على الفاتورة المرتبطة بأمر البيع. '
            'يختلف عن "مندوب المبيعات" الذي يجيء مباشرة من أمر البيع.'
        ),
    )

    # ─── إضافة الحقل إلى SELECT ─────────────────────────────────────────
    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        # نجيب أول فاتورة customer invoice مرتبطة بأمر البيع
        # account_move.invoice_user_id هو مندوب المبيعات على الفاتورة
        res['invoice_user_id'] = """(
                SELECT am.invoice_user_id
                  FROM account_move am
                 WHERE am.move_type IN ('out_invoice', 'out_refund')
                   AND am.state = 'posted'
                   AND am.id IN (
                       SELECT am2.id
                         FROM account_move am2
                        WHERE am2.invoice_origin = s.name
                          AND am2.company_id = s.company_id
                        ORDER BY am2.invoice_date ASC
                        LIMIT 1
                   )
                 LIMIT 1
            )"""
        return res
