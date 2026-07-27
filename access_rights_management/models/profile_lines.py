# -*- coding: utf-8 -*-
from lxml import etree
from markupsafe import escape

from odoo import api, fields, models, _


class AccessRightsLineMixin(models.AbstractModel):
    _name = 'access.rights.line.mixin'
    _description = 'Access Rights Rule Line (mixin)'

    profile_id = fields.Many2one(
        'access.rights.profile', string='Profile', required=True,
        index=True, ondelete='cascade')
    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, index=True, ondelete='cascade',
        domain="[('model', 'not like', 'access.rights.%'), ('transient', '=', False)]")
    model_name = fields.Char(related='model_id.model', string='Model Name', store=True)

    def _arm_clear_caches(self):
        self.env.registry.clear_all_caches()

    def _arm_audit(self, action):
        """Log rule changes in the profile chatter (audit trail)."""
        if not self.pool.ready or self.env.context.get('install_mode'):
            return
        per_profile = {}
        for line in self.filtered('profile_id'):
            per_profile.setdefault(line.profile_id, set()).add(
                line.model_name or line.display_name or '?')
        for profile, models_ in per_profile.items():
            profile.message_post(body=escape(_(
                "%(action)s — %(rule_type)s: %(models)s",
                action=action, rule_type=self._description,
                models=', '.join(sorted(models_)))))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._arm_audit(_("Rule added"))
        self._arm_clear_caches()
        return records

    def write(self, vals):
        res = super().write(vals)
        if set(vals) - {'profile_id'}:
            self._arm_audit(_("Rule updated"))
        self._arm_clear_caches()
        return res

    def unlink(self):
        self._arm_audit(_("Rule removed"))
        res = super().unlink()
        self._arm_clear_caches()
        return res


class AccessRightsModelLine(models.Model):
    _name = 'access.rights.model.line'
    _inherit = 'access.rights.line.mixin'
    _description = 'Model Access Rule'

    view_type_ids = fields.Many2many(
        'access.rights.view.type', 'arm_model_line_view_type_rel', 'line_id', 'view_type_id',
        string='Hide Views', help="These view types become unavailable for the model.")
    report_action_ids = fields.Many2many(
        'ir.actions.report', 'arm_model_line_report_rel', 'line_id', 'report_id',
        string='Hide Reports', domain="[('binding_model_id', '=', model_id)]",
        help="These print actions are removed from the model's toolbar.")
    server_action_ids = fields.Many2many(
        'ir.actions.server', 'arm_model_line_server_action_rel', 'line_id', 'action_id',
        string='Hide Actions', domain="[('binding_model_id', '=', model_id)]",
        help="These server actions are removed from the model's toolbar.")

    restrict_create = fields.Boolean(string='Hide Create')
    restrict_edit = fields.Boolean(string='Hide Edit')
    restrict_delete = fields.Boolean(string='Hide Delete')
    restrict_archive = fields.Boolean(string='Hide Archive')
    restrict_duplicate = fields.Boolean(string='Hide Duplicate')
    restrict_import = fields.Boolean(string='Hide Import')
    restrict_export = fields.Boolean(string='Hide Export')
    restrict_chatter = fields.Boolean(string='Hide Chatter')
    restrict_spreadsheet = fields.Boolean(string='Hide Spreadsheet')


class AccessRightsFieldLine(models.Model):
    _name = 'access.rights.field.line'
    _inherit = 'access.rights.line.mixin'
    _description = 'Field Access Rule'

    field_ids = fields.Many2many(
        'ir.model.fields', 'arm_field_line_field_rel', 'line_id', 'field_id',
        string='Fields', required=True, domain="[('model_id', '=', model_id)]")
    invisible = fields.Boolean(help="Hide the fields everywhere (views, export, filters, group by).")
    readonly = fields.Boolean(string='Read-Only', help="Make the fields read-only.")
    required = fields.Boolean(help="Make the fields mandatory.")
    remove_external_link = fields.Boolean(
        string='Remove External Link',
        help="Remove the internal-link/create/edit shortcuts of relational fields.")


class AccessRightsDomainLine(models.Model):
    _name = 'access.rights.domain.line'
    _inherit = 'access.rights.line.mixin'
    _description = 'Record Access Rule'

    model_id = fields.Many2one(
        domain="[('model', 'not like', 'access.rights.%'), ('transient', '=', False), ('abstract', '=', False)]")

    perm_read = fields.Boolean(string='Read', default=True)
    perm_create = fields.Boolean(string='Create')
    perm_write = fields.Boolean(string='Update')
    perm_unlink = fields.Boolean(string='Delete')

    apply_domain = fields.Boolean(
        string='Apply Filter',
        help="Limit the granted rights to the records matching the filter below.")
    domain = fields.Char(
        string='Filter', default='[]',
        help="Only records matching this filter are accessible. "
             "Dynamic values like user.id are supported (same as record rules).")

    @api.onchange('apply_domain')
    def _onchange_apply_domain(self):
        for line in self:
            if not line.apply_domain:
                line.domain = '[]'

    @api.onchange('perm_read')
    def _onchange_perm_read(self):
        for line in self:
            if not line.perm_read:
                line.perm_create = line.perm_write = line.perm_unlink = False

    @api.onchange('perm_create', 'perm_write', 'perm_unlink')
    def _onchange_other_perms(self):
        for line in self:
            if line.perm_create or line.perm_write or line.perm_unlink:
                line.perm_read = True


