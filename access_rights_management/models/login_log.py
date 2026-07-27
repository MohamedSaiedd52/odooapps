# -*- coding: utf-8 -*-
"""Login audit trail + device registry.

Device identity
---------------
A web server cannot see a client's MAC address: a MAC never crosses a router,
so it is only ever visible for clients sitting on the server's own subnet —
and even then only while the ARP entry is fresh. Behind nginx, a VPN or any
router the field stays empty, which makes it useless as an identity.

So a device is identified by a long-lived, random `arm_device_id` cookie that
this module issues on login. It survives IP changes (DHCP, Wi-Fi ↔ LAN, VPN),
it is per browser profile, and clearing it correctly reads as "a new device".
Clients that carry no cookie at all (XML-RPC, curl, integrations) fall back to
a browser fingerprint (hash of the User-Agent) + IP pair, which is still
stable enough to group their logins.
"""
import hashlib
import logging
import re
import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.http import request

_logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 180

# Name and lifetime of the device cookie. Two years: long enough that a
# regular workstation keeps one identity, short enough to expire eventually.
DEVICE_COOKIE = 'arm_device_id'
DEVICE_COOKIE_MAX_AGE = 2 * 365 * 24 * 3600
_TOKEN_RE = re.compile(r'^[0-9a-f]{32}$')

_UA_BROWSERS = [
    ('Edg', 'Edge'), ('OPR', 'Opera'), ('Chrome', 'Chrome'),
    ('Firefox', 'Firefox'), ('Safari', 'Safari'), ('MSIE', 'IE'),
    ('Trident', 'IE'),
]
_UA_OSES = [
    ('Windows NT 10', 'Windows 10/11'), ('Windows', 'Windows'),
    ('Android', 'Android'), ('iPhone', 'iOS'), ('iPad', 'iOS'),
    ('Mac OS X', 'macOS'), ('Linux', 'Linux'),
]


def _parse_user_agent(ua):
    """Best-effort (browser, os) out of a raw User-Agent string."""
    ua = ua or ''
    browser = next((label for token, label in _UA_BROWSERS if token in ua), '')
    os_name = next((label for token, label in _UA_OSES if token in ua), '')
    return browser, os_name


def fingerprint_of(user_agent):
    """Stable short hash of the browser build. Used to group the logins of
    clients that carry no cookie, and to keep a block in place when someone
    clears the device cookie."""
    if not user_agent:
        return False
    return hashlib.sha256(user_agent.encode('utf-8', 'replace')).hexdigest()[:32]


def current_device_token(create=True):
    """Read the device cookie of the current request, issuing one when the
    browser has none yet. Returns None outside an HTTP request (cron, RPC).

    The freshly issued token is cached on the request so that everything that
    runs later in the same request (audit line, device registration) uses the
    very token the browser is about to receive.
    """
    if not request:
        return None
    token = getattr(request, 'arm_device_token', None)
    if token:
        return token
    token = request.httprequest.cookies.get(DEVICE_COOKIE) or ''
    if not _TOKEN_RE.match(token):
        if not create:
            return None
        token = uuid.uuid4().hex
        try:
            request.future_response.set_cookie(
                DEVICE_COOKIE, token,
                max_age=DEVICE_COOKIE_MAX_AGE,
                httponly=True, samesite='Lax',
                secure=request.httprequest.is_secure,
                # security cookie: not subject to the marketing opt-in
                cookie_type='required')
        except Exception:
            _logger.exception("Could not issue the device cookie")
            return None
    request.arm_device_token = token
    return token


