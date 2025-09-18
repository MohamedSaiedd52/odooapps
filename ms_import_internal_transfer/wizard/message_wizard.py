# -*- coding: utf-8 -*-
from odoo import models, fields, _


class ImportTransferMessageWizard(models.TransientModel):
    _name = 'import.transfer.message.wizard'
    _description = 'Import Result Message'

    message = fields.Text(string='Message', readonly=True)

    def action_ok(self):
        return {'type': 'ir.actions.act_window_close'}
