# -*- coding: utf-8 -*-
"""Security-audit layer: export audit log, forced session logout, and the
'sensitive field' flag used by the Sensitive Data Map screen."""
import logging
from datetime import timedelta

from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)

EXPORT_LOG_RETENTION_DAYS = 180
DEFAULT_EXPORT_ALERT_THRESHOLD = 100


class AccessRightsSensitiveField(models.Model):
    """A field flagged as business-sensitive. Kept as its own record (rather
    than a column on ir.model.fields) because Odoo forbids writing extra
    attributes onto base fields."""
    _name = 'access.rights.sensitive.field'
    _description = 'Sensitive Data Field'
    _order = 'model_name, field_name'
    _rec_name = 'field_label'

    field_id = fields.Many2one('ir.model.fields', string='Field', required=True,
                               ondelete='cascade', index=True)
    model_name = fields.Char(related='field_id.model', store=True, index=True)
    field_name = fields.Char(related='field_id.name', store=True)
    field_label = fields.Char(related='field_id.field_description', string='Label')
    model_display = fields.Char(related='field_id.model_id.name', string='Document')
    field_groups_display = fields.Char(
        string='Field Groups', compute='_compute_audience')
    audience_count = fields.Integer(
        string='Users Who Can Read It', compute='_compute_audience')
    audience_preview = fields.Char(
        string='Audience', compute='_compute_audience')

    _sql_constraints = [
        ('field_uniq', 'unique(field_id)', 'This field is already flagged as sensitive.'),
    ]

    # ---- live audience: who can actually read this field today ----
    def _model_reader_users(self, model_name):
        """Internal users who have read access to `model_name` through their
        groups' ACL (a group-less ACL grants everyone)."""
        model = self.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if not model:
            return self.env['res.users']
        accesses = self.env['ir.model.access'].sudo().search(
            [('model_id', '=', model.id), ('perm_read', '=', True)])
        if not accesses:
            return self.env['res.users']
        if any(not access.group_id for access in accesses):
            return self.env['res.users'].sudo().search([('share', '=', False)])
        users = accesses.mapped('group_id.users').filtered(lambda u: not u.share)
        return users

    def _field_audience(self):
        """Internal users who can actually read the field today: model readers,
        narrowed by the field-level group restriction, minus users whose ARM
        profile makes the field invisible."""
        self.ensure_one()
        field = self.field_id
        readers = self._model_reader_users(field.model_id.model)
        if field.groups:
            readers = readers & field.groups.mapped('users')
        hidden_users = self.env['res.users']
        lines = self.env['access.rights.field.line'].sudo().search([
            ('model_name', '=', field.model_id.model),
            ('invisible', '=', True),
            ('field_ids', 'in', field.id)])
        for line in lines:
            profile = line.profile_id
            if not profile.active:
                continue
            if profile.apply_to_all_users:
                hidden_users |= readers.filtered(
                    lambda u: u not in profile.excluded_user_ids)
            else:
                hidden_users |= profile.user_ids
        return readers - hidden_users

    def _compute_audience(self):
        for rec in self:
            if not rec.field_id.exists():
                rec.audience_count = 0
                rec.audience_preview = ''
                rec.field_groups_display = ''
                continue
            audience = rec._field_audience()
            rec.audience_count = len(audience)
            names = audience[:8].mapped('name')
            more = len(audience) - len(names)
            rec.audience_preview = ', '.join(names) + (
                _(' … +%s more', more) if more > 0 else '')
            rec.field_groups_display = ', '.join(
                rec.field_id.groups.mapped('full_name')) or _('(no group restriction)')

    def action_view_audience(self):
        self.ensure_one()
        audience = self._field_audience()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Can read: %s / %s",
                      self.model_display, self.field_label),
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'domain': [('id', 'in', audience.ids)],
        }


