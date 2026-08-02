# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# a device that reported activity within this window is considered online
ONLINE_WINDOW_MINUTES = 30


class BioTimeTerminal(models.Model):
    _name = 'biotime.terminal'
    _description = "Biotime Terminal"

    name = fields.Char(string="Name")
    terminal_id = fields.Char(string="Terminal ID")
    terminal_sn = fields.Char(string="Terminal SN")
    ip_address = fields.Char(string="IP Address")
    alias = fields.Char(string="Alias")
    terminal_tz = fields.Char(string="Terminal TZ")
    biotime_id = fields.Many2one('biotime.config', string="Biotime")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company.id)
    last_activity = fields.Datetime(
        string="Last Activity", readonly=True,
        help="Last time the device talked to the BioTime server. "
             "Refreshed by the 'Get Devices' button.")
    device_state = fields.Char(string="Raw State", readonly=True)
    is_online = fields.Boolean(
        string="Online", compute="_compute_is_online",
        help="True when the device reported activity in the last %s minutes "
             "(as of the last device refresh)." % ONLINE_WINDOW_MINUTES)

    def _compute_is_online(self):
        threshold = fields.Datetime.now() - timedelta(minutes=ONLINE_WINDOW_MINUTES)
        for rec in self:
            rec.is_online = bool(rec.last_activity and rec.last_activity >= threshold)

    def action_refresh_status(self):
        """Re-fetch all devices of the parent server (upserts info + status)."""
        servers = self.mapped('biotime_id')
        servers.action_get_all_terminals()
