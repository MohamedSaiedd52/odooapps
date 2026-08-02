# -*- coding: utf-8 -*-
from datetime import timedelta

import pytz

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class BioTimePullWizard(models.TransientModel):
    _name = 'biotime.pull.wizard'
    _description = "Pull BioTime Transactions (Advanced)"

    server_id = fields.Many2one(
        'biotime.config', string="Server", required=True,
        default=lambda self: self.env['biotime.config'].search([], limit=1))
    terminal_ids = fields.Many2many(
        'biotime.terminal', string="Devices",
        domain="[('biotime_id', '=', server_id)]",
        help="Leave empty to pull from all devices.")
    bio_employee_id = fields.Many2one(
        'biotime.employee', string="Single Employee",
        domain="[('biotime_id', '=', server_id)]",
        help="Leave empty to pull all employees. Set it to re-pull the "
             "punches of one employee only (e.g. after fixing their ZK code).")
    from_date = fields.Datetime(
        string="From", required=True,
        default=lambda self: fields.Datetime.now() - timedelta(days=3))
    to_date = fields.Datetime(
        string="To", required=True,
        default=fields.Datetime.now)
    do_transfer = fields.Boolean(
        string="Transfer to Attendance after pull", default=True)

    @api.constrains('from_date', 'to_date')
    def _check_dates(self):
        for rec in self:
            if rec.from_date >= rec.to_date:
                raise UserError(_("'From' must be before 'To'."))

    def action_pull(self):
        self.ensure_one()
        server = self.server_id
        tz = pytz.timezone(server.tz or 'UTC')
        # Datetime fields are UTC; the BioTime API expects server-local times
        from_local = pytz.utc.localize(self.from_date).astimezone(tz).replace(tzinfo=None)
        to_local = pytz.utc.localize(self.to_date).astimezone(tz).replace(tzinfo=None)

        before = server.transaction_count
        server.action_pull_raw_transactions(
            from_date=from_local, to_date=to_local,
            terminals=self.terminal_ids or None,
            emp_code=self.bio_employee_id.emp_code or None)
        if self.do_transfer:
            server.action_transfer_transition(
                from_date=self.from_date, to_date=self.to_date,
                raise_if_empty=False)
        pulled = server.transaction_count - before
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Pull finished"),
                'message': _(
                    "%(count)s new punch(es) imported%(transfer)s.",
                    count=pulled,
                    transfer=_(" and transferred to attendance")
                    if self.do_transfer else ""),
                'type': 'success' if pulled else 'info',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
