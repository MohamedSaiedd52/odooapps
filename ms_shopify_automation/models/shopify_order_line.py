# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ShopifyOrderLine(models.Model):
    _name = 'shopify.order.line'
    _description = 'Shopify Order Line Item'
    _order = 'id'

    # Relations
    order_id = fields.Many2one(
        'shopify.order',
        string='Order',
        required=True,
        ondelete='cascade',
        index=True
    )
    instance_id = fields.Many2one(
        related='order_id.instance_id',
        store=True,
        string='Instance'
    )

    # Shopify IDs
    shopify_line_id = fields.Char('Shopify Line ID', required=True, index=True)
    shopify_product_id = fields.Char('Shopify Product ID', index=True)
    shopify_variant_id = fields.Char('Shopify Variant ID', index=True)

    # Product Info
    name = fields.Char('Name', compute='_compute_name', store=True)
    title = fields.Char('Product Title')
    variant_title = fields.Char('Variant Title')
    sku = fields.Char('SKU')
    vendor = fields.Char('Vendor')

    # Quantity & Pricing
    quantity = fields.Integer('Quantity', default=0)
    price = fields.Float('Unit Price', digits='Product Price')
    total_price = fields.Float('Total Price', compute='_compute_total_price', store=True)
    total_discount = fields.Float('Total Discount', digits='Product Price')
    net_price = fields.Float('Net Price', compute='_compute_total_price', store=True)

    # Fulfillment
    fulfillable_quantity = fields.Integer('Fulfillable Quantity')
    fulfillment_status = fields.Selection([
        ('pending', 'Pending'),
        ('fulfilled', 'Fulfilled'),
        ('partial', 'Partial'),
        ('not_eligible', 'Not Eligible'),
    ], string='Fulfillment Status')

    # Tax & Weight
    taxable = fields.Boolean('Taxable', default=False)
    grams = fields.Float('Weight (grams)')
    requires_shipping = fields.Boolean('Requires Shipping', default=True)

    # Gift Card
    gift_card = fields.Boolean('Is Gift Card', default=False)

    # ============ PRODUCT BARCODE ============
    barcode = fields.Char('Product Barcode', help='Barcode/GTIN from Shopify line item')

    # ============ TAX DETAILS ============
    total_tax = fields.Float('Total Tax', digits='Product Price')
    tax_lines_json = fields.Text('Tax Lines (JSON)', help='Tax details for this line item')

    # ============ DISCOUNT ALLOCATIONS ============
    discount_allocations_json = fields.Text('Discount Allocations (JSON)')

    # ============ PROPERTIES (custom attributes) ============
    properties_json = fields.Text('Properties (JSON)', help='Custom line item properties')

    # Link to Shopify Product mapping
    shopify_product_mapping_id = fields.Many2one(
        'shopify.product',
        string='Linked Shopify Product'
    )

    if hasattr(models, 'Constraint'):  # Odoo 19+ ignores _sql_constraints
        _unique_line_per_order = models.Constraint(
            'UNIQUE(shopify_line_id, order_id)',
            "Line item already exists for this order!")
    else:
        _sql_constraints = [
            ('unique_line_per_order', 'unique(shopify_line_id, order_id)',
             'Line item already exists for this order!')
        ]

    @api.depends('title', 'variant_title')
    def _compute_name(self):
        for rec in self:
            if rec.variant_title:
                rec.name = f"{rec.title} - {rec.variant_title}"
            else:
                rec.name = rec.title or 'Unknown Product'

    @api.depends('quantity', 'price', 'total_discount')
    def _compute_total_price(self):
        for rec in self:
            rec.total_price = rec.quantity * rec.price
            rec.net_price = rec.total_price - (rec.total_discount or 0)
