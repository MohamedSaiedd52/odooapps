# -*- coding: utf-8 -*-
import logging

from odoo import api, models, SUPERUSER_ID
from odoo.http import request, SessionExpiredException

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _auth_method_user(cls):
        super()._auth_method_user()
        cls._arm_enforce_login_security()

    @classmethod
    def _arm_enforce_login_security(cls):
        """Live enforcement of the profile login policy: a user whose login
        was disabled, whose IP is not allowed anymore, or whose allowed hours
        just ended is logged out on his next request — not only at his next
        login. Costs one ormcached dict lookup per request."""
        env = request.env
        if not env.uid or env.su:
            return
        if 'access.rights.profile' not in env or not env.registry.ready:
            return
        if request.session.get('arm_simulate_origin_uid'):
            # an admin is simulating this user for diagnostics: neither the
            # standing login policy nor a queued kick may destroy his session
            # (a pending kick stays queued for the user's own real sessions).
            return
        reason = None
        forced = False
        try:
            profile = env['access.rights.profile'].sudo()
            # 1. manual, one-shot forced logout (Live Sessions "kick") — applies
            #    to everyone (a compromised admin account can be kicked too).
            if env.uid in env['access.rights.session.kick'].sudo()._pending_uids():
                forced = True
                reason = 'kicked'
            else:
                # 2. standing policy (disable login / IP / hours); admins exempt.
                sec = profile._get_login_security(env.uid)
                reason = profile._check_login_security(sec, request.httprequest.remote_addr)
        except Exception:
            # enforcement must never break request dispatching
            return
        if reason:
            uid = env.uid
            login = env['res.users'].sudo().browse(uid).login
            _logger.info("Session terminated (%s) by access-rights profile for uid:%s ip:%s",
                         reason, uid, request.httprequest.remote_addr)
            request.session.logout(keep_db=True)
            try:
                with env.registry.cursor() as cr:
                    log_env = api.Environment(cr, SUPERUSER_ID, {})
                    if forced:
                        log_env['access.rights.session.kick']._consume(uid)
                    log_env['access.rights.login.log']._log(
                        login, uid, 'kicked', request.httprequest.remote_addr)
            except Exception:
                pass
            raise SessionExpiredException("Session terminated by access-rights policy")

    def session_info(self):
        info = super().session_info()
        try:
            origin_uid = request and request.session.uid \
                and request.session.get('arm_simulate_origin_uid')
            if origin_uid:
                origin = self.env['res.users'].sudo().browse(origin_uid)
                info['arm_simulate'] = {
                    'origin_name': origin.name,
                    'target_name': self.env.user.name,
                    'target_login': self.env.user.login,
                }
        except Exception:
            _logger.exception("Could not expose the simulation banner info")
        return info
