# -*- coding: utf-8 -*-
import logging

from odoo import api, models, _
from odoo.exceptions import AccessError

from .access_profile import PROTECTED_MODELS, READONLY_SAFE_MODELS

_logger = logging.getLogger(__name__)


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    def check(self, model, mode='read', raise_exception=True):
        if (self.env.su
                or 'access.rights.profile' not in self.env
                or not self.pool.ready
                or model in PROTECTED_MODELS
                or model not in self.env):
            return super().check(model, mode, raise_exception)

        profile = self.env['access.rights.profile']
        try:
            flags = profile._get_global_flags()
            lines = profile._get_domain_line_data(model)
        except Exception:
            # never break ACL checking because of a half-installed state
            return super().check(model, mode, raise_exception)

        # Read-only user: block everything but read, system-wide.
        if flags['readonly'] and mode != 'read' and model not in READONLY_SAFE_MODELS:
            if raise_exception:
                raise AccessError(_(
                    "You are a read-only user: you are not allowed to %(mode)s "
                    "'%(model)s' records.\n"
                    "(Blocked by an Access Rights profile — contact your administrator.)",
                    mode=mode, model=model))
            return False

        # Record rules defined in a profile grant/deny model-level access:
        # they replace the group-based ACL for that model.
        if lines:
            if any(line[mode] for line in lines):
                return True
            if raise_exception:
                profiles = ', '.join(sorted({line['profile'] for line in lines}))
                _logger.info(
                    'Access denied by access-rights profile for operation: %s, uid: %s, model: %s',
                    mode, self.env.uid, model)
                raise AccessError(_(
                    "You are not allowed to %(mode)s '%(model)s' records.\n"
                    "Blocked by Access Rights profile(s): %(profiles)s.\n"
                    "Contact your administrator to request access if necessary.",
                    mode=mode, model=model, profiles=profiles))
            return False

        return super().check(model, mode, raise_exception)
