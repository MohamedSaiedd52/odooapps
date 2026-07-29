# -*- coding: utf-8 -*-
"""MAC addresses are gone from the login audit (v2.2.0).

A MAC never crosses a router, so the column was empty for everyone who is not
on the server's own subnet — and it was the key devices were matched on. From
now on a device is recognised by a cookie it carries, with the browser
fingerprint (hash of the User-Agent) as the fallback key.

This migration:

1. backfills `fingerprint` from the User-Agent already stored on each device,
   so a **blocked** device stays blocked after the upgrade instead of being
   silently re-created as a brand-new, allowed device;
2. merges the device rows that only differed by MAC (same user, same browser,
   same IP), keeping the strictest status and every login they point to;
3. drops the three now-unused `mac_address` columns.
"""
import hashlib
import logging

_logger = logging.getLogger(__name__)


def _fingerprint(user_agent):
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode('utf-8', 'replace')).hexdigest()[:32]


def _backfill_fingerprints(cr):
    cr.execute("SELECT id, user_agent FROM access_rights_device "
               "WHERE fingerprint IS NULL AND user_agent IS NOT NULL")
    rows = cr.fetchall()
    for device_id, user_agent in rows:
        cr.execute("UPDATE access_rights_device SET fingerprint = %s WHERE id = %s",
                   (_fingerprint(user_agent), device_id))
    _logger.info("ARM: fingerprint backfilled on %s device(s)", len(rows))


def _merge_duplicate_devices(cr):
    """Same user + same browser + same IP used to be several rows when the ARP
    table handed out a MAC only some of the time. Keep one."""
    cr.execute("""
        SELECT user_id, fingerprint, ip_address, array_agg(id ORDER BY login_count DESC, id)
          FROM access_rights_device
         WHERE fingerprint IS NOT NULL
      GROUP BY user_id, fingerprint, ip_address
        HAVING count(*) > 1
    """)
    merged = 0
    for _user_id, _fingerprint_value, _ip, ids in cr.fetchall():
        keeper, duplicates = ids[0], ids[1:]
        cr.execute("SELECT state, login_count, first_seen, last_seen, device_token "
                   "FROM access_rights_device WHERE id = ANY(%s)", (ids,))
        rows = cr.fetchall()
        states = {row[0] for row in rows}
        state = ('blocked' if 'blocked' in states
                 else 'trusted' if 'trusted' in states else 'normal')
        token = next((row[4] for row in rows if row[4]), None)
        cr.execute("""
            UPDATE access_rights_device
               SET state = %s,
                   device_token = COALESCE(device_token, %s),
                   login_count = (SELECT COALESCE(sum(login_count), 0)
                                    FROM access_rights_device WHERE id = ANY(%s)),
                   first_seen = (SELECT min(first_seen)
                                   FROM access_rights_device WHERE id = ANY(%s)),
                   last_seen = (SELECT max(last_seen)
                                  FROM access_rights_device WHERE id = ANY(%s))
             WHERE id = %s
        """, (state, token, ids, ids, ids, keeper))
        cr.execute("UPDATE access_rights_login_log SET device_id = %s "
                   "WHERE device_id = ANY(%s)", (keeper, duplicates))
        cr.execute("UPDATE access_rights_anomaly SET device_id = %s "
                   "WHERE device_id = ANY(%s)", (keeper, duplicates))
        cr.execute("DELETE FROM access_rights_device WHERE id = ANY(%s)", (duplicates,))
        merged += len(duplicates)
    if merged:
        _logger.info("ARM: %s duplicate device row(s) merged", merged)


def _drop_mac_columns(cr):
    """Odoo cleans the `ir.model.fields` metadata of a removed field on its
    own but leaves the column in place; drop it here so no copy of the data
    survives the upgrade."""
    for table in ('access_rights_device', 'access_rights_login_log',
                  'access_rights_anomaly'):
        cr.execute("ALTER TABLE %s DROP COLUMN IF EXISTS mac_address" % table)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('public.access_rights_device')")
    if not cr.fetchone()[0]:
        return
    _backfill_fingerprints(cr)
    _merge_duplicate_devices(cr)
    _drop_mac_columns(cr)
