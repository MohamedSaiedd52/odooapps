# -*- coding: utf-8 -*-
import logging
from datetime import time, datetime
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from .utils import check_duplicated_punches
import pytz

_logger = logging.getLogger(__name__)


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    late_grace_minutes = fields.Integer(
        string="Late Grace Period (minutes)", default=0,
        help="An employee checking in within this many minutes after the "
             "shift start is still counted On Time.")


class HrEmployeeZk(models.Model):
    _inherit = 'hr.employee'

    zk_emp_code = fields.Char(
        string="ZK Employee Code", help="Employee code from ZK/BioTime")

    def action_push_to_biotime(self):
        """Open the wizard that creates the selected employee(s) on a
        BioTime server (reverse sync)."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send to BioTime'),
            'res_model': 'biotime.push.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_ids': [(6, 0, self.ids)]},
        }

    def _biotime_relink(self):
        """When an employee gets (or changes) a ZK code: link the matching
        biotime.employee records and recover any unmatched punches that were
        waiting for this code."""
        codes = [e.zk_emp_code for e in self if e.zk_emp_code]
        if not codes:
            return
        for emp in self:
            if not emp.zk_emp_code:
                continue
            self.env['biotime.employee'].sudo().search(
                [('emp_code', '=', emp.zk_emp_code)]).write(
                {'odoo_employee_id': emp.id})
        recovered = self.env['biotime.transaction.log'].sudo().search(
            [('emp_code', 'in', codes)])._reprocess_logs()
        if recovered:
            _logger.info(
                "BioTime: recovered %s unmatched punch(es) after linking "
                "employee code(s) %s", recovered, codes)

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._biotime_relink()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'zk_emp_code' in vals:
            self._biotime_relink()
        return res


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------
    state = fields.Selection(
        [
            ('on_time', 'On Time'),
            ('late_in', 'Late In'),
        ],
        string='Status',
        compute='_compute_state',
        store=True
    )

    late_minutes = fields.Integer(
        string="Late Minutes",
        compute="_compute_state",
        store=True
    )

    # --------------------------------------------------
    # MISSING CHECK
    # --------------------------------------------------
    missing_check = fields.Selection(
        [('ok', 'Found'), ('missing', 'Missing')],
        string="Missing Check",
        compute='_compute_missing_check',
        store=True,
        default='ok'
    )

    # --------------------------------------------------
    # SQL CONSTRAINTS
    # --------------------------------------------------
    # Odoo 19 syntax (replaces _sql_constraints)
    _unique_employee_checkin = models.Constraint(
        'UNIQUE(employee_id, check_in)',
        'Duplicate check-in for this employee!',
    )
    _unique_employee_checkout = models.Constraint(
        'UNIQUE(employee_id, check_out)',
        'Duplicate check-out for this employee!',
    )

    # --------------------------------------------------
    # MISSING CHECK COMPUTE
    # --------------------------------------------------
    @api.depends('check_in', 'check_out')
    def _compute_missing_check(self):
        for rec in self:
            if rec.check_in and rec.check_out:
                if rec.check_in == rec.check_out or check_duplicated_punches(rec.check_in, rec.check_out):
                    rec.missing_check = 'missing'
                else:
                    rec.missing_check = 'ok'
            else:
                rec.missing_check = 'missing'

    # --------------------------------------------------
    # STATE + LATE CALCULATION (FIXED)
    # --------------------------------------------------
    # depends on the calendar LINES too: editing the working schedule
    # (e.g. moving the start from 08:00 to 09:00) must recompute the
    # late status of existing attendances, not only future ones
    @api.depends('check_in', 'employee_id', 'employee_id.tz',
                 'employee_id.resource_calendar_id.late_grace_minutes',
                 'employee_id.resource_calendar_id.attendance_ids.hour_from',
                 'employee_id.resource_calendar_id.attendance_ids.dayofweek')
    def _compute_state(self):
        for rec in self:
            rec.state = False
            rec.late_minutes = 0

            if not rec.check_in or not rec.employee_id:
                continue

            employee = rec.employee_id

            # --------------------------------------------------
            # CONTRACT CHECK (only when hr_contract is installed —
            # `contract_id` does not exist on a bare `hr` install)
            # --------------------------------------------------
            if 'contract_id' in employee._fields:
                contract = employee.contract_id
                if not contract or contract.state != 'open' or not contract.date_start:
                    rec.state = 'on_time'
                    continue
                if contract.date_end and contract.date_end < rec.check_in.date():
                    rec.state = 'on_time'
                    continue

            # --------------------------------------------------
            # CALENDAR CHECK
            # --------------------------------------------------
            calendar = employee.resource_calendar_id
            if not calendar:
                rec.state = 'on_time'
                continue

            # --------------------------------------------------
            # TIMEZONE (employee → calendar → company → UTC)
            # --------------------------------------------------
            tz_name = (employee.tz or calendar.tz
                       or employee.company_id.partner_id.tz or 'UTC')
            employee_tz = pytz.timezone(tz_name)
            # check_in is stored as a naive UTC datetime; localize to UTC first,
            # otherwise .astimezone() would assume the server's local timezone.
            check_in_utc = pytz.utc.localize(rec.check_in)
            check_in_local = check_in_utc.astimezone(employee_tz)

            # --------------------------------------------------
            # WORKING HOURS
            # --------------------------------------------------
            attendance_lines = calendar.attendance_ids.filtered(
                lambda a: int(a.dayofweek) == check_in_local.weekday()
            )

            if not attendance_lines:
                rec.state = 'on_time'
                continue

            possible_starts = []
            for line in attendance_lines:
                hour = line.hour_from
                start_time = time(int(hour), int(round((hour % 1) * 60)))
                possible_starts.append(start_time)

            # Compare against the NEAREST shift start, not the earliest one:
            # an evening-shift employee clocking in at 16:00 must be measured
            # against the 16:00 shift, not flagged 8 hours late vs 08:00.
            check_in_time = check_in_local.time()
            work_start_time = min(
                possible_starts,
                key=lambda st: abs(
                    (check_in_time.hour * 60 + check_in_time.minute)
                    - (st.hour * 60 + st.minute)))

            # --------------------------------------------------
            # BUILD START DATETIME
            # --------------------------------------------------
            start_dt = datetime.combine(check_in_local.date(), work_start_time)
            start_dt = employee_tz.localize(start_dt)

            # --------------------------------------------------
            # LATE LOGIC (with grace period)
            # --------------------------------------------------
            grace = max(calendar.late_grace_minutes or 0, 0)
            # whole minutes only: 40 seconds past the start is not "late"
            late_minutes = int((check_in_local - start_dt).total_seconds() // 60)
            if late_minutes > grace:
                rec.state = 'late_in'
                rec.late_minutes = late_minutes
            else:
                rec.state = 'on_time'

    # --------------------------------------------------
    # VALIDATION (ANTI OVERLAP)
    # --------------------------------------------------
    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        for attendance in self:

            last_before_in = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<=', attendance.check_in),
                ('id', '!=', attendance.id),
            ], order='check_in desc', limit=1)

            if last_before_in and last_before_in.check_out and last_before_in.check_out > attendance.check_in:
                raise ValidationError(_(
                    "Attendance overlap for %(empl)s at %(dt)s",
                    empl=attendance.employee_id.name,
                    dt=attendance.check_in
                ))

            if attendance.check_out:
                last_before_out = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_in', '<', attendance.check_out),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)

                if last_before_out and last_before_out != last_before_in:
                    raise ValidationError(_(
                        "Checkout overlap for %(empl)s at %(dt)s",
                        empl=attendance.employee_id.name,
                        dt=last_before_out.check_in
                    ))
