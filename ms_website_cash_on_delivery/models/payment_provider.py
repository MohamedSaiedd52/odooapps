# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    custom_mode = fields.Selection(
        selection_add=[('cash_on_delivery', "Cash on Delivery")],
    )
    cod_min_order_amount = fields.Float(
        string="COD Minimum Order Amount",
        help="Hide Cash on Delivery when the order total is below this amount. "
             "0 means no minimum. Use the provider's generic 'Maximum Amount' "
             "field for the upper limit.")
    cod_fee_fixed = fields.Float(
        string="COD Fixed Fee",
        help="Fixed fee added to the order when the customer pays with "
             "Cash on Delivery. 0 disables the fixed fee.")
    cod_fee_percent = fields.Float(
        string="COD Fee (%)",
        help="Percentage of the order total added as Cash on Delivery fee. "
             "0 disables the percentage fee.")
    cod_allowed_zip_codes = fields.Char(
        string="COD Allowed Zip Codes",
        help="Comma-separated list of shipping zip codes where Cash on "
             "Delivery is available (e.g. 11511, 21532). Leave empty to "
             "allow every zip code.")

    def _ms_cod_zip_allowed(self, zip_code):
        """Whether COD may be offered for the given shipping zip code."""
        self.ensure_one()
        if not self.cod_allowed_zip_codes:
            return True
        allowed = {z.strip().lower()
                   for z in self.cod_allowed_zip_codes.split(',') if z.strip()}
        return bool(zip_code) and zip_code.strip().lower() in allowed

    @api.model
    def _get_compatible_providers(self, company_id, partner_id, amount,
                                  currency_id=None, **kwargs):
        """Filter out COD providers that fail the minimum amount or zip rules."""
        providers = super()._get_compatible_providers(
            company_id, partner_id, amount, currency_id=currency_id, **kwargs)
        cod_providers = providers.filtered(
            lambda p: p.custom_mode == 'cash_on_delivery')
        if not cod_providers:
            return providers

        sale_order_id = kwargs.get('sale_order_id')
        order = self.env['sale.order'].sudo().browse(sale_order_id) \
            if sale_order_id else self.env['sale.order'].sudo()
        partner = self.env['res.partner'].sudo().browse(partner_id)
        zip_code = (order and order.partner_shipping_id.zip) or partner.zip

        unfit = self.env['payment.provider']
        for provider in cod_providers:
            if provider.cod_min_order_amount and amount \
                    and amount < provider.cod_min_order_amount:
                unfit |= provider
            elif not provider._ms_cod_zip_allowed(zip_code):
                unfit |= provider
        return providers - unfit
