import re

from odoo import models, release

ODOO_VERSION = release.version_info[0]


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _custom_line_postprocessor(self, report, options, lines, warnings=None):
        # توقيع الدالة في 17 فيه warnings، ومن 18 اتشالت — فبنمررها للـ super في 17 بس
        if ODOO_VERSION >= 18:
            res = super()._custom_line_postprocessor(report, options, lines)
        else:
            res = super()._custom_line_postprocessor(report, options, lines, warnings=warnings)

        # 1. تحديد مكان عمود "العملة"
        currency_col_index = -1
        for i, col in enumerate(options.get('columns', [])):
            if col.get('expression_label') in ('amount_currency', 'currency'):
                currency_col_index = i
                break

        if currency_col_index == -1:
            return res

        # 2. جلب فلاتر التقرير
        domain = report._get_options_domain(options, 'strict_range')

        # 3. المرور على السطور لاصطياد سطر الشريك وسطر الإجمالي
        for line in res:
            line_id_str = str(line.get('id', ''))

            # حالة 1: سطر الشريك (الـ id فيه res.partner في كل النسخ 17/18/19)
            # ونتأكد إنه مش سطر حركة عادية (account.move.line)
            if 'res.partner' in line_id_str and 'account.move.line' not in line_id_str:
                try:
                    # اصطياد رقم الشريك (ID) من وسط الرموز
                    match = re.search(r'res\.partner[^\d]+(\d+)', line_id_str)
                    if match:
                        partner_id = int(match.group(1))
                        partner_domain = domain + [('partner_id', '=', partner_id)]

                        # حساب المجموع من الداتا بيز
                        move_lines = self.env['account.move.line'].search_read(partner_domain, ['amount_currency'])
                        total_currency = sum(ml['amount_currency'] for ml in move_lines)

                        # حقن الرقم
                        if 'columns' in line and len(line['columns']) > currency_col_index:
                            line['columns'][currency_col_index]['name'] = "$ {:,.2f}".format(total_currency)
                            line['columns'][currency_col_index]['no_format'] = total_currency
                except Exception:
                    pass

            # حالة 2: سطر الإجمالي العام أو الرصيد الافتتاحي
            elif 'total' in line_id_str.lower() or 'initial_balance' in line_id_str.lower():
                try:
                    move_lines = self.env['account.move.line'].search_read(domain, ['amount_currency'])
                    total_currency = sum(ml['amount_currency'] for ml in move_lines)

                    if 'columns' in line and len(line['columns']) > currency_col_index:
                        line['columns'][currency_col_index]['name'] = "$ {:,.2f}".format(total_currency)
                        line['columns'][currency_col_index]['no_format'] = total_currency
                except Exception:
                    pass

        return res
