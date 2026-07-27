# -*- coding: utf-8 -*-
"""Drop the retired access.rights.department model and table if the standard
model cleanup has not already removed them (belt-and-suspenders; idempotent)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("DELETE FROM ir_model_fields WHERE model = 'access.rights.department'")
    cr.execute("DELETE FROM ir_model WHERE model = 'access.rights.department'")
    cr.execute("DROP TABLE IF EXISTS access_rights_department CASCADE")
    _logger.info("ARM: retired access.rights.department model/table removed.")
