# -*- coding: utf-8 -*-

##############################################################################
#
#    Merged from rm_hr_attendance_sheet (attendance sheet payslip
#    integration) and fs_multi_shifts (extra leave deduction helper).
#
##############################################################################

from datetime import datetime, date, time as dt_time

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    sheet_id = fields.Many2one(comodel_name="attendance.sheet",
                               string="Attendance Sheet", required=False, )

    def _get_workday_lines(self):
        self.ensure_one()

        work_entry_obj = self.env['hr.work.entry.type']
        overtime_work_entry = work_entry_obj.search([('code', '=', 'ATTSHOT')])
        latin_work_entry = work_entry_obj.search([('code', '=', 'ATTSHLI')])
        absence_work_entry = work_entry_obj.search([('code', '=', 'ATTSHAB')])
        difftime_work_entry = work_entry_obj.search([('code', '=', 'ATTSHDT')])
        if not overtime_work_entry:
            raise ValidationError(_(
                'Please Add Work Entry Type For Attendance Sheet Overtime With Code ATTSHOT'))
        if not latin_work_entry:
            raise ValidationError(_(
                'Please Add Work Entry Type For Attendance Sheet Late In With Code ATTSHLI'))
        if not absence_work_entry:
            raise ValidationError(_(
                'Please Add Work Entry Type For Attendance Sheet Absence With Code ATTSHAB'))
        if not difftime_work_entry:
            raise ValidationError(_(
                'Please Add Work Entry Type For Attendance Sheet Diff Time With Code ATTSHDT'))

        overtime = [{
            'name': "Overtime",
            'code': 'OVT',
            'work_entry_type_id': overtime_work_entry[0].id,
            'sequence': 30,
            'number_of_days': self.sheet_id.no_overtime,
            'number_of_hours': self.sheet_id.tot_overtime,
        }]
        absence = [{
            'name': "Absence",
            'code': 'ABS',
            'work_entry_type_id': absence_work_entry[0].id,
            'sequence': 35,
            'number_of_days': self.sheet_id.no_absence,
            'number_of_hours': self.sheet_id.tot_absence,
        }]
        late = [{
            'name': "Late In",
            'code': 'LATE',
            'work_entry_type_id': latin_work_entry[0].id,
            'sequence': 40,
            'number_of_days': self.sheet_id.no_late,
            'number_of_hours': self.sheet_id.tot_late,
        }]
        difftime = [{
            'name': "Difference time",
            'code': 'DIFFT',
            'work_entry_type_id': difftime_work_entry[0].id,
            'sequence': 45,
            'number_of_days': self.sheet_id.no_difftime,
            'number_of_hours': self.sheet_id.tot_difftime,
        }]
        worked_days_lines = overtime + late + absence + difftime
        return worked_days_lines

    def compute_sheet(self):
        if self.sheet_id:
            worked_day_lines = self._get_workday_lines()
            if len(self.worked_days_line_ids) < 2:
                self.worked_days_line_ids = [(0, 0, x) for x in
                                             worked_day_lines]
        return super(HrPayslip, self).compute_sheet()

    # ------------------------------------------------------------------
    # Extra leave (permission) deduction helper - used in salary rules
    # ------------------------------------------------------------------
    def _to_datetime(self, value):
        """Convert various types (str, date, datetime) to a naive datetime."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        # date but not datetime -> set to midnight
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, dt_time.min)
        try:
            return fields.Datetime.from_string(value)
        except Exception:
            try:
                return fields.Datetime.from_string(str(value))
            except Exception:
                return None

    def _get_extra_leave_deduction(self, contract):
        """Deduction of the (hourly permission) leaves exceeding the
        allowed monthly quota.  Only the part overlapping the payslip
        period (date_from..date_to) is counted.

        Leave type id can be changed via the system parameter
        'payroll.leave_type_id_ghyab' (default 4) and the allowed minutes
        via 'payroll.allowed_minutes' (default 150).
        """
        self.ensure_one()

        date_from = self._to_datetime(self.date_from)
        date_to = self._to_datetime(self.date_to)
        if not date_from or not date_to:
            return 0.0

        leave_type_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'payroll.leave_type_id_ghyab', 4))

        domain = [
            ('employee_id', '=', contract.employee_id.id),
            ('holiday_status_id', '=', leave_type_id),
            ('state', '=', 'validate'),
            '|',
                '&',
                    ('request_date_from', '<=', fields.Datetime.to_string(date_to)),
                    ('request_date_to', '>=', fields.Datetime.to_string(date_from)),
                '&',
                    ('date_from', '<=', fields.Datetime.to_string(date_to)),
                    ('date_to', '>=', fields.Datetime.to_string(date_from)),
        ]

        leaves = self.env['hr.leave'].search(domain)

        leave_minutes = 0.0

        for leave in leaves:
            l_from = self._to_datetime(
                getattr(leave, 'date_from', None)
                or getattr(leave, 'request_date_from', None))
            l_to = self._to_datetime(
                getattr(leave, 'date_to', None)
                or getattr(leave, 'request_date_to', None))

            # no dates -> fall back on number_of_hours
            if not l_from or not l_to:
                hours = float(leave.number_of_hours or 0.0)
                leave_minutes += hours * 60.0
                continue

            # only the part inside the payslip period
            effective_from = l_from if l_from > date_from else date_from
            effective_to = l_to if l_to < date_to else date_to

            if effective_from >= effective_to:
                continue

            duration_seconds = (effective_to - effective_from).total_seconds()
            leave_minutes += duration_seconds / 60.0

        allowed_minutes = int(self.env['ir.config_parameter'].sudo().get_param(
            'payroll.allowed_minutes', 150))
        excess_minutes = max(0.0, leave_minutes - allowed_minutes)

        basic_salary = contract.wage or 0.0
        if basic_salary <= 0.0:
            return 0.0

        minute_rate = basic_salary / 30.0 / 8.0 / 60.0
        return excess_minutes * minute_rate
