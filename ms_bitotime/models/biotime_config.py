# -*- coding: utf-8 -*-
import logging
import requests, json
from datetime import datetime, timedelta
import pytz

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get

_logger = logging.getLogger(__name__)

from .utils import *
from . import utils
from odoo.exceptions import UserError

class BioTime(models.Model):
    _name = 'biotime.config'
    _description = "BioTime Configuration"
    _inherit = ['mail.thread']
    # ==============================
    # Fields
    # ==============================
    name = fields.Char(string="Name", default="Server")
    # Store host (without port or protocol)
    server_host = fields.Char(
        string="Server Host",
        default="10.10.10.10",
        help="Just the IP address or domain, e.g. 10.10.10.10"
    )

    # Store port separately as an integer
    port = fields.Integer(
        string="Port",
        default=6070,
        help="Port number the BioTime server listens on."
    )
    username = fields.Char(string="Username", default="admin")
    password = fields.Char(string="Password", default="Admin")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company.id)

    tz = fields.Selection(
        _tz_get, string='Timezone', required=True,
        default=lambda self: self._context.get('tz') or self.env.user.tz or self.env.ref('base.user_admin').tz or 'UTC',
        help="This field is used in order to define in which timezone the resources will work."
    )

    pull_from_date = fields.Datetime('Pull From Date')
    pull_to_date = fields.Datetime('Pull To Date')

    terminal_count = fields.Integer(string="Devices", compute="_compute_terminal_count")
    emp_count = fields.Integer(string="Employee", compute="_compute_emp_count")
    transaction_count = fields.Integer(
        string="Transactions",
        compute="_compute_transaction_count"
    )
    server_url = fields.Char(
        string="Server URL",
        compute="_compute_server_url",
        store=False,
        help="Full URL built from host and port."
    )
    # ==============================
    # Utils
    # ==============================
    def convert_to_utc(self, date, timezone):
        """Convert local time string to UTC time string"""
        date_format = '%Y-%m-%d %H:%M:%S'
        local_dt = datetime.strptime(date, date_format)
        local_tz = pytz.timezone(timezone)
        local_dt = local_tz.localize(local_dt)
        utc_dt = local_dt.astimezone(pytz.utc)
        str_time = str(utc_dt)
        if '+' in str_time:
            str_time = str_time.split('+')[0]
        return str_time

    def generate_access_token(self):
        """Get Access Token from BioTime"""
        for rec in self:
            url = "%s/api-token-auth/" % rec.server_url
            payload = json.dumps({
                "username": rec.username,
                "password": rec.password
            })
            headers = {'Content-Type': 'application/json'}

            response = requests.post(url, headers=headers, data=payload)

            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                if not token:
                    raise ValidationError(_("No token returned from BioTime server."))
                return token
            else:
                raise ValidationError(_("Failed to authenticate with BioTime: %s") % response.text)




    @api.depends('server_host', 'port')
    def _compute_server_url(self):
        for rec in self:
            rec.server_url = f"http://{rec.server_host}:{rec.port}"
    # ==============================
    # Devices
    # ==============================
    def action_get_all_terminals(self):
        """Import BioTime terminals"""
        for rec in self:
            terminal_env = self.env['biotime.terminal'].sudo()
            url = "%s/iclock/api/terminals/" % rec.server_url

            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Token %s' % rec.generate_access_token()
            }

            response = requests.get(url, headers=headers)
            data = response.json()

            if data.get('data'):
                for terminal in data['data']:
                    check = terminal_env.search([
                        ('biotime_id', '=', rec.id),
                        ('terminal_sn', '=', terminal.get('sn')),
                    ])
                    if not check:
                        terminal_env.create({
                            'name': terminal.get('terminal_name') or 'New Device',
                            'terminal_id': terminal.get('id'),
                            'terminal_sn': terminal.get('sn'),
                            'ip_address': terminal.get('ip_address'),
                            'alias': terminal.get('alias'),
                            'terminal_tz': terminal.get('terminal_tz'),
                            'biotime_id': rec.id
                        })

    def _compute_terminal_count(self):
        for rec in self:
            rec.terminal_count = self.env['biotime.terminal'].search_count([('biotime_id', '=', rec.id)])

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

    log_count = fields.Integer(
        string="Unmatched Logs",
        compute="_compute_log_count"
    )

    def _compute_log_count(self):
        for rec in self:
            rec.log_count = self.env['biotime.transaction.log'].sudo().search_count([
                ('server_id', '=', rec.id)
            ])

    def action_open_logs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Unmatched Transactions',
            'res_model': 'biotime.transaction.log',
            'view_mode': 'list',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id},
        }
    # ==============================
    # Employees
    # ==============================
    def action_get_all_employees(self, page=1):
        """Import employees and link to hr.employee"""
        for rec in self:
            employee_env = self.env['biotime.employee'].sudo()
            url = "%s/personnel/api/employees/?page=%s" % (rec.server_url, page)

            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Token %s' % rec.generate_access_token()
            }

            response = requests.get(url, headers=headers)
            data = response.json()

            if data.get('data'):
                for employee in data['data']:
                    emp_code = employee.get('emp_code')
                    emp_name = employee.get('first_name')
                    emp_id = employee.get('id')

                    hr_emp = self.env['hr.employee'].sudo().search([
                        ('zk_emp_code', '=', emp_code)
                    ], limit=1)

                    bio_emp = employee_env.search([
                        ('biotime_id', '=', rec.id),
                        ('employee_id', '=', emp_id),
                    ], limit=1)

                    if not bio_emp:
                        employee_env.create({
                            'name': emp_name,
                            'employee_id': emp_id,
                            'emp_code': emp_code,
                            'biotime_id': rec.id,
                            'odoo_employee_id': hr_emp.id if hr_emp else False,
                        })
                    else:
                        bio_emp.write({
                            'name': emp_name,
                            'emp_code': emp_code,
                            'odoo_employee_id': hr_emp.id if hr_emp else False,
                        })

            # ✅ next pages
            if data.get('next'):
                next_page = data.get('next').split('page=')[1]
                self.action_get_all_employees(page=next_page)

    def _compute_emp_count(self):
        for rec in self:
            rec.emp_count = self.env['biotime.employee'].search_count([('biotime_id', '=', rec.id)])

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

    # ==============================
    #         Pull raw transactions
    # ==============================
    def action_pull_raw_transactions(self, from_date=False, to_date=False):
        """
        Pull raw transactions from BioTime server and store only
        the first Check In and last Check Out per employee per day.
        """

        for rec in self:
            # 1️⃣ Get API token
            token = rec.generate_access_token()

            # 2️⃣ Get all terminals for this BioTime server
            terminals = self.env['biotime.terminal'].sudo().search([('biotime_id', '=', rec.id)])
            if not terminals:
                _logger.warning("⚠️ No terminals found for BioTime server: %s", rec.name)
                continue

            for terminal in terminals:
                base_url = f"{rec.server_url}"
                if from_date and to_date:
                    start_time = from_date.strftime('%Y-%m-%d %H:%M:%S')
                    end_time = to_date.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    start_time, end_time = "", ""

                _logger.info("🔍 Fetching transactions for terminal %s (%s)",
                             terminal.name, terminal.terminal_sn or "NO_SN")

                # 📌 First page
                response = utils.get_transactions(
                    base_url,
                    token,
                    start_time,
                    device_sn=terminal.terminal_sn
                )

                if response.status_code != 200:
                    _logger.error("❌ Failed to fetch transactions from %s: %s",
                                  terminal.name, response.text)
                    continue

                payload = response.json()
                transactions = payload.get('data', [])
                total_count = 0

                # 📝 Temporary store punches {emp_code: {day: [records]}}
                emp_punches = {}

                while True:
                    for t in transactions:
                        emp_code = t.get('emp_code')
                        punch_time_str = t.get('punch_time')
                        if not emp_code or not punch_time_str:
                            continue

                        # ➡ convert time from device timezone to UTC
                        punch_time_utc = datetime.strptime(
                            rec.convert_to_utc(punch_time_str, rec.tz),
                            '%Y-%m-%d %H:%M:%S'
                        )

                        # match HR employee if possible
                        hr_emp = self.env['hr.employee'].sudo().search([
                            ('zk_emp_code', '=', emp_code)
                        ], limit=1)

                        if not hr_emp:
                            # 👇 لو الموظف مش موجود → نحفظ في Log بدل Transactions
                            self.env['biotime.transaction.log'].sudo().create({
                                'transaction_id': t.get('id'),
                                'emp_code': emp_code,
                                'emp_name': t.get('emp_name'),
                                'department': t.get('department_name'),
                                'punch_time': punch_time_utc,
                                'punch_state': t.get('punch_state'),
                                'punch_state_display': t.get('punch_state_display'),
                                'device_id': terminal.id,
                                'server_id': rec.id,
                                'note': '⚠️ No matching employee found in Odoo',
                            })
                            continue
                        day_key = punch_time_utc.date()
                        if emp_code not in emp_punches:
                            emp_punches[emp_code] = {}
                        if day_key not in emp_punches[emp_code]:
                            emp_punches[emp_code][day_key] = []
                        emp_punches[emp_code][day_key].append({
                            'transaction_id': t.get('id'),
                            'employee_id': hr_emp.id if hr_emp else False,
                            'department': t.get('department_name'),
                            'punch_time': punch_time_utc,
                            'punch_state': t.get('punch_state'),
                            'punch_state_display': t.get('punch_state_display'),
                            'device_id': terminal.id,
                            'server_id': rec.id,
                        })

                    # 📌 Pagination
                    next_url = payload.get("next")
                    if not next_url:
                        break

                    response = utils.get_next_page(next_url, token)
                    if response.status_code != 200:
                        break

                    payload = response.json()
                    transactions = payload.get('data', [])

                # ✅ After collecting → filter first in + last out
                for emp_code, days in emp_punches.items():
                    for day, punches in days.items():
                        if not punches:
                            continue

                        punches_sorted = sorted(punches, key=lambda x: x['punch_time'])
                        first_punch = punches_sorted[0]
                        last_punch = punches_sorted[-1] if len(punches_sorted) > 1 else None

                        # ➕ Create First Check In
                        exists = self.env['biotime.transaction'].sudo().search_count([
                            ('transaction_id', '=', first_punch['transaction_id']),
                            ('server_id', '=', rec.id)
                        ])
                        if not exists:
                            self.env['biotime.transaction'].sudo().create(first_punch)
                            total_count += 1

                        # ➕ Create Last Check Out (different from first)
                        if last_punch and last_punch['transaction_id'] != first_punch['transaction_id']:
                            exists = self.env['biotime.transaction'].sudo().search_count([
                                ('transaction_id', '=', last_punch['transaction_id']),
                                ('server_id', '=', rec.id)
                            ])
                            if not exists:
                                self.env['biotime.transaction'].sudo().create(last_punch)
                                total_count += 1

                _logger.info("✅ Pulled %s new transactions from terminal %s (%s)",
                             total_count, terminal.name, terminal.terminal_sn or "NO_SN")

    def action_pull_raw_transactions_button(self):
        # لو المستخدم اختار من → إلى
        if self.pull_from_date and self.pull_to_date:
            self.action_pull_raw_transactions(
                from_date=self.pull_from_date,
                to_date=self.pull_to_date
            )
        else:
            # 🕛 الكرون: نسحب اليوم السابق كامل بالـ timezone بتاع السيرفر
            tz = pytz.timezone(self.tz or "UTC")  # خدها من config أو خليها افتراضي UTC
            now = datetime.now(tz)

            from_date = (now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            to_date = (now - timedelta(days=1)).replace(
                hour=23, minute=59, second=59, microsecond=0
            )

            _logger.info("📅 Pulling for %s: %s → %s", self.name, from_date, to_date)

            self.action_pull_raw_transactions(from_date=from_date, to_date=to_date)
    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = self.env['biotime.transaction'].sudo().search_count([
                ('server_id', '=', rec.id)
            ])

    def action_view_transactions(self):
        """Open biotime.transaction records related to this server"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Raw Transactions'),
            'view_mode': 'list',
            'res_model': 'biotime.transaction',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id}
        }

    # ==============================
    #   Cron: Pull yesterday's data
    # ==============================
    def cron_pull_yesterday_transactions(self):
        tz = pytz.timezone("Africa/Tripoli")  # أو خليه rec.tz لو عندك timezone في config
        now = datetime.now(tz)

        from_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        to_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)

        for rec in self.search([]):
            rec.action_pull_raw_transactions(from_date=from_date, to_date=to_date)

  # ==============================
    # Transfer Attendance
    # ==============================
    def action_transfer_transition(self, from_date=None, to_date=None):
        from datetime import timedelta

        for rec in self:
            # 1️⃣ Build domain
            domain = [('server_id', '=', rec.id)]
            if from_date:
                domain.append(('punch_time', '>=', from_date))
            if to_date:
                domain.append(('punch_time', '<', to_date + timedelta(days=1)))

            transactions = self.env['biotime.transaction'].sudo().search(domain)
            if not transactions:
                raise UserError(_("No transactions found to transfer."))

            # 2️⃣ Group by employee and day
            grouped = {}
            for t in transactions:
                if not t.employee_id:
                    continue
                day_key = t.punch_time.date()
                emp_id = t.employee_id.id
                grouped.setdefault(emp_id, {})
                grouped[emp_id].setdefault(day_key, []).append(t)

            created = 0
            for emp_id, days in grouped.items():
                for day, punches in days.items():
                    punches_sorted = sorted(punches, key=lambda x: x.punch_time)

                    check_in = punches_sorted[0].punch_time if punches_sorted else False
                    check_out = punches_sorted[-1].punch_time if len(punches_sorted) > 1 else False

                    # 3️⃣ Skip if attendance already exists for this day
                    exists = self.env['hr.attendance'].sudo().search_count([
                        ('employee_id', '=', emp_id),
                        ('check_in', '>=', datetime.combine(day, datetime.min.time())),
                        ('check_in', '<', datetime.combine(day, datetime.max.time()))
                    ])
                    if exists:
                        continue

                    # 4️⃣ Create new attendance
                    self.env['hr.attendance'].with_context(biotime_import=True).sudo().create({
                        'employee_id': emp_id,
                        'check_in': check_in or False,
                        'check_out': check_out or False,
                        'missing_check': 'missing' if not (check_in and check_out) else 'ok',
                    })
                    created += 1

            _logger.info(
                "✅ %s hr.attendance records created from BioTime transactions "
                "for server %s within range %s – %s",
                created, rec.name, from_date, to_date
            )
