# Runs at the very end of the upgrade. During the upgrade that merges
# queue_job into ms_bitotime, the old (still loaded) queue_job package
# re-creates a few of its own ir_model_data rows (field selection / model
# inherit entries). Drop them so nothing remains owned by the old module.


def migrate(cr, version):
    cr.execute("DELETE FROM ir_model_data WHERE module = 'queue_job'")
