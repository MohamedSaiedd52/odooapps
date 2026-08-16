from dateutil.relativedelta import relativedelta
from odoo import fields, models


class HrLoanDelayWizard(models.TransientModel):
    _name = 'hr.loan.delay.wizard'
    _description = 'Delay Loan Installments'

    loan_id = fields.Many2one(
        'hr.loan', string="Loan", required=True,
        default=lambda self: self.env.context.get('active_id'))
    months = fields.Integer(string="Number of Months", required=True, default=1)

    def action_submit(self):
        """Shift unpaid installment dates forward by the specified months."""
        for wizard in self:
            unpaid_lines = wizard.loan_id.loan_line_ids.filtered(
                lambda l: not l.paid)
            for line in unpaid_lines:
                line.date = line.date + relativedelta(months=wizard.months)
        return {'type': 'ir.actions.act_window_close'}
