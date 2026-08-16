# -*- coding: utf-8 -*-
# Part of HR Loan Accounting. Author: Mohamed Saied.
from odoo import fields, models


class HrSalaryRule(models.Model):
    """Inherits the model hr.salary.rule to add new field company_id on salary
    rule model"""
    _inherit = 'hr.salary.rule'

    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 copy=False, readonly=True, help="Company",
                                 default=lambda self: self.env.user.company_id)
