# -*- coding: utf-8 -*-
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _arm_hidden_menu_ids(self):
        if self.env.su or 'access.rights.profile' not in self.env or not self.pool.ready:
            return set()
        return set(self.env['access.rights.profile']._get_hidden_menu_ids())

    @api.model
    def _visible_menu_ids(self, debug=False):
        # super() stays ormcached per group set; we subtract per user+company
        # on every call, so no stale cross-user results.
        visible = super()._visible_menu_ids(debug=debug)
        hidden = self._arm_hidden_menu_ids()
        if hidden:
            visible = visible - hidden
        return visible

    @api.model
    def load_menus(self, debug):
        menus = super().load_menus(debug)
        hidden = self._arm_hidden_menu_ids()
        if not hidden:
            return menus
        # super()'s result is ormcached: never mutate it, build a filtered copy
        filtered = {}
        for key, item in menus.items():
            if key in hidden:
                continue
            item = dict(item)
            if item.get('children'):
                item['children'] = [c for c in item['children'] if c not in hidden]
            filtered[key] = item
        return filtered
