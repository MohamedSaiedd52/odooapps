# -*- coding: utf-8 -*-
# Part of HR Loan Accounting. Author: Mohamed Saied.
from odoo import fields, models


class HrEmployee(models.Model):
    """ Inheriting hr employee for computing number of loans for employees """
    _inherit = "hr.employee"

    loan_count = fields.Integer(string="Loan Count", help="Count of Loans.",
                                compute='_compute_loan_count')

    def _compute_loan_count(self):
        """ Compute the number of loans associated with the employee. """
        for record in self:
            record.loan_count = self.env['hr.loan'].search_count(
                [('employee_id', '=', self.id)])

    def action_loans(self):
        """ Get the list of loans associated with the current employee.
           This method returns an action that opens a window displaying a tree
           view and form view of loans related to the employee. """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Loans',
            'view_mode': 'tree,form',
            'res_model': 'hr.loan',
            'domain': [('employee_id', '=', self.id)],
            'context': "{'create': False}"
        }
