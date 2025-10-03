# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, time, timedelta
import pytz


class BiotimeDashboard(models.Model):
    _name = 'biotime.dashboard'
    _description = 'Biotime Dashboard'

    # ---------- Helpers ----------
    def _today_utc_range(self, tz_name):
        tz = pytz.timezone(tz_name or 'UTC')
        now_local = datetime.now(tz)
        start_local = tz.localize(datetime.combine(now_local.date(), time.min)).astimezone(pytz.utc)
        end_local = tz.localize(datetime.combine(now_local.date(), time.max)).astimezone(pytz.utc)
        return start_local.replace(tzinfo=None), end_local.replace(tzinfo=None)

    # ---------- Dashboard Data ----------
    @api.model
    def get_dashboard_data(self):
        Terminal = self.env['biotime.terminal'].sudo()
        Employee = self.env['biotime.employee'].sudo()
        Attendance = self.env['hr.attendance'].sudo()
        Config = self.env['biotime.config'].sudo()

        cfg = Config.search([], limit=1)
        devices_count = employees_count = attendance_today = 0

        if cfg:
            devices_count = Terminal.search_count([('biotime_id', '=', cfg.id)])
            employees_count = Employee.search_count([('biotime_id', '=', cfg.id)])
            start_utc, end_utc = self._today_utc_range(cfg.tz or 'UTC')
            attendance_today = Attendance.search_count([
                ('check_in', '>=', start_utc),
                ('check_in', '<=', end_utc),
            ])

        return {
            'devices': devices_count,
            'employees': employees_count,
            'attendance': attendance_today,
        }

    @api.model
    def get_weekly_attendance(self):
        Attendance = self.env['hr.attendance'].sudo()
        Config = self.env['biotime.config'].sudo()
        cfg = Config.search([], limit=1)

        tz = pytz.timezone(cfg.tz or 'UTC') if cfg else pytz.UTC
        today = datetime.now(tz).date()

        data = []
        labels = []

        for i in range(7):
            day = today - timedelta(days=i)
            start_local = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.utc)
            end_local = tz.localize(datetime.combine(day, time.max)).astimezone(pytz.utc)
            count = Attendance.search_count([
                ('check_in', '>=', start_local),
                ('check_in', '<=', end_local),
            ])
            labels.append(day.strftime('%a'))   # e.g. Mon, Tue, ...
            data.append(count)

        # reverse to show oldest → newest
        return {
            'labels': labels[::-1],
            'data': data[::-1],
        }
