# -*- coding: utf-8 -*-
"""17.0 → 18.0.

Odoo 18 renamed the list view type from 'tree' to 'list'. Two places in this
module stored the old spelling and are not refreshed by the data files
(`view_type_data.xml` is noupdate):

1. `access.rights.view.type.technical_name` — the value a "Hide Views" rule is
   matched on;
2. `access.rights.view.node.node_type` is unaffected, but the buttons/tabs
   harvested from list views were stored while scanning `type = 'tree'` views;
   nothing to do there, the rows are keyed by model, not by view type.

Actions stored on this module's own records use `view_mode`, which Odoo's own
upgrade rewrites.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('public.access_rights_view_type')")
    if not cr.fetchone()[0]:
        return
    cr.execute("""
        UPDATE access_rights_view_type
           SET technical_name = 'list'
         WHERE technical_name = 'tree'
    """)
    if cr.rowcount:
        _logger.info("ARM: %s view type(s) renamed from 'tree' to 'list'", cr.rowcount)
