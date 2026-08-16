# -*- coding: utf-8 -*-
# Part of HR Loan Accounting. Author: Mohamed Saied.
from odoo import fields, models


class HrLoanLine(models.Model):
    """Model hr.loan.line for creating installment details"""
    _name = "hr.loan.line"
    _description = "Installment Line"

    date = fields.Date(string="Payment Date", required=True,
                       help="Date of the payment")
    employee_id = fields.Many2one(comodel_name='hr.employee', string="Employee",
                                  help="Employee of Loan Line")
    amount = fields.Float(string="Amount", required=True, help="Loan Amount")
    paid = fields.Boolean(string="Paid", help="Loan is Paid")
    loan_id = fields.Many2one(comodel_name='hr.loan', string="Loan Ref.",
                              help="Loan Reference")
    payslip_id = fields.Many2one(comodel_name='hr.payslip',
                                 string="Payslip Ref.",
                                 help="Payslip Reference")
