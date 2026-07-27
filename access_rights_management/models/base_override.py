# -*- coding: utf-8 -*-
from odoo import api, models

from .access_profile import PROTECTED_MODELS


class Base(models.AbstractModel):
    _inherit = 'base'

    def _arm_profile(self):
        """Return the profile model when the app is usable in this env,
        else None (skip for superuser, module loading, protected models)."""
        if (self.env.su
                or 'access.rights.profile' not in self.env
                or not self.pool.ready
                or self._name in PROTECTED_MODELS):
            return None
        return self.env['access.rights.profile']

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        """Odoo caches postprocessed view archs across users. Our field/button/
        tab/chatter rules are per user+company, so profiled users must get their
        own cache entries. Users without a profile keep sharing the normal
        cache — no global cache flushes needed on page loads."""
        key = super()._get_view_cache_key(view_id, view_type, **options)
        profile = self._arm_profile()
        if profile is not None and profile._user_is_profiled():
            key = key + ('arm', self.env.uid, self.env.company.id)
        return key

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options)
        profile = self._arm_profile()
        if profile is None:
            return res
        model_flags = profile._get_model_flags(self._name)
        hidden_ids = set(model_flags['hidden_report_ids']) | set(model_flags['hidden_server_action_ids'])
        if not hidden_ids:
            return res
        for view_type in ('form', 'list', 'tree'):
            toolbar = res['views'].get(view_type, {}).get('toolbar')
            if toolbar:
                new_toolbar = dict(toolbar)
                for section in ('print', 'action'):
                    if new_toolbar.get(section):
                        new_toolbar[section] = [
                            entry for entry in new_toolbar[section]
                            if entry.get('id') not in hidden_ids
                        ]
                res['views'][view_type]['toolbar'] = new_toolbar
        return res

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        profile = self._arm_profile()
        if profile is None:
            return arch, view

        global_flags = profile._get_global_flags()
        model_flags = profile._get_model_flags(self._name)
        domain_lines = profile._get_domain_line_data(self._name)

        if view_type == 'form':
            hide_chatter = (
                global_flags['hide_chatter']
                or model_flags['restrict_chatter']
                or profile._get_chatter_rules(self._name)['hide_chatter']
            )
            if hide_chatter:
                for div in arch.xpath("//div[@class='oe_chatter']"):
                    div.getparent().remove(div)

        if view_type in ('tree', 'kanban'):
            if global_flags['hide_import'] or model_flags['restrict_import']:
                arch.attrib['import'] = 'false'
            if global_flags['hide_export'] or model_flags['restrict_export']:
                arch.attrib['export_xlsx'] = 'false'

        if view_type in ('form', 'tree', 'kanban'):
            if global_flags['readonly']:
                arch.attrib.update({'create': 'false', 'edit': 'false', 'delete': 'false'})
            else:
                create = edit = delete = None
                if model_flags['restrict_create']:
                    create = 'false'
                if model_flags['restrict_edit']:
                    edit = 'false'
                if model_flags['restrict_delete']:
                    delete = 'false'
                if domain_lines:
                    # rights granted by record rules drive the view buttons too
                    if not any(line['create'] for line in domain_lines):
                        create = 'false'
                    if not any(line['write'] for line in domain_lines):
                        edit = 'false'
                    if not any(line['unlink'] for line in domain_lines):
                        delete = 'false'
                if create:
                    arch.attrib['create'] = create
                if edit:
                    arch.attrib['edit'] = edit
                if delete:
                    arch.attrib['delete'] = delete

        return arch, view