class AccessRightsDevice(models.Model):
    """A device (browser profile) a user logs in from. Gives managers
    device-level control: name and trust the usual ones, block the odd one —
    a blocked device cannot log in even with the right password."""
    _name = 'access.rights.device'
    _description = 'Login Device'
    _order = 'last_seen desc'
    _rec_name = 'display_label'

    user_id = fields.Many2one('res.users', string='User', required=True,
                              ondelete='cascade', index=True)
    label = fields.Char(string='Device Name',
                        help="Your own name for this device (Reception PC, "
                             "Ahmed's laptop...). Shown everywhere instead of "
                             "the browser description.")
    device_token = fields.Char(string='Device ID', index=True, readonly=True,
                               help="Random identifier stored in the device's "
                                    "browser. It is what identifies the device "
                                    "across IP changes.")
    fingerprint = fields.Char(string='Browser Fingerprint', index=True, readonly=True,
                              help="Hash of the browser build. Used for clients "
                                   "that carry no cookie, and to keep a block in "
                                   "place if the device cookie is cleared.")
    ip_address = fields.Char(string='Last IP', readonly=True)
    user_agent = fields.Char(readonly=True)
    browser = fields.Char(readonly=True)
    os = fields.Char(string='OS', readonly=True)
    first_seen = fields.Datetime(readonly=True)
    last_seen = fields.Datetime(readonly=True, index=True)
    login_count = fields.Integer(readonly=True, default=0)
    state = fields.Selection([
        ('normal', 'Normal'),
        ('trusted', 'Trusted'),
        ('blocked', 'Blocked'),
    ], default='normal', required=True, index=True, string='Status')
    note = fields.Char(string='Note')
    display_label = fields.Char(compute='_compute_display_label')

    @api.depends('label', 'browser', 'os', 'ip_address', 'user_id')
    def _compute_display_label(self):
        for rec in self:
            if rec.label:
                rec.display_label = rec.label
                continue
            device = ' on '.join(part for part in (rec.browser, rec.os) if part)
            rec.display_label = "%s — %s" % (
                rec.user_id.name or '?',
                device or rec.ip_address or _('Unknown device'))

    # ------------------------------------------------------------------
    # capture
    # ------------------------------------------------------------------
    @api.model
    def _register_login(self, uid, ip, user_agent):
        """Find-or-create the device of a successful login and update its
        counters. Returns the device. Never raises."""
        try:
            token = current_device_token()
            if not (token or fingerprint_of(user_agent) or ip):
                # nothing at all to recognise this client by: a device record
                # would be a new meaningless row on every single login
                return self.browse()
            device = self._find_device(uid, ip, user_agent, token)
            browser, os_name = _parse_user_agent(user_agent)
            now = fields.Datetime.now()
            if device:
                device.sudo().write({
                    # a device recorded before it had a token (or before this
                    # upgrade) is adopted here instead of being duplicated
                    'device_token': token or device.device_token,
                    'fingerprint': fingerprint_of(user_agent) or device.fingerprint,
                    'ip_address': ip or device.ip_address,
                    'user_agent': (user_agent or '')[:256] or device.user_agent,
                    'browser': browser or device.browser,
                    'os': os_name or device.os,
                    'last_seen': now,
                    'login_count': device.login_count + 1,
                })
            else:
                device = self.sudo().create({
                    'user_id': uid,
                    'device_token': token,
                    'fingerprint': fingerprint_of(user_agent),
                    'ip_address': ip and str(ip)[:64],
                    'user_agent': (user_agent or '')[:256],
                    'browser': browser,
                    'os': os_name,
                    'first_seen': now,
                    'last_seen': now,
                    'login_count': 1,
                })
            return device
        except Exception:
            _logger.exception("Could not register login device")
            return self.browse()

    @api.model
    def _find_device(self, uid, ip, user_agent, token=None):
        """The device record this request comes from, or an empty recordset.
        Never writes — adoption of a token-less record is done by the caller
        that owns the write (`_register_login`)."""
        domain = [('user_id', '=', uid)]
        fingerprint = fingerprint_of(user_agent)
        if token:
            device = self.sudo().search(
                domain + [('device_token', '=', token)], limit=1)
            if device:
                return device
            # first login after the upgrade / after the cookie was issued:
            # reuse the record already written for this browser + IP
            return self.sudo().search(
                domain + [('device_token', '=', False),
                          ('fingerprint', '=', fingerprint),
                          ('ip_address', '=', ip)], limit=1)
        # cookie-less client (RPC, integration): browser + IP is all we have
        if fingerprint:
            return self.sudo().search(
                domain + [('fingerprint', '=', fingerprint),
                          ('ip_address', '=', ip)], limit=1)
        if ip:
            return self.sudo().search(domain + [('ip_address', '=', ip)], limit=1)
        return self.browse()

    @api.model
    def _check_blocked(self, uid, ip, user_agent):
        """True if the login must be denied because its device is blocked.

        Deleting the cookie does not lift a block: the same browser on the
        same address stays blocked through its fingerprint.
        """
        try:
            device = self._find_device(uid, ip, user_agent,
                                       current_device_token(create=False))
            if device and device.state == 'blocked':
                return True
            fingerprint = fingerprint_of(user_agent)
            if not fingerprint:
                return False
            return bool(self.sudo().search_count([
                ('user_id', '=', uid), ('state', '=', 'blocked'),
                ('fingerprint', '=', fingerprint),
                ('ip_address', '=', ip),
            ]))
        except Exception:
            _logger.exception("Device block check failed; allowing login")
            return False

    # ------------------------------------------------------------------
    # manager actions
    # ------------------------------------------------------------------
    def action_trust(self):
        self.write({'state': 'trusted'})

    def action_block(self):
        self.write({'state': 'blocked'})
        # terminate the user's open sessions right away
        for device in self:
            self.env['access.rights.session.kick'].sudo().create({
                'user_id': device.user_id.id,
                'reason': _("Device blocked (%s)", device.display_label),
            })

    def action_reset(self):
        self.write({'state': 'normal'})

    def action_view_logins(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Logins — %s", self.display_label),
            'res_model': 'access.rights.login.log',
            'view_mode': 'tree',
            'domain': [('device_id', '=', self.id)],
        }


