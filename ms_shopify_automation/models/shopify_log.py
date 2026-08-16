from odoo import models, fields, api

class ShopifyLog(models.Model):
    _name = 'shopify.log'
    _description = 'Shopify Sync Log'
    _order = 'create_date desc'

    name = fields.Char('Log Name')
    log_type = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ], string='Log Type', default='info')
    job_id = fields.Many2one('shopify.queue.job', string='Related Job')
    message = fields.Text('Message')
    create_date = fields.Datetime('Created On', readonly=True)
    write_date = fields.Datetime('Last Updated', readonly=True)
    note = fields.Text('Notes')

    @api.model
    def _cron_cleanup_old_logs(self, days=30):
        """Cron job to cleanup old logs"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff_date)])
        count = len(old_logs)
        old_logs.unlink()
        return count 