class AccessRightsNodeLine(models.Model):
    _name = 'access.rights.node.line'
    _inherit = 'access.rights.line.mixin'
    _description = 'Button/Tab Access Rule'

    button_node_ids = fields.Many2many(
        'access.rights.view.node', 'arm_node_line_button_rel', 'line_id', 'node_id',
        string='Hide Buttons',
        domain="[('model_id', '=', model_id), ('node_type', '=', 'button')]")
    page_node_ids = fields.Many2many(
        'access.rights.view.node', 'arm_node_line_page_rel', 'line_id', 'node_id',
        string='Hide Tabs',
        domain="[('model_id', '=', model_id), ('node_type', '=', 'page')]")
    link_node_ids = fields.Many2many(
        'access.rights.view.node', 'arm_node_line_link_rel', 'line_id', 'node_id',
        string='Hide Kanban Links',
        domain="[('model_id', '=', model_id), ('node_type', '=', 'link')]")

    @api.onchange('model_id')
    def _onchange_model_id_scan(self):
        """Scan the model's views once so buttons/tabs/links become selectable."""
        if self.model_id:
            self.env['access.rights.view.node']._scan_model_views(self.model_id)


class AccessRightsSearchLine(models.Model):
    _name = 'access.rights.search.line'
    _inherit = 'access.rights.line.mixin'
    _description = 'Filter/Group-By Access Rule'

    filter_node_ids = fields.Many2many(
        'access.rights.search.node', 'arm_search_line_filter_rel', 'line_id', 'node_id',
        string='Hide Filters',
        domain="[('model_id', '=', model_id), ('node_type', '=', 'filter')]")
    group_node_ids = fields.Many2many(
        'access.rights.search.node', 'arm_search_line_group_rel', 'line_id', 'node_id',
        string='Hide Group By',
        domain="[('model_id', '=', model_id), ('node_type', '=', 'group')]")

    @api.onchange('model_id')
    def _onchange_model_id_scan(self):
        if self.model_id:
            self.env['access.rights.search.node']._scan_model_search_views(self.model_id)


class AccessRightsChatterLine(models.Model):
    _name = 'access.rights.chatter.line'
    _inherit = 'access.rights.line.mixin'
    _description = 'Chatter Access Rule'

    hide_chatter = fields.Boolean(string='Hide Chatter')
    hide_send_mail = fields.Boolean(string='Hide Send Message')
    hide_log_notes = fields.Boolean(string='Hide Log Notes')
    hide_schedule_activity = fields.Boolean(string='Hide Activities')


class AccessRightsViewType(models.Model):
    _name = 'access.rights.view.type'
    _description = 'View Type'
    _order = 'name'

    name = fields.Char(required=True)
    technical_name = fields.Char(required=True)