class AccessRightsLoginLog(models.Model):
    _name = 'access.rights.login.log'
    _description = 'Login Audit Log'
    _order = 'id desc'
    _rec_name = 'login'

    login = fields.Char(index=True, readonly=True)
    user_id = fields.Many2one('res.users', string='User', ondelete='set null',
                              index=True, readonly=True)
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Wrong Credentials'),
        ('blocked_disabled', 'Blocked — Login Disabled'),
        ('blocked_ip', 'Blocked — IP Not Allowed'),
        ('blocked_hours', 'Blocked — Outside Login Hours'),
        ('blocked_device', 'Blocked — Device Blocked'),
        ('kicked', 'Session Terminated'),
        ('twofa_missing', 'Logged In — 2FA Missing'),
        ('simulate_start', 'Simulation Started'),
        ('simulate_stop', 'Simulation Ended'),
    ], required=True, index=True, readonly=True)
    ip_address = fields.Char(string='IP Address', readonly=True)
    device_id = fields.Many2one('access.rights.device', string='Device',
                                ondelete='set null', index=True, readonly=True)
    browser = fields.Char(readonly=True)
    os = fields.Char(string='OS', readonly=True)
    user_agent = fields.Char(readonly=True)
    note = fields.Char(readonly=True)

    @api.model
    def _log(self, login, uid, status, ip=None, user_agent=None, note=None):
        """Write one audit line. Must never raise: it runs inside the
        login/dispatch flow."""
        try:
            if not user_agent and request:
                user_agent = request.httprequest.user_agent.string or None
            browser, os_name = _parse_user_agent(user_agent)
            Device = self.env['access.rights.device']
            device = Device.browse()
            if uid and status in ('success', 'twofa_missing'):
                device = Device._register_login(
                    uid, ip and str(ip)[:64], user_agent)
            elif uid:
                # denied / terminated: link the known device if we recognise
                # it, but never create one for an attempt that did not succeed
                device = Device._find_device(
                    uid, ip and str(ip)[:64], user_agent,
                    current_device_token(create=False))
            log = self.sudo().create({
                'login': login and login[:128],
                'user_id': uid or False,
                'status': status,
                'ip_address': ip and str(ip)[:64],
                'device_id': device.id or False,
                'browser': browser,
                'os': os_name,
                'user_agent': user_agent and user_agent[:256],
                'note': note and note[:256],
            })
            if status in ('success', 'twofa_missing'):
                self.env['access.rights.anomaly']._scan_login(log, device)
        except Exception:
            _logger.exception("Could not write login audit log")

    def action_open_device(self):
        self.ensure_one()
        if not self.device_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'access.rights.device',
            'res_id': self.device_id.id,
            'view_mode': 'form',
        }

    def action_block_device(self):
        """Block the device this login came from, straight from the audit line."""
        for log in self:
            if log.device_id and log.device_id.state != 'blocked':
                log.device_id.action_block()

    @api.autovacuum
    def _gc_login_logs(self):
        """Drop audit lines older than the configured retention (default %s
        days, parameter access_rights_management.login_log_retention_days).
        """ % DEFAULT_RETENTION_DAYS
        param = self.env['ir.config_parameter'].sudo().get_param(
            'access_rights_management.login_log_retention_days')
        try:
            days = int(param) if param else DEFAULT_RETENTION_DAYS
        except ValueError:
            days = DEFAULT_RETENTION_DAYS
        if days <= 0:  # 0 disables the vacuum
            return
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.sudo().search([('create_date', '<', cutoff)])
        if old:
            _logger.info("Login audit log: vacuuming %s lines older than %s days",
                         len(old), days)
            old.unlink()
