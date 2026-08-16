from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHrLoanAccounting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Loan Test Employee',
        })
        cls.loan_account = cls.env['account.account'].create({
            'name': 'Employee Loans Test',
            'code': '130199',
            'account_type': 'asset_current',
        })
        cls.treasury_account = cls.env['account.account'].create({
            'name': 'Loan Treasury Test',
            'code': '101799',
            'account_type': 'asset_cash',
        })
        cls.journal = cls.env['account.journal'].create({
            'name': 'Loan Test Bank',
            'code': 'LTBK',
            'type': 'bank',
        })

    def _make_loan(self, employee, amount=1200.0, installments=6, **extra):
        vals = {
            'employee_id': employee.id,
            'loan_amount': amount,
            'installment': installments,
            'payment_date': fields.Date.today(),
        }
        vals.update(extra)
        loan = self.env['hr.loan'].create(vals)
        loan.action_compute_installment()
        loan.action_submit()
        return loan

    def test_approve_requires_accounting_setup(self):
        """Approving without journal/accounts must raise a blocking error."""
        loan = self._make_loan(self.employee)
        with self.assertRaises(UserError):
            loan.action_approve()

    def test_approve_creates_posted_journal_entry(self):
        """Approval posts a balanced entry: debit loan, credit treasury."""
        loan = self._make_loan(
            self.employee,
            journal_id=self.journal.id,
            loan_account_id=self.loan_account.id,
            treasury_account_id=self.treasury_account.id,
        )
        loan.action_approve()
        self.assertEqual(loan.state, 'approve')

        move = self.env['account.move'].search([('ref', '=', loan.name)])
        self.assertEqual(len(move), 1)
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.journal_id, self.journal)

        debit_line = move.line_ids.filtered(lambda l: l.debit)
        credit_line = move.line_ids.filtered(lambda l: l.credit)
        self.assertEqual(debit_line.account_id, self.loan_account)
        self.assertEqual(debit_line.debit, loan.loan_amount)
        self.assertEqual(credit_line.account_id, self.treasury_account)
        self.assertEqual(credit_line.credit, loan.loan_amount)

        self.assertEqual(loan.move_count, 1)
        action = loan.action_view_journal_entries()
        self.assertEqual(action['res_id'], move.id)

    def test_delay_wizard_shifts_only_unpaid_lines(self):
        """The wizard moves unpaid installment dates forward, paid stay put."""
        employee = self.env['hr.employee'].create({'name': 'Delay Employee'})
        loan = self._make_loan(
            employee,
            journal_id=self.journal.id,
            loan_account_id=self.loan_account.id,
            treasury_account_id=self.treasury_account.id,
        )
        loan.action_approve()

        paid_line = loan.loan_line_ids.sorted('date')[0]
        paid_line.paid = True
        paid_date = paid_line.date
        unpaid_dates = {
            line.id: line.date
            for line in loan.loan_line_ids - paid_line
        }

        wizard = self.env['hr.loan.delay.wizard'].create({
            'loan_id': loan.id,
            'months': 2,
        })
        wizard.action_submit()

        self.assertEqual(paid_line.date, paid_date)
        for line in loan.loan_line_ids - paid_line:
            self.assertEqual(
                line.date,
                unpaid_dates[line.id] + relativedelta(months=2))
