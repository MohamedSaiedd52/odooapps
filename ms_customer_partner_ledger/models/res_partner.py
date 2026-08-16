from odoo import models, _, fields

RECEIVABLE_PAYABLE = ('asset_receivable', 'liability_payable')

# The opening balance and the total due are scoped to ``env.companies`` explicitly:
# the statement is printed for the company the user is standing on, and relying on
# the multi-company record rule alone would leak sister-company figures whenever the
# rendering runs as superuser.


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def get_partner_name(self, partner_id):
        return self.env['res.partner'].browse(int(partner_id)).name

    def get_line_ref(self, line_id, ref):
        if ref:
            ref = ref.replace(' تسديد حساب', 'سداد العميل')

        move_line = self.env['account.move.line'].browse(line_id)

        return (ref + '- ' if ref else '') + move_line.move_id.name

    def get_partner_initial_bal(self, partner_id, date_from):
        if not date_from:
            return 0
        move_lines = self.env['account.move.line'].search([
            ('date', '<', date_from),
            ('partner_id', '=', int(partner_id)),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', 'in', RECEIVABLE_PAYABLE),
            ('company_id', 'in', self.env.companies.ids),
        ])

        if move_lines:
            return sum(move_lines.mapped('debit')) - sum(move_lines.mapped('credit'))
        else:
            return 0

    def get_partner_total_due(self, partner_id):
        """ Amount the partner still owes, whatever the printed period is.

        Sums ``amount_residual`` over the posted receivable/payable move lines,
        so entries that have since been paid contribute nothing even when they
        fall inside the statement period.
        """
        move_lines = self.env['account.move.line'].search([
            ('partner_id', '=', int(partner_id)),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', 'in', RECEIVABLE_PAYABLE),
            ('full_reconcile_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ])
        return sum(move_lines.mapped('amount_residual'))
