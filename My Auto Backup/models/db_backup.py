#############################################################################
#
#      Eng Mohamed Saied 
#
#############################################################################


from odoo import api, fields, models, _
from odoo.service import db
from odoo.exceptions import ValidationError, UserError
import os
import datetime
import logging
import time

_logger = logging.getLogger(__name__)

class DbBackupConfigure(models.Model):
    _name = 'db.backup.configure'
    _description = 'Database Backup Configuration'

    name = fields.Char(string='Name', required=True)
    db_name = fields.Char(string='Database Name', required=True)
    master_pwd = fields.Char(string='Master Password', required=True)
    backup_format = fields.Selection([('zip', 'Zip'), ('dump', 'Dump')], required=True, default='zip')
    backup_destination = fields.Selection([('local', 'Local Storage')], required=True)
    backup_path = fields.Char(string='Backup Path')
    active = fields.Boolean(default=True)
    auto_remove = fields.Boolean(string='Auto Remove Old Backups')
    days_to_remove = fields.Integer(string='Days to Retain Backups')
    backup_filename = fields.Char(string='Generated Filename')
    generated_exception = fields.Text(string='Exception Details')
    last_backup_status = fields.Selection([('success', 'Success'), ('failure', 'Failure')], string="Last Backup Status")
    backup_progress = fields.Integer(string="Backup Progress (%)", default=0)

    @api.constrains('db_name', 'master_pwd')
    def _check_db_credentials(self):
        """Check if database credentials are valid."""
        if self.db_name not in db.list_dbs():
            raise ValidationError(_("Database %s does not exist.") % self.db_name)
        try:
            db.check_super(self.master_pwd)
        except Exception as e:
            raise ValidationError(_("Master Password is invalid. Error: %s") % e)

    @api.constrains('backup_path')
    def _check_backup_path(self):
        """Ensure the backup path is a valid directory."""
        if self.backup_path and not os.path.isdir(self.backup_path):
            raise ValidationError(_("Backup path '%s' is not a valid directory.") % self.backup_path)

    def _generate_backup(self):
        """Generate a backup for this record with real-time progress."""
        if self.backup_destination == 'local' and not self.backup_path:
            raise UserError(_("Backup path is required for local storage."))

        backup_time = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"{self.db_name}_{backup_time}.{self.backup_format}"
        self.backup_filename = backup_filename
        backup_file = os.path.join(self.backup_path, backup_filename)
        self.backup_progress = 0

        try:
            os.makedirs(self.backup_path, exist_ok=True)
            total_steps = 10
            for i in range(1, total_steps + 1):
                time.sleep(1)  # Simulate progress
                self.backup_progress = int((i / total_steps) * 100)
            self.backup_progress = 100
            with open(backup_file, "wb") as f:
                db.dump_db(self.db_name, f, self.backup_format)

            if self.auto_remove:
                self._remove_old_backups()

            self.env['db.backup.log'].create({
                'db_config_id': self.id,
                'status': 'success',
                'details': "Backup completed successfully.",
                'file_path': backup_file,
            })
            self.last_backup_status = 'success'
        except Exception as e:
            self.backup_progress = 0
            _logger.error("Backup failed for database %s: %s", self.db_name, e)
            self.generated_exception = str(e)
            self.env['db.backup.log'].create({
                'db_config_id': self.id,
                'status': 'failure',
                'details': str(e),
            })
            self.last_backup_status = 'failure'

    def _remove_old_backups(self):
        """Remove old backups based on the retention policy."""
        if not self.auto_remove or not self.days_to_remove:
            return
        try:
            now = datetime.datetime.utcnow()
            for filename in os.listdir(self.backup_path):
                file_path = os.path.join(self.backup_path, filename)
                if os.path.isfile(file_path):
                    if filename.endswith(f".{self.backup_format}") and filename.startswith(self.db_name):
                        creation_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
                        if (now - creation_time).days > self.days_to_remove:
                            os.remove(file_path)
        except Exception as e:
            _logger.error("Error removing old backups: %s", e)

    def _schedule_auto_backup(self):
        """Method to trigger automatic database backup for active records."""
        active_records = self.search([('active', '=', True)])
        for record in active_records:
            try:
                record._generate_backup()
                _logger.info("Backup successfully created for database: %s", record.db_name)
            except Exception as e:
                _logger.error("Failed to create backup for database %s: %s", record.db_name, e)


class DbBackupLog(models.Model):
    _name = 'db.backup.log'
    _description = 'Database Backup Log'

    db_config_id = fields.Many2one('db.backup.configure', string="Configuration")
    backup_date = fields.Datetime(string="Backup Date", default=fields.Datetime.now)
    status = fields.Selection([('success', 'Success'), ('failure', 'Failure')], string="Status")
    details = fields.Text(string="Details")
    file_path = fields.Char(string="File Path")
    file_size = fields.Float(string="File Size (MB)", compute="_compute_file_size")

    def _compute_file_size(self):
        for record in self:
            if record.file_path and os.path.isfile(record.file_path):
                record.file_size = os.path.getsize(record.file_path) / (1024 * 1024)
            else:
                record.file_size = 0

    def download_backup(self):
        """Download the backup file."""
        self.ensure_one()
        if self.file_path and os.path.isfile(self.file_path):
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content?model=db.backup.log&id={self.id}&field=file_path&download=true',
                'target': 'self',
            }
        else:
            raise UserError(_("Backup file not found."))

    def delete_backup(self):
        """Delete the backup file."""
        self.ensure_one()
        if self.file_path and os.path.isfile(self.file_path):
            os.remove(self.file_path)
            self.file_path = False
        else:
            raise UserError(_("Backup file not found or already deleted."))
