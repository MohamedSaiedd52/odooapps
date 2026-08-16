from odoo import models, api, fields


class CustomerAccountReport(models.AbstractModel):
    _name = "report.customer_partner_ledger.rep_cus_acc"
    _description = "Customer Account Statement"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        # The action returned by custom_pl_pdf travels to the browser and back as
        # JSON, which turns the partner ids used as keys of `lines` into strings.
        data['lines'] = {int(k): v for k, v in (data.get('lines') or {}).items()}

        env = self._env_of_printing_company(data)
        company = env['res.company'].browse(int(data['company_id'])) if data.get('company_id') else env.company
        if not company.exists():
            company = env.company
        currency = company.currency_id

        partners = env["res.partner"].browse([int(p) for p in data.get("partner_ids") or []])
        data['summary'] = {
            partner.id: self._get_partner_summary(partner, data, currency)
            for partner in partners
        }
        return {
            'doc_ids': docids,
            'doc_model': env['res.partner'],
            'data': data,
            'docs': partners,
            'company': company,
            'print_date': data.get("to_date") or fields.Date.today(),
            'currency': currency
        }

    def _env_of_printing_company(self, data):
        """ Environment scoped to the companies selected when the report was asked for.

        The letterhead and the figures then both follow the company the user was
        standing on, whatever the company selection of the rendering request is.
        """
        allowed_company_ids = [int(c) for c in data.get('allowed_company_ids') or []]
        if not allowed_company_ids:
            return self.env
        return self.env(context={**self.env.context, 'allowed_company_ids': allowed_company_ids})

    def _get_partner_summary(self, partner, data, currency):
        """ Statement footer of one partner.

        Also stamps the running balance on every line of ``data['lines']`` so the
        template only has to print it.
        """
        opening = currency.round(partner.get_partner_initial_bal(partner.id, data.get('from_date')))
        lines = data['lines'].get(partner.id) or []

        balance = opening
        for line in lines:
            balance = currency.round(balance + line['debit'] - line['credit'])
            line['running_balance'] = balance

        return {
            'opening': opening,
            'debit': currency.round(sum(line['debit'] for line in lines)),
            'credit': currency.round(sum(line['credit'] for line in lines)),
            'closing': balance,
            'total_due': currency.round(partner.get_partner_total_due(partner.id)),
        }
