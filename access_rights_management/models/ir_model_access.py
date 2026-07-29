# -*- coding: utf-8 -*-
import logging

from odoo import api, models, _
from odoo.exceptions import AccessError

from .access_profile import PROTECTED_MODELS, READONLY_SAFE_MODELS

_logger = logging.getLogger(__name__)


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    def _arm_verdict(self, model, mode):
        """What this app has to say about `mode` on `model` for the current user.

        Returns ``(verdict, message)``:

        * ``(True, None)``  — a profile record rule grants the access outright
          (it replaces the group-based ACL for that model);
        * ``(False, msg)``  — a profile denies it, `msg` says which one and why;
        * ``(None, None)``  — nothing to say, the standard ACL decides.
        """
        if (self.env.su
                or 'access.rights.profile' not in self.env
                or not self.pool.ready
                or model in PROTECTED_MODELS
                or model not in self.env):
            return None, None

        profile = self.env['access.rights.profile']
        try:
            flags = profile._get_global_flags()
            lines = profile._get_domain_line_data(model)
        except Exception:
            # never break ACL checking because of a half-installed state
            return None, None

        # Read-only user: block everything but read, system-wide.
        if flags['readonly'] and mode != 'read' and model not in READONLY_SAFE_MODELS:
            return False, _(
                "You are a read-only user: you are not allowed to %(mode)s "
                "'%(model)s' records.\n"
                "(Blocked by an Access Rights profile — contact your administrator.)",
                mode=mode, model=model)

        # Record rules defined in a profile grant/deny model-level access:
        # they replace the group-based ACL for that model.
        if lines:
            if any(line[mode] for line in lines):
                return True, None
            return False, _(
                "You are not allowed to %(mode)s '%(model)s' records.\n"
                "Blocked by Access Rights profile(s): %(profiles)s.\n"
                "Contact your administrator to request access if necessary.",
                mode=mode, model=model,
                profiles=', '.join(sorted({line['profile'] for line in lines})))

        return None, None

    def _arm_log_denied(self, model, mode):
        _logger.info(
            'Access denied by access-rights profile for operation: %s, uid: %s, model: %s',
            mode, self.env.uid, model)

    @api.model
    def check(self, model, mode='read', raise_exception=True):
        verdict, message = self._arm_verdict(model, mode)
        if verdict is True:
            return True
        if verdict is False:
            if raise_exception:
                self._arm_log_denied(model, mode)
                raise AccessError(message)
            return False
        return super().check(model, mode, raise_exception)

    def _make_access_error(self, model, mode):
        """18.0 asks for the message separately from the decision.

        `BaseModel._check_access` calls `check(..., raise_exception=False)` and
        then builds the exception itself, so without this override a user
        blocked by a profile is told to ask for a security group — a group that
        would not lift the block, because it does not come from the ACL.
        """
        verdict, message = self._arm_verdict(model, mode)
        if verdict is False:
            self._arm_log_denied(model, mode)
            return AccessError(message)
        return super()._make_access_error(model, mode)
