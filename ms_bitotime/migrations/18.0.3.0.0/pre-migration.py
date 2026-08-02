# The job queue engine (OCA queue_job) is now embedded inside ms_bitotime.
# When upgrading a database where the standalone queue_job module is
# installed, take over its records (channels, groups, subtype, cron, model
# metadata, ...) so the upgrade does not create duplicates and the existing
# jobs/channels keep working. Records whose xml_id is not re-declared by
# ms_bitotime (wizards, test job function, ...) are garbage-collected by
# Odoo at the end of the upgrade.
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "SELECT 1 FROM ir_module_module WHERE name = 'queue_job' "
        "AND state NOT IN ('uninstalled', 'uninstallable')"
    )
    if not cr.fetchone():
        return

    _logger.info("Merging standalone queue_job module into ms_bitotime")

    # Move every xml_id of queue_job to ms_bitotime, unless ms_bitotime
    # already owns an xml_id with the same name.
    cr.execute(
        """
        UPDATE ir_model_data d
        SET module = 'ms_bitotime'
        WHERE module = 'queue_job'
          AND NOT EXISTS (
              SELECT 1 FROM ir_model_data d2
              WHERE d2.module = 'ms_bitotime' AND d2.name = d.name
          )
        """
    )
    # Drop the few remaining duplicates (if any).
    cr.execute("DELETE FROM ir_model_data WHERE module = 'queue_job'")

    # The standalone module is superseded: mark it uninstalled so Odoo does
    # not try to load or upgrade it anymore.
    cr.execute(
        "UPDATE ir_module_module SET state = 'uninstalled' "
        "WHERE name = 'queue_job'"
    )
