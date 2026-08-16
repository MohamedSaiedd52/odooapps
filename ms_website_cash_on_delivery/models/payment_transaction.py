# -*- coding: utf-8 -*-
from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _set_pending(self, *args, **kwargs):
        """Flag COD orders and apply the configured COD fee.

        Cash on Delivery rides the custom-provider flow: the transaction is
        set to pending and the order is confirmed. This is the single hook
        every version (17/18/19) goes through.
        """
        txs = super()._set_pending(*args, **kwargs)
        for tx in self.filtered(
                lambda t: t.provider_id.custom_mode == 'cash_on_delivery'):
            orders = tx.sale_order_ids.sudo()
            orders.filtered(lambda o: not o.is_cod_order).write(
                {'is_cod_order': True})
            for order in orders:
                order._ms_apply_cod_fee(tx.provider_id)
        return txs
