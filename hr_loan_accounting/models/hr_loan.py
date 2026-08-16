# -*- coding: utf-8 -*-
# Part of HR Loan Accounting. Author: Mohamed Saied.
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrLoan(models.Model):
    """Model for Loan Requests for employees."""
    _name = 'hr.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Loan Request"

    name = fields.Char(string="Loan Name", default="/", readonly=True,
                       help="Name of the loan")
    date = fields.Date(string="Date", default=fields.Date.today(),
                       readonly=True, help="Date of the loan")
    employee_id = fields.Many2one(comodel_name='hr.employee', string="Employee",
                                  required=True, help="Employee for the loan")
    department_id = fields.Many2one(comodel_name='hr.department',
                                    related="employee_id.department_id",
                                    readonly=True,
                                    string="Department",
                                    help="Department of employee")
    installment = fields.Integer(string="No Of Installments", default=1,
                                 help="Number of installments")
    payment_date = fields.Date(string="Payment Start Date", required=True,
                               default=fields.Date.today(),
                               help="Date of the payment")
    loan_line_ids = fields.One2many(comodel_name='hr.loan.line',
                                    help="Details of the Loan Repayment",
                                    inverse_name='loan_id', string="Loan Line",
                                    index=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 help="Company",
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one(comodel_name='res.currency',
                                  string='Currency', required=True,
                                  help="Currency",
                                  default=lambda self:
                                  self.env.user.company_id.currency_id)
    job_position_id = fields.Many2one(comodel_name='hr.job',
                                      related="employee_id.job_id",
                                      readonly=True, string="Job Position",
                                      help="Job position of employee")
    loan_amount = fields.Float(string="Loan Amount", required=True,
                               help="Loan amount")
    total_amount = fields.Float(string="Total Amount", store=True,
                                readonly=True, compute='_compute_loan_amount',
                                help="Total loan amount")
    balance_amount = fields.Float(string="Balance Amount", store=True,
                                  compute='_compute_loan_amount',
                                  help="Balance amount")
    total_paid_amount = fields.Float(string="Total Paid Amount", store=True,
                                     compute='_compute_loan_amount',
                                     help="Total paid amount")
    state = fields.Selection([
        ('draft', 'Draft'), ('waiting_approval_1', 'Submitted'),
        ('approve', 'Approved'), ('refuse', 'Refused'), ('cancel', 'Canceled'),
    ], string="State", help="State of loan request", default='draft',
        tracking=True, copy=False, )
    loan_account_id = fields.Many2one(
        'account.account', string="Loan Account",
        help="Account used to record the loan receivable (debit side).")
    treasury_account_id = fields.Many2one(
        'account.account', string="Treasury Account",
        help="Account used to record the cash/bank disbursement (credit side).")
    journal_id = fields.Many2one(
        'account.journal', string="Journal",
        domain="[('type', 'in', ['bank', 'cash'])]",
        help="Journal used for the loan disbursement entry.")
    move_count = fields.Integer(
        string="Journal Entry Count", compute='_compute_move_count')

    @api.model
    def default_get(self, field_list):
        """ Retrieve default values for specified fields. """
        result = super(HrLoan, self).default_get(field_list)
        if result.get('user_id'):
            ts_user_id = result['user_id']
        else:
            ts_user_id = self.env.context.get('user_id', self.env.user.id)
        result['employee_id'] = self.env['hr.employee'].search(
            [('user_id', '=', ts_user_id)], limit=1).id
        return result

    def _compute_loan_amount(self):
        """ calculate the total amount paid towards the loan. """
        total_paid = 0.0
        for loan in self:
            for line in loan.loan_line_ids:
                if line.paid:
                    total_paid += line.amount
            balance_amount = loan.loan_amount - total_paid
            loan.total_amount = loan.loan_amount
            loan.balance_amount = balance_amount
            loan.total_paid_amount = total_paid

    def _compute_move_count(self):
        move_model = self.env['account.move']
        for loan in self:
            loan.move_count = move_model.search_count(
                [('ref', '=', loan.name)])

    @api.model_create_multi
    def create(self, vals_list):
        """Creates new HR loan records with the provided values."""
        for values in vals_list:
            loan_count = self.env['hr.loan'].search_count(
                [('employee_id', '=', values['employee_id']),
                 ('state', '=', 'approve'),
                 ('balance_amount', '!=', 0)])
            if loan_count:
                raise ValidationError(
                    _("The employee has already a pending installment"))
            values['name'] = self.env['ir.sequence'].next_by_code(
                'hr.loan.seq') or ' '
        return super(HrLoan, self).create(vals_list)

    def action_compute_installment(self):
        """This automatically create the installment the employee need to pay
        to company based on payment start date and the no of installments."""
        for loan in self:
            loan.loan_line_ids.unlink()
            date_start = datetime.strptime(str(loan.payment_date), '%Y-%m-%d')
            amount = loan.loan_amount / loan.installment
            for i in range(1, loan.installment + 1):
                self.env['hr.loan.line'].create({
                    'date': date_start,
                    'amount': amount,
                    'employee_id': loan.employee_id.id,
                    'loan_id': loan.id})
                date_start = date_start + relativedelta(months=1)
            loan._compute_loan_amount()
        return True

    def action_refuse(self):
        """Action to refuse the loan"""
        return self.write({'state': 'refuse'})

    def action_submit(self):
        """Action to submit the loan"""
        self.write({'state': 'waiting_approval_1'})

    def action_cancel(self):
        """Action to cancel the loan"""
        self.write({'state': 'cancel'})

    def action_approve(self):
        """Approve the loan and post a journal entry for the disbursement."""
        for loan in self:
            if not loan.loan_line_ids:
                raise ValidationError(_("Please Compute installment"))
            if not loan.journal_id or not loan.loan_account_id \
                    or not loan.treasury_account_id:
                raise UserError(_(
                    "Please set the Loan Account, Treasury Account, and "
                    "Journal before approving the loan."))
            loan.write({'state': 'approve'})
            move_vals = {
                'journal_id': loan.journal_id.id,
                'date': fields.Date.context_today(self),
                'ref': loan.name,
                'line_ids': [
                    (0, 0, {
                        'name': loan.name,
                        'account_id': loan.loan_account_id.id,
                        'debit': loan.loan_amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'name': loan.name,
                        'account_id': loan.treasury_account_id.id,
                        'debit': 0.0,
                        'credit': loan.loan_amount,
                    }),
                ],
            }
            move = self.env['account.move'].create(move_vals)
            move.action_post()
        return True

    def action_view_journal_entries(self):
        """Open journal entries related to this loan."""
        self.ensure_one()
        moves = self.env['account.move'].search([('ref', '=', self.name)])
        action = {
            'name': _('Journal Entries'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
            'context': {'default_ref': self.name},
        }
        if len(moves) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = moves.id
        return action

    def unlink(self):
        """Unlink loan lines"""
        for loan in self:
            if loan.state not in ('draft', 'cancel'):
                raise UserError(
                    'You cannot delete a loan which is not in draft or '
                    'cancelled state')
        return super(HrLoan, self).unlink()
