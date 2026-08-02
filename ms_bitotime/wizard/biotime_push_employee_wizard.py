# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BioTimePushEmployeeWizard(models.TransientModel):
    _name = 'biotime.push.employee.wizard'
    _description = "Create Odoo Employees on BioTime (Reverse Sync)"

    server_id = fields.Many2one(
        'biotime.config', string="Server", required=True,
        default=lambda self: self.env['biotime.config'].search([], limit=1))
    employee_ids = fields.Many2many(
        'hr.employee', string="Employees", required=True)
    department_id = fields.Integer(
        string="BioTime Department ID", default=1,
        help="Internal id of the department on the BioTime server "
             "(1 = the default 'Department').")
    area_id = fields.Integer(
        string="BioTime Area ID", default=1,
        help="Internal id of the area on the BioTime server "
             "(1 = the default 'Area'). Devices are assigned to areas; the "
             "employee must be in the device's area to be pushed to it.")

    def action_push(self):
        self.ensure_one()
        BioEmp = self.env['biotime.employee'].sudo()
        created, skipped, errors = 0, 0, []
        for emp in self.employee_ids:
            code = emp.zk_emp_code or emp.pin or str(emp.id)
            existing = BioEmp.search([
                ('biotime_id', '=', self.server_id.id),
                ('emp_code', '=', code)], limit=1)
            if existing:
                skipped += 1
                continue
            try:
                bio_id = self.server_id.push_employee_to_biotime(
                    code, emp.name,
                    department_id=self.department_id,
                    area_ids=[self.area_id] if self.area_id else None)
            except UserError as exc:
                errors.append("%s: %s" % (emp.name, exc.args[0]))
                continue
            if not emp.zk_emp_code:
                emp.sudo().write({'zk_emp_code': code})
            BioEmp.create({
                'name': emp.name,
                'employee_id': bio_id,
                'emp_code': code,
                'biotime_id': self.server_id.id,
                'odoo_employee_id': emp.id,
            })
            created += 1

        if errors and not created:
            raise UserError(_(
                "No employee could be created on BioTime:\n%s")
                % "\n".join(errors))
        message = _("%s employee(s) created on BioTime, %s already existed.") \
            % (created, skipped)
        if errors:
            message += _(" Failed: %s") % "; ".join(errors)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Reverse sync finished"),
                'message': message,
                'type': 'warning' if errors else 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
