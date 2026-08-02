# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)


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
        inverse="_inverse_odoo_employee_id",
        store=True,
        readonly=False,
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

    def _inverse_odoo_employee_id(self):
        """Picking an employee manually writes the ZK code onto them, which
        also recovers any unmatched punches waiting for that code
        (see HrEmployeeZk._biotime_relink)."""
        for rec in self:
            if rec.odoo_employee_id and rec.emp_code and \
                    rec.odoo_employee_id.zk_emp_code != rec.emp_code:
                rec.odoo_employee_id.sudo().write({'zk_emp_code': rec.emp_code})

    def action_pull_my_transactions(self):
        """Open the pull wizard pre-filtered on this employee only."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pull Punches — %s') % (self.name or self.emp_code),
            'res_model': 'biotime.pull.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_server_id': self.biotime_id.id,
                'default_bio_employee_id': self.id,
            },
        }