class AccessRightsViewNode(models.Model):
    """Buttons, notebook pages and kanban links harvested from view archs."""
    _name = 'access.rights.view.node'
    _description = 'View Node'
    _rec_name = 'attribute_string'
    _order = 'attribute_string'

    model_id = fields.Many2one('ir.model', string='Model', required=True, index=True, ondelete='cascade')
    node_type = fields.Selection(
        [('button', 'Button'), ('page', 'Tab'), ('link', 'Kanban Link')],
        required=True, index=True)
    attribute_name = fields.Char(string='Technical Name')
    attribute_string = fields.Char(string='Label', required=True)
    button_type = fields.Selection([('object', 'Object'), ('action', 'Action')])
    is_smart_button = fields.Boolean(string='Smart Button')

    @api.depends('attribute_string', 'attribute_name', 'is_smart_button')
    def _compute_display_name(self):
        for node in self:
            name = node.attribute_string or node.attribute_name or ''
            if node.attribute_name and node.attribute_string:
                name = "%s (%s)" % (name, node.attribute_name)
            if node.is_smart_button:
                name = "%s [Smart]" % name
            node.display_name = name

    # -------------------------------------------------------------------
    # View scanning
    # -------------------------------------------------------------------
    def _node_exists(self, model_id, node_type, name, string):
        return bool(self.sudo().search_count([
            ('model_id', '=', model_id),
            ('node_type', '=', node_type),
            ('attribute_name', '=', name or False),
            ('attribute_string', '=', string),
        ]))

    def _store_node(self, model_id, node_type, name, string, button_type=False, smart=False):
        if string and not self._node_exists(model_id, node_type, name, string):
            self.sudo().create({
                'model_id': model_id,
                'node_type': node_type,
                'attribute_name': name or False,
                'attribute_string': string,
                'button_type': button_type or False,
                'is_smart_button': smart,
            })

    @api.model
    def _button_label(self, btn):
        """Best-effort human label of a <button> element."""
        label = btn.get('string')
        if label:
            return label
        # smart buttons: label lives in inner spans / o_stat_text elements
        texts = []
        for el in btn.findall('.//*'):
            if el.tag in ('span', 'field') and (el.get('class') or '').find('o_stat_value') != -1:
                continue
            if el.text and el.text.strip():
                texts.append(el.text.strip())
        if texts:
            return ' '.join(texts[:2])
        if btn.text and btn.text.strip():
            return btn.text.strip()
        return False

    @api.model
    def _scan_model_views(self, model):
        """Harvest buttons, tabs and kanban links from every form/tree/kanban
        view of `model` so managers can pick them from a list."""
        model_name = model.model
        if model_name not in self.env:
            return
        View = self.env['ir.ui.view'].sudo()
        for view_type in ('form', 'tree', 'kanban'):
            for view in View.search([('model', '=', model_name), ('type', '=', view_type)]):
                try:
                    res = self.env[model_name].sudo().get_view(view_id=view.id, view_type=view_type)
                    doc = etree.XML(res['arch'])
                except Exception:
                    continue
                smart_zone = doc.xpath("//div[@class='oe_button_box']")
                smart_buttons = set()
                if smart_zone:
                    smart_buttons = set(smart_zone[0].xpath(".//button[@type='object' or @type='action']"))
                for btn in doc.xpath("//button[@type='object' or @type='action']"):
                    label = self._button_label(btn)
                    if btn.get('name') and label:
                        self._store_node(model.id, 'button', btn.get('name'), label,
                                         button_type=btn.get('type'), smart=btn in smart_buttons)
                for link in doc.xpath("//a[@type]"):
                    label = (link.text or '').strip()
                    if link.get('name') and label:
                        self._store_node(model.id, 'link', link.get('name'), label,
                                         button_type=link.get('type'))
                if view_type == 'form':
                    for page in doc.xpath("//page"):
                        if page.get('string'):
                            self._store_node(model.id, 'page', page.get('name'), page.get('string'))


class AccessRightsSearchNode(models.Model):
    """Filters and group-bys harvested from search view archs."""
    _name = 'access.rights.search.node'
    _description = 'Search Node'
    _rec_name = 'attribute_string'
    _order = 'attribute_string'

    model_id = fields.Many2one('ir.model', string='Model', required=True, index=True, ondelete='cascade')
    node_type = fields.Selection([('filter', 'Filter'), ('group', 'Group By')], required=True, index=True)
    attribute_name = fields.Char(string='Technical Name')
    attribute_string = fields.Char(string='Label', required=True)

    @api.depends('attribute_string', 'attribute_name')
    def _compute_display_name(self):
        for node in self:
            name = node.attribute_string or node.attribute_name or ''
            if node.attribute_name and node.attribute_string:
                name = "%s (%s)" % (name, node.attribute_name)
            node.display_name = name

    def _store_node(self, model_id, node_type, name, string):
        if not (name and string):
            return
        exists = self.sudo().search_count([
            ('model_id', '=', model_id), ('node_type', '=', node_type),
            ('attribute_name', '=', name),
        ])
        if not exists:
            self.sudo().create({
                'model_id': model_id,
                'node_type': node_type,
                'attribute_name': name,
                'attribute_string': string,
            })

    @api.model
    def _scan_model_search_views(self, model):
        model_name = model.model
        if model_name not in self.env:
            return
        View = self.env['ir.ui.view'].sudo()
        for view in View.search([('model', '=', model_name), ('type', '=', 'search')]):
            try:
                arch, _view = self.env[model_name].sudo()._get_view(view_id=view.id, view_type='search')
            except Exception:
                continue
            # group-bys: <filter context="{'group_by': ...}"> inside <group>
            for group in arch.xpath("//group//filter"):
                if group.get('name') and group.get('string') and group.get('context'):
                    self._store_node(model.id, 'group', group.get('name'), group.get('string'))
            # plain filters: <filter> without a group_by context
            for flt in arch.xpath("//filter"):
                if flt.get('name') and flt.get('string') and not flt.get('context'):
                    if flt.get('invisible') in ('1', 'True', 'true'):
                        continue
                    self._store_node(model.id, 'filter', flt.get('name'), flt.get('string'))
