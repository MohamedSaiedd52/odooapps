# -*- coding: utf-8 -*-
import logging
import requests
import json
import secrets
from datetime import datetime, timedelta
from collections import defaultdict

import pytz

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.base.models.res_partner import _tz_get
from ..queue.exception import RetryableJobError

from .utils import get_transactions, get_next_page

_logger = logging.getLogger(__name__)

# (connect timeout, read timeout) in seconds. Without this, requests waits on
# the OS default TCP timeout (minutes) and hangs the queue_job worker.
REQUEST_TIMEOUT = (10, 60)


class BioTime(models.Model):
    _name = 'biotime.config'
    _description = "BioTime Configuration"
    _inherit = ['mail.thread']

    name = fields.Char(string="Name", default="Server")
    server_host = fields.Char(
        string="Server Host", default="10.10.10.10",
        help="Just the IP address or domain, e.g. 10.10.10.10")
    port = fields.Integer(string="Port", default=6070)
    username = fields.Char(string="Username", default="admin")
    password = fields.Char(string="Password", default="Admin")
    company_id = fields.Many2one(
        'res.company', string="Company",
        default=lambda self: self.env.company.id)
    tz = fields.Selection(
        _tz_get, string='Timezone', required=True,
        default=lambda self: self._context.get('tz') or self.env.user.tz or 'UTC')
    pull_from_date = fields.Datetime('Pull From Date')
    pull_to_date = fields.Datetime('Pull To Date')
    pull_overlap_days = fields.Integer(
        string="Re-pull Window (days)", default=3,
        help="The automatic sync re-pulls this many past days on every run, so "
             "punches uploaded late by an offline device are still caught. "
             "Already-imported punches are never duplicated.")
    max_shift_hours = fields.Integer(
        string="Max Shift Length (hours)", default=14,
        help="Punches within this many hours of the first punch of a shift "
             "belong to the same shift. This is what lets a night shift "
             "(e.g. 22:00 → 06:00) cross midnight without being split in two.")
    auto_transfer = fields.Boolean(
        string="Auto Transfer to Attendance", default=True,
        help="After every automatic pull (nightly cron), immediately build "
             "hr.attendance records from the pulled punches.")
    last_pull_date = fields.Datetime(string="Last Pull", readonly=True)
    last_transfer_date = fields.Datetime(string="Last Transfer", readonly=True)
    webhook_enabled = fields.Boolean(
        string="Enable Push Webhook", default=False,
        help="Accept punches pushed in real time to "
             "/biotime/webhook (JSON POST with the token below).")
    webhook_token = fields.Char(
        string="Webhook Token", copy=False,
        default=lambda self: secrets.token_urlsafe(24),
        help="Secret token the push client must send in the "
             "X-Biotime-Token header (or 'token' key in the JSON body).")
    terminal_count = fields.Integer(string="Devices", compute="_compute_terminal_count")
    emp_count = fields.Integer(string="Employee", compute="_compute_emp_count")
    transaction_count = fields.Integer(string="Transactions", compute="_compute_transaction_count")
    log_count = fields.Integer(string="Unmatched Logs", compute="_compute_log_count")
    server_url = fields.Char(
        string="Server URL", compute="_compute_server_url", store=False)

    # ── Computed ──
    @api.depends('server_host', 'port')
    def _compute_server_url(self):
        for rec in self:
            rec.server_url = "http://%s:%s" % (rec.server_host, rec.port)

    def _compute_terminal_count(self):
        for rec in self:
            rec.terminal_count = self.env['biotime.terminal'].search_count(
                [('biotime_id', '=', rec.id)])

    def _compute_emp_count(self):
        for rec in self:
            rec.emp_count = self.env['biotime.employee'].search_count(
                [('biotime_id', '=', rec.id)])

    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = self.env['biotime.transaction'].sudo().search_count(
                [('server_id', '=', rec.id)])

    def _compute_log_count(self):
        for rec in self:
            rec.log_count = self.env['biotime.transaction.log'].sudo().search_count(
                [('server_id', '=', rec.id)])

    # ── Utils ──
    def convert_to_utc(self, date_str, timezone):
        date_format = '%Y-%m-%d %H:%M:%S'
        local_dt = datetime.strptime(date_str, date_format)
        local_tz = pytz.timezone(timezone)
        local_dt = local_tz.localize(local_dt)
        utc_dt = local_dt.astimezone(pytz.utc)
        return utc_dt.strftime(date_format)

    def generate_access_token(self):
        self.ensure_one()
        url = "%s/api-token-auth/" % self.server_url
        payload = json.dumps({
            "username": self.username,
            "password": self.password
        })
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            url, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            if not token:
                raise ValidationError(_("No token returned from BioTime server."))
            return token
        else:
            raise ValidationError(
                _("Failed to authenticate with BioTime: %s") % response.text)

    def action_test_connection(self):
        """Try to authenticate against the BioTime server and show the result
        as a toast notification instead of failing silently on first pull."""
        self.ensure_one()
        try:
            self.generate_access_token()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exc:
            raise UserError(_(
                "Could not reach BioTime server at %s.\n\n%s")
                % (self.server_url, exc)) from exc
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Connection successful"),
                'message': _("Authenticated with BioTime server %s.") % self.server_url,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_open_pull_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pull Transactions (Advanced)'),
            'res_model': 'biotime.pull.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_server_id': self.id},
        }

    # ── Smart Buttons ──
    def action_get_terminals_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Devices'),
            'view_mode': 'list,form',
            'res_model': 'biotime.terminal',
            'domain': [('biotime_id', '=', self.id)],
            'context': {'default_biotime_id': self.id}
        }

    def action_get_emp_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Employees'),
            'view_mode': 'list,form',
            'res_model': 'biotime.employee',
            'domain': [('biotime_id', '=', self.id)],
            'context': {'default_biotime_id': self.id}
        }

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Raw Transactions'),
            'view_mode': 'list',
            'res_model': 'biotime.transaction',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id}
        }

    def action_open_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Unmatched Transactions',
            'res_model': 'biotime.transaction.log',
            'view_mode': 'list',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id},
        }

    # ── Devices ──
    def action_get_all_terminals(self):
        for rec in self:
            terminal_env = self.env['biotime.terminal'].sudo()
            url = "%s/iclock/api/terminals/" % rec.server_url
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Token %s' % rec.generate_access_token()
            }
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            data = response.json()
            if data.get('data'):
                existing = {
                    t.terminal_sn: t
                    for t in terminal_env.search([('biotime_id', '=', rec.id)])
                }
                to_create = []
                for terminal in data['data']:
                    sn = terminal.get('sn')
                    last_activity = False
                    if terminal.get('last_activity'):
                        try:
                            last_activity = datetime.strptime(
                                rec.convert_to_utc(
                                    terminal['last_activity'][:19].replace('T', ' '),
                                    rec.tz),
                                '%Y-%m-%d %H:%M:%S')
                        except (ValueError, TypeError):
                            last_activity = False
                    vals = {
                        'name': terminal.get('terminal_name') or terminal.get('alias') or 'New Device',
                        'terminal_id': terminal.get('id'),
                        'terminal_sn': sn,
                        'ip_address': terminal.get('ip_address'),
                        'alias': terminal.get('alias'),
                        'terminal_tz': terminal.get('terminal_tz'),
                        'last_activity': last_activity,
                        'device_state': str(terminal.get('state', '')),
                        'biotime_id': rec.id,
                    }
                    if sn in existing:
                        # refresh device info/status on every click, not only
                        # on first discovery
                        existing[sn].write(vals)
                    else:
                        to_create.append(vals)
                if to_create:
                    terminal_env.create(to_create)

    # ── Employees ──
    def action_get_all_employees(self, page=1):
        for rec in self:
            employee_env = self.env['biotime.employee'].sudo()
            url = "%s/personnel/api/employees/?page=%s" % (rec.server_url, page)
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Token %s' % rec.generate_access_token()
            }
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            data = response.json()

            if data.get('data'):
                all_codes = [e.get('emp_code') for e in data['data'] if e.get('emp_code')]
                hr_emps = {
                    e.zk_emp_code: e.id
                    for e in self.env['hr.employee'].sudo().search(
                        [('zk_emp_code', 'in', all_codes)])
                }
                # employee_id is a Char field, so it is read back as a string.
                # Normalize the key to str on both sides, otherwise the lookup
                # never matches and duplicate biotime.employee records are created.
                bio_emps = {
                    (b.biotime_id.id, str(b.employee_id)): b
                    for b in employee_env.search([('biotime_id', '=', rec.id)])
                }
                to_create = []
                for employee in data['data']:
                    emp_code = employee.get('emp_code')
                    emp_name = employee.get('first_name')
                    emp_id = employee.get('id')
                    hr_emp_id = hr_emps.get(emp_code, False)
                    bio_emp = bio_emps.get((rec.id, str(emp_id)))

                    if not bio_emp:
                        to_create.append({
                            'name': emp_name,
                            'employee_id': emp_id,
                            'emp_code': emp_code,
                            'biotime_id': rec.id,
                            'odoo_employee_id': hr_emp_id,
                        })
                    else:
                        bio_emp.write({
                            'name': emp_name,
                            'emp_code': emp_code,
                            'odoo_employee_id': hr_emp_id,
                        })
                if to_create:
                    employee_env.create(to_create)

            if data.get('next'):
                next_page = data.get('next').split('page=')[1]
                self.action_get_all_employees(page=next_page)

    # ── Pull Raw Transactions (Optimized) ──
    def action_pull_raw_transactions(self, from_date=False, to_date=False,
                                     terminals=None, emp_code=None):
        """Fetch punches from every terminal and store ALL of them.

        Every punch is kept in `biotime.transaction` (deduplicated by the
        BioTime transaction id) — picking the shift boundaries is the job of
        `action_transfer_transition`, so a punch can never be lost here.
        `from_date`/`to_date` must be in the *server's* timezone (`self.tz`).
        `terminals` (recordset) limits the pull to specific devices and
        `emp_code` limits it to a single employee.
        """
        for rec in self:
            token = rec.generate_access_token()
            if terminals is None:
                terminals = self.env['biotime.terminal'].sudo().search(
                    [('biotime_id', '=', rec.id)])
            if not terminals:
                _logger.warning("No terminals found for BioTime server: %s", rec.name)
                continue

            all_emp_codes = set()
            all_raw = []
            failed_terminals = []

            for terminal in terminals:
                if from_date and to_date:
                    start_time = from_date.strftime('%Y-%m-%d %H:%M:%S')
                    end_time = to_date.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    start_time = ""
                    end_time = None

                response = get_transactions(
                    rec.server_url, token, start_time,
                    device_sn=terminal.terminal_sn, end_time=end_time,
                    emp_code=emp_code)
                if response.status_code != 200:
                    _logger.error("Failed to fetch from %s: %s",
                                  terminal.name, response.text)
                    failed_terminals.append(terminal.name or terminal.terminal_sn)
                    continue

                payload = response.json()
                transactions = payload.get('data', [])

                while True:
                    for t in transactions:
                        emp_code = t.get('emp_code')
                        if emp_code:
                            all_emp_codes.add(emp_code)
                        all_raw.append((t, terminal))

                    next_url = payload.get("next")
                    if not next_url:
                        break
                    response = get_next_page(next_url, token)
                    if response.status_code != 200:
                        failed_terminals.append(
                            "%s (page break)" % (terminal.name or terminal.terminal_sn))
                        break
                    payload = response.json()
                    transactions = payload.get('data', [])

            if failed_terminals:
                # loud, not just a log line: the punches of these devices were
                # NOT imported this run — the overlap window will retry them
                rec.message_post(body=_(
                    "BioTime pull: could not reach device(s) %s — their punches "
                    "were not imported this run. They will be retried on the "
                    "next pull (re-pull window: %s day(s)).")
                    % (", ".join(failed_terminals), rec.pull_overlap_days))

            rec.last_pull_date = fields.Datetime.now()
            if not all_raw:
                continue

            hr_emp_map = {}
            if all_emp_codes:
                for emp in self.env['hr.employee'].sudo().search(
                        [('zk_emp_code', 'in', list(all_emp_codes))]):
                    hr_emp_map[emp.zk_emp_code] = emp.id

            existing_tx = set()
            existing_records = self.env['biotime.transaction'].sudo().search(
                [('server_id', '=', rec.id)])
            for tx in existing_records:
                existing_tx.add(tx.transaction_id)

            # unmatched logs must be deduplicated too, otherwise every pull
            # (incl. the nightly cron) re-creates the same log lines
            existing_log_tx = {
                log.transaction_id
                for log in self.env['biotime.transaction.log'].sudo().search(
                    [('server_id', '=', rec.id)])
            }

            log_to_create = []
            tx_to_create = []

            for t, terminal in all_raw:
                emp_code = t.get('emp_code')
                punch_time_str = t.get('punch_time')
                if not emp_code or not punch_time_str:
                    continue

                punch_time_utc = datetime.strptime(
                    rec.convert_to_utc(punch_time_str, rec.tz),
                    '%Y-%m-%d %H:%M:%S')

                hr_emp_id = hr_emp_map.get(emp_code)
                if not hr_emp_id:
                    if str(t.get('id')) in existing_log_tx:
                        continue
                    existing_log_tx.add(str(t.get('id')))
                    log_to_create.append({
                        'transaction_id': t.get('id'),
                        'emp_code': emp_code,
                        'emp_name': t.get('emp_name'),
                        'department': t.get('department_name'),
                        'punch_time': punch_time_utc,
                        'punch_state': t.get('punch_state'),
                        'punch_state_display': t.get('punch_state_display'),
                        'device_id': terminal.id,
                        'server_id': rec.id,
                        'note': 'No matching employee found in Odoo',
                    })
                    continue

                # store EVERY punch, once
                if t.get('id') in existing_tx:
                    continue
                existing_tx.add(t.get('id'))
                tx_to_create.append({
                    'transaction_id': t.get('id'),
                    'employee_id': hr_emp_id,
                    'department': t.get('department_name'),
                    'punch_time': punch_time_utc,
                    'punch_state': t.get('punch_state'),
                    'punch_state_display': t.get('punch_state_display'),
                    'device_id': terminal.id,
                    'server_id': rec.id,
                })

            if log_to_create:
                self.env['biotime.transaction.log'].sudo().create(log_to_create)
            if tx_to_create:
                self.env['biotime.transaction'].sudo().create(tx_to_create)

            _logger.info("Pulled %s new transactions for server %s",
                         len(tx_to_create), rec.name)

    def _pull_window(self):
        """Default pull window in the server's local timezone: the last
        `pull_overlap_days` full days up to now. The overlap is deliberate —
        it re-catches punches that an offline device uploaded late."""
        self.ensure_one()
        tz = pytz.timezone(self.tz or "UTC")
        now = datetime.now(tz)
        days = max(self.pull_overlap_days or 1, 1)
        from_date = (now - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        return from_date, now

    def action_pull_raw_transactions_button(self):
        for rec in self:
            if rec.pull_from_date and rec.pull_to_date:
                # Datetime fields are stored in UTC; the BioTime API expects
                # times in the server's local timezone — convert, otherwise
                # the window is shifted and edge-of-day punches are lost
                tz = pytz.timezone(rec.tz or "UTC")
                from_date = pytz.utc.localize(
                    rec.pull_from_date).astimezone(tz).replace(tzinfo=None)
                to_date = pytz.utc.localize(
                    rec.pull_to_date).astimezone(tz).replace(tzinfo=None)
            else:
                from_date, to_date = rec._pull_window()
            rec.action_pull_raw_transactions(
                from_date=from_date, to_date=to_date)

    # ── Cron ──
    def cron_pull_yesterday_transactions(self):
        """Nightly cron (03:00): enqueue one queue_job per BioTime server."""
        for rec in self.search([]):
            rec.with_delay(
                description=_("BioTime: pull yesterday transactions (%s)") % rec.name,
                identity_key="biotime_pull_yesterday_%s" % rec.id,
            )._job_pull_yesterday_transactions()

    def _job_pull_yesterday_transactions(self):
        self.ensure_one()
        from_date, to_date = self._pull_window()
        try:
            self.action_pull_raw_transactions(
                from_date=from_date, to_date=to_date)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exc:
            raise RetryableJobError(
                "BioTime server unreachable, job will retry: %s" % exc) from exc
        if self.auto_transfer:
            # transfer the same window so the nightly cron produces finished
            # hr.attendance records without any manual click
            self.action_transfer_transition(
                from_date=from_date.astimezone(pytz.utc).replace(tzinfo=None),
                to_date=to_date.astimezone(pytz.utc).replace(tzinfo=None),
                raise_if_empty=False)
        return True

    # ── Reverse Sync (Odoo → BioTime) ──
    def push_employee_to_biotime(self, emp_code, first_name,
                                 department_id=1, area_ids=None):
        """Create an employee on the BioTime server. Returns the BioTime
        employee id. `department_id`/`area_ids` are BioTime internal ids
        (both default to 1 = the built-in Department/Area)."""
        self.ensure_one()
        url = "%s/personnel/api/employees/" % self.server_url
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Token %s' % self.generate_access_token(),
        }
        payload = {
            'emp_code': str(emp_code),
            'first_name': first_name or str(emp_code),
            'department': department_id or 1,
            'area': area_ids or [1],
        }
        response = requests.post(
            url, headers=headers, data=json.dumps(payload),
            timeout=REQUEST_TIMEOUT)
        if response.status_code not in (200, 201):
            raise UserError(_(
                "BioTime refused to create employee %(code)s:\n%(err)s",
                code=emp_code, err=response.text))
        return response.json().get('id')

    # ── Transfer to Attendance ──
    def action_transfer_transition(self, from_date=None, to_date=None,
                                   raise_if_empty=True):
        """Build/refresh hr.attendance from the raw punches.

        Punches are grouped into *shifts*: consecutive punches of an employee
        belong to the same shift while they are within `max_shift_hours` of
        the shift's first punch — so a night shift (22:00 → 06:00) stays one
        attendance instead of being split at midnight, and an employee who
        works two separate shifts on the same day gets TWO attendance records
        (the break in between is not counted as worked time).

        Existing attendances are UPDATED, not skipped: when a checkout is
        uploaded late by an offline device, the next transfer completes the
        open attendance instead of losing the punch.
        """
        for rec in self:
            domain = [('server_id', '=', rec.id), ('employee_id', '!=', False)]
            if from_date:
                domain.append(('punch_time', '>=', from_date))
            if to_date:
                domain.append(('punch_time', '<', to_date + timedelta(days=1)))

            transactions = self.env['biotime.transaction'].sudo().search(
                domain, order='punch_time')
            if not transactions:
                if raise_if_empty:
                    raise UserError(_("No transactions found to transfer."))
                continue

            max_gap = timedelta(hours=max(rec.max_shift_hours or 14, 1))
            Attendance = self.env['hr.attendance'].with_context(
                biotime_import=True).sudo()

            by_emp = defaultdict(list)
            for t in transactions:
                by_emp[t.employee_id.id].append(t)

            created_vals = []
            processed = self.env['biotime.transaction'].sudo().browse()
            updated = 0

            for emp_id, punches in by_emp.items():
                punches.sort(key=lambda p: p.punch_time)

                # split into shifts: a punch starts a new shift when it is
                # more than max_gap after the first punch of the current one
                shifts = []
                current = [punches[0]]
                for p in punches[1:]:
                    if p.punch_time - current[0].punch_time <= max_gap:
                        current.append(p)
                    else:
                        shifts.append(current)
                        current = [p]
                shifts.append(current)

                for shift in shifts:
                    check_in = shift[0].punch_time
                    check_out = shift[-1].punch_time if len(shift) > 1 else False

                    # an existing attendance belongs to this shift when its
                    # check_in obeys the same grouping rule as the punches:
                    # within max_gap of the shift's first punch
                    existing = Attendance.search([
                        ('employee_id', '=', emp_id),
                        ('check_in', '>=', check_in - max_gap),
                        ('check_in', '<=', check_out or check_in),
                    ], order='check_in desc', limit=1)

                    if not existing:
                        created_vals.append({
                            'employee_id': emp_id,
                            'check_in': check_in,
                            'check_out': check_out or False,
                        })
                    else:
                        vals = {}
                        if check_in < existing.check_in:
                            vals['check_in'] = check_in
                        new_in = vals.get('check_in', existing.check_in)
                        if check_out and check_out > new_in and (
                                not existing.check_out
                                or check_out > existing.check_out):
                            vals['check_out'] = check_out
                        if vals:
                            existing.write(vals)
                            updated += 1
                    processed |= self.env['biotime.transaction'].sudo().browse(
                        [p.id for p in shift])

            if created_vals:
                Attendance.create(created_vals)
            if processed:
                processed.write({'is_transferred': True})

            rec.last_transfer_date = fields.Datetime.now()
            _logger.info(
                "BioTime transfer for server %s: %s attendance(s) created, "
                "%s updated", rec.name, len(created_vals), updated)