class AccessRightsExportLog(models.Model):
    """One line per CSV/Excel download, answering the three questions an audit
    actually asks: **which fields** left the system, **from which screen**, and
    **with which saved export template**."""
    _name = 'access.rights.export.log'
    _description = 'Data Export Audit Log'
    _order = 'id desc'
    _rec_name = 'model_name'

    user_id = fields.Many2one('res.users', string='User', ondelete='set null',
                              index=True, readonly=True)
    model = fields.Char(string='Model', index=True, readonly=True)
    model_name = fields.Char(string='Document', readonly=True)
    record_count = fields.Integer(string='Records', readonly=True)
    field_count = fields.Integer(string='Fields', readonly=True)
    fields_preview = fields.Char(string='Exported Fields (Technical)', readonly=True)
    field_labels = fields.Char(string='Exported Fields', readonly=True,
                               help="The column headers of the exported file, "
                                    "in the order the user arranged them.")
    line_ids = fields.One2many('access.rights.export.log.line', 'log_id',
                               string='Fields', readonly=True)
    sensitive_fields = fields.Char(string='Sensitive Fields Included', readonly=True)
    export_format = fields.Selection(
        [('csv', 'CSV'), ('xlsx', 'Excel')], string='Format', readonly=True)
    ip_address = fields.Char(string='IP Address', readonly=True)
    is_sensitive = fields.Boolean(string='Sensitive', index=True, readonly=True)
    is_large = fields.Boolean(string='Large Export', readonly=True)

    # ---- where it was exported from ----
    screen_name = fields.Char(string='Screen', index=True, readonly=True,
                              help="The menu / action the user was on when they "
                                   "exported (as shown in the breadcrumb).")
    action_id = fields.Many2one('ir.actions.act_window', string='Screen Action',
                                ondelete='set null', readonly=True)
    view_type = fields.Char(string='View', readonly=True)
    scope = fields.Selection([
        ('selected', 'Selected Records'),
        ('filtered', 'Everything Matching the Filter'),
    ], string='Scope', readonly=True)

    # ---- how the field list was built ----
    export_template_id = fields.Many2one('ir.exports', string='Export Template',
                                         ondelete='set null', readonly=True)
    template_name = fields.Char(string='Template', index=True, readonly=True,
                                help="The saved export template used, or empty "
                                     "when the user picked the fields by hand.")
    import_compat = fields.Boolean(string='Import-Compatible', readonly=True,
                                   help="The export was made in the format that "
                                        "can be re-imported into Odoo.")

    @api.model
    def _sensitive_models(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'access_rights_management.sensitive_models', '')
        return {m.strip() for m in param.split(',') if m.strip()}

    @api.model
    def _export_alert_threshold(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'access_rights_management.export_alert_threshold')
        try:
            return int(param) if param else DEFAULT_EXPORT_ALERT_THRESHOLD
        except (TypeError, ValueError):
            return DEFAULT_EXPORT_ALERT_THRESHOLD

    @api.model
    def _origin_values(self, model, origin):
        """Turn the `arm_origin` block the web client sends with an export
        (screen + saved template) into stored values. Everything in it comes
        from the browser, so every reference is validated before it is kept."""
        values = {
            'screen_name': None, 'action_id': False, 'view_type': None,
            'export_template_id': False, 'template_name': None,
            'import_compat': False, 'scope': None,
        }
        if not isinstance(origin, dict):
            return values

        def as_id(key):
            try:
                return int(origin.get(key) or 0)
            except (TypeError, ValueError):
                return 0

        def as_text(key, size):
            value = origin.get(key)
            return str(value)[:size] if isinstance(value, str) and value else None

        action = self.env['ir.actions.act_window'].sudo().browse(as_id('action_id')).exists()
        if action and action.res_model == model:
            values['action_id'] = action.id
        values['screen_name'] = as_text('screen_name', 128) or action.name or None
        values['view_type'] = as_text('view_type', 32)
        values['import_compat'] = bool(origin.get('import_compat'))
        values['scope'] = 'selected' if origin.get('scope') == 'selected' else 'filtered'
        template = self.env['ir.exports'].sudo().browse(as_id('template_id')).exists()
        if template and template.resource == model:
            values['export_template_id'] = template.id
            values['template_name'] = template.name
        else:
            # no template, or one deleted between the export and this line
            values['template_name'] = as_text('template_name', 128)
        return values

    @api.model
    def _log_export(self, model, record_count, field_names, export_format,
                    ip=None, fields_info=None, origin=None):
        """Record one export. Never raises — it runs inside request dispatch.

        `fields_info` is the exported column list as the web client built it
        ([{name, label, type}, ...], in the user's own order); `origin` is the
        screen/template block added by this module's export patch.
        """
        try:
            fields_info = [f for f in (fields_info or []) if f.get('name')]
            if not field_names:
                field_names = [f['name'] for f in fields_info]
            model_rec = self.env['ir.model'].sudo().search([('model', '=', model)], limit=1)
            flagged = set(self.env['access.rights.sensitive.field'].sudo().search(
                [('model_name', '=', model)]).mapped('field_name'))
            # a nested column ('partner_id/name') exposes its root field
            included = sorted({
                name for name in field_names
                if name.split('/')[0] in flagged})
            is_sensitive = model in self._sensitive_models() or bool(included)
            is_large = record_count >= self._export_alert_threshold()
            labels = [f.get('label') or f['name'] for f in fields_info]
            values = {
                'user_id': self.env.uid,
                'model': model,
                'model_name': model_rec.name if model_rec else model,
                'record_count': record_count,
                'field_count': len(field_names or []),
                'fields_preview': (', '.join(field_names or []))[:500],
                'field_labels': (', '.join(labels))[:500] or None,
                'sensitive_fields': (', '.join(included))[:500] or None,
                'export_format': export_format,
                'ip_address': ip and str(ip)[:64],
                'is_sensitive': is_sensitive,
                'is_large': is_large,
                'line_ids': [(0, 0, {
                    'sequence': index,
                    'field_path': field['name'][:128],
                    'field_label': (field.get('label') or field['name'])[:128],
                    'field_type': (field.get('type') or '')[:32],
                    'is_sensitive': field['name'].split('/')[0] in flagged,
                }) for index, field in enumerate(fields_info)],
            }
            values.update(self._origin_values(model, origin))
            log = self.sudo().create(values)
            if is_sensitive and is_large:
                log._alert_managers()
        except Exception:
            _logger.exception("Could not write export audit log")

    def _alert_managers(self):
        """Post a warning in the chatter of every manager that a large
        sensitive export just happened. Best-effort — never raises."""
        self.ensure_one()
        try:
            managers = self.env['res.users'].sudo().search([
                ('groups_id', 'in', self.env.ref(
                    'access_rights_management.group_access_rights_manager').id),
                ('id', '!=', self.user_id.id),
            ])
            partners = managers.partner_id
            if not partners:
                return
            body = _(
                "⚠ Large sensitive export: %(user)s exported %(count)s "
                "%(model)s record(s) as %(fmt)s from %(ip)s.",
                user=self.user_id.name, count=self.record_count,
                model=self.model_name, fmt=(self.export_format or '').upper(),
                ip=self.ip_address or '?')
            details = [
                (_("Screen"), self.screen_name),
                (_("Template"), self.template_name or _("(fields picked by hand)")),
                (_("Sensitive fields"), self.sensitive_fields),
                (_("Columns"), self.field_labels),
            ]
            body += '<ul>' + ''.join(
                '<li><b>%s:</b> %s</li>' % (label, value)
                for label, value in details if value) + '</ul>'
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=partners.ids,
                subject=_("Large sensitive data export"),
                body=body)
        except Exception:
            _logger.exception("Could not alert managers about a sensitive export")

    @api.autovacuum
    def _gc_export_logs(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'access_rights_management.export_log_retention_days')
        try:
            days = int(param) if param else EXPORT_LOG_RETENTION_DAYS
        except ValueError:
            days = EXPORT_LOG_RETENTION_DAYS
        if days <= 0:
            return
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.sudo().search([('create_date', '<', cutoff)])
        if old:
            old.unlink()


