# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.fields import Command


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_cod_order = fields.Boolean(
        string="Cash on Delivery", copy=False,
        help="This order was placed with the Cash on Delivery payment method.")
    cod_fee_amount = fields.Monetary(
        string="COD Fee", copy=False,
        help="Cash on Delivery fee added to this order.")

    def _ms_apply_cod_fee(self, provider):
        """Add the COD fee line configured on the provider (idempotent)."""
        self.ensure_one()
        if not provider.cod_fee_fixed and not provider.cod_fee_percent:
            return
        fee_product = self.env.ref(
            'ms_website_cash_on_delivery.product_cod_fee',
            raise_if_not_found=False)
        if not fee_product:
            return
        if self.order_line.filtered(
                lambda l: l.product_id.id == fee_product.id):
            return  # fee already applied
        fee = provider.cod_fee_fixed \
            + self.amount_total * provider.cod_fee_percent / 100.0
        fee = self.currency_id.round(fee)
        if fee <= 0:
            return
        self.write({
            'order_line': [Command.create({
                'product_id': fee_product.id,
                'name': fee_product.name,
                'product_uom_qty': 1,
                'price_unit': fee,
            })],
            'cod_fee_amount': fee,
        })
