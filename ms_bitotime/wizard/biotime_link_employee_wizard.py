# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BioTimeLinkEmployeeWizard(models.TransientModel):
    _name = 'biotime.link.employee.wizard'
    _description = "Link Unmatched Punches to an Employee"

    log_ids = fields.Many2many(
        'biotime.transaction.log', string="Unmatched Punches", required=True)
    emp_code = fields.Char(
        string="ZK Code", compute="_compute_emp_code")
    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True,
        help="This employee will get the ZK code of the selected punches; "
             "all their unmatched punches are then converted to transactions.")

    @api.depends('log_ids')
    def _compute_emp_code(self):
        for rec in self:
            codes = set(rec.log_ids.mapped('emp_code'))
            rec.emp_code = ", ".join(sorted(codes))

    def action_confirm(self):
        self.ensure_one()
        codes = set(self.log_ids.mapped('emp_code'))
        if len(codes) > 1:
            raise UserError(_(
                "The selected punches belong to %s different ZK codes (%s). "
                "Select punches of a single code, or use 'Create Employee' "
                "to create one employee per code.")
                % (len(codes), ", ".join(sorted(codes))))
        code = codes.pop()
        other = self.env['hr.employee'].sudo().search(
            [('zk_emp_code', '=', code),
             ('id', '!=', self.employee_id.id)], limit=1)
        if other:
            raise UserError(_(
                "ZK code %s is already assigned to employee %s.")
                % (code, other.name))
        Log = self.env['biotime.transaction.log'].sudo()
        before = Log.search_count([('emp_code', '=', code)])
        # writing the code triggers _biotime_relink → logs auto-recovered
        self.employee_id.sudo().write({'zk_emp_code': code})
        remaining = Log.search_count([('emp_code', '=', code)])
        return self.env['biotime.transaction.log']._notify_recovered(
            before - remaining)
