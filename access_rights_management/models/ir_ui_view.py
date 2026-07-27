# -*- coding: utf-8 -*-
import ast

from odoo import models
from odoo.http import request

from .access_profile import PROTECTED_MODELS


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    def _arm_request_profile(self, name_manager):
        model_name = name_manager.model._name
        if ('access.rights.profile' not in self.env
                or not self.pool.ready
                or model_name in PROTECTED_MODELS):
            return None, model_name
        env = self.env
        if env.su:
            # View postprocessing runs on a sudo'd ir.ui.view recordset
            # (see BaseModel._get_view): recover the real user environment
            # from the HTTP request; outside a request (cron, shell as
            # superuser) there is nobody to restrict.
            if request and getattr(request, 'env', None) is not None \
                    and request.env.uid and not request.env.su:
                env = request.env
            else:
                return None, model_name
        return env['access.rights.profile'], model_name

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    def _postprocess_tag_field(self, node, name_manager, node_info):
        super()._postprocess_tag_field(node, name_manager, node_info)
        profile, model_name = self._arm_request_profile(name_manager)
        if profile is None:
            return
        rules = profile._get_field_rules(model_name)
        rule = rules.get(node.get('name'))
        if not rule:
            return
        invisible, readonly, required, no_link = rule
        if invisible:
            node.set('invisible', '1')
            node.set('column_invisible', 'True')
            node_info['invisible'] = True
            node_info['column_invisible'] = True
        if readonly:
            node.set('readonly', '1')
            node.set('force_save', '1')
            node_info['readonly'] = True
        if required:
            node.set('required', '1')
            node_info['required'] = True
        if no_link:
            options = {}
            if node.get('options'):
                try:
                    options = ast.literal_eval(node.get('options'))
                except (ValueError, SyntaxError):
                    options = {}
            options.update({'no_create': True, 'no_edit': True, 'no_open': True, 'no_quick_create': True})
            node.set('options', str(options))
            if node.get('widget') in ('product_configurator', 'many2one_avatar_user'):
                del node.attrib['widget']

    def _postprocess_tag_label(self, node, name_manager, node_info):
        super()._postprocess_tag_label(node, name_manager, node_info)
        profile, model_name = self._arm_request_profile(name_manager)
        if profile is None or not node.get('for'):
            return
        rule = profile._get_field_rules(model_name).get(node.get('for'))
        if rule and rule[0]:  # invisible
            node.set('invisible', '1')
            node_info['invisible'] = True

    # ------------------------------------------------------------------
    # Buttons / tabs / kanban links (no postprocessor exists in core for
    # these tags: defining the method registers it in the dispatcher)
    # ------------------------------------------------------------------
    def _arm_hide_node(self, node, node_info):
        node.set('invisible', '1')
        node.attrib.pop('attrs', None)
        node_info['invisible'] = True

    def _postprocess_tag_button(self, node, name_manager, node_info):
        parent = getattr(super(), '_postprocess_tag_button', None)
        if parent:
            parent(node, name_manager, node_info)
        profile, model_name = self._arm_request_profile(name_manager)
        if profile is None:
            return
        hidden = profile._get_hidden_nodes(model_name)['button']
        if node.get('name') and node.get('name') in hidden:
            self._arm_hide_node(node, node_info)

    def _postprocess_tag_page(self, node, name_manager, node_info):
        parent = getattr(super(), '_postprocess_tag_page', None)
        if parent:
            parent(node, name_manager, node_info)
        profile, model_name = self._arm_request_profile(name_manager)
        if profile is None:
            return
        hidden = profile._get_hidden_nodes(model_name)['page']
        if (node.get('name') and node.get('name') in hidden) or \
                (node.get('string') and node.get('string') in hidden):
            self._arm_hide_node(node, node_info)

    def _postprocess_tag_a(self, node, name_manager, node_info):
        parent = getattr(super(), '_postprocess_tag_a', None)
        if parent:
            parent(node, name_manager, node_info)
        profile, model_name = self._arm_request_profile(name_manager)
        if profile is None:
            return
        hidden = profile._get_hidden_nodes(model_name)['link']
        if node.get('name') and node.get('name') in hidden:
            self._arm_hide_node(node, node_info)

    # ------------------------------------------------------------------
    # Search view filters & group-bys
    # ------------------------------------------------------------------
    def _postprocess_tag_filter(self, node, name_manager, node_info):
        parent = getattr(super(), '_postprocess_tag_filter', None)
        if parent:
            parent(node, name_manager, node_info)
        profile, model_name = self._arm_request_profile(name_manager)
        if profile is None or not node.get('name'):
            return
        hidden = profile._get_hidden_search_nodes(model_name)
        if node.get('name') in hidden['filter'] or node.get('name') in hidden['group']:
            node.set('invisible', '1')
            node_info['invisible'] = True
