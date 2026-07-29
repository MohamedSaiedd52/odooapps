# -*- coding: utf-8 -*-
import json
import logging

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.web.controllers.action import Action
from odoo.addons.web.controllers.export import Export, CSVExport, ExcelExport
from odoo.addons.web.controllers.home import Home

from odoo.addons.access_rights_management.models.access_profile import PROTECTED_MODELS

_logger = logging.getLogger(__name__)


def _arm_log_export(data, export_format):
    """Audit one export request (best-effort, never breaks the download).

    `data` is the very payload the web client posted, so it already carries
    the exported columns with their labels and — thanks to this module's
    export patch — the screen and saved template they came from.
    """
    try:
        if not _arm_available():
            return
        params = json.loads(data)
        model = params.get('model')
        if not model or model in PROTECTED_MODELS or 'access.rights.export.log' not in request.env:
            return
        ids = params.get('ids')
        if ids:
            count = len(ids)
        else:
            count = request.env[model].sudo().with_context(
                active_test=False).search_count(params.get('domain') or [])
        fields_info = [{
            'name': field.get('name'),
            'label': field.get('label'),
            'type': field.get('type'),
        } for field in params.get('fields') or [] if field.get('name')]
        origin = params.get('arm_origin') or {}
        if isinstance(origin, dict):
            origin.setdefault('scope', 'selected' if ids else 'filtered')
            origin.setdefault('import_compat', params.get('import_compat'))
        request.env['access.rights.export.log'].sudo()._log_export(
            model, count, None, export_format,
            ip=request.httprequest.remote_addr,
            fields_info=fields_info, origin=origin)
    except Exception:
        _logger.exception("Could not audit a data export")


def _arm_available():
    return (request.session.uid
            and 'access.rights.profile' in request.env
            and request.env.registry.ready)


def _arm_filter_action_views(action):
    """Drop the view types a profile hides from an act_window action dict."""
    if not (isinstance(action, dict) and action.get('res_model') and action.get('views')):
        return action
    model_name = action['res_model']
    if model_name in PROTECTED_MODELS:
        return action
    profile = request.env['access.rights.profile']
    hidden_types = set(profile._get_model_flags(model_name)['hidden_view_types'])
    if not hidden_types:
        return action
    # 'tree' and 'list' name the same view type: 18.0 says 'list', but rules
    # configured before the upgrade may still carry the old spelling
    if hidden_types & {'tree', 'list'}:
        hidden_types |= {'tree', 'list'}
    remaining = [view for view in action['views'] if view[1] not in hidden_types]
    if not remaining:
        raise UserError(_(
            "You don't have permission to open any view of this document. "
            "Please contact your administrator."))
    action = dict(action, views=remaining)
    if action.get('view_mode'):
        modes = [m for m in action['view_mode'].split(',') if m not in hidden_types]
        action['view_mode'] = ','.join(modes) or action['view_mode']
    return action


class ArmAction(Action):

    @http.route('/web/action/load', type='jsonrpc', auth='user', readonly=True)
    def load(self, action_id, context=None):
        action = super().load(action_id, context=context)
        if action and _arm_available() and not request.env.su:
            action = _arm_filter_action_views(action)
        return action

    @http.route('/web/action/run', type='jsonrpc', auth='user')
    def run(self, action_id, context=None):
        action = super().run(action_id, context=context)
        if action and _arm_available() and not request.env.su:
            action = _arm_filter_action_views(action)
        return action


class ArmExport(Export):

    @http.route('/web/export/get_fields', type='jsonrpc', auth='user', readonly=True)
    def get_fields(self, model, domain, **kwargs):
        """Drop the fields a profile hides from the export field selector.

        18.0 builds the list inside `get_fields` (the 17.0 `fields_get` helper
        is gone), so the filtering happens on the returned entries. Each entry
        carries the full path in 'id' ('partner_id/name' when expanding a
        relation), and `model` is always the model those leaves belong to.
        """
        fields = super().get_fields(model, domain, **kwargs)
        if not _arm_available() or request.env.su or model in PROTECTED_MODELS:
            return fields
        hidden = set(request.env['access.rights.profile'].get_hidden_fields(model))
        hidden.discard('id')
        if not hidden:
            return fields
        return [field for field in fields
                if str(field.get('id') or '').rsplit('/', 1)[-1] not in hidden]


class ArmCSVExport(CSVExport):

    @http.route()
    def web_export_csv(self, data):
        response = super().web_export_csv(data)
        _arm_log_export(data, 'csv')
        return response


class ArmExcelExport(ExcelExport):

    @http.route()
    def web_export_xlsx(self, data):
        response = super().web_export_xlsx(data)
        _arm_log_export(data, 'xlsx')
        return response


class ArmHome(Home):

    # same route set as 18.0's Home.web_client — re-declaring only '/web'
    # would leave '/odoo' (the real web client entry point) unpatched
    @http.route(['/web', '/odoo', '/odoo/<path:subpath>', '/scoped_app/<path:subpath>'],
                type='http', auth='none', readonly=Home._web_client_readonly)
    def web_client(self, s_action=None, **kw):
        # Force developer mode off for restricted users.
        try:
            if _arm_available():
                env = request.env(user=request.session.uid)
                if 'access.rights.profile' in env:
                    flags = env['access.rights.profile']._get_global_flags()
                    if flags['disable_debug_mode'] and (request.session.debug or kw.get('debug')):
                        request.session.debug = ''
                        if kw.get('debug') and kw.get('debug') != '0':
                            # stay on the path the user asked for ('/odoo/...'),
                            # only strip the debug flag
                            return request.redirect_query(
                                request.httprequest.path,
                                query=dict(request.params, debug='0'))
        except Exception:
            # the debug guard must never block the web client
            pass
        return super().web_client(s_action=s_action, **kw)
