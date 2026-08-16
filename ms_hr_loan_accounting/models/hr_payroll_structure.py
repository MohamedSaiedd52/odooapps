# -*- coding: utf-8 -*-
# Part of HR Loan Accounting. Author: Mohamed Saied.
from odoo import fields, models


class HrPayrollStructure(models.Model):
    """Inherits the model hr.payroll.structure to add new field company_id on
    'hr.payroll.structure'"""
    _inherit = 'hr.payroll.structure'

    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 copy=False, readonly=True, help="Company",
                                 default=lambda self: self.env.user.company_id)
