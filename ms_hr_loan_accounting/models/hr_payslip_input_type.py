# -*- coding: utf-8 -*-
# Part of HR Loan Accounting. Author: Mohamed Saied.
from odoo import fields, models


class HrPayslipInputType(models.Model):
    """Inherited model for 'hr.payslip.input.type'"""
    _inherit = 'hr.payslip.input.type'

    input_id = fields.Many2one(comodel_name='hr.salary.rule',
                               string="Salary Rule",
                               help="Salary rule in Payslip Input")
