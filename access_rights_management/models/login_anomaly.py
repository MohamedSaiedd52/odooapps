# -*- coding: utf-8 -*-
"""Unusual-login detection.

Every successful login is scored against the user's own history: a device or
IP never seen before, an hour the user never works at, a burst of failed
attempts, or two different networks within minutes. Anything suspicious
becomes an `access.rights.anomaly` record and (optionally) an immediate
notification to the access-rights managers.

Detection runs inside the login flow and must never raise or block a login.
"""
import logging
from datetime import timedelta

import pytz

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# A user needs some history before "never seen before" means anything.
MIN_HISTORY_LOGINS = 5
# Window and threshold for the failed-attempts burst.
FAILED_WINDOW_MINUTES = 30
FAILED_THRESHOLD = 5
# Window for the "two networks at once" check.
IMPOSSIBLE_TRAVEL_MINUTES = 10


class AccessRightsAnomaly(models.Model):
    _name = 'access.rights.anomaly'
    _description = 'Unusual Login'
    _order = 'id desc'
    _rec_name = 'display_name'

    user_id = fields.Many2one('res.users', string='User', required=True,
                              ondelete='cascade', index=True, readonly=True)
    log_id = fields.Many2one('access.rights.login.log', string='Login',
                             ondelete='set null', readonly=True)
    device_id = fields.Many2one('access.rights.device', string='Device',
                                ondelete='set null', readonly=True)
    kind = fields.Selection([
        ('new_device', 'New Device'),
        ('new_ip', 'New IP Address'),
        ('odd_hour', 'Unusual Hour'),
        ('failed_burst', 'Repeated Failed Attempts'),
        ('parallel_network', 'Two Networks At Once'),
    ], required=True, index=True, readonly=True)
    severity = fields.Selection([
        ('info', 'Info'), ('warning', 'Warning'), ('high', 'High'),
    ], required=True, default='warning', index=True, readonly=True)
    detail = fields.Char(readonly=True)
    ip_address = fields.Char(string='IP Address', readonly=True)
    occurred_at = fields.Datetime(readonly=True, index=True,
                                  default=fields.Datetime.now)
    state = fields.Selection([
        ('new', 'New'),
        ('reviewed', 'Reviewed — OK'),
        ('acted', 'Action Taken'),
    ], default='new', required=True, index=True, string='Status')
    reviewed_by = fields.Many2one('res.users', string='Reviewed By', readonly=True)
    review_note = fields.Char(string='Note')
    display_name = fields.Char(compute='_compute_display_name')

    @api.depends('user_id', 'kind')
    def _compute_display_name(self):
        labels = dict(self._fields['kind']._description_selection(self.env))
        for rec in self:
            rec.display_name = "%s — %s" % (rec.user_id.name or '?',
                                            labels.get(rec.kind, rec.kind))

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------
    @api.model
    def _enabled(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'access_rights_management.anomaly_detection', 'on')
        return str(param).strip().lower() not in ('0', 'off', 'false')

    @api.model
    def _notify_enabled(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'access_rights_management.anomaly_notify', 'on')
        return str(param).strip().lower() not in ('0', 'off', 'false')

    @api.model
    def _work_hours(self):
        """(from_hour, to_hour) considered normal, local time. Configurable
        with access_rights_management.work_hours = '7-19'."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'access_rights_management.work_hours', '7-19')
        try:
            start, end = str(param).split('-')
            return int(start), int(end)
        except (ValueError, AttributeError):
            return 7, 19

    @api.model
    def _scan_login(self, log, device):
        """Score one successful login. `log` is the audit line just written,
        `device` its device (may be empty). Never raises."""
        try:
            if not self._enabled() or not log or not log.user_id:
                return self.browse()
            Log = self.env['access.rights.login.log'].sudo()
            user = log.user_id
            history = Log.search_count([
                ('user_id', '=', user.id), ('status', '=', 'success'),
                ('id', '!=', log.id)])
            findings = []

            # 1. a device we have never seen for this user
            if device and device.login_count <= 1 and history >= MIN_HISTORY_LOGINS:
                findings.append(('new_device', 'warning', _(
                    "First login from this device (%s).",
                    device.display_label or log.ip_address or '?')))

            # 2. an IP never used by this user before
            if log.ip_address and history >= MIN_HISTORY_LOGINS:
                seen_ip = Log.search_count([
                    ('user_id', '=', user.id), ('status', '=', 'success'),
                    ('ip_address', '=', log.ip_address), ('id', '!=', log.id)])
                if not seen_ip:
                    findings.append(('new_ip', 'warning', _(
                        "First login from %s.", log.ip_address)))

            # 3. outside the normal working hours (user's own timezone)
            hour_from, hour_to = self._work_hours()
            tz = pytz.timezone(user.tz or self.env.user.tz or 'UTC')
            local = pytz.utc.localize(log.create_date).astimezone(tz)
            if not (hour_from <= local.hour < hour_to):
                findings.append(('odd_hour', 'warning', _(
                    "Logged in at %(time)s local time (normal hours are "
                    "%(start)s:00–%(end)s:00).",
                    time=local.strftime('%H:%M'),
                    start=hour_from, end=hour_to)))

            # 4. a burst of failed attempts just before this success
            since = log.create_date - timedelta(minutes=FAILED_WINDOW_MINUTES)
            failed = Log.search_count([
                ('login', '=', log.login), ('status', '=', 'failed'),
                ('create_date', '>=', since)])
            if failed >= FAILED_THRESHOLD:
                findings.append(('failed_burst', 'high', _(
                    "%(count)s failed attempts in the %(minutes)s minutes "
                    "before this login.", count=failed,
                    minutes=FAILED_WINDOW_MINUTES)))

            # 5. the same account active from two different networks at once
            if log.ip_address:
                since = log.create_date - timedelta(minutes=IMPOSSIBLE_TRAVEL_MINUTES)
                others = Log.search([
                    ('user_id', '=', user.id), ('status', '=', 'success'),
                    ('create_date', '>=', since), ('id', '!=', log.id),
                    ('ip_address', '!=', False),
                ])
                other_networks = {
                    ip.rsplit('.', 1)[0] for ip in others.mapped('ip_address')
                } - {log.ip_address.rsplit('.', 1)[0]}
                if other_networks:
                    findings.append(('parallel_network', 'high', _(
                        "Also active from %(nets)s within %(minutes)s minutes — "
                        "the account may be shared or stolen.",
                        nets=', '.join(sorted(other_networks)) + '.x',
                        minutes=IMPOSSIBLE_TRAVEL_MINUTES)))

            if not findings:
                return self.browse()

            records = self.sudo().create([{
                'user_id': user.id,
                'log_id': log.id,
                'device_id': device.id if device else False,
                'kind': kind,
                'severity': severity,
                'detail': detail,
                'ip_address': log.ip_address,
                'occurred_at': log.create_date,
            } for kind, severity, detail in findings])
            records._notify_managers()
            return records
        except Exception:
            _logger.exception("Unusual-login detection failed")
            return self.browse()

    def _notify_managers(self):
        """Post one summary notification to the access-rights managers.
        Best-effort — never raises."""
        try:
            if not self or not self._notify_enabled():
                return
            high = self.filtered(lambda a: a.severity == 'high')
            if not high:
                return  # only escalate the serious ones
            managers = self.env['res.users'].sudo().search([
                ('groups_id', 'in', self.env.ref(
                    'access_rights_management.group_access_rights_manager').id),
            ])
            partners = managers.partner_id - self.user_id.partner_id
            if not partners:
                return
            user = self[0].user_id
            body = _("⚠ Unusual login for %(user)s from %(ip)s:", user=user.name,
                     ip=self[0].ip_address or '?')
            body += '<ul>' + ''.join(
                '<li>%s</li>' % anomaly.detail for anomaly in high) + '</ul>'
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=partners.ids,
                subject=_("Unusual login: %s", user.name),
                body=body)
        except Exception:
            _logger.exception("Could not notify managers about an unusual login")

    # ------------------------------------------------------------------
    # manager actions
    # ------------------------------------------------------------------
    def action_mark_reviewed(self):
        self.write({'state': 'reviewed', 'reviewed_by': self.env.uid})

    def action_block_device(self):
        for anomaly in self:
            if anomaly.device_id and anomaly.device_id.state != 'blocked':
                anomaly.device_id.action_block()
        self.write({'state': 'acted', 'reviewed_by': self.env.uid})

    def action_end_sessions(self):
        for anomaly in self:
            self.env['access.rights.session.kick'].sudo().create({
                'user_id': anomaly.user_id.id,
                'reason': _("Unusual login reviewed by %s", self.env.user.login),
            })
        self.write({'state': 'acted', 'reviewed_by': self.env.uid})

    def action_open_user(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'res_id': self.user_id.id,
            'view_mode': 'form',
        }

    @api.autovacuum
    def _gc_anomalies(self):
        """Drop reviewed anomalies older than 180 days."""
        cutoff = fields.Datetime.now() - timedelta(days=180)
        old = self.sudo().search([
            ('occurred_at', '<', cutoff), ('state', '!=', 'new')])
        if old:
            old.unlink()
