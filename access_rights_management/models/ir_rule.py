# -*- coding: utf-8 -*-
import logging

from odoo import api, models
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

from .access_profile import PROTECTED_MODELS

_logger = logging.getLogger(__name__)


class IrRule(models.Model):
    _inherit = 'ir.rule'

    @api.model
    def _compute_domain(self, model_name, mode="read"):
        # 19.0 works with `Domain` objects instead of the list-of-tuples
        # domains and `odoo.osv.expression` of 18.0.
        # super() stays ormcached; this wrapper is evaluated per call so the
        # current user/company always get the right extra restriction.
        res = super()._compute_domain(model_name, mode)
        if (self.env.su
                or 'access.rights.profile' not in self.env
                or not self.pool.ready
                or model_name in PROTECTED_MODELS):
            return res

        try:
            lines = self.env['access.rights.profile']._get_domain_line_data(model_name)
        except Exception:
            return res
        if not lines:
            return res

        eval_context = None
        domains = []
        for line in lines:
            if not line[mode]:
                continue
            if line['apply_domain'] and line['domain'] and line['domain'] != '[]':
                if eval_context is None:
                    eval_context = self._eval_context()
                try:
                    domain = safe_eval(line['domain'], eval_context)
                    domains.append(Domain(domain) if domain else Domain.TRUE)
                except Exception:
                    _logger.warning(
                        "Invalid access-rights domain %r on model %s (profile %s): line skipped",
                        line['domain'], model_name, line['profile'])
                    domains.append(Domain.FALSE)
            else:
                domains.append(Domain.TRUE)

        extra = Domain.OR(domains) if domains else Domain.FALSE
        # AND with the standard record rules: a profile can only restrict
        # further, never widen what the base security allows.
        return (res if res is not None else Domain.TRUE) & extra
