from odoo import models, release

ODOO_VERSION = release.version_info[0]


class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _cur_sum_amount_currency(self, report, group_options, extra_domain=None):
        # مجموع العملة من الداتا بيز حسب فلاتر التقرير
        domain = report._get_options_domain(group_options, 'strict_range') + (extra_domain or [])
        move_lines = self.env['account.move.line'].search_read(domain, ['amount_currency'])
        return sum(ml['amount_currency'] for ml in move_lines)

    if ODOO_VERSION <= 18:
        # في 17/18 سطر عنوان الحساب وسطر الإجمالي بيتبنوا بالدوال دي مباشرة

        def _get_account_title_line(self, report, options, account, has_lines, eval_dict):
            line = super()._get_account_title_line(report, options, account, has_lines, eval_dict)

            for column in line.get('columns', []):
                if column.get('expression_label') == 'amount_currency':
                    cg_key = column.get('column_group_key')
                    vals = eval_dict.get(cg_key, eval_dict) if cg_key else eval_dict

                    val = vals.get('amount_currency', 0.0) if isinstance(vals, dict) else 0.0
                    # تنسيق الرقم عشان يظهر بشكل محاسبي مظبوط
                    formatted_val = "{:,.2f}".format(val or 0.0)

                    column['name'] = formatted_val
                    column['no_format'] = val

            return line

        def _get_total_line(self, report, options, eval_dict):
            # سطر الإجمالي بيتبني بـ _get_total_line و eval_dict فيه debit/credit/balance بس
            # (من غير amount_currency)، فبنحسب المجموع بنفسنا من الداتا بيز
            line = super()._get_total_line(report, options, eval_dict)

            options_per_group = report._split_options_per_column_group(options)
            for column in line.get('columns', []):
                if column.get('expression_label') == 'amount_currency':
                    cg_key = column.get('column_group_key')
                    group_options = options_per_group.get(cg_key, options)

                    val = self._cur_sum_amount_currency(report, group_options)
                    column['name'] = "{:,.2f}".format(val)
                    column['no_format'] = val

            return line

    else:
        # في 19 التقرير اتعاد كتابته على المحرك العام ومفيش _get_account_title_line
        # ولا _get_total_line، فبنحقن المجاميع بعد بناء السطور كلها

        def _custom_line_postprocessor(self, report, options, lines):
            lines = super()._custom_line_postprocessor(report, options, lines)

            currency_cols = [
                (idx, col.get('column_group_key'))
                for idx, col in enumerate(options.get('columns', []))
                if col.get('expression_label') == 'amount_currency'
            ]
            if not currency_cols:
                return lines

            options_per_group = report._split_options_per_column_group(options)

            # مجموع العملة لكل حساب بـ read_group واحدة لكل مجموعة أعمدة بدل استعلام لكل سطر
            sums_by_group = {}
            for _idx, cg_key in currency_cols:
                group_options = options_per_group.get(cg_key, options)
                domain = report._get_options_domain(group_options, 'strict_range')
                grouped = self.env['account.move.line']._read_group(
                    domain, ['account_id'], ['amount_currency:sum'],
                )
                sums_by_group[cg_key] = {account.id: (total or 0.0) for account, total in grouped}

            for line in lines:
                parsed = report._parse_line_id(line['id'])
                markup, model, res_id = parsed[-1]
                account_id = None
                if model == 'account.account':
                    account_id = res_id
                elif markup == 'total' and model is None:
                    # سطر "Total <حساب>" (totals_below_sections) بيشارك نفس dicts الأعمدة
                    # مع سطر الحساب الأب — لازم ياخد مجموع الحساب نفسه مش الإجمالي العام
                    account_id = next(
                        (pid for _pmk, pmodel, pid in parsed[:-1] if pmodel == 'account.account'),
                        None,
                    )
                else:
                    continue

                if account_id is not None:
                    values = {cg_key: sums.get(account_id, 0.0) for cg_key, sums in sums_by_group.items()}
                else:
                    # الإجمالي العام (مفيش حساب أب في سلسلة الـ id)
                    values = {cg_key: sum(sums.values()) for cg_key, sums in sums_by_group.items()}

                for idx, cg_key in currency_cols:
                    if len(line.get('columns', [])) <= idx:
                        continue
                    val = values[cg_key]
                    column = line['columns'][idx]
                    column['name'] = "{:,.2f}".format(val)
                    column['no_format'] = val

            return lines
