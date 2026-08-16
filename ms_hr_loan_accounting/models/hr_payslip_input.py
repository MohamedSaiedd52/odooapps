# -*- coding: utf-8 -*-
# Part of HR Loan Accounting. Author: Mohamed Saied.
from odoo import fields, models


class HrPayslipInput(models.Model):
    """Inherited model for 'hr.payslip.input'"""
    _inherit = 'hr.payslip.input'

    loan_line_id = fields.Many2one(comodel_name='hr.loan.line',
                                   string="Loan Installment",
                                   help="Loan installment in Payslip Input")
