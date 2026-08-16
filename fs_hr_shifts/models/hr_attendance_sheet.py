# -*- coding: utf-8 -*-

##############################################################################
#
#    Merged from rm_hr_attendance_sheet (Eng.Ramadan Khalil) and
#    fs_multi_shifts.
#
##############################################################################

import pytz
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, exceptions, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date
import math

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"


class AttendanceSheet(models.Model):
    _name = 'attendance.sheet'
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
    _description = 'Hr Attendance Sheet'

    name = fields.Char("name")
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee',
                                  required=True)

    batch_id = fields.Many2one(comodel_name='attendance.sheet.batch',
                               string='Attendance Sheet Batch')
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string='Department', store=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 copy=False, required=True,
                                 default=lambda self: self.env.company)
    date_from = fields.Date(string='Date From', readonly=True, required=True,
                            default=lambda self: fields.Date.to_string(
                                date.today().replace(day=1)), )
    date_to = fields.Date(string='Date To', readonly=True, required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1,
                                                              days=-1)).date()))
    line_ids = fields.One2many(comodel_name='attendance.sheet.line',
                               string='Attendances', readonly=True,
                               inverse_name='att_sheet_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Approved')], default='draft', tracking=True,
        string='Status', required=True, readonly=True, index=True,
        help=' * The \'Draft\' status is used when a HR user is creating a new  attendance sheet. '
             '\n* The \'Confirmed\' status is used when  attendance sheet is confirmed by HR user.'
             '\n* The \'Approved\' status is used when  attendance sheet is accepted by the HR Manager.')
    no_overtime = fields.Integer(compute="_compute_sheet_total",
                                 string="No of overtimes", readonly=True,
                                 store=True)
    tot_overtime = fields.Float(compute="_compute_sheet_total",
                                string="Total Over Time", readonly=True,
                                store=True)
    tot_difftime = fields.Float(compute="_compute_sheet_total",
                                string="Total Diff time Hours", readonly=True,
                                store=True)
    no_difftime = fields.Integer(compute="_compute_sheet_total",
                                 string="No of Diff Times", readonly=True,
                                 store=True)
    tot_late = fields.Float(compute="_compute_sheet_total",
                            string="Total Late In", readonly=True, store=True)
    no_late = fields.Integer(compute="_compute_sheet_total",
                             string="No of Lates",
                             readonly=True, store=True)
    no_absence = fields.Integer(compute="_compute_sheet_total",
                                string="No of Absence Days", readonly=True,
                                store=True)
    tot_absence = fields.Float(compute="_compute_sheet_total",
                               string="Total absence Hours", readonly=True,
                               store=True)
    tot_worked_hour = fields.Float(compute="_compute_sheet_total",
                                   string="Total Late In", readonly=True,
                                   store=True)
    att_policy_id = fields.Many2one(comodel_name='hr.attendance.policy',
                                    string="Attendance Policy ", required=True)
    payslip_id = fields.Many2one(comodel_name='hr.payslip', string='PaySlip')

    contract_id = fields.Many2one('hr.contract', string='Contract',
                                  readonly=True)

    def unlink(self):
        if any(self.filtered(
                lambda att: att.state not in ('draft', 'confirm'))):
            # TODO:un comment validation in case on non testing
            pass
            # raise UserError(_(
            #     'You cannot delete an attendance sheet which is '
            #     'not draft or confirmed!'))
        return super(AttendanceSheet, self).unlink()

    @api.constrains('date_from', 'date_to')
    def check_date(self):
        for sheet in self:
            emp_sheets = self.env['attendance.sheet'].search(
                [('employee_id', '=', sheet.employee_id.id),
                 ('id', '!=', sheet.id)])
            for emp_sheet in emp_sheets:
                if max(sheet.date_from, emp_sheet.date_from) < min(
                        sheet.date_to, emp_sheet.date_to):
                    raise UserError(_(
                        'You Have Already Attendance Sheet For That '
                        'Period  Please pick another date !'))

    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_approve(self):
        self.action_create_payslip()
        self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        self.name = 'Attendance Sheet - %s - %s' % (self.employee_id.name or '',
                                                    format_date(self.env,
                                                                self.date_from,
                                                                date_format="MMMM y"))
        self.company_id = employee.company_id
        contracts = employee._get_contracts(date_from, date_to)
        if not contracts:
            raise ValidationError(
                _('There Is No Valid Contract For Employee %s' % employee.name))
        self.contract_id = contracts[0]
        if not self.contract_id.att_policy_id:
            raise ValidationError(_(
                "Employee %s does not have attendance policy" % employee.name))
        self.att_policy_id = self.contract_id.att_policy_id

    @api.depends('line_ids.overtime', 'line_ids.diff_time', 'line_ids.late_in')
    def _compute_sheet_total(self):
        """
        Compute Total overtime,late ,absence,diff time and worked hours
        :return:
        """
        for sheet in self:
            # Compute Total Overtime
            overtime_lines = sheet.line_ids.filtered(lambda l: l.overtime > 0)
            sheet.tot_overtime = sum([l.overtime for l in overtime_lines])
            sheet.no_overtime = len(overtime_lines)
            # Compute Total Late In
            late_lines = sheet.line_ids.filtered(lambda l: l.late_in > 0)
            sheet.tot_late = sum([l.late_in for l in late_lines])
            sheet.no_late = len(late_lines)
            # Compute Absence
            absence_lines = sheet.line_ids.filtered(
                lambda l: l.diff_time > 0 and l.status == "ab")
            sheet.tot_absence = sum([l.diff_time for l in absence_lines])
            sheet.no_absence = len(absence_lines)
            # conmpute earlyout
            diff_lines = sheet.line_ids.filtered(
                lambda l: l.diff_time > 0 and l.status != "ab")
            sheet.tot_difftime = sum([l.diff_time for l in diff_lines])
            sheet.no_difftime = len(diff_lines)

    def _get_float_from_time(self, time):
        str_time = datetime.strftime(time, "%H:%M")
        split_time = [int(n) for n in str_time.split(":")]
        float_time = split_time[0] + split_time[1] / 60.0
        return float_time

    def get_attendance_intervals(self, employee, day_start, day_end, tz,
                                 extra_hours=0):
        """Attendance (check in/out) intervals of ``employee`` for the day.

        :param day_start: datetime start of the day
        :param day_end: datetime end of the day
        :param extra_hours: extend the search window after the day end
            (used by multi-shift sheets so a shift ending after midnight
            is still captured).
        """
        day_start_native = day_start.replace(tzinfo=tz).astimezone(
            pytz.utc).replace(tzinfo=None)
        day_end_native = day_end.replace(tzinfo=tz).astimezone(
            pytz.utc).replace(tzinfo=None)
        res = []
        attendances = self.env['hr.attendance'].sudo().search(
            [('employee_id', '=', employee.id),
             ('check_in', '>=', day_start_native),
             ('check_in', '<=', day_end_native + timedelta(hours=extra_hours))],
            order="check_in")
        for att in attendances:
            check_in = att.check_in
            check_out = att.check_out
            if not check_out:
                continue
            res.append((check_in, check_out))
        return res

    def _get_emp_leave_intervals(self, emp, start_datetime=None,
                                 end_datetime=None):
        leaves = []
        leave_obj = self.env['hr.leave']
        leave_ids = leave_obj.search([
            ('employee_id', '=', emp.id),
            ('state', '=', 'validate')])

        for leave in leave_ids:
            date_from = leave.date_from
            if end_datetime and date_from > end_datetime:
                continue
            date_to = leave.date_to
            if start_datetime and date_to < start_datetime:
                continue
            leaves.append((date_from, date_to))
        return leaves

    def get_public_holiday(self, date, emp):
        public_holiday = []
        public_holidays = self.env['resource.calendar.leaves'].sudo().search(
            [('date_from', '<=', date), ('date_to', '>=', date),
             ('work_entry_type_id.name', '=', 'Generic Time Off')])
        for ph in public_holidays:
            public_holiday.append(ph.id)
        return public_holiday

    def _get_planned_in_out(self, emp, day):
        """Planned work intervals for ``day`` coming from Planning slots.

        Returns a list of (start, end) naive-UTC tuples.  A slot belongs
        to ``day`` when it starts inside that day in the employee
        timezone.  The real slot start/end datetimes are used, so any
        change on a shift (shorter Thursday, moved shift, second period
        with new hours...) is reflected exactly on the attendance sheet.
        Overlapping or duplicated slots are merged so the same planned
        period is never counted twice.
        """
        tz = pytz.timezone(emp.tz or 'UTC')
        day_start_local = tz.localize(datetime(day.year, day.month, day.day))
        day_end_local = day_start_local + timedelta(days=1)
        day_start_utc = day_start_local.astimezone(pytz.utc).replace(
            tzinfo=None)
        day_end_utc = day_end_local.astimezone(pytz.utc).replace(tzinfo=None)
        slots = self.env['planning.slot'].sudo().search([
            ('employee_id', '=', emp.id),
            ('start_datetime', '>=', day_start_utc),
            ('start_datetime', '<', day_end_utc),
        ], order='start_datetime')
        res = []
        for slot in slots:
            if not slot.start_datetime or not slot.end_datetime:
                continue
            if slot.end_datetime <= slot.start_datetime:
                continue
            res.append((slot.start_datetime, slot.end_datetime))
        if not res:
            return []
        return self.env['resource.calendar'].att_interval_clean(res)

    def get_attendances(self):
        """Generate the attendance sheet lines.

        Multi-shift employees (contract flag) get their planned intervals
        from Planning slots, everyone else from the working calendar.
        """
        for att_sheet in self:
            att_sheet.line_ids.unlink()
            if att_sheet.employee_id.contract_id.is_multi_shifts:
                att_sheet._generate_lines_from_planning()
            else:
                att_sheet._generate_lines_from_calendar()

    def _check_sheet_config(self):
        self.ensure_one()
        emp = self.employee_id
        if not emp.tz:
            raise ValidationError(
                _("Please add time zone for employee : %s") % emp.name)
        tz = pytz.timezone(emp.tz)
        calendar_id = emp.contract_id.resource_calendar_id
        if not calendar_id:
            raise ValidationError(_(
                'Please add working hours to the %s `s contract ') % emp.name)
        if not self.att_policy_id:
            raise ValidationError(_(
                'Please add Attendance Policy to the %s `s contract ') % emp.name)
        return emp, tz, calendar_id, self.att_policy_id

    def _generate_lines_from_calendar(self):
        """Original attendance sheet computation based on the working
        calendar of the contract (rm_hr_attendance_sheet behaviour)."""
        self.ensure_one()
        att_line = self.env["attendance.sheet.line"]
        from_date = self.date_from
        to_date = self.date_to
        emp, tz, calendar_id, policy_id = self._check_sheet_config()

        all_dates = [(from_date + timedelta(days=x)) for x in
                     range((to_date - from_date).days + 1)]
        abs_cnt = 0
        late_cnt = []
        diff_cnt = []
        for day in all_dates:
            day_start = datetime(day.year, day.month, day.day)
            day_end = day_start.replace(hour=23, minute=59, second=59)
            work_intervals = calendar_id.att_get_work_intervals(day_start,
                                                                day_end, tz)
            abs_cnt, late_cnt, diff_cnt = self._generate_day_lines(
                att_line, day, day_start, day_end, work_intervals, emp, tz,
                calendar_id, policy_id, abs_cnt, late_cnt, diff_cnt,
                extra_hours=0, multi_shifts=False)

    def _generate_lines_from_planning(self):
        """Attendance sheet computation for multi-shift employees: the
        planned intervals come from Planning slots (fs_multi_shifts
        behaviour, fixed to use the real slot start/end)."""
        self.ensure_one()
        att_line = self.env["attendance.sheet.line"]
        from_date = self.date_from
        to_date = self.date_to
        emp, tz, calendar_id, policy_id = self._check_sheet_config()

        all_dates = [(from_date + timedelta(days=x)) for x in
                     range((to_date - from_date).days + 1)]
        abs_cnt = 0
        late_cnt = []
        diff_cnt = []
        for day in all_dates:
            day_start = datetime(day.year, day.month, day.day)
            day_end = day_start.replace(hour=23, minute=59, second=59)
            work_intervals = self._get_planned_in_out(emp, day)
            if not work_intervals:
                # no planning slot that day -> fall back to the calendar
                work_intervals = calendar_id.att_get_work_intervals(
                    day_start, day_end, tz)
            abs_cnt, late_cnt, diff_cnt = self._generate_day_lines(
                att_line, day, day_start, day_end, work_intervals, emp, tz,
                calendar_id, policy_id, abs_cnt, late_cnt, diff_cnt,
                extra_hours=2, multi_shifts=True)

    def _generate_day_lines(self, att_line, day, day_start, day_end,
                            work_intervals, emp, tz, calendar_id, policy_id,
                            abs_cnt, late_cnt, diff_cnt, extra_hours=0,
                            multi_shifts=False):
        """Create the attendance sheet lines of one day and return the
        updated (abs_cnt, late_cnt, diff_cnt) counters."""
        self.ensure_one()
        day_str = str(day.weekday())
        date_str = day.strftime('%Y-%m-%d')
        attendance_intervals = self.get_attendance_intervals(
            emp, day_start, day_end, tz, extra_hours=extra_hours)
        leaves = self._get_emp_leave_intervals(emp, day_start, day_end)
        public_holiday = self.get_public_holiday(date_str, emp)
        reserved_intervals = []
        overtime_policy = policy_id.get_overtime()
        abs_flag = False
        if work_intervals:
            if public_holiday:
                if attendance_intervals:
                    for attendance_interval in attendance_intervals:
                        overtime = attendance_interval[1] - \
                                   attendance_interval[0]
                        float_overtime = overtime.total_seconds() / 3600
                        if float_overtime <= overtime_policy['ph_after']:
                            act_float_overtime = float_overtime = 0
                        else:
                            act_float_overtime = (float_overtime -
                                                  overtime_policy['ph_after'])
                            float_overtime = (float_overtime -
                                              overtime_policy['ph_after']) * \
                                             overtime_policy['ph_rate']
                        ac_sign_in = pytz.utc.localize(
                            attendance_interval[0]).astimezone(tz)
                        float_ac_sign_in = self._get_float_from_time(
                            ac_sign_in)
                        worked_hours = attendance_interval[1] - \
                                       attendance_interval[0]
                        float_worked_hours = worked_hours.total_seconds() / 3600
                        float_ac_sign_out = float_ac_sign_in + float_worked_hours
                        values = {
                            'date': date_str,
                            'day': day_str,
                            'ac_sign_in': float_ac_sign_in,
                            'ac_sign_out': float_ac_sign_out,
                            'worked_hours': float_worked_hours,
                            'overtime': float_overtime,
                            'act_overtime': act_float_overtime,
                            'att_sheet_id': self.id,
                            'status': 'ph',
                            'note': _("working on Public Holiday")
                        }
                        att_line.create(values)
                else:
                    values = {
                        'date': date_str,
                        'day': day_str,
                        'att_sheet_id': self.id,
                        'status': 'ph',
                    }
                    att_line.create(values)
            else:
                for i, work_interval in enumerate(work_intervals):
                    float_worked_hours = 0
                    att_work_intervals = []
                    diff_intervals = []
                    late_in_interval = []
                    diff_time = timedelta(hours=00, minutes=00, seconds=00)
                    late_in = timedelta(hours=00, minutes=00, seconds=00)
                    overtime = timedelta(hours=00, minutes=00, seconds=00)
                    for j, att_interval in enumerate(attendance_intervals):
                        if max(work_interval[0], att_interval[0]) < min(
                                work_interval[1], att_interval[1]):
                            current_att_interval = att_interval
                            if i + 1 < len(work_intervals):
                                next_work_interval = work_intervals[i + 1]
                                if max(next_work_interval[0],
                                       current_att_interval[0]) < min(
                                        next_work_interval[1],
                                        current_att_interval[1]):
                                    split_att_interval = (
                                        next_work_interval[0],
                                        current_att_interval[1])
                                    current_att_interval = (
                                        current_att_interval[0],
                                        next_work_interval[0])
                                    attendance_intervals[
                                        j] = current_att_interval
                                    attendance_intervals.insert(
                                        j + 1, split_att_interval)
                            att_work_intervals.append(current_att_interval)
                    reserved_intervals += att_work_intervals
                    pl_sign_in = self._get_float_from_time(
                        pytz.utc.localize(work_interval[0]).astimezone(tz))
                    pl_sign_out = self._get_float_from_time(
                        pytz.utc.localize(work_interval[1]).astimezone(tz))
                    ac_sign_in = 0
                    ac_sign_out = 0
                    status = ""
                    if att_work_intervals:
                        if len(att_work_intervals) > 1:
                            late_in_interval = (
                                work_interval[0],
                                att_work_intervals[0][0])
                            overtime_interval = (
                                work_interval[1],
                                att_work_intervals[-1][1])
                            if overtime_interval[1] < overtime_interval[0]:
                                overtime = timedelta(hours=0, minutes=0,
                                                     seconds=0)
                            else:
                                overtime = overtime_interval[1] - \
                                           overtime_interval[0]
                            remain_interval = (
                                att_work_intervals[0][1],
                                work_interval[1])
                            for att_work_interval in att_work_intervals:
                                float_worked_hours += (
                                    att_work_interval[1] -
                                    att_work_interval[0]).total_seconds() / 3600
                                if att_work_interval[1] <= remain_interval[0]:
                                    continue
                                if att_work_interval[0] >= remain_interval[1]:
                                    break
                                if remain_interval[0] < \
                                        att_work_interval[0] < \
                                        remain_interval[1]:
                                    diff_intervals.append((
                                        remain_interval[0],
                                        att_work_interval[0]))
                                    remain_interval = (
                                        att_work_interval[1],
                                        remain_interval[1])
                            if remain_interval and remain_interval[0] <= \
                                    work_interval[1]:
                                diff_intervals.append((remain_interval[0],
                                                       work_interval[1]))
                            ac_sign_in = self._get_float_from_time(
                                pytz.utc.localize(
                                    att_work_intervals[0][0]).astimezone(tz))
                            ac_sign_out = ac_sign_in + ((
                                att_work_intervals[-1][1] -
                                att_work_intervals[0][0]).total_seconds() / 3600)
                        else:
                            late_in_interval = (
                                work_interval[0],
                                att_work_intervals[0][0])
                            overtime_interval = (
                                work_interval[1],
                                att_work_intervals[-1][1])
                            if overtime_interval[1] < overtime_interval[0]:
                                overtime = timedelta(hours=0, minutes=0,
                                                     seconds=0)
                                diff_intervals.append((
                                    overtime_interval[1],
                                    overtime_interval[0]))
                            else:
                                overtime = overtime_interval[1] - \
                                           overtime_interval[0]
                            ac_sign_in = self._get_float_from_time(
                                pytz.utc.localize(
                                    att_work_intervals[0][0]).astimezone(tz))
                            worked_hours = att_work_intervals[0][1] - \
                                           att_work_intervals[0][0]
                            float_worked_hours = worked_hours.total_seconds() / 3600
                            ac_sign_out = ac_sign_in + float_worked_hours
                            if multi_shifts:
                                ac_sign_out = ac_sign_out if ac_sign_out < 24 \
                                    else ac_sign_out - 24
                    else:
                        late_in_interval = []
                        diff_intervals.append(
                            (work_interval[0], work_interval[1]))
                        status = "ab"
                    if diff_intervals:
                        for diff_in in diff_intervals:
                            if leaves:
                                status = "leave"
                                diff_clean_intervals = calendar_id.att_interval_without_leaves(
                                    diff_in, leaves)
                                for diff_clean in diff_clean_intervals:
                                    diff_time += diff_clean[1] - diff_clean[0]
                            else:
                                diff_time += diff_in[1] - diff_in[0]
                    if late_in_interval:
                        if late_in_interval[1] < late_in_interval[0]:
                            late_in = timedelta(hours=0, minutes=0, seconds=0)
                        else:
                            if leaves:
                                late_clean_intervals = calendar_id.att_interval_without_leaves(
                                    late_in_interval, leaves)
                                for late_clean in late_clean_intervals:
                                    late_in += late_clean[1] - late_clean[0]
                            else:
                                late_in = late_in_interval[1] - \
                                          late_in_interval[0]
                    float_overtime = overtime.total_seconds() / 3600
                    if float_overtime <= overtime_policy['wd_after']:
                        act_float_overtime = float_overtime = 0
                    else:
                        act_float_overtime = float_overtime
                        float_overtime = float_overtime * \
                                         overtime_policy['wd_rate']
                    # 1 minute = 0.0166 hour
                    float_late = math.floor(late_in.total_seconds() / 60) / 60
                    act_float_late = math.floor(late_in.total_seconds() / 60)
                    policy_late, late_cnt = policy_id.get_late(float_late,
                                                               late_cnt)
                    float_diff = math.floor(
                        diff_time.total_seconds() / 3600 * 100) / 100
                    if status == 'ab':
                        if not abs_flag:
                            abs_cnt += 1
                        abs_flag = True
                        act_float_diff = float_diff
                        float_diff = policy_id.get_absence(float_diff, abs_cnt)
                    else:
                        act_float_diff = float_diff
                        float_diff, diff_cnt = policy_id.get_diff(float_diff,
                                                                  diff_cnt)
                    values = {
                        'date': date_str,
                        'day': day_str,
                        'pl_sign_in': pl_sign_in,
                        'pl_sign_out': pl_sign_out,
                        'ac_sign_in': ac_sign_in,
                        'ac_sign_out': ac_sign_out,
                        'late_in': policy_late,
                        'act_late_in': act_float_late,
                        'worked_hours': float_worked_hours,
                        'overtime': float_overtime,
                        'act_overtime': act_float_overtime,
                        'diff_time': float_diff,
                        'act_diff_time': act_float_diff,
                        'status': status,
                        'att_sheet_id': self.id
                    }
                    att_line.create(values)
                out_work_intervals = [x for x in attendance_intervals if
                                      x not in reserved_intervals]
                if out_work_intervals:
                    if multi_shifts and len(attendance_intervals) >= 2:
                        # keep fs_multi_shifts behaviour: with several
                        # attendances the leftovers are already handled
                        # by the split logic above
                        return abs_cnt, late_cnt, diff_cnt
                    for att_out in out_work_intervals:
                        overtime = att_out[1] - att_out[0]
                        ac_sign_in = self._get_float_from_time(
                            pytz.utc.localize(att_out[0]).astimezone(tz))
                        float_worked_hours = overtime.total_seconds() / 3600
                        ac_sign_out = ac_sign_in + float_worked_hours
                        float_overtime = overtime.total_seconds() / 3600
                        if float_overtime <= overtime_policy['wd_after']:
                            float_overtime = act_float_overtime = 0
                        else:
                            act_float_overtime = float_overtime
                            float_overtime = act_float_overtime * \
                                             overtime_policy['wd_rate']
                        values = {
                            'date': date_str,
                            'day': day_str,
                            'pl_sign_in': 0,
                            'pl_sign_out': 0,
                            'ac_sign_in': ac_sign_in,
                            'ac_sign_out': ac_sign_out,
                            'overtime': float_overtime,
                            'worked_hours': float_worked_hours,
                            'act_overtime': act_float_overtime,
                            'note': _("overtime out of work intervals"),
                            'att_sheet_id': self.id
                        }
                        att_line.create(values)
        else:
            if attendance_intervals:
                # working on a weekend day -> overtime
                for attendance_interval in attendance_intervals:
                    overtime = attendance_interval[1] - attendance_interval[0]
                    float_overtime = overtime.total_seconds() / 3600
                    if float_overtime <= overtime_policy['we_after']:
                        float_overtime = 0
                        act_float_overtime = 0
                    else:
                        act_float_overtime = float_overtime
                        float_overtime = act_float_overtime * \
                                         overtime_policy['we_rate']
                    ac_sign_in = pytz.utc.localize(
                        attendance_interval[0]).astimezone(tz)
                    ac_sign_out = pytz.utc.localize(
                        attendance_interval[1]).astimezone(tz)
                    worked_hours = attendance_interval[1] - \
                                   attendance_interval[0]
                    float_worked_hours = worked_hours.total_seconds() / 3600
                    values = {
                        'date': date_str,
                        'day': day_str,
                        'ac_sign_in': self._get_float_from_time(ac_sign_in),
                        'ac_sign_out': self._get_float_from_time(ac_sign_out),
                        'overtime': float_overtime,
                        'act_overtime': act_float_overtime,
                        'worked_hours': float_worked_hours,
                        'att_sheet_id': self.id,
                        'status': 'weekend',
                        'note': _("working in weekend")
                    }
                    att_line.create(values)
            else:
                values = {
                    'date': date_str,
                    'day': day_str,
                    'att_sheet_id': self.id,
                    'status': 'weekend',
                    'note': ""
                }
                att_line.create(values)
        return abs_cnt, late_cnt, diff_cnt

    def action_payslip(self):
        self.ensure_one()
        payslip_id = self.payslip_id
        if not payslip_id:
            payslip_id = self.action_create_payslip()[0]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': payslip_id.id,
            'views': [(False, 'form')],
        }

    def action_create_payslip(self):
        payslip_obj = self.env['hr.payslip']
        payslips = payslip_obj
        for sheet in self:
            contracts = sheet.employee_id._get_contracts(sheet.date_from,
                                                         sheet.date_to)
            if not contracts:
                raise ValidationError(
                    _('There is no active contract for current employee'))
            if sheet.payslip_id:
                raise ValidationError(_('Payslip Has Been Created Before'))
            payslip_name = contracts[0].structure_type_id.default_struct_id.payslip_name or _(
                'Salary Slip')
            name = '%(payslip_name)s - %(employee_name)s - %(dates)s' % {
                'payslip_name': payslip_name,
                'employee_name': sheet.employee_id.name,
                'dates': format_date(self.env, sheet.date_from,
                                     date_format="MMMM y")
            }

            payslip_id = payslip_obj.create({
                'name': name,
                'employee_id': sheet.employee_id.id,
                'date_from': sheet.date_from,
                'date_to': sheet.date_to,
                'sheet_id': sheet.id,
                'contract_id': contracts[0].id,
                'struct_id': contracts[0].structure_type_id.default_struct_id.id,
            })
            worked_day_lines = self._get_workday_lines()
            payslip_id.worked_days_line_ids = [(0, 0, x) for x in
                                               worked_day_lines]
            payslip_id.compute_sheet()
            sheet.payslip_id = payslip_id
            payslips += payslip_id
        return payslips

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
            'number_of_days': self.no_overtime,
            'number_of_hours': self.tot_overtime,
        }]
        absence = [{
            'name': "Absence",
            'code': 'ABS',
            'work_entry_type_id': absence_work_entry[0].id,
            'sequence': 35,
            'number_of_days': self.no_absence,
            'number_of_hours': self.tot_absence,
        }]
        late = [{
            'name': "Late In",
            'code': 'LATE',
            'work_entry_type_id': latin_work_entry[0].id,
            'sequence': 40,
            'number_of_days': self.no_late,
            'number_of_hours': self.tot_late,
        }]
        difftime = [{
            'name': "Difference time",
            'code': 'DIFFT',
            'work_entry_type_id': difftime_work_entry[0].id,
            'sequence': 45,
            'number_of_days': self.no_difftime,
            'number_of_hours': self.tot_difftime,
        }]
        worked_days_lines = overtime + late + absence + difftime
        return worked_days_lines


