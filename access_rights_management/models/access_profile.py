# -*- coding: utf-8 -*-
import ipaddress
import logging
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, tools, _
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Models of this app itself: they can never be targeted by a rule, so a
# manager cannot lock himself (or anybody) out of the configuration screens.
PROTECTED_MODELS = [
    'access.rights.profile',
    'access.rights.model.line',
    'access.rights.field.line',
    'access.rights.domain.line',
    'access.rights.node.line',
    'access.rights.search.line',
    'access.rights.chatter.line',
    'access.rights.view.node',
    'access.rights.search.node',
    'access.rights.view.type',
    'access.rights.login.log',
    'access.rights.export.log',
    'access.rights.export.log.line',
    'access.rights.session.kick',
    'access.rights.sensitive.field',
    'access.rights.copy.wizard',
    'access.rights.device',
    'access.rights.anomaly',
    'access.rights.change',
    'access.rights.rollout.wizard',
]

WEEKDAY_FIELDS = ['login_mon', 'login_tue', 'login_wed', 'login_thu',
                  'login_fri', 'login_sat', 'login_sun']

# Models a read-only user must still be able to write on for the web client
# to work (login tracking, presence, personal settings...).
READONLY_SAFE_MODELS = [
    'res.users', 'res.users.log', 'res.users.settings', 'res.lang',
    'bus.presence', 'mail.presence', 'mail.activity',
    'discuss.channel', 'discuss.channel.member',
]


