# -*- coding: utf-8 -*-

##############################################################################
#
#    Merged from planning_shifts_generator and fixed:
#
#    * Re-generating a period no longer duplicates shifts: existing slots
#      of the same role in the generated period are replaced (optional
#      checkbox, enabled by default).  This was the main "change shift"
#      problem: the old wizard always created new slots on top of the old
#      ones, so changed shifts were counted twice.
#    * Only ONE reset-log per contract is kept, storing the real original
#      values.  The old wizard created a new log on every run, so after a
#      second run the log contained the already-modified values and
#      "Reset Contracts" could restore the wrong state.
#    * Proper date validations with user-friendly errors (the old wizard
#      raised a bare ValueError).
#
##############################################################################

import math

from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AutoGenerateShifts(models.TransientModel):
    _name = 'auto.generate.shifts.wizard'
    _description = 'Auto Generate Shifts Wizard'

    role_id = fields.Many2one('planning.role', string="Role", required=True)
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company
    )

    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)

    start_hour = fields.Float(string="Normal Start Hour", default=7.0)
    end_hour = fields.Float(string="Normal End Hour", default=15.0)
    thursday_start_hour = fields.Float(string="Thursday Start Hour",
                                       default=7.0)
    thursday_end_hour = fields.Float(string="Thursday End Hour", default=12.5)
    friday_off = fields.Boolean(string="Exclude Fridays", default=True)

    replace_existing = fields.Boolean(
        string="Replace Existing Shifts", default=True,
        help="Delete the shifts of the same role already planned inside "
             "the generated period before creating the new ones.  Keep it "
             "enabled when changing shift times so the old shifts are "
             "replaced instead of duplicated.")

    second_period = fields.Boolean(string="Add Second Period")
    second_start_date = fields.Date(string="Second Period Start")
    second_end_date = fields.Date(string="Second Period End")
    second_start_hour = fields.Float(string="Second Start Hour", default=9.0)
    second_end_hour = fields.Float(string="Second End Hour", default=17.0)
    second_thursday_start = fields.Float(string="Second Thursday Start",
                                         default=9.0)
    second_thursday_end = fields.Float(string="Second Thursday End",
                                       default=14.5)

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def float_to_time(self, hour_float):
        frac, hours = math.modf(hour_float)
        minutes = int(round(frac * 60))
        return int(hours), minutes

    def to_utc_naive(self, dt, tzname):
        local_tz = pytz.timezone(tzname)
        local_dt = local_tz.localize(dt)
        utc_dt = local_dt.astimezone(pytz.utc)
        return utc_dt.replace(tzinfo=None)

    def _get_employee_tz(self, employee, company):
        return employee.resource_calendar_id.tz \
            or company.resource_calendar_id.tz or 'UTC'

    def _check_dates(self):
        self.ensure_one()
        if self.date_end < self.date_start:
            raise UserError(_(
                "The end date (%s) must be after the start date (%s).")
                % (self.date_end, self.date_start))
        if self.start_hour >= self.end_hour:
            raise UserError(
                _("The normal end hour must be after the start hour."))
        if self.thursday_start_hour >= self.thursday_end_hour:
            raise UserError(
                _("The Thursday end hour must be after the start hour."))
        if self.second_period:
            if not self.second_start_date or not self.second_end_date:
                raise UserError(_(
                    "Please set the start and end dates of the second "
                    "period."))
            if self.second_end_date < self.second_start_date:
                raise UserError(_(
                    "The second period end date must be after its start "
                    "date."))
            if self.second_start_date <= self.date_end and \
                    self.second_end_date >= self.date_start:
                raise UserError(_(
                    "The second period overlaps the first period. The "
                    "same day would get two shifts - please fix the "
                    "dates."))
            if self.second_start_hour >= self.second_end_hour:
                raise UserError(_(
                    "The second period end hour must be after its start "
                    "hour."))
            if self.second_thursday_start >= self.second_thursday_end:
                raise UserError(_(
                    "The second period Thursday end hour must be after "
                    "its start hour."))

    def _delete_existing_slots(self, employee, role, start, end, tzname):
        """Remove the slots of ``role`` already planned for ``employee``
        inside [start, end] so the newly generated shifts replace them."""
        local_tz = pytz.timezone(tzname)
        start_dt = local_tz.localize(
            datetime.combine(start, datetime.min.time())).astimezone(
            pytz.utc).replace(tzinfo=None)
        end_dt = local_tz.localize(
            datetime.combine(end + timedelta(days=1),
                             datetime.min.time())).astimezone(
            pytz.utc).replace(tzinfo=None)
        slots = self.env['planning.slot'].sudo().search([
            ('resource_id', '=', employee.resource_id.id),
            ('role_id', '=', role.id),
            ('start_datetime', '<', end_dt),
            ('end_datetime', '>', start_dt),
        ])
        if slots:
            slots.unlink()

    def generate_for_range(self, employee, company, role, start, end,
                           start_hour, end_hour, thu_start, thu_end,
                           friday_off):
        PlanningSlot = self.env['planning.slot'].sudo()
        local_tz = self._get_employee_tz(employee, company)

        if self.replace_existing:
            self._delete_existing_slots(employee, role, start, end, local_tz)

        for day in (datetime.combine(start + timedelta(days=i),
                                     datetime.min.time())
                    for i in range((end - start).days + 1)):
            if friday_off and day.weekday() == 4:
                continue
            if day.weekday() == 3:
                s_h, s_m = self.float_to_time(thu_start)
                e_h, e_m = self.float_to_time(thu_end)
            else:
                s_h, s_m = self.float_to_time(start_hour)
                e_h, e_m = self.float_to_time(end_hour)

            start_time = day.replace(hour=s_h, minute=s_m)
            end_time = day.replace(hour=e_h, minute=e_m)

            PlanningSlot.create({
                'resource_id': employee.resource_id.id,
                'role_id': role.id,
                'start_datetime': self.to_utc_naive(start_time, local_tz),
                'end_datetime': self.to_utc_naive(end_time, local_tz),
                'company_id': company.id,
                'state': 'draft',
            })

    def _switch_contract_to_planning(self, employee):
        """Flag the running contract as multi-shift / planning-based and
        keep (only once) its original values so it can be restored."""
        contract = self.env["hr.contract"].search([
            ("employee_id", "=", employee.id),
            ("state", "=", "open")
        ], limit=1)
        if not contract:
            return

        # keep the FIRST log per contract: it holds the real original
        # values.  Creating a new log on every run would overwrite them
        # with already-modified values.
        existing_log = self.env["contract.reset.log"].search(
            [("contract_id", "=", contract.id)], limit=1)
        if not existing_log:
            self.env["contract.reset.log"].create({
                "contract_id": contract.id,
                "old_is_multi_shifts": contract.is_multi_shifts,
                "old_work_entry_source": contract.work_entry_source,
            })

        vals = {}
        if not contract.is_multi_shifts:
            vals["is_multi_shifts"] = True
        if contract.work_entry_source != "calendar_planning":
            vals["work_entry_source"] = "calendar_planning"
        if vals:
            contract.write(vals)

    # ------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------
    def action_generate(self):
        self.ensure_one()
        self._check_dates()
        comp = self.company_id
        role = self.role_id

        employees = role.resource_ids.mapped('employee_id').filtered(
            lambda e: e and e.resource_id)
        if not employees:
            raise UserError(
                _("There are no employees linked to the role %s!")
                % role.name)

        for emp in employees:
            # first period
            self.generate_for_range(emp, comp, role, self.date_start,
                                    self.date_end,
                                    self.start_hour, self.end_hour,
                                    self.thursday_start_hour,
                                    self.thursday_end_hour,
                                    self.friday_off)

            # second period
            if self.second_period and self.second_start_date and \
                    self.second_end_date:
                self.generate_for_range(emp, comp, role,
                                        self.second_start_date,
                                        self.second_end_date,
                                        self.second_start_hour,
                                        self.second_end_hour,
                                        self.second_thursday_start,
                                        self.second_thursday_end,
                                        self.friday_off)

            self._switch_contract_to_planning(emp)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shifts Generated'),
                'message': _(
                    'Shifts created successfully for role %s!') % role.name,
                'sticky': False,
            }
        }

    def action_reset_contracts(self):
        logs = self.env["contract.reset.log"].search([], order="id")
        done_contracts = self.env["hr.contract"]
        for log in logs:
            contract = log.contract_id
            if contract in done_contracts:
                continue
            done_contracts |= contract
            contract.write({
                "is_multi_shifts": log.old_is_multi_shifts,
                "work_entry_source": log.old_work_entry_source or 'calendar',
            })

        logs.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contracts Reset'),
                'message': _('Contracts values restored to original!'),
                'sticky': False,
            }
        }
