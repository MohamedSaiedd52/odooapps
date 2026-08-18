# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.line_ids._ms_enforce_analytic_policy()
        return posted


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.constrains('analytic_distribution', 'account_id', 'debit', 'credit')
    def _ms_check_analytic_policy(self):
        self._ms_enforce_analytic_policy()

    def _ms_enforce_analytic_policy(self):
        errors = []
        for line in self:
            error = line._ms_analytic_policy_error()
            if error:
                errors.append(error)
        if errors:
            raise ValidationError('\n'.join(errors))

    def _ms_analytic_policy_error(self):
        """Return the violation message for this line, or None if it is valid."""
        self.ensure_one()
        if self.display_type in ('line_section', 'line_note'):
            return None
        currency = self.company_currency_id
        if currency.is_zero(self.debit) and currency.is_zero(self.credit):
            return None
        company = self.company_id or self.env.company
        policy = self.account_id._ms_effective_analytic_policy(company)
        has_analytic = bool(self.analytic_distribution)
        line_label = self.name or self.move_id.name or ''

        if policy == 'forbidden' and has_analytic:
            analytic_ids = [int(k) for k in self.analytic_distribution]
            names = self.env['account.analytic.account'].browse(analytic_ids).mapped('name')
            return _(
                "Account '%(account)s' forbids analytic distribution, but the "
                "journal item '%(line)s' carries: %(analytics)s.",
                account=self.account_id.display_name,
                line=line_label,
                analytics=', '.join(names),
            )

        required = policy == 'always' or (
            policy == 'posted' and self.parent_state == 'posted'
        )
        if not required:
            return None
        if not has_analytic:
            return _(
                "Account '%(account)s' requires an analytic distribution on "
                "the journal item '%(line)s', but none is set.",
                account=self.account_id.display_name,
                line=line_label,
            )
        if company.ms_analytic_full_coverage:
            coverage = sum(self.analytic_distribution.values())
            if float_compare(coverage, 100.0, precision_digits=2) < 0:
                return _(
                    "Account '%(account)s' requires a full 100%% analytic "
                    "coverage on the journal item '%(line)s', but the "
                    "distribution only covers %(coverage)s%%.",
                    account=self.account_id.display_name,
                    line=line_label,
                    coverage=round(coverage, 2),
                )
        return None