class AccessRightsProfile(models.Model):
    _name = 'access.rights.profile'
    _description = 'Access Rights Profile'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    department_id = fields.Many2one(
        'hr.department', string='Department', tracking=True,
        ondelete='set null', index=True,
        help="The company department this role belongs to (the real HR "
             "department), e.g. the 'Accountant' role belongs to the "
             "'Accounting' department.")
    color = fields.Integer(related='department_id.color')
    user_ids = fields.Many2many(
        'res.users', 'access_rights_profile_user_rel', 'profile_id', 'user_id',
        string='Users', domain=[('share', '=', False)], tracking=True,
        help="The rules of this profile apply to these users.")
    apply_to_all_users = fields.Boolean(
        string='Global Profile', tracking=True,
        help="Apply this profile to every internal user (except the excluded "
             "ones) — no need to list users one by one.")
    excluded_user_ids = fields.Many2many(
        'res.users', 'access_rights_profile_excluded_user_rel', 'profile_id', 'user_id',
        string='Excluded Users', domain=[('share', '=', False)], tracking=True,
        help="Users this global profile does NOT apply to.")
    company_ids = fields.Many2many(
        'res.company', 'access_rights_profile_company_rel', 'profile_id', 'company_id',
        string='Companies', default=lambda self: self.env.company)
    apply_all_companies = fields.Boolean(
        string='Apply In All Companies', default=True, tracking=True,
        help="If set, the profile applies whatever the current company is. "
             "Otherwise it only applies while working in one of the selected companies.")

    date_from = fields.Date(
        string='Valid From', tracking=True,
        help="The profile only applies from this date (e.g. temporary access "
             "for an auditor or a vacation replacement). Empty = no start limit. "
             "Dates are evaluated in UTC, refreshed daily at midnight.")
    date_to = fields.Date(
        string='Valid Until', tracking=True,
        help="The profile stops applying after this date (inclusive). "
             "Empty = never expires.")
    validity_state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('valid', 'Valid'),
        ('expired', 'Expired'),
    ], compute='_compute_validity_state', string='Validity')

    readonly = fields.Boolean(
        string='Read-Only User', tracking=True,
        help="Users of this profile can only read data — every create/write/delete "
             "is blocked system-wide (UI and API).")
    disable_debug_mode = fields.Boolean(
        string='Disable Developer Mode', tracking=True,
        help="Developer mode is forced off for these users.")
    disable_login = fields.Boolean(
        string='Disable Login', tracking=True,
        help="Users of this profile cannot log in at all. Their currently "
             "open sessions are terminated as well.")

    # Login security (system administrators are always exempt, so a
    # misconfigured rule can never lock the admins out).
    restrict_ip = fields.Boolean(
        string='Restrict Allowed IPs', tracking=True,
        help="Users of this profile can only log in (and stay logged in) from "
             "the IP addresses / networks listed below.")
    allowed_ip_list = fields.Char(
        string='Allowed IPs', tracking=True,
        help="Comma-separated IP addresses or CIDR networks, e.g. "
             "'192.168.1.0/24, 41.208.70.5'.")
    restrict_login_hours = fields.Boolean(
        string='Restrict Login Hours', tracking=True,
        help="Users of this profile can only log in (and stay logged in) "
             "during the working days/hours below.")
    require_2fa = fields.Boolean(
        string='Require Two-Factor Auth', tracking=True,
        help="Users of this profile must enable two-factor authentication "
             "(TOTP). Non-compliant users are flagged in the Security Hygiene "
             "panel and reminded at login. Admins are exempt.")
    login_tz = fields.Selection(
        _tz_get, string='Timezone',
        default=lambda self: self.env.user.tz or 'UTC')
    login_hour_from = fields.Float(string='Allowed From', default=8.0)
    login_hour_to = fields.Float(string='Allowed Until', default=18.0)
    login_mon = fields.Boolean(string='Mon', default=True)
    login_tue = fields.Boolean(string='Tue', default=True)
    login_wed = fields.Boolean(string='Wed', default=True)
    login_thu = fields.Boolean(string='Thu', default=True)
    login_fri = fields.Boolean(string='Fri', default=False)
    login_sat = fields.Boolean(string='Sat', default=False)
    login_sun = fields.Boolean(string='Sun', default=True)

    # Global (all models) switches
    hide_chatter = fields.Boolean(help="Hide the chatter everywhere.")
    hide_send_mail = fields.Boolean(string='Hide Send Message', help="Hide the Send Message chatter button everywhere.")
    hide_log_notes = fields.Boolean(string='Hide Log Notes', help="Hide the Log Note chatter button everywhere.")
    hide_schedule_activity = fields.Boolean(string='Hide Activities', help="Hide the Activities chatter button everywhere.")
    hide_export = fields.Boolean(string='Hide Export', help="Hide the export options everywhere.")
    hide_import = fields.Boolean(string='Hide Import', help="Hide the import option everywhere.")
    hide_spreadsheet = fields.Boolean(string='Hide Spreadsheet', help="Hide the 'Insert in spreadsheet' options everywhere.")
    hide_add_property = fields.Boolean(string='Hide Add Property', help="Hide the 'Add Properties' option everywhere.")

    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', 'access_rights_profile_menu_rel', 'profile_id', 'menu_id',
        string='Hidden Menus',
        help="These menus (with their sub-menus) are hidden from the profile users.")

    model_line_ids = fields.One2many('access.rights.model.line', 'profile_id', string='Model Rules', copy=True)
    field_line_ids = fields.One2many('access.rights.field.line', 'profile_id', string='Field Rules', copy=True)
    domain_line_ids = fields.One2many('access.rights.domain.line', 'profile_id', string='Record Rules', copy=True)
    node_line_ids = fields.One2many('access.rights.node.line', 'profile_id', string='Button/Tab Rules', copy=True)
    search_line_ids = fields.One2many('access.rights.search.line', 'profile_id', string='Search Rules', copy=True)
    chatter_line_ids = fields.One2many('access.rights.chatter.line', 'profile_id', string='Chatter Rules', copy=True)

    total_rules = fields.Integer(compute='_compute_total_rules', string='Rules')
    user_count = fields.Integer(compute='_compute_user_count', string='User Count')

    @api.depends('user_ids')
    def _compute_user_count(self):
        for profile in self:
            profile.user_count = len(profile.user_ids)

    @api.depends('hide_menu_ids', 'model_line_ids', 'field_line_ids', 'domain_line_ids',
                 'node_line_ids', 'search_line_ids', 'chatter_line_ids')
    def _compute_total_rules(self):
        for profile in self:
            profile.total_rules = (
                len(profile.hide_menu_ids) + len(profile.model_line_ids)
                + len(profile.field_line_ids) + len(profile.domain_line_ids)
                + len(profile.node_line_ids) + len(profile.search_line_ids)
                + len(profile.chatter_line_ids))

    @api.depends('date_from', 'date_to')
    def _compute_validity_state(self):
        today = fields.Date.today()
        for profile in self:
            if profile.date_to and profile.date_to < today:
                profile.validity_state = 'expired'
            elif profile.date_from and profile.date_from > today:
                profile.validity_state = 'scheduled'
            else:
                profile.validity_state = 'valid'

    @api.constrains('date_from', 'date_to')
    def _check_validity_dates(self):
        for profile in self:
            if profile.date_from and profile.date_to and profile.date_from > profile.date_to:
                raise ValidationError(_(
                    "Profile '%s': 'Valid From' must be before 'Valid Until'.",
                    profile.name))

    @api.constrains('restrict_ip', 'allowed_ip_list')
    def _check_allowed_ip_list(self):
        for profile in self.filtered('restrict_ip'):
            tokens = [t.strip() for t in (profile.allowed_ip_list or '').split(',') if t.strip()]
            if not tokens:
                raise ValidationError(_(
                    "Profile '%s': 'Restrict Allowed IPs' is enabled but no IP "
                    "address is listed.", profile.name))
            for token in tokens:
                try:
                    ipaddress.ip_network(token, strict=False)
                except ValueError:
                    raise ValidationError(_(
                        "Profile '%(profile)s': '%(token)s' is not a valid IP "
                        "address or network (use e.g. 192.168.1.0/24).",
                        profile=profile.name, token=token))

    @api.constrains('restrict_login_hours', 'login_hour_from', 'login_hour_to',
                    *WEEKDAY_FIELDS)
    def _check_login_hours(self):
        for profile in self.filtered('restrict_login_hours'):
            if not (0.0 <= profile.login_hour_from < profile.login_hour_to <= 24.0):
                raise ValidationError(_(
                    "Profile '%s': allowed login hours must satisfy "
                    "0:00 ≤ from < until ≤ 24:00.", profile.name))
            if not any(profile[day] for day in WEEKDAY_FIELDS):
                raise ValidationError(_(
                    "Profile '%s': select at least one allowed login day.",
                    profile.name))

    def copy_data(self, default=None):
        # 18.0 copies whole recordsets: name each duplicate after its own source
        vals_list = super().copy_data(default=default)
        if not default or 'name' not in default:
            for profile, vals in zip(self, vals_list):
                vals['name'] = _("%s (copy)", profile.name)
        return vals_list

    # -------------------------------------------------------------------
    # Guards & cache invalidation
    # -------------------------------------------------------------------
    def _check_readonly_admin(self):
        for profile in self.filtered('readonly'):
            for user in profile.user_ids:
                if user.has_group('base.group_system') or user.has_group('base.group_erp_manager'):
                    raise UserError(_(
                        "Administrator '%s' cannot be made read-only: you would "
                        "lock the system configuration.", user.name))

    def _check_global_safety(self):
        # a global read-only/no-login profile would lock every user
        # (administrators included) out of the system
        for profile in self.filtered('apply_to_all_users'):
            if profile.readonly or profile.disable_login:
                raise UserError(_(
                    "Profile '%s': 'Read-Only User' and 'Disable Login' cannot "
                    "be combined with 'Global Profile' — you would lock everyone "
                    "out. Assign explicit users instead.", profile.name))

    def _arm_clear_caches(self):
        # Rules feed ormcache'd helpers and cached view archs: flush everything
        # once per configuration change (never on normal page loads).
        self.env.registry.clear_all_caches()

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)
        profiles._check_readonly_admin()
        profiles._check_global_safety()
        self._arm_clear_caches()
        # a profile created with users already assigned is a grant too
        if not self.env.context.get('arm_skip_change_log'):
            Change = self.env['access.rights.change']
            for profile in profiles:
                for user in profile.user_ids:
                    Change._record(user, 'profile', 'granted', profile)
        return profiles

    def write(self, vals):
        # snapshot the membership so a change made from the profile side is
        # logged in the permission timeline too
        before = {}
        if 'user_ids' in vals and not self.env.context.get('arm_skip_change_log'):
            before = {profile.id: profile.user_ids for profile in self}
        res = super().write(vals)
        self._check_readonly_admin()
        self._check_global_safety()
        self._arm_clear_caches()
        if before:
            Change = self.env['access.rights.change']
            for profile in self:
                old_users = before.get(profile.id, self.env['res.users'])
                for user in profile.user_ids - old_users:
                    Change._record(user, 'profile', 'granted', profile)
                for user in old_users - profile.user_ids:
                    Change._record(user, 'profile', 'revoked', profile)
        return res

    def unlink(self):
        res = super().unlink()
        self._arm_clear_caches()
        return res

    def toggle_active_value(self):
        for profile in self:
            profile.active = not profile.active
        return True

    # -------------------------------------------------------------------
    # Applicability domains
    # -------------------------------------------------------------------
    @api.model
    def _validity_domain(self, prefix=''):
        """Date-validity clauses. They live inside ormcached lookups: the
        daily cron (_cron_daily_refresh) flushes the caches so a new day is
        always re-evaluated."""
        today = fields.Date.today()
        return [
            '|', (prefix + 'date_from', '=', False), (prefix + 'date_from', '<=', today),
            '|', (prefix + 'date_to', '=', False), (prefix + 'date_to', '>=', today),
        ]

    @api.model
    def _profile_domain(self):
        """Profiles applying to the current user in the current company."""
        return [
            '|', ('user_ids', 'in', self.env.uid),
                 '&', ('apply_to_all_users', '=', True),
                      ('excluded_user_ids', 'not in', [self.env.uid]),
            '|', ('apply_all_companies', '=', True),
                 ('company_ids', 'in', self.env.company.id),
        ] + self._validity_domain()

    @api.model
    def _line_domain(self, model_name=None):
        """Rule lines applying to the current user in the current company."""
        domain = [
            ('profile_id.active', '=', True),
            '|', ('profile_id.user_ids', 'in', self.env.uid),
                 '&', ('profile_id.apply_to_all_users', '=', True),
                      ('profile_id.excluded_user_ids', 'not in', [self.env.uid]),
            '|', ('profile_id.apply_all_companies', '=', True),
                 ('profile_id.company_ids', 'in', self.env.company.id),
        ] + self._validity_domain('profile_id.')
        if model_name:
            domain = [('model_name', '=', model_name)] + domain
        return domain

    # -------------------------------------------------------------------
    # Cached rule lookups (flushed by _arm_clear_caches on any change).
    # Never mutate a returned value.
    # -------------------------------------------------------------------
    @api.model
    @tools.ormcache('self.env.uid')
    def _user_is_profiled(self):
        """Whether any active profile targets the current user (any company).
        Used to decide if this user needs private view-cache entries."""
        return bool(self.sudo().search_count([
            '|', ('user_ids', 'in', self.env.uid),
                 '&', ('apply_to_all_users', '=', True),
                      ('excluded_user_ids', 'not in', [self.env.uid]),
        ]))

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id')
    def _get_global_flags(self):
        profiles = self.sudo().search(self._profile_domain())
        return {
            'readonly': any(profiles.mapped('readonly')),
            'disable_debug_mode': any(profiles.mapped('disable_debug_mode')),
            'hide_chatter': any(profiles.mapped('hide_chatter')),
            'hide_send_mail': any(profiles.mapped('hide_send_mail')),
            'hide_log_notes': any(profiles.mapped('hide_log_notes')),
            'hide_schedule_activity': any(profiles.mapped('hide_schedule_activity')),
            'hide_export': any(profiles.mapped('hide_export')),
            'hide_import': any(profiles.mapped('hide_import')),
            'hide_spreadsheet': any(profiles.mapped('hide_spreadsheet')),
            'hide_add_property': any(profiles.mapped('hide_add_property')),
        }

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id')
    def _get_hidden_menu_ids(self):
        profiles = self.sudo().search(self._profile_domain())
        menu_ids = set(profiles.hide_menu_ids.ids)
        # never hide this app's own menu: a manager cannot lock himself out
        own_root = self.env.ref('access_rights_management.menu_access_rights_root',
                                raise_if_not_found=False)
        if own_root:
            menu_ids.discard(own_root.id)
        return tuple(menu_ids)

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_model_flags(self, model_name):
        lines = self.env['access.rights.model.line'].sudo().search(self._line_domain(model_name))
        return {
            'restrict_create': any(lines.mapped('restrict_create')),
            'restrict_edit': any(lines.mapped('restrict_edit')),
            'restrict_delete': any(lines.mapped('restrict_delete')),
            'restrict_archive': any(lines.mapped('restrict_archive')),
            'restrict_duplicate': any(lines.mapped('restrict_duplicate')),
            'restrict_export': any(lines.mapped('restrict_export')),
            'restrict_import': any(lines.mapped('restrict_import')),
            'restrict_chatter': any(lines.mapped('restrict_chatter')),
            'restrict_spreadsheet': any(lines.mapped('restrict_spreadsheet')),
            'hidden_view_types': tuple(set(lines.mapped('view_type_ids.technical_name'))),
            'hidden_report_ids': tuple(set(lines.mapped('report_action_ids').ids)),
            'hidden_server_action_ids': tuple(set(lines.mapped('server_action_ids').ids)),
        }

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_field_rules(self, model_name):
        """{field_name: (invisible, readonly, required, no_external_link)}"""
        lines = self.env['access.rights.field.line'].sudo().search(self._line_domain(model_name))
        rules = {}
        for line in lines:
            for field in line.field_ids:
                current = rules.get(field.name, (False, False, False, False))
                rules[field.name] = (
                    current[0] or line.invisible,
                    current[1] or line.readonly,
                    current[2] or line.required,
                    current[3] or line.remove_external_link,
                )
        return rules

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_hidden_nodes(self, model_name):
        """{'button': frozenset(names), 'page': frozenset(names+strings), 'link': frozenset(names)}"""
        lines = self.env['access.rights.node.line'].sudo().search(self._line_domain(model_name))
        buttons, pages, links = set(), set(), set()
        for node in lines.mapped('button_node_ids'):
            if node.attribute_name:
                buttons.add(node.attribute_name)
        for node in lines.mapped('page_node_ids'):
            if node.attribute_name:
                pages.add(node.attribute_name)
            if node.attribute_string:
                pages.add(node.attribute_string)
        for node in lines.mapped('link_node_ids'):
            if node.attribute_name:
                links.add(node.attribute_name)
        return {'button': frozenset(buttons), 'page': frozenset(pages), 'link': frozenset(links)}

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_hidden_search_nodes(self, model_name):
        """{'filter': frozenset(names), 'group': frozenset(names)}"""
        lines = self.env['access.rights.search.line'].sudo().search(self._line_domain(model_name))
        return {
            'filter': frozenset(n for n in lines.mapped('filter_node_ids.attribute_name') if n),
            'group': frozenset(n for n in lines.mapped('group_node_ids.attribute_name') if n),
        }

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_chatter_rules(self, model_name):
        lines = self.env['access.rights.chatter.line'].sudo().search(self._line_domain(model_name))
        return {
            'hide_chatter': any(lines.mapped('hide_chatter')),
            'hide_send_mail': any(lines.mapped('hide_send_mail')),
            'hide_log_notes': any(lines.mapped('hide_log_notes')),
            'hide_schedule_activity': any(lines.mapped('hide_schedule_activity')),
        }

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_domain_line_data(self, model_name):
        lines = self.env['access.rights.domain.line'].sudo().search(self._line_domain(model_name))
        return tuple({
            'read': line.perm_read,
            'write': line.perm_write,
            'create': line.perm_create,
            'unlink': line.perm_unlink,
            'apply_domain': line.apply_domain,
            'domain': line.domain or '[]',
            'profile': line.profile_id.name,
        } for line in lines)

    # -------------------------------------------------------------------
    # Login security (login flow + per-request session enforcement)
    # -------------------------------------------------------------------
    @api.model
    @tools.ormcache('uid')
    def _get_login_security(self, uid):
        """Aggregated login restrictions for `uid`, from every active,
        date-valid profile targeting the user. Company scoping is ignored on
        purpose: at login time there is no current company yet.

        System administrators are exempt so a bad rule can never lock the
        admins out."""
        user = self.env['res.users'].sudo().browse(uid)
        if (not user.exists()
                or user.has_group('base.group_system')
                or user.has_group('base.group_erp_manager')):
            return {'exempt': True, 'disable_login': False,
                    'ip_rules': (), 'hour_rules': ()}
        profiles = self.sudo().search([
            '|', ('user_ids', 'in', uid),
                 '&', ('apply_to_all_users', '=', True),
                      ('excluded_user_ids', 'not in', [uid]),
        ] + self._validity_domain())
        ip_rules, hour_rules = [], []
        for profile in profiles:
            if profile.restrict_ip and profile.allowed_ip_list:
                tokens = tuple(t.strip() for t in profile.allowed_ip_list.split(',') if t.strip())
                if tokens:
                    ip_rules.append((profile.name, tokens))
            if profile.restrict_login_hours:
                days = tuple(i for i, day in enumerate(WEEKDAY_FIELDS) if profile[day])
                hour_rules.append((profile.name, days,
                                   profile.login_hour_from, profile.login_hour_to,
                                   profile.login_tz or 'UTC'))
        return {
            'exempt': False,
            'disable_login': any(profiles.mapped('disable_login')),
            'require_2fa': any(profiles.mapped('require_2fa')),
            'ip_rules': tuple(ip_rules),
            'hour_rules': tuple(hour_rules),
        }

    @api.model
    @tools.ormcache('uid')
    def _requires_2fa(self, uid):
        """Whether any active, date-valid profile requires 2FA for this user.
        Admins are exempt (so a bad rule can never brick their access)."""
        sec = self._get_login_security(uid)
        return bool(not sec.get('exempt') and sec.get('require_2fa'))

    @api.model
    def _check_login_security(self, sec, ip):
        """Evaluate `sec` (from _get_login_security) against the client IP and
        the current time. Returns a blocking reason or None. Every restricting
        profile must be satisfied (restrictions intersect, like everywhere
        else in this app)."""
        if sec.get('exempt'):
            return None
        if sec['disable_login']:
            return 'blocked_disabled'
        if ip and sec['ip_rules']:
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                addr = None
            if addr:
                for _profile, tokens in sec['ip_rules']:
                    for token in tokens:
                        try:
                            if addr in ipaddress.ip_network(token, strict=False):
                                break
                        except ValueError:
                            continue
                    else:
                        return 'blocked_ip'
        for _profile, days, hour_from, hour_to, tz in sec['hour_rules']:
            try:
                now = datetime.now(pytz.timezone(tz))
            except Exception:
                now = datetime.utcnow()
            hour = now.hour + now.minute / 60.0
            if now.weekday() not in days or not hour_from <= hour < hour_to:
                return 'blocked_hours'
        return None

    # -------------------------------------------------------------------
    # Daily cron
    # -------------------------------------------------------------------
    @api.model
    def _cron_daily_refresh(self):
        """Runs shortly after midnight UTC: flush the ormcaches so the date
        clauses of _validity_domain are re-evaluated for the new day, and
        leave an audit note on profiles that just expired."""
        yesterday = fields.Date.today() - timedelta(days=1)
        for profile in self.search([('date_to', '=', yesterday)]):
            profile.message_post(body=_(
                "Validity period ended on %s — this profile no longer applies.",
                fields.Date.to_string(yesterday)))
        for profile in self.search([('date_from', '=', fields.Date.today())]):
            profile.message_post(body=_(
                "Validity period starts today — this profile is now in force."))
        self.env.registry.clear_all_caches()

    # -------------------------------------------------------------------
    # Public RPC endpoints used by the JS patches
    # -------------------------------------------------------------------
    @api.model
    def get_removed_action_options(self, model_name):
        """Keys to strip from the action/cog menus of `model_name`."""
        if self.env.su or not model_name or model_name in PROTECTED_MODELS:
            return []
        flags = self._get_global_flags()
        model_flags = self._get_model_flags(model_name)
        removed = set()
        if flags['hide_export'] or model_flags['restrict_export']:
            removed.add('export')
        if flags['readonly']:
            removed.update({'archive', 'unarchive', 'duplicate', 'delete'})
        if model_flags['restrict_archive']:
            removed.update({'archive', 'unarchive'})
        if model_flags['restrict_duplicate']:
            removed.add('duplicate')
        if model_flags['restrict_delete']:
            removed.add('delete')
        return sorted(removed)

    @api.model
    def get_hidden_fields(self, model_name):
        """Names of invisible fields of `model_name` for the current user."""
        if self.env.su or not model_name or model_name in PROTECTED_MODELS:
            return []
        return sorted(name for name, rule in self._get_field_rules(model_name).items() if rule[0])

    @api.model
    def get_chatter_flags(self, model_name):
        """True means: hide it."""
        if self.env.su or not model_name:
            return {'hide_send_mail': False, 'hide_log_notes': False, 'hide_schedule_activity': False}
        flags = self._get_global_flags()
        rules = self._get_chatter_rules(model_name)
        return {
            'hide_send_mail': flags['hide_send_mail'] or rules['hide_send_mail'],
            'hide_log_notes': flags['hide_log_notes'] or rules['hide_log_notes'],
            'hide_schedule_activity': flags['hide_schedule_activity'] or rules['hide_schedule_activity'],
        }

    @api.model
    def is_spreadsheet_hidden(self, action_model, action_id):
        if self.env.su:
            return False
        if self._get_global_flags()['hide_spreadsheet']:
            return True
        model_name = self.env[action_model].sudo().browse(action_id).res_model
        return bool(model_name) and self._get_model_flags(model_name)['restrict_spreadsheet']

    @api.model
    def is_add_property_hidden(self, model_name):
        if self.env.su:
            return False
        return self._get_global_flags()['hide_add_property']
