from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    quantity = fields.Float(
        digits=(16, 2),
    )