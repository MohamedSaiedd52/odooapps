# -*- coding: utf-8 -*-
import logging
from datetime import time, datetime
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from .utils import check_duplicated_punches
import pytz
_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # الحالة (في الميعاد / متأخر)
    state = fields.Selection(
        [
            ('on_time', 'On Time'),
            ('late_in', 'Late In'),
        ],
        string='Status',
        compute='_compute_state',
        store=True
    )

    # عدد دقائق التأخير
    late_minutes = fields.Integer(
        string="Late Minutes",
        compute="_compute_state",
        store=True
    )

    # بدل Boolean → Selection
    missing_check = fields.Selection(
        [('ok', 'Found'), ('missing', 'Missing')],
        string="Missing Check",
        compute='_compute_missing_check',
        store=True,
        default='ok'
    )

    _sql_constraints = [
        (
            'unique_employee_checkin',
            'unique(employee_id, check_in)',
            'Duplicate check-in for this employee!'
        ),
        (
            'unique_employee_checkout',
            'unique(employee_id, check_out)',
            'Duplicate check-out for this employee!'
        )
    ]

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


    @api.depends('check_in', 'employee_id')
    def _compute_state(self):
        for rec in self:
            rec.state = False
            rec.late_minutes = 0

            if not rec.check_in:
                continue

            employee = rec.employee_id

            # تحقق من العقد
            if not employee.contract_date_start or \
                    (employee.contract_date_end and employee.contract_date_end < rec.check_in.date()):
                rec.state = 'on_time'
                continue

            calendar = employee.resource_calendar_id
            if not calendar:
                rec.state = 'on_time'
                continue

            # اجعل check_in aware بالـ timezone الخاص بالموظف
            employee_tz = pytz.timezone(employee.tz or 'Africa/Tripoli')
            check_in_local = rec.check_in.astimezone(employee_tz)

            # خطوط العمل الخاصة بيوم check_in
            attendance_lines = calendar.attendance_ids.filtered(
                lambda a: int(a.dayofweek) == check_in_local.weekday()
            )

            if attendance_lines:
                possible_starts = []
                for line in attendance_lines:
                    hour = line.hour_from
                    start_time = time(int(hour), int((hour % 1) * 60))
                    possible_starts.append(start_time)

                # أقرب بداية قبل check_in
                work_start_time = min(possible_starts)

                # اجعل start_dt aware بنفس timezone
                start_dt = datetime.combine(check_in_local.date(), work_start_time)
                start_dt = employee_tz.localize(start_dt)

                if check_in_local.time() > work_start_time:
                    rec.state = 'late_in'
                    diff = check_in_local - start_dt
                    rec.late_minutes = int(diff.total_seconds() // 60)
                else:
                    rec.state = 'on_time'
            else:
                rec.state = 'on_time'

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        """
        Modified version:
        يسمح بوجود open attendance بدون ما يرمي ValidationError
        """
        for attendance in self:
            last_attendance_before_check_in = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<=', attendance.check_in),
                ('id', '!=', attendance.id),
            ], order='check_in desc', limit=1)

            if last_attendance_before_check_in and last_attendance_before_check_in.check_out and last_attendance_before_check_in.check_out > attendance.check_in:
                raise ValidationError(
                    _("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s",
                      empl_name=attendance.employee_id.name,
                      datetime=attendance.check_in))

            if attendance.check_out:
                last_attendance_before_check_out = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_in', '<', attendance.check_out),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if last_attendance_before_check_out and last_attendance_before_check_in != last_attendance_before_check_out:
                    raise ValidationError(
                        _("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s",
                          empl_name=attendance.employee_id.name,
                          datetime=last_attendance_before_check_out.check_in))
