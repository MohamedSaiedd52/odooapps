# -*- coding: utf-8 -*-
from odoo import fields, models

ANALYTIC_POLICIES = [
    ('always', 'Always Required'),
    ('posted', 'Required on Posting'),
    ('forbidden', 'Forbidden'),
]


class AccountAccount(models.Model):
    _inherit = 'account.account'

    ms_analytic_policy = fields.Selection(
        selection=ANALYTIC_POLICIES,
        string='Analytic Requirement',
        tracking=True,
        help=(
            "Controls whether journal items on this account must carry an "
            "analytic distribution:\n"
            "- Empty: use the company default policy (Accounting Settings).\n"
            "- Always Required: the line is blocked on save without analytics.\n"
            "- Required on Posting: drafts are free, posting is blocked "
            "without analytics.\n"
            "- Forbidden: the line is blocked if an analytic distribution "
            "is present."
        ),
    )

    def _ms_effective_analytic_policy(self, company):
        """Return the policy to enforce for this account in the given company."""
        self.ensure_one()
        return (
            self.ms_analytic_policy
            or (company and company.ms_analytic_policy_default)
            or 'optional'
        )
