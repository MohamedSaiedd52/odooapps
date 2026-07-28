# -*- coding: utf-8 -*-
from collections import Counter, OrderedDict
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError
from odoo.http import request


class AccessRightsStudio(models.AbstractModel):
    """Data provider for the Dashboard OWL screen + the user simulation flow.
    (Every other screen of the app is a regular Odoo view.)"""
    _name = 'access.rights.studio'
    _description = 'Access Rights Studio'

    def _check_manager(self):
        if not self.env.user.has_group('access_rights_management.group_access_rights_manager'):
            raise AccessError(_("Only access rights managers can use these screens."))

    # ------------------------------------------------------------------
    # Dashboard (grouped by the real company departments — hr.department)
    # ------------------------------------------------------------------
    DENIED_STATUSES = ('failed', 'blocked_disabled', 'blocked_ip',
                       'blocked_hours', 'blocked_device', 'kicked')

    @api.model
    def _dashboard_profile_data(self, profile):
        return {
            'id': profile.id,
            'name': profile.name,
            'user_count': profile.user_count,
            'total_rules': profile.total_rules,
            'readonly': profile.readonly,
            'is_global': profile.apply_to_all_users,
        }

    @api.model
    def _recent_denied_logins(self, limit=8):
        Log = self.env['access.rights.login.log'].sudo()
        status_labels = dict(Log._fields['status']._description_selection(self.env))
        return [{
            'id': log.id,
            'login': log.user_id.name or log.login or '?',
            'status': status_labels.get(log.status, log.status),
            'status_key': log.status,
            'ip': log.ip_address or '',
            'device': log.device_id.display_label or '',
            'date': str(log.create_date)[:16],
        } for log in Log.search([('status', 'in', self.DENIED_STATUSES)], limit=limit)]

    @api.model
    def _login_series(self, days=14):
        """Per-local-day success/denied counts for the activity chart."""
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        today = datetime.now(tz).date()
        start_local = today - timedelta(days=days - 1)
        start_utc = tz.localize(
            datetime.combine(start_local, datetime.min.time())
        ).astimezone(pytz.utc).replace(tzinfo=None)

        logs = self.env['access.rights.login.log'].sudo().search_read(
            [('create_date', '>=', start_utc),
             ('status', 'not in', ('simulate_start', 'simulate_stop'))],
            ['create_date', 'status'])

        buckets = OrderedDict(
            ((start_local + timedelta(days=i)).isoformat(), {'success': 0, 'denied': 0})
            for i in range(days))
        for log in logs:
            local_day = pytz.utc.localize(log['create_date']).astimezone(tz).date().isoformat()
            if local_day not in buckets:
                continue
            key = 'denied' if log['status'] in self.DENIED_STATUSES else 'success'
            buckets[local_day][key] += 1
        return [{'date': day, 'label': day[8:10] + '/' + day[5:7],
                 'success': v['success'], 'denied': v['denied']}
                for day, v in buckets.items()]

    @api.model
    def _denied_reasons(self, days=30):
        """Denied logins of the last `days` days, broken down by reason."""
        Log = self.env['access.rights.login.log'].sudo()
        status_labels = dict(Log._fields['status']._description_selection(self.env))
        since = fields.Datetime.now() - timedelta(days=days)
        counts = Counter(
            log['status'] for log in Log.search_read(
                [('status', 'in', self.DENIED_STATUSES),
                 ('create_date', '>=', since)], ['status']))
        return [{'key': status, 'label': status_labels.get(status, status),
                 'count': count}
                for status, count in counts.most_common()]

    @api.model
    def _security_hygiene(self):
        """Ready-to-act security risks computed from the current user base."""
        Users = self.env['res.users'].sudo()
        internal = Users.search([('share', '=', False), ('active', '=', True)])
        now = fields.Datetime.now()
        stale_cut = now - timedelta(days=90)
        never_cut = now - timedelta(days=30)
        Profile = self.env['access.rights.profile'].sudo()
        has_global = bool(Profile.search_count([('apply_to_all_users', '=', True)]))
        admin_group = self.env.ref('base.group_system')

        stale, never, no_profile, twofa = [], [], [], []
        totp_available = 'totp_enabled' in Users._fields
        for user in internal:
            info = {'id': user.id, 'name': user.name, 'login': user.login,
                    'login_date': str(user.login_date)[:10] if user.login_date else ''}
            if user.login_date and user.login_date < stale_cut:
                stale.append(info)
            elif not user.login_date and user.create_date and user.create_date < never_cut:
                never.append(info)
            if not has_global and not user.access_profile_ids:
                no_profile.append(info)
            if (totp_available and Profile._requires_2fa(user.id)
                    and not user.totp_enabled):
                twofa.append(info)

        admins = internal.filtered(lambda u: admin_group in u.groups_id)
        return {
            'admin_count': len(admins),
            'admins': [{'id': u.id, 'name': u.name, 'login': u.login} for u in admins],
            'internal_users': len(internal),
            'stale': stale,
            'never_logged_in': never,
            'no_profile': no_profile,
            'twofa_missing': twofa,
            'large_sensitive_exports_7d': self.env['access.rights.export.log'].sudo().search_count([
                ('is_sensitive', '=', True), ('is_large', '=', True),
                ('create_date', '>=', now - timedelta(days=7))]),
            'blocked_devices': self.env['access.rights.device'].sudo().search_count(
                [('state', '=', 'blocked')]),
            'unusual_logins': self.env['access.rights.anomaly'].sudo().search_count(
                [('state', '=', 'new')]),
            'admin_grants_30d': self.env['access.rights.change'].sudo().search_count([
                ('is_admin_change', '=', True), ('action', '=', 'granted'),
                ('create_date', '>=', now - timedelta(days=30))]),
        }

    @api.model
    def get_dashboard_data(self):
        self._check_manager()
        Profile = self.env['access.rights.profile']
        profiles = Profile.search([])
        departments = profiles.mapped('department_id').sorted(
            lambda d: (d.name or '').lower())
        internal_users = self.env['res.users'].search_count([('share', '=', False)])
        covered_users = profiles.user_ids
        if any(profiles.mapped('apply_to_all_users')):
            covered = internal_users
        else:
            covered = len(covered_users)
        Device = self.env['access.rights.device'].sudo()
        return {
            'kpis': {
                'departments': len(departments),
                'roles': len(profiles),
                'covered_users': covered,
                'internal_users': internal_users,
                'global_profiles': len(profiles.filtered('apply_to_all_users')),
                'readonly_roles': len(profiles.filtered('readonly')),
                'rules': sum(profiles.mapped('total_rules')),
                'blocked_logins_7d': self.env['access.rights.login.log'].sudo().search_count([
                    ('status', 'in', self.DENIED_STATUSES),
                    ('create_date', '>=', fields.Datetime.now() - timedelta(days=7)),
                ]),
                'devices': Device.search_count([]),
                'blocked_devices': Device.search_count([('state', '=', 'blocked')]),
                'sensitive_fields': self.env['access.rights.sensitive.field'].sudo().search_count([]),
                'unusual_logins': self.env['access.rights.anomaly'].sudo().search_count(
                    [('state', '=', 'new')]),
            },
            'coverage': {
                'covered': covered,
                'uncovered': max(internal_users - covered, 0),
            },
            'login_series': self._login_series(),
            'denied_reasons': self._denied_reasons(),
            'departments': [{
                'id': department.id,
                'name': department.name,
                'description': department.complete_name if department.parent_id else '',
                'icon': department.arm_icon or 'fa-building',
                'color': department.color or 0,
                'user_count': department.arm_user_count,
                'rule_count': department.arm_rule_count,
                'roles': [self._dashboard_profile_data(p)
                          for p in department.access_profile_ids],
            } for department in departments],
            'unassigned': [self._dashboard_profile_data(p)
                           for p in profiles.filtered(lambda p: not p.department_id)],
            'recent_denied': self._recent_denied_logins(),
            'hygiene': self._security_hygiene(),
        }

    # ------------------------------------------------------------------
    # Simulate a user (see the UI exactly as they see it)
    # ------------------------------------------------------------------
    @api.model
    def simulate_user(self, user_id):
        """Switch the current HTTP session to `user_id` without a password.
        Restricted to Settings administrators; both ends are written to the
        login audit. The admin returns with `simulate_stop` (banner button)."""
        self._check_manager()
        if not self.env.user.has_group('base.group_system'):
            return {'error': _("Only administrators (Settings access) can simulate users.")}
        if not request:
            return {'error': _("Simulation needs an interactive web session.")}
        if request.session.get('arm_simulate_origin_uid'):
            return {'error': _("You are already simulating a user. Go back to your own account first.")}
        target = self.env['res.users'].sudo().with_context(active_test=False).browse(user_id)
        if not target.exists() or target.id == SUPERUSER_ID:
            return {'error': _("User not found.")}
        if target.id == self.env.uid:
            return {'error': _("You cannot simulate yourself.")}
        if not target.active:
            return {'error': _("Cannot simulate an archived user.")}
        if target.share:
            return {'error': _("Cannot simulate a portal/public user.")}

        origin = self.env.user
        ip = request.httprequest.remote_addr
        self.env['access.rights.login.log']._log(
            target.login, target.id, 'simulate_start', ip,
            note=_("Simulated by %s", origin.login))
        request.session['arm_simulate_origin_uid'] = origin.id
        request.session['arm_simulate_origin_login'] = origin.login
        # same switch the 2FA flow uses: finalize() re-keys uid, context and
        # session_token, and rotates the session id
        request.session.pre_login = target.login
        request.session.pre_uid = target.id
        request.session.finalize(request.env)
        request.update_env(user=request.session.uid)
        return {'ok': True, 'name': target.name}

    @api.model
    def simulate_stop(self):
        """Return a simulated session to the original administrator. No
        manager check: the current (simulated) user may have no rights at
        all — safety comes from the session, which only ever stores the
        admin who started the simulation."""
        if not request or not request.session.get('arm_simulate_origin_uid'):
            return {'error': _("This session is not simulating anyone.")}
        origin_uid = request.session.pop('arm_simulate_origin_uid')
        request.session.pop('arm_simulate_origin_login', None)
        target = self.env.user
        origin = self.env['res.users'].sudo().browse(origin_uid)
        self.env['access.rights.login.log']._log(
            target.login, target.id, 'simulate_stop',
            request.httprequest.remote_addr,
            note=_("Simulation ended by %s", origin.login or '?'))
        if not origin.exists() or not origin.active:
            request.session.logout(keep_db=True)
            return {'ok': True, 'logged_out': True}
        request.session.pre_login = origin.login
        request.session.pre_uid = origin.id
        request.session.finalize(request.env)
        request.update_env(user=request.session.uid)
        return {'ok': True, 'name': origin.name}
