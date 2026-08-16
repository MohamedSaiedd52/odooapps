# -*- coding: utf-8 -*-
"""
MS Journal Dashboard – GL Balance
===================================
Problem (standard Odoo):
  The bank/cash kanban card on the Accounting dashboard splits the balance into
  multiple lines:
    • Line 1 – account_balance          : bank-statement balance + direct payments
    • Line 2 – outstanding_pay_account_balance : unmatched transit payments
    • Line 3 – misc_operations_balance  : manual entries from other journals

  When the accountant posts a manual journal entry that touches the bank/cash
  account (e.g. from a Miscellaneous journal), that amount appears in Line 3
  SEPARATELY and the total on Line 1 looks wrong compared to the GL.

Fix:
  Replace Lines 1–3 with a single, consolidated number taken directly from the
  General Ledger (sum of all posted debit-credit lines on the bank/cash
  default account). This always matches what the accountant sees in
  Accounting ▶ Reporting ▶ General Ledger.
"""

from odoo import models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # ------------------------------------------------------------------
    # Helper: GL balance from account_move_line
    # ------------------------------------------------------------------

    def _ms_get_gl_balance(self):
        """Return a dict {journal_id: (gl_balance, has_lines)} computed directly
        from posted account_move_line rows on each journal's default account.

        Currency logic:
          • If the journal has its own currency (foreign-currency bank account)
            → sum amount_currency (amounts in journal currency).
          • Otherwise → sum balance (amounts in company currency).
        """
        if not self:
            return {}

        self.env.cr.execute("""
            SELECT j.id                                                AS journal_id,
                   COALESCE(SUM(
                       CASE
                           WHEN j.currency_id IS NOT NULL
                           THEN aml.amount_currency
                           ELSE aml.balance
                       END
                   ), 0.0)                                             AS gl_balance,
                   COUNT(aml.id)                                       AS line_count
              FROM account_journal j
         LEFT JOIN (
                    SELECT l.id,
                           l.account_id,
                           l.balance,
                           l.amount_currency
                      FROM account_move_line l
                      JOIN account_move m ON m.id = l.move_id
                                         AND m.state = 'posted'
                                         AND m.company_id = ANY(%(companies)s)
                   ) aml ON aml.account_id = j.default_account_id
             WHERE j.id = ANY(%(journals)s)
          GROUP BY j.id
        """, {
            'companies': self.env.companies.ids,
            'journals': self.ids,
        })

        query_res = {row['journal_id']: row for row in self.env.cr.dictfetchall()}
        result = {}
        for journal in self:
            row = query_res.get(journal.id, {})
            result[journal.id] = (
                row.get('gl_balance', 0.0),
                bool(row.get('line_count', 0)),
            )
        return result

    # ------------------------------------------------------------------
    # Override: patch dashboard data after standard computation
    # ------------------------------------------------------------------

    def _fill_bank_cash_dashboard_data(self, dashboard_data):
        """After the standard fill, replace the split balance with a single
        GL balance so the kanban card shows one number that matches the GL."""
        super()._fill_bank_cash_dashboard_data(dashboard_data)

        bank_cash_journals = self.filtered(
            lambda j: j.type in ('bank', 'cash', 'credit'))
        if not bank_cash_journals:
            return

        gl_balances = bank_cash_journals._ms_get_gl_balance()

        for journal in bank_cash_journals:
            currency = (
                journal.currency_id
                or self.env['res.currency'].browse(
                    journal.company_id.sudo().currency_id.id)
            )
            accessible = (
                journal.company_id.id
                in journal.company_id._accessible_branches().ids
            )
            gl_balance, has_lines = gl_balances[journal.id]

            dashboard_data[journal.id].update({
                # ── Primary balance = GL balance (single number) ──────────
                'account_balance': currency.format(gl_balance),
                'nb_lines_bank_account_balance': has_lines and accessible,

                # ── Suppress secondary lines (already in GL) ──────────────
                'outstanding_pay_account_balance': currency.format(0),
                'nb_lines_outstanding_pay_account_balance': False,
                'nb_misc_operations': 0,
                'misc_operations_balance': None,
            })
