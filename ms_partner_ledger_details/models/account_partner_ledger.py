# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)

INVOICE_TYPES = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
DETAIL_EXPAND_FN = '_report_expand_unfoldable_line_partner_ledger_ms_details'


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    # ------------------------------------------------------------------
    # 1) Tag each invoice move-line as unfoldable after the standard
    #    partner -> move-lines expansion.
    # ------------------------------------------------------------------
    def _report_expand_unfoldable_line_partner_ledger(
            self, line_dict_id, groupby, options, progress, offset,
            unfold_all_batch_data=None):
        result = super()._report_expand_unfoldable_line_partner_ledger(
            line_dict_id, groupby, options, progress, offset,
            unfold_all_batch_data=unfold_all_batch_data)

        report = self.env['account.report'].browse(options['report_id'])
        for line in result.get('lines', []):
            try:
                self._ms_tag_invoice_line(report, line, options)
            except Exception:
                _logger.exception(
                    "MS partner-ledger: failed to tag line %s",
                    line.get('id'))
        return result

    def _ms_tag_invoice_line(self, report, line, options):
        """Tag an invoice move-line as unfoldable and, when in export mode,
        mark it as already unfolded so _fully_unfold_lines_if_needed expands it."""
        parsed = report._parse_line_id(line['id'])
        if not parsed:
            return
        model, res_id = parsed[-1][1], parsed[-1][2]
        if model != 'account.move.line' or not res_id:
            return
        aml = self.env['account.move.line'].browse(res_id).exists()
        if not aml or aml.move_id.move_type not in INVOICE_TYPES:
            return
        if not aml.move_id.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product'):
            return

        line['unfoldable'] = True
        line['expand_function'] = DETAIL_EXPAND_FN
        line['groupby'] = None

        # During PDF / XLSX export _fully_unfold_lines_if_needed() only
        # recurses into lines that have unfolded=True.  The standard
        # _get_report_line_move_line() never sets this flag, so our detail
        # rows would be silently dropped from the export.
        # Fix: set unfolded=True when:
        #   • the user already opened this line in the UI (ID in unfolded_lines), OR
        #   • we are generating a file/print export  →  auto-expand everything.
        is_export = options.get('export_mode') in ('file', 'print')
        line['unfolded'] = (
            line['id'] in options.get('unfolded_lines', [])
            or options.get('unfold_all', False)
            or is_export
        )

    # ------------------------------------------------------------------
    # 2) Expand an invoice line into its product lines.
    # ------------------------------------------------------------------
    def _report_expand_unfoldable_line_partner_ledger_ms_details(
            self, line_dict_id, groupby, options, progress, offset,
            unfold_all_batch_data=None):
        report = self.env['account.report'].browse(options['report_id'])
        parsed = report._parse_line_id(line_dict_id)
        res_id = parsed[-1][2] if parsed else False
        aml = self.env['account.move.line'].browse(res_id).exists()

        lines = []
        if aml:
            product_lines = aml.move_id.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product')
            base_level = len(parsed) + 1
            for pline in product_lines:
                lines.append(self._ms_build_product_line(
                    report, options, line_dict_id, pline, base_level, aml))

        return {
            'lines': lines,
            'offset_increment': len(lines),
            'has_more': False,
        }

    # ------------------------------------------------------------------
    # 3) Build one product-line row with correct Debit / Credit placement.
    # ------------------------------------------------------------------
    def _ms_build_product_line(self, report, options, parent_line_id,
                                pline, level, aml):
        """
        Build a child row for a single invoice product line.

        Column mapping:
          - Invoice  (aml.debit  > 0)  → price_subtotal in **Debit**  column
          - Refund   (aml.credit > 0)  → price_subtotal in **Credit** column
          - Balance column             → always blank for detail rows
          - All other columns          → blank

        The same column dict is used by the screen renderer, the PDF
        exporter (export_mode='print'), and the XLSX exporter
        (export_mode='file'). For file exports the framework reads
        no_format directly, so a numeric value there is enough.
        """
        currency = pline.currency_id or pline.company_id.currency_id

        line_id = report._get_generic_line_id(
            'account.move.line', pline.id,
            parent_line_id=parent_line_id, markup='ms_detail')

        # ── Label ────────────────────────────────────────────────────────
        qty_txt = self._ms_fmt_qty(pline.quantity)
        uom_txt = pline.product_uom_id.name or ''
        product_txt = pline.product_id.display_name or pline.name or ''
        label = "%s  —  %s %s" % (product_txt, qty_txt, uom_txt)

        # ── Which side? ──────────────────────────────────────────────────
        # Use actual debit/credit of the parent move-line (receivable /
        # payable) so the detail rows always mirror the parent's direction.
        is_debit_side = aml.debit > aml.credit   # True=Debit, False=Credit
        amount = pline.price_subtotal             # always positive

        # ── Build columns list (same order as options['columns']) ────────
        columns = []
        for col in options.get('columns', []):
            expr = col.get('expression_label', '')
            if expr == 'debit' and is_debit_side:
                columns.append({
                    'name': self._ms_fmt(report, options, amount, currency),
                    'no_format': amount,
                    'class': 'number',
                    'figure_type': 'monetary',
                })
            elif expr == 'credit' and not is_debit_side:
                columns.append({
                    'name': self._ms_fmt(report, options, amount, currency),
                    'no_format': amount,
                    'class': 'number',
                    'figure_type': 'monetary',
                })
            else:
                # Balance and any other columns → blank cell (not zero)
                columns.append({
                    'name': '',
                    'no_format': None,
                    'class': 'number',
                    'figure_type': 'monetary',
                })

        return {
            'id': line_id,
            'name': label,
            'level': level,
            'parent_id': parent_line_id,
            'unfoldable': False,
            'unfolded': False,
            'columns': columns,
            'caret_options': 'account.move.line',
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ms_fmt(self, report, options, value, currency):
        try:
            # Odoo 18/19: format_value(options, value, figure_type, format_params)
            return report.format_value(
                options, value, figure_type='monetary',
                format_params={'currency_id': currency.id})
        except TypeError:
            # Odoo 17: format_value(options, value, currency=..., figure_type=...)
            return report.format_value(
                options, value, currency=currency, figure_type='monetary')

    def _ms_fmt_qty(self, qty):
        if qty == int(qty):
            return str(int(qty))
        return ("%.2f" % qty).rstrip('0').rstrip('.')
