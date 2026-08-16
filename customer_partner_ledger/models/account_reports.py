# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError

PARTNER_LEDGER_HANDLER = 'account.partner.ledger.report.handler'


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def _init_options_buttons(self, options, previous_options=None):
        super()._init_options_buttons(options, previous_options)
        # The "Save" export wizard is not offered on these reports.
        options['buttons'] = [
            button for button in options['buttons']
            if button.get('action') != 'open_report_export_wizard'
        ]
        # The custom statement only makes sense on reports that expose the
        # Partners filter (Partner Ledger, Aged Receivable/Payable).
        # 'always_show' keeps the button in the toolbar itself: Odoo 18 and 19
        # only render those, the rest end up hidden in the cog menu.
        if self.filter_partner:
            options['buttons'].append({
                'name': _('PL'),
                'sequence': 30,
                'action': 'custom_pl_pdf',
                'always_show': True,
                'branch_allowed': True,
            })

    def _get_aml_values(self, options, partner_ids, offset=0, limit=None):
        """ Move lines of ``partner_ids``, dated by invoice date.

        Delegates to the Partner Ledger handler, whose query already selects
        ``COALESCE(invoice_date, date) AS invoice_date``; the rows are re-keyed
        on ``date`` and re-sorted so the statement reads in invoice-date order
        instead of accounting-date order.
        """
        rslt = self.env[PARTNER_LEDGER_HANDLER]._get_aml_values(options, partner_ids, offset=offset, limit=limit)
        for aml_results in rslt.values():
            for aml_result in aml_results:
                aml_result['date'] = aml_result.get('invoice_date') or aml_result.get('date')
            aml_results.sort(key=lambda aml: (str(aml['date'] or ''), aml['id']))
        return rslt

    def custom_pl_pdf(self, options):
        partner_ids = [int(partner) for partner in options.get('partner_ids') or []]
        if not partner_ids:
            raise UserError(_('Please Select Partners'))

        partner_lines = self._get_aml_values(options, partner_ids)

        from_date = options.get('date', {}).get('date_from', '')
        to_date = options.get('date', {}).get('date_to', '')

        res = {
            'ids': [],
            'model': 'res.partner',
            "lines": partner_lines,
            "from_date": from_date,
            "to_date": to_date,
            "partner_ids": partner_ids,
            # The statement belongs to the company the user is standing on. The PDF is
            # rendered by a second request, so pin the company and the whole selection
            # here instead of letting the renderer resolve them again.
            "company_id": self.env.company.id,
            "allowed_company_ids": self.env.companies.ids,
        }

        report = self.env.ref('customer_partner_ledger.action_report_cus_acc')
        return report.with_context(discard_logo_check=True).report_action([], data=res)
