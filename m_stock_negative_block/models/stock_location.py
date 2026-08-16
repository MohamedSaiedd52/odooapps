# -*- coding: utf-8 -*-
from odoo import models, fields


class StockLocation(models.Model):
    _inherit = 'stock.location'

    allow_negative_stock = fields.Boolean(
        string='Allow Negative Stock',
        default=False,
        help='If checked, this location - and every location below it - is '
             'excluded from the negative stock validation: transfers may take '
             'goods out of it even when the resulting on-hand quantity becomes '
             'negative.'
    )

    def _is_negative_stock_allowed(self):
        """Return True when negative stock is tolerated for this location.

        The flag is inherited downwards: ticking it on ``WH/Stock`` also
        excludes every shelf underneath it, which is how people expect a
        warehouse-wide setting to behave.
        """
        self.ensure_one()
        location = self
        while location:
            if location.allow_negative_stock:
                return True
            location = location.location_id
        return False
