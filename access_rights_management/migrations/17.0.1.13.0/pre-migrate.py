# -*- coding: utf-8 -*-
"""access.rights.profile.department_id switched comodel from the app's own
access.rights.department to the real hr.department. Remap the stored foreign
keys by department name (any translation), and clear the old model's data so
the standard stale-data cleanup does not try to unlink records of a model that
no longer exists.
"""
import logging

_logger = logging.getLogger(__name__)


def _values(name):
    """Yield every string a translated (jsonb) or plain name may hold."""
    if not name:
        return
    if isinstance(name, dict):
        for value in name.values():
            if value:
                yield value
    else:
        yield name


def _norm(text):
    return ' '.join((text or '').split()).strip().lower()


def migrate(cr, version):
    cr.execute("SELECT to_regclass('public.access_rights_department')")
    if not cr.fetchone()[0]:
        return  # nothing to migrate (fresh install path)

    # old department id -> name
    cr.execute("SELECT id, name FROM access_rights_department")
    old_names = {row[0]: row[1] for row in cr.fetchall()}

    # hr.department: every name translation -> id (first match wins)
    cr.execute("SELECT id, name FROM hr_department")
    hr_by_name = {}
    for hid, hname in cr.fetchall():
        for value in _values(hname):
            hr_by_name.setdefault(_norm(value), hid)

    cr.execute(
        "SELECT id, department_id FROM access_rights_profile "
        "WHERE department_id IS NOT NULL")
    remapped = cleared = 0
    for profile_id, old_dep in cr.fetchall():
        new_id = None
        for value in _values(old_names.get(old_dep)):
            new_id = hr_by_name.get(_norm(value))
            if new_id:
                break
        cr.execute(
            "UPDATE access_rights_profile SET department_id = %s WHERE id = %s",
            (new_id, profile_id))
        if new_id:
            remapped += 1
        else:
            cleared += 1
    _logger.info("ARM department migration: %s profile(s) remapped to "
                 "hr.department, %s cleared (no name match).", remapped, cleared)

    # drop the old model's records + xmlids so _process_end skips them
    cr.execute("DELETE FROM ir_model_data WHERE module = 'access_rights_management' "
               "AND model = 'access.rights.department'")
    cr.execute("DELETE FROM access_rights_department")