class AccessRightsExportLogLine(models.Model):
    """One exported column. Kept as records (not just a comma-separated string)
    so an auditor can search "who exported the cost price" across every export,
    and so the sensitive columns of an export can be highlighted."""
    _name = 'access.rights.export.log.line'
    _description = 'Exported Field'
    _order = 'log_id desc, sequence, id'
    _rec_name = 'field_label'

    log_id = fields.Many2one('access.rights.export.log', string='Export',
                             required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=0, readonly=True)
    field_path = fields.Char(string='Field', required=True, index=True, readonly=True,
                             help="Technical name. A path such as "
                                  "partner_id/country_id/name is a column taken "
                                  "from a linked record.")
    field_label = fields.Char(string='Column', readonly=True)
    field_type = fields.Char(string='Type', readonly=True)
    is_sensitive = fields.Boolean(string='Sensitive', index=True, readonly=True)
    user_id = fields.Many2one(related='log_id.user_id', string='User', store=True)
    model = fields.Char(related='log_id.model', string='Model', store=True)
    export_date = fields.Datetime(related='log_id.create_date', string='When', store=True)


class AccessRightsSessionKick(models.Model):
    """One-shot forced logout of a user's open sessions. Created from the Live
    Sessions screen; enforced on the target user's next request (`ir.http`)."""
    _name = 'access.rights.session.kick'
    _description = 'Forced Session Logout'
    _order = 'id desc'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='User', required=True,
                              ondelete='cascade', index=True)
    requested_by = fields.Many2one('res.users', string='Requested By',
                                   default=lambda self: self.env.uid, readonly=True)
    reason = fields.Char()
    consumed = fields.Boolean(default=False, index=True,
                              help="Set once the user's session was actually terminated.")
    consumed_date = fields.Datetime(readonly=True)

    def _arm_flush(self):
        self.env.registry.clear_all_caches()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._arm_flush()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._arm_flush()
        return res

    def unlink(self):
        res = super().unlink()
        self._arm_flush()
        return res

    @api.model
    @tools.ormcache()
    def _pending_uids(self):
        """UIDs with an unconsumed forced-logout order (cached; the cache is
        flushed whenever a kick record changes)."""
        return tuple(self.sudo().search([('consumed', '=', False)]).mapped('user_id').ids)

    @api.model
    def _consume(self, uid):
        """Mark the pending kick order(s) of `uid` as done. Runs on the target
        user's request once we have logged them out."""
        pending = self.sudo().search([('user_id', '=', uid), ('consumed', '=', False)])
        if pending:
            pending.write({'consumed': True, 'consumed_date': fields.Datetime.now()})