class AttendanceSheetLine(models.Model):
    _name = 'attendance.sheet.line'
    _description = 'Attendance Sheet Line'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sum', 'Summary'),
        ('confirm', 'Confirmed'),
        ('done', 'Approved')], related='att_sheet_id.state', store=True, )

    date = fields.Date("Date")
    day = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday')
    ], 'Day of Week', required=True, index=True, )
    att_sheet_id = fields.Many2one(comodel_name='attendance.sheet',
                                   ondelete="cascade",
                                   string='Attendance Sheet', readonly=True)
    employee_id = fields.Many2one(related='att_sheet_id.employee_id',
                                  string='Employee')
    pl_sign_in = fields.Float("Planned sign in", readonly=True)
    pl_sign_out = fields.Float("Planned sign out", readonly=True)
    worked_hours = fields.Float("Worked Hours", readonly=True)
    ac_sign_in = fields.Float("Actual sign in", readonly=True)
    ac_sign_out = fields.Float("Actual sign out", readonly=True)
    overtime = fields.Float("Overtime", readonly=True)
    act_overtime = fields.Float("Actual Overtime", readonly=True)
    late_in = fields.Float("Late In", readonly=True)
    diff_time = fields.Float("Diff Time",
                             help="Diffrence between the working time and attendance time(s) ",
                             readonly=True)
    act_late_in = fields.Float("Actual Late In", readonly=True)
    act_diff_time = fields.Float("Actual Diff Time",
                                 help="Diffrence between the working time and attendance time(s) ",
                                 readonly=True)
    status = fields.Selection(string="Status",
                              selection=[('ab', 'Absence'),
                                         ('weekend', 'Week End'),
                                         ('ph', 'Public Holiday'),
                                         ('leave', 'Leave'), ],
                              required=False, readonly=True)
    note = fields.Text("Note", readonly=True)
