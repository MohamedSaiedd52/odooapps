# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class BiotimeTransaction(models.Model):
    _name = "biotime.transaction"
    _description = "Biotime Transaction"
    _order = "punch_time desc"

    transaction_id = fields.Integer("Transaction ID", required=True, index=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", index=True)
    department = fields.Char("Department")
    punch_time = fields.Datetime("Punch Time", required=True, index=True)
    punch_state = fields.Char("Punch State")
    punch_state_display = fields.Char("Punch State Display")
    device_id = fields.Many2one("biotime.terminal", string="Device")
    server_id = fields.Many2one("biotime.config", string="Server", required=True, index=True)
    is_transferred = fields.Boolean("Is Transferred", default=False)

    _sql_constraints = [
        ('unique_transaction_server',
         'UNIQUE(transaction_id, server_id)',
         'Transaction already exists for this server!'),
    ]


class BioTimeTransactionLog(models.Model):
    _name = 'biotime.transaction.log'
    _description = 'Unmatched BioTime Transactions'
    _order = 'punch_time desc'

    transaction_id = fields.Char("Transaction ID")
    emp_code = fields.Char("Employee Code")
    emp_name = fields.Char("Employee Name")
    department = fields.Char("Department")
    punch_time = fields.Datetime("Punch Time")
    punch_state = fields.Char("Punch State")
    punch_state_display = fields.Char("Punch State Display")
    device_id = fields.Many2one('biotime.terminal', "Device")
    server_id = fields.Many2one('biotime.config', "Server")
    note = fields.Text("Note")

    # ── Fixing unmatched punches ──
    def action_create_employee(self):
        """Create the missing hr.employee from the log line, then convert all
        log lines of that employee code into real transactions."""
        employees = self.env['hr.employee']
        for code in set(self.mapped('emp_code')):
            log = self.filtered(lambda l: l.emp_code == code)[0]
            existing = self.env['hr.employee'].sudo().search(
                [('zk_emp_code', '=', code)], limit=1)
            if not existing:
                employees |= self.env['hr.employee'].sudo().create({
                    'name': log.emp_name or code,
                    'zk_emp_code': code,
                })
        recovered = self.env['biotime.transaction.log'].sudo().search(
            [('emp_code', 'in', list(set(self.mapped('emp_code'))))]
        )._reprocess_logs()
        return self._notify_recovered(recovered)

    def action_link_employee(self):
        """Open a wizard to link these punches to an existing employee."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Link Punches to Employee'),
            'res_model': 'biotime.link.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_log_ids': [(6, 0, self.ids)]},
        }

    def _reprocess_logs(self):
        """Convert log lines whose emp_code now matches an hr.employee into
        real biotime.transaction records, then delete those lines.
        Returns the number of punches recovered."""
        codes = list(set(self.mapped('emp_code')))
        if not codes:
            return 0
        emp_map = {
            e.zk_emp_code: e.id
            for e in self.env['hr.employee'].sudo().search(
                [('zk_emp_code', 'in', codes)])
        }
        Transaction = self.env['biotime.transaction'].sudo()
        to_create, resolved = [], self.browse()
        for log in self:
            emp_id = emp_map.get(log.emp_code)
            if not emp_id:
                continue
            try:
                tx_id = int(log.transaction_id)
            except (TypeError, ValueError):
                _logger.warning(
                    "Unmatched log %s has a non-numeric transaction id %r, "
                    "skipping", log.id, log.transaction_id)
                continue
            if not Transaction.search_count([
                    ('transaction_id', '=', tx_id),
                    ('server_id', '=', log.server_id.id)]):
                to_create.append({
                    'transaction_id': tx_id,
                    'employee_id': emp_id,
                    'department': log.department,
                    'punch_time': log.punch_time,
                    'punch_state': log.punch_state,
                    'punch_state_display': log.punch_state_display,
                    'device_id': log.device_id.id,
                    'server_id': log.server_id.id,
                })
            resolved |= log
        if to_create:
            Transaction.create(to_create)
        if resolved:
            resolved.unlink()
        return len(to_create)

    def _notify_recovered(self, recovered):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Punches recovered"),
                'message': _(
                    "%s punch(es) converted to transactions. Run 'Transfer "
                    "to Attendance' to build the attendance records.") % recovered,
                'type': 'success' if recovered else 'warning',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }