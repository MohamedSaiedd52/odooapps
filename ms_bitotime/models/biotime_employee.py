   # -*- coding: utf-8 -*-
import logging
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import requests, json



# ==============================
# HrEmployee Extension
# ==============================
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    zk_emp_code = fields.Char(string="ZK Employee Code", help="Employee code from ZK/BioTime")


# ==============================
# BioTime Employee
# ==============================
class BioTimeEmployee(models.Model):
    _name = 'biotime.employee'
    _description = "Biotime Employee"

    name = fields.Char(string="Name")
    emp_code = fields.Char(string="Employee Code ZK")
    employee_id = fields.Char(string="Employee ID")
    odoo_employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        compute="_compute_odoo_employee_id",
        store=True
    )
    biotime_id = fields.Many2one('biotime.config', string="Biotime")
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company.id
    )

    @api.depends('emp_code')
    def _compute_odoo_employee_id(self):
        for rec in self:
            if rec.emp_code:
                employee = self.env['hr.employee'].sudo().search(
                    [('zk_emp_code', '=', rec.emp_code)], limit=1
                )
                rec.odoo_employee_id = employee.id if employee else False
            else:
                rec.odoo_employee_id = False
