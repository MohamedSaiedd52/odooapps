# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLineShopify(models.Model):
    """Extend sale.order.line to exclude Shopify special products from scheme discount"""
    _inherit = 'sale.order.line'

    # Products that should NOT receive scheme discount
    EXCLUDED_FROM_SCHEME_DISCOUNT = ['SHOPIFY-SHIPPING', 'SHOPIFY-DISCOUNT', 'SHOPIFY-TAX']

    def _shopify_discount_depends(self):
        # order_id.discount_rate only exists when sale_discount_total is installed
        deps = ['product_id']
        if 'discount_rate' in self.env['sale.order']._fields:
            deps.append('order_id.discount_rate')
        return deps

    @api.depends(_shopify_discount_depends)
    def _compute_discount(self):
        """Override to exclude Shopify shipping/discount products from scheme discount"""
        if 'discount_rate' not in self.env['sale.order']._fields:
            return super()._compute_discount()
        for line in self:
            # Check if this product should be excluded from scheme discount
            if line.product_id and line.product_id.default_code in self.EXCLUDED_FROM_SCHEME_DISCOUNT:
                line.discount = 0.0
            else:
                # Apply normal scheme discount
                line.discount = line.order_id.discount_rate or 0.0


class SaleOrderShopify(models.Model):
    """Extend sale.order to add Shopify order details"""
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False, **kwargs):
        """Override to remove discount from shipping lines on invoices"""
        # Call original method
        invoices = super()._create_invoices(grouped=grouped, final=final, **kwargs)

        # For Shopify orders, remove discount from shipping lines
        for invoice in invoices:
            # Check if any related sale order is a Shopify order
            sale_orders = invoice.line_ids.sale_line_ids.order_id
            is_shopify = any(order.is_shopify_order for order in sale_orders)

            if is_shopify:
                # Find shipping/discount/tax lines and remove scheme discount
                excluded_codes = SaleOrderLineShopify.EXCLUDED_FROM_SCHEME_DISCOUNT
                excluded_lines = invoice.invoice_line_ids.filtered(
                    lambda l: l.product_id and l.product_id.default_code in excluded_codes
                )
                if excluded_lines:
                    excluded_lines.write({'discount': 0})
                    _logger.info("Removed discount from Shopify special lines on invoice %s", invoice.name)

        return invoices

    # Shopify Reference
    shopify_order_id = fields.Char('Shopify Order ID', readonly=True)
    shopify_order_number = fields.Char('Shopify Order #', readonly=True)
    is_shopify_order = fields.Boolean('Is Shopify Order', default=False, readonly=True)

    # Order Status
    shopify_financial_status = fields.Selection([
        ('pending', 'Pending'),
        ('authorized', 'Authorized'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
        ('voided', 'Voided'),
    ], string='Payment Status', readonly=True)

    shopify_fulfillment_status = fields.Selection([
        ('unfulfilled', 'Unfulfilled'),
        ('partial', 'Partial'),
        ('fulfilled', 'Fulfilled'),
    ], string='Fulfillment Status', readonly=True)

    # Fulfillment Details
    shopify_fulfilled_at = fields.Datetime('Fulfilled Date', readonly=True)
    shopify_tracking_number = fields.Char('Tracking Number', readonly=True)
    shopify_tracking_company = fields.Char('Shipping Carrier', readonly=True)
    shopify_tracking_url = fields.Char('Tracking URL', readonly=True)
    shopify_fulfillment_location = fields.Char('Fulfillment Location', readonly=True)

    # Order Summary (Totals)
    shopify_subtotal = fields.Monetary('Subtotal', currency_field='currency_id', readonly=True)
    shopify_discount_code = fields.Char('Discount Code', readonly=True)
    shopify_discount_amount = fields.Monetary('Discount', currency_field='currency_id', readonly=True)
    shopify_shipping_method = fields.Char('Shipping Method', readonly=True)
    shopify_shipping_cost = fields.Monetary('Shipping Cost', currency_field='currency_id', readonly=True)
    shopify_tax_name = fields.Char('Tax Name', readonly=True, default='VAT')
    shopify_tax_rate = fields.Float('Tax Rate (%)', readonly=True)
    shopify_tax_amount = fields.Monetary('Tax Amount', currency_field='currency_id', readonly=True)
    shopify_total = fields.Monetary('Total', currency_field='currency_id', readonly=True)

    # Computed field for display
    shopify_discount_display = fields.Char('Discount Display', compute='_compute_discount_display')
    shopify_shipping_display = fields.Char('Shipping Display', compute='_compute_shipping_display')
    shopify_tax_display = fields.Char('Tax Display', compute='_compute_tax_display')

    @api.depends('shopify_discount_code', 'shopify_discount_amount')
    def _compute_discount_display(self):
        for order in self:
            if order.shopify_discount_code:
                order.shopify_discount_display = f"{order.shopify_discount_code}"
            else:
                order.shopify_discount_display = ""

    @api.depends('shopify_shipping_method')
    def _compute_shipping_display(self):
        for order in self:
            order.shopify_shipping_display = order.shopify_shipping_method or ""

    @api.depends('shopify_tax_name', 'shopify_tax_rate')
    def _compute_tax_display(self):
        for order in self:
            if order.shopify_tax_rate:
                order.shopify_tax_display = f"{order.shopify_tax_name or 'VAT'} {order.shopify_tax_rate:.0f}%"
            else:
                order.shopify_tax_display = ""
