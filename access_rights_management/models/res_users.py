# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    access_profile_ids = fields.Many2many(
        'access.rights.profile', 'access_rights_profile_user_rel', 'user_id', 'profile_id',
        string='Access Profiles')
    arm_device_count = fields.Integer(compute='_compute_arm_counts')
    arm_login_count = fields.Integer(compute='_compute_arm_counts')

    def _compute_arm_counts(self):
        Device = self.env['access.rights.device'].sudo()
        Log = self.env['access.rights.login.log'].sudo()
        for user in self:
            user.arm_device_count = Device.search_count([('user_id', '=', user.id)])
            user.arm_login_count = Log.search_count([('user_id', '=', user.id)])

    def write(self, vals):
        tracked = 'access_profile_ids' in vals or 'groups_id' in vals
        before = {}
        if tracked and not self.env.context.get('arm_skip_change_log'):
            for user in self:
                before[user.id] = (user.groups_id, user.access_profile_ids)
        res = super().write(vals)
        if tracked:
            self.sudo().access_profile_ids._check_readonly_admin()
            self.env.registry.clear_all_caches()
            Change = self.env['access.rights.change']
            for user in self:
                snapshot = before.get(user.id)
                if not snapshot:
                    continue
                old_groups, old_profiles = snapshot
                if 'groups_id' in vals:
                    Change._record_diff(user, 'group', old_groups, user.groups_id)
                if 'access_profile_ids' in vals:
                    Change._record_diff(user, 'profile', old_profiles,
                                        user.access_profile_ids)
        return res

    # ------------------------------------------------------------------
    # Manager actions (user form buttons)
    # ------------------------------------------------------------------
    def action_arm_simulate(self):
        """See the UI exactly as this user sees it (audited, no password)."""
        self.ensure_one()
        result = self.env['access.rights.studio'].simulate_user(self.id)
        if result.get('error'):
            raise UserError(result['error'])
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_arm_kick(self):
        """Terminate this user's open sessions on their next request."""
        self.ensure_one()
        if not self.env.user.has_group('access_rights_management.group_access_rights_manager'):
            raise UserError(_("Only access rights managers can end sessions."))
        self.env['access.rights.session.kick'].sudo().create({
            'user_id': self.id,
            'reason': _("Ended from the user form by %s", self.env.user.login),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _("Sessions ended"),
                'message': _("%s will be logged out on their next request.", self.name),
            },
        }

    def action_arm_view_devices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Devices — %s", self.name),
            'res_model': 'access.rights.device',
            'view_mode': 'list,form',
            'domain': [('user_id', '=', self.id)],
        }

    def action_arm_view_logins(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Login Audit — %s", self.name),
            'res_model': 'access.rights.login.log',
            'view_mode': 'list,pivot',
            'domain': [('user_id', '=', self.id)],
        }

    @classmethod
    def _arm_log_login(cls, login, uid, status, ip):
        """Audit one login attempt on its own cursor (the main transaction of
        a failed login is rolled back)."""
        try:
            with cls.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                if 'access.rights.login.log' in env and env.registry.ready:
                    env['access.rights.login.log']._log(login, uid, status, ip)
        except Exception:
            _logger.exception("Could not write login audit log")

    @classmethod
    def _login(cls, db, credential, user_agent_env):
        # 18.0: `credential` is a dict ({'type', 'login', 'password'|...}) and
        # the method returns an `auth_info` dict, not a bare uid.
        login = (credential or {}).get('login')
        ip = (user_agent_env or {}).get('REMOTE_ADDR')
        if not ip and request:
            ip = request.httprequest.remote_addr
        try:
            auth_info = super()._login(db, credential, user_agent_env=user_agent_env)
        except AccessDenied:
            cls._arm_log_login(login, None, 'failed', ip)
            raise
        uid = auth_info['uid']

        status = None
        try:
            with cls.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                if 'access.rights.profile' in env and env.registry.ready:
                    profile = env['access.rights.profile']
                    sec = profile._get_login_security(uid)
                    status = profile._check_login_security(sec, ip)
        except Exception:
            # never brick the login flow on an unexpected state
            _logger.exception("Access-rights login check failed; allowing login")
            status = None

        if status:
            cls._arm_log_login(login, uid, status, ip)
            _logger.info("Login blocked (%s) by access-rights profile for db:%s login:%s ip:%s",
                         status, db, login, ip)
            raise AccessDenied()

        # blocked device: deny the login regardless of credentials
        device_blocked = False
        try:
            with cls.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                if 'access.rights.device' in env and env.registry.ready:
                    user_agent = None
                    if request:
                        user_agent = request.httprequest.user_agent.string or None
                    device_blocked = env['access.rights.device']._check_blocked(
                        uid, ip, user_agent)
        except Exception:
            _logger.exception("Device block check failed; allowing login")
        if device_blocked:
            cls._arm_log_login(login, uid, 'blocked_device', ip)
            _logger.info("Login blocked (blocked device) for db:%s login:%s ip:%s",
                         db, login, ip)
            raise AccessDenied()

        # 2FA compliance: the login is allowed (blocking would deadlock — the
        # user could not reach preferences to enable it), but a non-compliant
        # user is recorded so managers can chase it in Security Hygiene.
        login_status = 'success'
        try:
            with cls.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                if 'access.rights.profile' in env and env.registry.ready:
                    if (env['access.rights.profile']._requires_2fa(uid)
                            and not env['res.users'].browse(uid).totp_enabled):
                        login_status = 'twofa_missing'
        except Exception:
            _logger.exception("Access-rights 2FA check failed; treating as compliant")
        cls._arm_log_login(login, uid, login_status, ip)
        return auth_info
