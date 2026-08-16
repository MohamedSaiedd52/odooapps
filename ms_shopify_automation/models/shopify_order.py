# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api
import logging
from odoo.exceptions import UserError
from odoo.tools.translate import _
from dateutil import parser as date_parser

from .compat import (STORABLE_TYPE, SO_LINE_TAX_FIELD, default_product_category,
                     default_tax_group)

_logger = logging.getLogger(__name__)


def parse_shopify_date(date_str):
    """Parse Shopify ISO date format to Odoo datetime"""
    if not date_str:
        return False
    try:
        # Parse ISO format with timezone (e.g., '2025-11-17T20:07:37+03:00')
        dt = date_parser.parse(date_str)
        # Return without timezone for Odoo
        return dt.replace(tzinfo=None)
    except Exception:
        return False


class ShopifyOrder(models.Model):
    _name = 'shopify.order'
    _description = 'Shopify Order Mapping'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Order Reference', compute='_compute_name', store=True)
    shopify_order_id = fields.Char('Shopify Order ID', required=True, tracking=True)
    shopify_order_number = fields.Char('Order Number')
    odoo_order_id = fields.Many2one('sale.order', string='Odoo Sale Order')
    instance_id = fields.Many2one('shopify.instance', string='Shopify Instance', required=True, ondelete='cascade')
    sync_status = fields.Selection([
        ('synced', 'Synced'),
        ('pending', 'Pending'),
        ('error', 'Error'),
    ], string='Sync Status', default='pending', tracking=True)
    last_sync = fields.Datetime('Last Sync')
    active = fields.Boolean('Active', default=True)

    # Shopify Order Details
    shopify_customer_id = fields.Char('Shopify Customer ID')
    customer_email = fields.Char('Customer Email')
    customer_name = fields.Char('Customer Name')
    financial_status = fields.Selection([
        ('pending', 'Pending'),
        ('authorized', 'Authorized'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
        ('partially_refunded', 'Partially Refunded'),
        ('refunded', 'Refunded'),
        ('voided', 'Voided'),
    ], string='Financial Status')
    fulfillment_status = fields.Selection([
        ('unfulfilled', 'Unfulfilled'),
        ('partial', 'Partial'),
        ('fulfilled', 'Fulfilled'),
        ('restocked', 'Restocked'),
    ], string='Fulfillment Status')
    total_price = fields.Float('Total Price')
    subtotal_price = fields.Float('Subtotal Price')
    total_tax = fields.Float('Total Tax')
    total_discounts = fields.Float('Total Discounts')
    currency = fields.Char('Currency')
    order_date = fields.Datetime('Order Date')
    cancelled_at = fields.Datetime('Cancelled At')
    cancel_reason = fields.Char('Cancel Reason')

    note = fields.Text('Notes')

    # ============ SHIPPING ADDRESS FIELDS ============
    shipping_name = fields.Char('Shipping Name')
    shipping_company = fields.Char('Shipping Company')
    shipping_address1 = fields.Char('Shipping Address 1')
    shipping_address2 = fields.Char('Shipping Address 2')
    shipping_city = fields.Char('Shipping City')
    shipping_province = fields.Char('Shipping Province/State')
    shipping_province_code = fields.Char('Shipping Province Code')
    shipping_country = fields.Char('Shipping Country')
    shipping_country_code = fields.Char('Shipping Country Code')
    shipping_zip = fields.Char('Shipping Zip/Postal Code')
    shipping_phone = fields.Char('Shipping Phone')

    # ============ BILLING ADDRESS FIELDS ============
    billing_name = fields.Char('Billing Name')
    billing_company = fields.Char('Billing Company')
    billing_address1 = fields.Char('Billing Address 1')
    billing_address2 = fields.Char('Billing Address 2')
    billing_city = fields.Char('Billing City')
    billing_province = fields.Char('Billing Province/State')
    billing_province_code = fields.Char('Billing Province Code')
    billing_country = fields.Char('Billing Country')
    billing_country_code = fields.Char('Billing Country Code')
    billing_zip = fields.Char('Billing Zip/Postal Code')
    billing_phone = fields.Char('Billing Phone')

    # ============ TRACKING / FULFILLMENT FIELDS ============
    tracking_number = fields.Char('Tracking Number')
    tracking_url = fields.Char('Tracking URL')
    tracking_company = fields.Char('Tracking Company/Carrier')
    fulfillment_id = fields.Char('Shopify Fulfillment ID')
    fulfilled_at = fields.Datetime('Fulfilled At')

    # ============ SHIPPING LINES FIELDS ============
    shipping_method = fields.Char('Shipping Method')
    shipping_cost = fields.Float('Shipping Cost', digits='Product Price')
    shipping_tax = fields.Float('Shipping Tax', digits='Product Price')
    shipping_carrier_identifier = fields.Char('Carrier Identifier')

    # ============ DISCOUNT CODES ============
    discount_codes = fields.Char('Discount Codes', help='Comma-separated list of applied discount codes')
    discount_codes_json = fields.Text('Discount Codes (JSON)', help='Full discount codes data from Shopify')

    # ============ TAX LINES ============
    tax_lines_json = fields.Text('Tax Lines (JSON)', help='Detailed tax breakdown from Shopify')

    # ============ RELATED PARTNER ADDRESSES (for Odoo sync) ============
    shipping_address_id = fields.Many2one('res.partner', string='Shipping Address Partner')
    billing_address_id = fields.Many2one('res.partner', string='Billing Address Partner')

    # Order Line Items
    line_ids = fields.One2many(
        'shopify.order.line',
        'order_id',
        string='Order Lines'
    )

    # Risk Assessment
    risk_ids = fields.One2many(
        'shopify.risk',
        'order_id',
        string='Risk Assessments'
    )

    if hasattr(models, 'Constraint'):  # Odoo 19+ ignores _sql_constraints
        _uniq_shopify_order_instance = models.Constraint(
            'UNIQUE(shopify_order_id, instance_id)',
            "This Shopify order is already mapped for this instance!")
    else:
        _sql_constraints = [
            ('uniq_shopify_order_instance', 'unique(shopify_order_id, instance_id)',
             'This Shopify order is already mapped for this instance!'),
        ]

    @api.depends('shopify_order_id', 'shopify_order_number')
    def _compute_name(self):
        for rec in self:
            if rec.shopify_order_number:
                rec.name = f"#{rec.shopify_order_number}"
            else:
                rec.name = rec.shopify_order_id or 'New'

    def import_orders_from_shopify(self, instance, max_records=0):
        """Import orders from Shopify for the given instance using Access Token

        Args:
            instance: shopify.instance record
            max_records: Maximum number of orders to import (0 = unlimited)
        """
        if not instance:
            raise UserError(_('No Shopify instance provided.'))

        if instance.state != 'connected':
            raise UserError(_('Please test the connection first!'))

        # Create queue job
        job = self.env['shopify.queue.job'].create({
            'name': f'Import Orders ({instance.name})',
            'job_type': 'import_order',
            'instance_id': instance.id,
            'status': 'in_progress',
        })

        try:
            # Use cursor-based pagination with batch processing for large datasets
            endpoint = 'orders.json'
            params = {'limit': 250, 'status': 'any'}

            # ALWAYS respect sync_from_date if set (minimum date filter)
            # Then use last_order_sync for incremental updates
            is_incremental = False

            # First check sync_from_date - this is the absolute minimum date
            if instance.sync_from_date:
                # Convert date to datetime string for Shopify API (start of day)
                sync_date_str = f"{instance.sync_from_date.isoformat()}T00:00:00"
                params['created_at_min'] = sync_date_str
                _logger.info("Sync from date filter: %s", sync_date_str)

            # If we have a last sync, use updated_at_min for incremental sync
            # But only if it's after sync_from_date
            if instance.last_order_sync:
                if not instance.sync_from_date or instance.last_order_sync.date() >= instance.sync_from_date:
                    params['updated_at_min'] = instance.last_order_sync.isoformat()
                    is_incremental = True
                    _logger.info("Incremental sync: fetching orders updated after %s", instance.last_order_sync)

            if not instance.sync_from_date and not instance.last_order_sync:
                _logger.info("Full sync: fetching all orders (first time) - SET sync_from_date TO LIMIT!")

            page_count = 0
            max_pages = 2000  # Safety limit: 2000 pages * 250 = 500,000 orders max

            total_created = 0
            total_updated = 0
            total_errors = 0
            total_fetched = 0
            total_processed = 0
            batch_size = 50  # Process and commit every 50 orders (orders have more data)

            # If max_records is set, adjust the limit parameter
            if max_records > 0 and max_records < 250:
                params['limit'] = max_records

            while page_count < max_pages:
                # Check if we've reached the max_records limit
                if max_records > 0 and total_processed >= max_records:
                    _logger.info("Reached max_records limit of %d", max_records)
                    break
                page_count += 1
                result, next_link = instance._shopify_request_with_link(endpoint, params=params)
                orders_batch = result.get('orders', [])
                batch_count = len(orders_batch)
                total_fetched += batch_count

                _logger.info("Order import page %d: fetched %d orders (total fetched: %d)",
                            page_count, batch_count, total_fetched)

                # Process this batch immediately instead of storing all in memory
                for shopify_order in orders_batch:
                    try:
                        order_id = str(shopify_order.get('id'))

                        # Check if order mapping already exists
                        existing_mapping = self.search([
                            ('shopify_order_id', '=', order_id),
                            ('instance_id', '=', instance.id)
                        ], limit=1)

                        # Get customer info
                        customer_data = shopify_order.get('customer', {}) or {}
                        customer_email = shopify_order.get('email', '') or customer_data.get('email', '')
                        customer_name = f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip()

                        # === SHIPPING ADDRESS ===
                        shipping_addr = shopify_order.get('shipping_address', {}) or {}

                        # === BILLING ADDRESS ===
                        billing_addr = shopify_order.get('billing_address', {}) or {}

                        # === TRACKING / FULFILLMENT ===
                        fulfillments = shopify_order.get('fulfillments', []) or []
                        first_fulfillment = fulfillments[0] if fulfillments else {}
                        tracking_urls = first_fulfillment.get('tracking_urls', []) or []

                        # === SHIPPING LINES ===
                        shipping_lines = shopify_order.get('shipping_lines', []) or []
                        first_shipping = shipping_lines[0] if shipping_lines else {}
                        shipping_tax_lines = first_shipping.get('tax_lines', []) or []

                        # === DISCOUNT CODES ===
                        discount_codes_list = shopify_order.get('discount_codes', []) or []

                        order_vals = {
                            'shopify_order_id': order_id,
                            'shopify_order_number': str(shopify_order.get('order_number', '')),
                            'instance_id': instance.id,
                            'shopify_customer_id': str(customer_data.get('id', '')) if customer_data else '',
                            'customer_email': customer_email,
                            'customer_name': customer_name or shopify_order.get('name', 'Unknown'),
                            'financial_status': shopify_order.get('financial_status', 'pending'),
                            'fulfillment_status': shopify_order.get('fulfillment_status') or 'unfulfilled',
                            'total_price': float(shopify_order.get('total_price', 0)),
                            'subtotal_price': float(shopify_order.get('subtotal_price', 0)),
                            'total_tax': float(shopify_order.get('total_tax', 0)),
                            'total_discounts': float(shopify_order.get('total_discounts', 0)),
                            'currency': shopify_order.get('currency', ''),
                            'order_date': parse_shopify_date(shopify_order.get('created_at')),
                            'cancelled_at': parse_shopify_date(shopify_order.get('cancelled_at')),
                            'cancel_reason': shopify_order.get('cancel_reason', ''),
                            'sync_status': 'synced',
                            'last_sync': fields.Datetime.now(),
                            # === SHIPPING ADDRESS ===
                            'shipping_name': shipping_addr.get('name', ''),
                            'shipping_company': shipping_addr.get('company', ''),
                            'shipping_address1': shipping_addr.get('address1', ''),
                            'shipping_address2': shipping_addr.get('address2', ''),
                            'shipping_city': shipping_addr.get('city', ''),
                            'shipping_province': shipping_addr.get('province', ''),
                            'shipping_province_code': shipping_addr.get('province_code', ''),
                            'shipping_country': shipping_addr.get('country', ''),
                            'shipping_country_code': shipping_addr.get('country_code', ''),
                            'shipping_zip': shipping_addr.get('zip', ''),
                            'shipping_phone': shipping_addr.get('phone', ''),
                            # === BILLING ADDRESS ===
                            'billing_name': billing_addr.get('name', ''),
                            'billing_company': billing_addr.get('company', ''),
                            'billing_address1': billing_addr.get('address1', ''),
                            'billing_address2': billing_addr.get('address2', ''),
                            'billing_city': billing_addr.get('city', ''),
                            'billing_province': billing_addr.get('province', ''),
                            'billing_province_code': billing_addr.get('province_code', ''),
                            'billing_country': billing_addr.get('country', ''),
                            'billing_country_code': billing_addr.get('country_code', ''),
                            'billing_zip': billing_addr.get('zip', ''),
                            'billing_phone': billing_addr.get('phone', ''),
                            # === TRACKING / FULFILLMENT ===
                            'tracking_number': first_fulfillment.get('tracking_number', ''),
                            'tracking_url': tracking_urls[0] if tracking_urls else '',
                            'tracking_company': first_fulfillment.get('tracking_company', ''),
                            'fulfillment_id': str(first_fulfillment.get('id', '')) if first_fulfillment.get('id') else '',
                            'fulfilled_at': parse_shopify_date(first_fulfillment.get('created_at')) if first_fulfillment else False,
                            # === SHIPPING LINES ===
                            'shipping_method': first_shipping.get('title', ''),
                            'shipping_cost': float(first_shipping.get('price', 0) or 0),
                            'shipping_tax': sum(float(t.get('price', 0) or 0) for t in shipping_tax_lines),
                            'shipping_carrier_identifier': first_shipping.get('carrier_identifier', ''),
                            # === DISCOUNT CODES ===
                            'discount_codes': ', '.join([dc.get('code', '') for dc in discount_codes_list]),
                            'discount_codes_json': json.dumps(discount_codes_list) if discount_codes_list else '',
                            # === TAX LINES ===
                            'tax_lines_json': json.dumps(shopify_order.get('tax_lines', [])),
                        }

                        if existing_mapping:
                            existing_mapping.write(order_vals)
                            # Sync line items for existing order
                            existing_mapping._sync_order_line_items(shopify_order)
                            # Update or Create Sale Order
                            if existing_mapping.odoo_order_id:
                                # Update existing Sale Order
                                self._update_odoo_sale_order(existing_mapping.odoo_order_id, instance, shopify_order)
                            else:
                                # Sale Order was deleted - create new one
                                odoo_order = self._create_odoo_sale_order(instance, shopify_order)
                                if odoo_order:
                                    existing_mapping.odoo_order_id = odoo_order.id
                            total_updated += 1
                        else:
                            # Create Odoo sale order
                            odoo_order = self._create_odoo_sale_order(instance, shopify_order)
                            order_vals['odoo_order_id'] = odoo_order.id if odoo_order else False
                            new_order = self.create(order_vals)
                            # Sync line items for new order
                            new_order._sync_order_line_items(shopify_order)
                            total_created += 1

                        total_processed += 1

                        # Check if we've reached max_records limit
                        if max_records > 0 and total_processed >= max_records:
                            _logger.info("Reached max_records limit of %d during processing", max_records)
                            break

                        # Commit every batch_size records to save progress
                        if (total_created + total_updated) % batch_size == 0:
                            self.env.cr.commit()
                            _logger.info("Progress: %d created, %d updated (committed)", total_created, total_updated)

                    except Exception as e:
                        total_errors += 1
                        _logger.error("Error importing order %s: %s", shopify_order.get('id', 'Unknown'), str(e))
                        if total_errors % 50 == 0:  # Log every 50 errors
                            self.env['shopify.log'].create({
                                'name': 'Order Import Errors',
                                'log_type': 'error',
                                'job_id': job.id,
                                'message': f'Batch errors: {total_errors} errors so far',
                            })
                            self.env.cr.commit()

                # Commit after each page
                self.env.cr.commit()

                # Check if we've reached max_records limit
                if max_records > 0 and total_processed >= max_records:
                    break

                # Check if there's a next page
                if not next_link or batch_count < 250:
                    break

                # Use next page URL for cursor-based pagination
                endpoint = next_link
                params = {}

            # Update job status and last sync time
            job.write({'status': 'done'})
            instance.write({'last_order_sync': fields.Datetime.now()})

            sync_type = "Incremental" if is_incremental else "Full"
            self.env['shopify.log'].create({
                'name': 'Order Import Completed',
                'log_type': 'info',
                'job_id': job.id,
                'message': f'{sync_type} import completed: {total_created} created, {total_updated} updated, {total_errors} errors (total fetched: {total_fetched})',
            })
            self.env.cr.commit()

            _logger.info("%s order import completed: %d created, %d updated, %d errors",
                        sync_type, total_created, total_updated, total_errors)

            return True

        except Exception as e:
            job.write({'status': 'failed', 'error_message': str(e)})
            self.env['shopify.log'].create({
                'name': 'Order Import Failed',
                'log_type': 'error',
                'job_id': job.id,
                'message': f'Order import failed: {str(e)}',
            })
            raise UserError(_('Failed to import orders: %s') % str(e))

    def _get_or_create_address_partner(self, address_data, parent_partner, address_type):
        """Create or find a res.partner for the given address data

        Args:
            address_data: dict with address fields from Shopify
            parent_partner: the main customer partner
            address_type: 'delivery' or 'invoice'

        Returns:
            res.partner record or False
        """
        if not address_data:
            return False

        # Build address key for comparison
        address_key = f"{address_data.get('address1', '')}-{address_data.get('city', '')}-{address_data.get('zip', '')}"

        if not address_key or address_key == '--':
            return False

        # Try to find existing address under this partner
        domain = [
            ('parent_id', '=', parent_partner.id),
            ('street', '=', address_data.get('address1', '')),
            ('city', '=', address_data.get('city', '')),
            ('zip', '=', address_data.get('zip', '')),
            ('type', '=', address_type),
        ]
        existing = self.env['res.partner'].search(domain, limit=1)
        if existing:
            return existing

        # Get country
        country = False
        if address_data.get('country_code'):
            country = self.env['res.country'].search([('code', '=', address_data['country_code'].upper())], limit=1)

        # Get state/province
        state = False
        if address_data.get('province_code') and country:
            state = self.env['res.country.state'].search([
                ('code', '=', address_data['province_code']),
                ('country_id', '=', country.id)
            ], limit=1)

        # Create new address partner
        partner_vals = {
            'name': address_data.get('name', '') or parent_partner.name,
            'parent_id': parent_partner.id,
            'type': address_type,
            'street': address_data.get('address1', ''),
            'street2': address_data.get('address2', ''),
            'city': address_data.get('city', ''),
            'state_id': state.id if state else False,
            'country_id': country.id if country else False,
            'zip': address_data.get('zip', ''),
            'phone': address_data.get('phone', ''),
        }

        return self.env['res.partner'].create(partner_vals)

    # ============ PRODUCTION INTEGRATION HELPER METHODS ============

    def _get_customer_for_order(self, instance, shopify_order):
        """Get customer for order - either fixed customer or create/lookup

        If use_fixed_customer is enabled, returns the fixed customer.
        Otherwise, creates or finds customer from Shopify data.
        """
        # Production Mode: Use fixed customer
        if instance.use_fixed_customer and instance.fixed_customer_id:
            return instance.fixed_customer_id

        # Normal Mode: Get or create customer from Shopify data
        customer_data = shopify_order.get('customer', {}) or {}
        customer_email = shopify_order.get('email', '') or customer_data.get('email', '')
        customer_name = f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip()

        partner = False
        if customer_email:
            partner = self.env['res.partner'].search([('email', '=', customer_email)], limit=1)

        if not partner and customer_data.get('id'):
            customer_mapping = self.env['shopify.customer'].search([
                ('shopify_customer_id', '=', str(customer_data['id'])),
                ('instance_id', '=', instance.id)
            ], limit=1)
            if customer_mapping:
                partner = customer_mapping.odoo_partner_id

        if not partner:
            partner = self.env['res.partner'].create({
                'name': customer_name or customer_email or 'Shopify Customer',
                'email': customer_email,
                'phone': customer_data.get('phone', ''),
                'is_company': False,
                'customer_rank': 1,
            })

        return partner

    def _build_customer_full_name(self, shopify_order):
        """Build the full customer name from Shopify order data

        Priority: shipping_address > billing_address > customer > email
        """
        shipping = shopify_order.get('shipping_address', {}) or {}
        billing = shopify_order.get('billing_address', {}) or {}
        customer = shopify_order.get('customer', {}) or {}

        # Try shipping address first
        first_name = shipping.get('first_name') or billing.get('first_name') or customer.get('first_name') or ''
        last_name = shipping.get('last_name') or billing.get('last_name') or customer.get('last_name') or ''

        full_name = f"{first_name} {last_name}".strip()

        if not full_name:
            full_name = (
                shipping.get('name') or
                billing.get('name') or
                f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or
                shopify_order.get('email') or
                'Unknown Customer'
            )

        return full_name

    def _get_shipping_method_title(self, shopify_order):
        """Extract shipping method title from Shopify order"""
        shipping_lines = shopify_order.get('shipping_lines', []) or []
        if shipping_lines:
            return shipping_lines[0].get('title', '')
        return ''

    def _get_first_tracking_number(self, shopify_order):
        """Extract first tracking number from fulfillments"""
        fulfillments = shopify_order.get('fulfillments', []) or []
        if fulfillments:
            return fulfillments[0].get('tracking_number', '') or ''
        return ''

    def _get_discount_scheme_for_order(self, instance, shopify_order):
        """Find matching discount.scheme for Shopify discount codes

        Returns discount.scheme record or False
        Priority:
        1. Match Shopify discount code to scheme name
        2. Use instance default_discount_scheme_id
        3. Use "NONE-NONE" scheme as fallback
        """
        if not instance.map_discount_codes:
            return False

        # Check if discount.scheme model exists (sale_discount_total module)
        if 'discount.scheme' not in self.env:
            _logger.debug("discount.scheme model not found - sale_discount_total module not installed")
            return False

        discount_codes = shopify_order.get('discount_codes', []) or []

        # Try to find matching discount scheme by code name
        if discount_codes:
            try:
                for code_data in discount_codes:
                    code_name = code_data.get('code', '')
                    if code_name:
                        # Search case-insensitive
                        scheme = self.env['discount.scheme'].search([
                            ('name', '=ilike', code_name)
                        ], limit=1)
                        if scheme:
                            _logger.debug("Found matching scheme '%s' for code '%s'", scheme.name, code_name)
                            return scheme
            except Exception as e:
                _logger.warning("Error looking up discount scheme: %s", str(e))

        # No matching scheme found - use fallbacks
        # Priority 1: Instance default
        if instance.default_discount_scheme_id:
            return instance.default_discount_scheme_id

        # Priority 2: Use "NONE-NONE" scheme as fallback for orders without matching code
        try:
            none_scheme = self.env['discount.scheme'].search([
                ('name', '=', 'NONE-NONE')
            ], limit=1)
            if none_scheme:
                _logger.debug("Using NONE-NONE scheme as fallback")
                return none_scheme
        except Exception as e:
            _logger.warning("Error looking up NONE-NONE scheme: %s", str(e))

        return False

    def _create_odoo_sale_order(self, instance, shopify_order):
        """Create Odoo sale order from Shopify order data

        LIVE PRODUCTION APPROACH:
        - Product lines use ORIGINAL prices (before discount), tax-exclusive
        - 15% VAT applied to each product line
        - ONE Discount line at the end with negative total discount, also with 15% VAT
        - Shipping line without tax
        """
        try:
            # Get customer (uses fixed customer if configured)
            partner = self._get_customer_for_order(instance, shopify_order)

            # Get original customer data for sala_fileds
            customer_data = shopify_order.get('customer', {}) or {}
            customer_email = shopify_order.get('email', '') or customer_data.get('email', '')

            # Get or create shipping address partner
            shipping_address_data = shopify_order.get('shipping_address', {})
            shipping_partner = self._get_or_create_address_partner(
                shipping_address_data,
                partner,
                'delivery'
            )

            # Get or create billing address partner
            billing_address_data = shopify_order.get('billing_address', {})
            billing_partner = self._get_or_create_address_partner(
                billing_address_data,
                partner,
                'invoice'
            )

            # Extract Shopify order details
            discount_codes = shopify_order.get('discount_codes', [])
            discount_code = discount_codes[0].get('code', '') if discount_codes else ''
            discount_amount = float(shopify_order.get('total_discounts', 0))

            shipping_lines = shopify_order.get('shipping_lines', [])
            shipping_method = shipping_lines[0].get('title', '') if shipping_lines else ''
            shipping_cost = float(shipping_lines[0].get('price', 0)) if shipping_lines else 0

            tax_lines = shopify_order.get('tax_lines', [])
            tax_name = tax_lines[0].get('title', 'VAT') if tax_lines else 'VAT'
            tax_rate = float(tax_lines[0].get('rate', 0)) * 100 if tax_lines else 15  # Default 15%
            tax_amount = float(shopify_order.get('total_tax', 0))

            fulfillments = shopify_order.get('fulfillments', [])
            tracking_number = ''
            tracking_company = ''
            tracking_url = ''
            fulfilled_at = False
            fulfillment_location = ''
            if fulfillments:
                tracking_number = fulfillments[0].get('tracking_number', '') or ''
                tracking_company = fulfillments[0].get('tracking_company', '') or ''
                tracking_url = fulfillments[0].get('tracking_url', '') or ''
                fulfilled_at = parse_shopify_date(fulfillments[0].get('created_at'))
                fulfillment_location = fulfillments[0].get('location_id', '') or fulfillments[0].get('origin_address', {}).get('city', '') or ''

            # Create sale order with shipping/billing addresses and Shopify details
            order_vals = {
                'partner_id': partner.id,
                'partner_shipping_id': shipping_partner.id if shipping_partner else partner.id,
                'partner_invoice_id': billing_partner.id if billing_partner else partner.id,
                'date_order': parse_shopify_date(shopify_order.get('created_at')) or fields.Datetime.now(),
                'client_order_ref': f"Shopify-{shopify_order.get('order_number', shopify_order['id'])}",
                'company_id': instance.company_id.id,
                # Shopify Details
                'is_shopify_order': True,
                'shopify_order_id': str(shopify_order.get('id', '')),
                'shopify_order_number': str(shopify_order.get('order_number', '')),
                'shopify_discount_code': discount_code,
                'shopify_discount_amount': discount_amount,
                'shopify_shipping_method': shipping_method,
                'shopify_shipping_cost': shipping_cost,
                'shopify_tax_name': tax_name,
                'shopify_tax_rate': tax_rate,
                'shopify_tax_amount': tax_amount,
                'shopify_subtotal': float(shopify_order.get('subtotal_price', 0)),
                'shopify_total': float(shopify_order.get('total_price', 0)),
                'shopify_tracking_number': tracking_number,
                'shopify_tracking_company': tracking_company,
                'shopify_tracking_url': tracking_url,
                'shopify_fulfilled_at': fulfilled_at,
                'shopify_fulfillment_location': fulfillment_location,
                'shopify_fulfillment_status': shopify_order.get('fulfillment_status') or 'unfulfilled',
                'shopify_financial_status': shopify_order.get('financial_status') or 'pending',
            }

            # Get currency from Shopify and activate it if needed
            currency_code = shopify_order.get('currency', 'SAR')
            currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
            if currency:
                # Activate currency if not active
                if not currency.active:
                    currency.sudo().write({'active': True})
                    _logger.info("Activated currency: %s", currency_code)
                order_vals['currency_id'] = currency.id

            # ============ SALA_FILEDS INTEGRATION ============
            # Add custom fields from sala_fileds module if available
            # These fields store the actual customer info when using fixed customer
            shipping_addr = shopify_order.get('shipping_address', {}) or {}

            # Check if sala_fileds fields exist on sale.order model
            SaleOrder = self.env['sale.order']
            if 'customer_name' in SaleOrder._fields:
                # Build customer name from Shopify data
                order_vals['customer_name'] = self._build_customer_full_name(shopify_order)

            if 'mobile' in SaleOrder._fields:
                order_vals['mobile'] = shipping_addr.get('phone') or customer_data.get('phone', '')

            if 'city' in SaleOrder._fields:
                order_vals['city'] = shipping_addr.get('city', '')

            if 'shipping_method' in SaleOrder._fields:
                order_vals['shipping_method'] = self._get_shipping_method_title(shopify_order)

            if 'tracking_number' in SaleOrder._fields:
                order_vals['tracking_number'] = self._get_first_tracking_number(shopify_order)

            if 'order_number' in SaleOrder._fields:
                order_vals['order_number'] = str(shopify_order.get('order_number', ''))

            # Add country if field exists
            if 'country_id' in SaleOrder._fields and shipping_addr.get('country_code'):
                country = self.env['res.country'].search([
                    ('code', '=', shipping_addr['country_code'].upper())
                ], limit=1)
                if country:
                    order_vals['country_id'] = country.id

            # ============ DISCOUNT SCHEME INTEGRATION ============
            # Map Shopify discount codes to discount.scheme if configured
            discount_scheme = False
            if 'discount_scheme_id' in SaleOrder._fields and instance.map_discount_codes:
                discount_scheme = self._get_discount_scheme_for_order(instance, shopify_order)
                if discount_scheme:
                    order_vals['discount_scheme_id'] = discount_scheme.id

            odoo_order = self.env['sale.order'].create(order_vals)

            # ============ GET TAX FOR PRODUCTS ============
            # Get or create 15% VAT tax (or whatever rate from Shopify)
            # Default to 15% if no tax_lines in order
            if tax_rate == 0:
                tax_rate = 15  # Default VAT rate
            tax_record = self._get_or_create_tax_for_shopify(tax_rate, tax_name, instance.company_id)

            # ============ LIVE PRODUCTION APPROACH ============
            # Track total discount to add as separate line at the end
            total_line_discount = 0.0

            # Add order lines with ORIGINAL prices (before discount)
            line_items = shopify_order.get('line_items', [])
            for item in line_items:
                product = self._get_or_create_product(instance, item)

                # Skip line if product not found (in production mode with sync_products_from_shopify=False)
                if not product:
                    _logger.warning("Skipping order line - product not found: %s", item.get('name', item.get('sku', 'Unknown')))
                    continue

                # Get the ORIGINAL price from Shopify (TAX INCLUSIVE)
                shopify_price = float(item.get('price', 0))
                quantity = float(item.get('quantity', 1))

                # ============ Get line discount (for tracking, NOT for applying to price) ============
                line_total_discount = float(item.get('total_discount', 0))
                if line_total_discount == 0:
                    discount_allocations = item.get('discount_allocations', []) or []
                    for allocation in discount_allocations:
                        line_total_discount += float(allocation.get('amount', 0))

                # Accumulate total discount for the discount line
                total_line_discount += line_total_discount

                _logger.debug("Line %s: original_price=%s, qty=%s, discount=%s (accumulated)",
                             item.get('sku', 'N/A'), shopify_price, quantity, line_total_discount)

                # Convert ORIGINAL tax-inclusive price to tax-exclusive
                # Formula: untaxed = price_incl / (1 + tax_rate/100)
                original_untaxed_price = shopify_price / (1 + tax_rate / 100)

                line_vals = {
                    'order_id': odoo_order.id,
                    'product_id': product.id,
                    'name': item.get('name', product.name),
                    'product_uom_qty': quantity,
                    'price_unit': original_untaxed_price,  # ORIGINAL price, tax-exclusive
                    'discount': 0,  # NO discount on line - will add as separate line
                }

                # Apply VAT tax to product lines
                if tax_record:
                    line_vals[SO_LINE_TAX_FIELD] = [(6, 0, [tax_record.id])]
                else:
                    line_vals[SO_LINE_TAX_FIELD] = [(5, 0, 0)]

                self.env['sale.order.line'].create(line_vals)

            # ============ ADD SHIPPING LINE (with tax, same total) ============
            if shipping_cost > 0:
                shipping_product = self._get_or_create_shipping_product()
                # Convert shipping cost to tax-exclusive so total stays the same
                # e.g. 50 / 1.15 = 43.48 → 43.48 + 15% VAT = 50
                shipping_untaxed = shipping_cost / (1 + tax_rate / 100) if tax_rate else shipping_cost
                shipping_line_vals = {
                    'order_id': odoo_order.id,
                    'product_id': shipping_product.id,
                    'name': f"Shipping: {shipping_method}" if shipping_method else "Shipping",
                    'product_uom_qty': 1,
                    'price_unit': shipping_untaxed,
                    'discount': 0,
                }
                if tax_record:
                    shipping_line_vals[SO_LINE_TAX_FIELD] = [(6, 0, [tax_record.id])]
                self.env['sale.order.line'].create(shipping_line_vals)

            # ============ ADD DISCOUNT LINE (negative amount with tax) ============
            # Only create discount line for the REMAINING discount after scheme
            # Formula: Discount Line = Shopify Total Discount - Scheme Discount
            total_shopify_discount = float(shopify_order.get('total_discounts', 0))

            if total_shopify_discount > 0:
                # Calculate how much the scheme already covers
                scheme_discount_amount = 0
                if discount_scheme:
                    scheme_percentage = discount_scheme.discount_percentage or 0
                    # Calculate product subtotal (tax-inclusive, ORIGINAL prices)
                    product_subtotal_incl = sum(
                        float(item.get('price', 0)) * float(item.get('quantity', 1))
                        for item in line_items
                    )
                    # Scheme covers this amount (tax-inclusive)
                    scheme_discount_amount = product_subtotal_incl * (scheme_percentage / 100)
                    _logger.info(
                        "Scheme '%s' (%s%%) covers: %s of total Shopify discount: %s",
                        discount_scheme.name, scheme_percentage, scheme_discount_amount, total_shopify_discount
                    )

                # Remaining discount not covered by scheme
                remaining_discount = total_shopify_discount - scheme_discount_amount

                # Only create discount line if there's remaining discount
                if remaining_discount > 0.50:  # Threshold to avoid tiny lines due to rounding
                    discount_product = self._get_or_create_discount_product()

                    # Convert to tax-exclusive
                    discount_untaxed = remaining_discount / (1 + tax_rate / 100)

                    discount_line_vals = {
                        'order_id': odoo_order.id,
                        'product_id': discount_product.id,
                        'name': f"Discount: {discount_code}" if discount_code else "Discount",
                        'product_uom_qty': 1,
                        'price_unit': -discount_untaxed,  # NEGATIVE amount, tax-exclusive
                        'discount': 0,
                    }

                    # Apply same VAT tax to discount line
                    if tax_record:
                        discount_line_vals[SO_LINE_TAX_FIELD] = [(6, 0, [tax_record.id])]
                    else:
                        discount_line_vals[SO_LINE_TAX_FIELD] = [(5, 0, 0)]

                    self.env['sale.order.line'].create(discount_line_vals)
                    _logger.info("Added discount line for remaining: -%s (Shopify: %s - Scheme: %s)",
                                remaining_discount, total_shopify_discount, scheme_discount_amount)
                else:
                    _logger.info("No discount line needed - scheme covers full discount (remaining: %s)", remaining_discount)

            return odoo_order

        except Exception as e:
            _logger.error("Error creating Odoo sale order: %s", str(e))
            return False

    def _update_odoo_sale_order(self, odoo_order, instance, shopify_order):
        """Update existing Odoo sale order with Shopify data

        LIVE PRODUCTION APPROACH:
        - Product lines use ORIGINAL prices (before discount), tax-exclusive
        - 15% VAT applied to each product line
        - ONE Discount line at the end with negative total discount, also with 15% VAT
        - Shipping line without tax
        """
        try:
            # Extract Shopify order details
            discount_codes = shopify_order.get('discount_codes', [])
            discount_code = discount_codes[0].get('code', '') if discount_codes else ''
            discount_amount = float(shopify_order.get('total_discounts', 0))

            shipping_lines = shopify_order.get('shipping_lines', [])
            shipping_method = shipping_lines[0].get('title', '') if shipping_lines else ''
            shipping_cost = float(shipping_lines[0].get('price', 0)) if shipping_lines else 0

            tax_lines = shopify_order.get('tax_lines', [])
            tax_name = tax_lines[0].get('title', 'VAT') if tax_lines else 'VAT'
            tax_rate = float(tax_lines[0].get('rate', 0)) * 100 if tax_lines else 15  # Default 15%
            tax_amount = float(shopify_order.get('total_tax', 0))

            fulfillments = shopify_order.get('fulfillments', [])
            tracking_number = ''
            tracking_company = ''
            tracking_url = ''
            fulfilled_at = False
            fulfillment_location = ''
            if fulfillments:
                tracking_number = fulfillments[0].get('tracking_number', '') or ''
                tracking_company = fulfillments[0].get('tracking_company', '') or ''
                tracking_url = fulfillments[0].get('tracking_url', '') or ''
                fulfilled_at = parse_shopify_date(fulfillments[0].get('created_at'))
                fulfillment_location = fulfillments[0].get('location_id', '') or ''

            # Get currency and activate if needed
            currency_code = shopify_order.get('currency', 'SAR')
            currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
            if currency and not currency.active:
                currency.sudo().write({'active': True})
                _logger.info("Activated currency: %s", currency_code)

            # Update sale order Shopify fields
            update_vals = {
                'shopify_discount_code': discount_code,
                'shopify_discount_amount': discount_amount,
                'shopify_shipping_method': shipping_method,
                'shopify_shipping_cost': shipping_cost,
                'shopify_tax_name': tax_name,
                'shopify_tax_rate': tax_rate,
                'shopify_tax_amount': tax_amount,
                'shopify_subtotal': float(shopify_order.get('subtotal_price', 0)),
                'shopify_total': float(shopify_order.get('total_price', 0)),
                'shopify_tracking_number': tracking_number,
                'shopify_tracking_company': tracking_company,
                'shopify_tracking_url': tracking_url,
                'shopify_fulfilled_at': fulfilled_at,
                'shopify_fulfillment_location': fulfillment_location,
                'shopify_fulfillment_status': shopify_order.get('fulfillment_status') or 'unfulfilled',
                'shopify_financial_status': shopify_order.get('financial_status') or 'pending',
            }

            if currency:
                update_vals['currency_id'] = currency.id

            # Get discount scheme for this order
            discount_scheme = False
            SaleOrder = self.env['sale.order']
            if 'discount_scheme_id' in SaleOrder._fields and instance.map_discount_codes:
                discount_scheme = self._get_discount_scheme_for_order(instance, shopify_order)
                if discount_scheme:
                    update_vals['discount_scheme_id'] = discount_scheme.id

            odoo_order.write(update_vals)

            # Delete existing order lines and recreate them
            odoo_order.order_line.unlink()

            # ============ GET TAX FOR PRODUCTS ============
            # Default to 15% if no tax_lines in order
            if tax_rate == 0:
                tax_rate = 15  # Default VAT rate
            tax_record = self._get_or_create_tax_for_shopify(tax_rate, tax_name, instance.company_id)

            # ============ LIVE PRODUCTION APPROACH ============
            # Track total discount to add as separate line at the end
            total_line_discount = 0.0

            # Add order lines with ORIGINAL prices (before discount)
            line_items = shopify_order.get('line_items', [])
            for item in line_items:
                product = self._get_or_create_product(instance, item)

                # Skip line if product not found (in production mode with sync_products_from_shopify=False)
                if not product:
                    _logger.warning("Skipping order line - product not found: %s", item.get('name', item.get('sku', 'Unknown')))
                    continue

                # Get the ORIGINAL price from Shopify (TAX INCLUSIVE)
                shopify_price = float(item.get('price', 0))
                quantity = float(item.get('quantity', 1))

                # ============ Get line discount (for tracking, NOT for applying to price) ============
                line_total_discount = float(item.get('total_discount', 0))
                if line_total_discount == 0:
                    discount_allocations = item.get('discount_allocations', []) or []
                    for allocation in discount_allocations:
                        line_total_discount += float(allocation.get('amount', 0))

                # Accumulate total discount for the discount line
                total_line_discount += line_total_discount

                _logger.debug("Line %s: original_price=%s, qty=%s, discount=%s (accumulated)",
                             item.get('sku', 'N/A'), shopify_price, quantity, line_total_discount)

                # Convert ORIGINAL tax-inclusive price to tax-exclusive
                # Formula: untaxed = price_incl / (1 + tax_rate/100)
                original_untaxed_price = shopify_price / (1 + tax_rate / 100)

                line_vals = {
                    'order_id': odoo_order.id,
                    'product_id': product.id,
                    'name': item.get('name', product.name),
                    'product_uom_qty': quantity,
                    'price_unit': original_untaxed_price,  # ORIGINAL price, tax-exclusive
                    'discount': 0,  # NO discount on line - will add as separate line
                }

                # Apply VAT tax to product lines
                if tax_record:
                    line_vals[SO_LINE_TAX_FIELD] = [(6, 0, [tax_record.id])]
                else:
                    line_vals[SO_LINE_TAX_FIELD] = [(5, 0, 0)]

                self.env['sale.order.line'].create(line_vals)

            # ============ ADD SHIPPING LINE (with tax, same total) ============
            if shipping_cost > 0:
                shipping_product = self._get_or_create_shipping_product()
                # Convert shipping cost to tax-exclusive so total stays the same
                # e.g. 50 / 1.15 = 43.48 → 43.48 + 15% VAT = 50
                shipping_untaxed = shipping_cost / (1 + tax_rate / 100) if tax_rate else shipping_cost
                shipping_line_vals = {
                    'order_id': odoo_order.id,
                    'product_id': shipping_product.id,
                    'name': f"Shipping: {shipping_method}" if shipping_method else "Shipping",
                    'product_uom_qty': 1,
                    'price_unit': shipping_untaxed,
                    'discount': 0,
                }
                if tax_record:
                    shipping_line_vals[SO_LINE_TAX_FIELD] = [(6, 0, [tax_record.id])]
                self.env['sale.order.line'].create(shipping_line_vals)

            # ============ ADD DISCOUNT LINE (negative amount with tax) ============
            # Only create discount line for the REMAINING discount after scheme
            # Formula: Discount Line = Shopify Total Discount - Scheme Discount
            total_shopify_discount = float(shopify_order.get('total_discounts', 0))

            if total_shopify_discount > 0:
                # Calculate how much the scheme already covers
                scheme_discount_amount = 0
                if discount_scheme:
                    scheme_percentage = discount_scheme.discount_percentage or 0
                    # Calculate product subtotal (tax-inclusive, ORIGINAL prices)
                    product_subtotal_incl = sum(
                        float(item.get('price', 0)) * float(item.get('quantity', 1))
                        for item in line_items
                    )
                    # Scheme covers this amount (tax-inclusive)
                    scheme_discount_amount = product_subtotal_incl * (scheme_percentage / 100)
                    _logger.info(
                        "Scheme '%s' (%s%%) covers: %s of total Shopify discount: %s",
                        discount_scheme.name, scheme_percentage, scheme_discount_amount, total_shopify_discount
                    )

                # Remaining discount not covered by scheme
                remaining_discount = total_shopify_discount - scheme_discount_amount

                # Only create discount line if there's remaining discount
                if remaining_discount > 0.50:  # Threshold to avoid tiny lines due to rounding
                    discount_product = self._get_or_create_discount_product()

                    # Convert to tax-exclusive
                    discount_untaxed = remaining_discount / (1 + tax_rate / 100)

                    discount_line_vals = {
                        'order_id': odoo_order.id,
                        'product_id': discount_product.id,
                        'name': f"Discount: {discount_code}" if discount_code else "Discount",
                        'product_uom_qty': 1,
                        'price_unit': -discount_untaxed,  # NEGATIVE amount, tax-exclusive
                        'discount': 0,
                    }

                    # Apply same VAT tax to discount line
                    if tax_record:
                        discount_line_vals[SO_LINE_TAX_FIELD] = [(6, 0, [tax_record.id])]
                    else:
                        discount_line_vals[SO_LINE_TAX_FIELD] = [(5, 0, 0)]

                    self.env['sale.order.line'].create(discount_line_vals)
                    _logger.info("Added discount line for remaining: -%s (Shopify: %s - Scheme: %s)",
                                remaining_discount, total_shopify_discount, scheme_discount_amount)
                else:
                    _logger.info("No discount line needed - scheme covers full discount (remaining: %s)", remaining_discount)

            _logger.info("Updated Sale Order %s with Shopify data (LIVE approach)", odoo_order.name)
            return True

        except Exception as e:
            _logger.error("Error updating Odoo sale order: %s", str(e))
            return False

    def _get_or_create_tax(self, tax_rate, tax_name, company):
        """Find or create a tax matching the Shopify tax rate"""
        # Search for existing tax with same rate
        tax = self.env['account.tax'].search([
            ('amount', '=', tax_rate),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)

        if tax:
            return tax

        # Create new tax
        try:
            vals = {
                'name': f"{tax_name} {tax_rate}%",
                'amount': tax_rate,
                'type_tax_use': 'sale',
                'company_id': company.id,
                'description': f"Imported from Shopify - {tax_name}",
            }
            tax_group_id = default_tax_group(self.env, company)
            if tax_group_id:
                vals['tax_group_id'] = tax_group_id
            with self.env.cr.savepoint():
                tax = self.env['account.tax'].create(vals)
            _logger.info("Created new tax: %s (%.2f%%)", tax.name, tax_rate)
            return tax
        except Exception as e:
            _logger.error("Error creating tax: %s", str(e))
            return False

    def _get_or_create_tax_for_shopify(self, tax_rate, tax_name, company):
        """Find or create a regular tax for Shopify orders

        We use a regular tax (NOT price_include) because we'll convert
        the Shopify tax-inclusive price to untaxed price ourselves.
        """
        # Search for existing tax with same rate (NOT price_include)
        tax = self.env['account.tax'].search([
            ('amount', '=', tax_rate),
            ('type_tax_use', '=', 'sale'),
            ('price_include', '=', False),
            ('company_id', '=', company.id),
        ], limit=1)

        if tax:
            return tax

        # Create new regular tax
        try:
            vals = {
                'name': f"{tax_name} {tax_rate}%",
                'amount': tax_rate,
                'type_tax_use': 'sale',
                'price_include': False,
                'company_id': company.id,
                'description': f"Imported from Shopify",
            }
            tax_group_id = default_tax_group(self.env, company)
            if tax_group_id:
                vals['tax_group_id'] = tax_group_id
            with self.env.cr.savepoint():
                tax = self.env['account.tax'].create(vals)
            _logger.info("Created new tax: %s (%.2f%%)", tax.name, tax_rate)
            return tax
        except Exception as e:
            _logger.error("Error creating tax: %s", str(e))
            return False

    def _get_or_create_shipping_product(self):
        """Get or create a shipping product for Shopify orders"""
        shipping_product = self.env['product.product'].search([
            ('default_code', '=', 'SHOPIFY-SHIPPING'),
        ], limit=1)

        if shipping_product:
            return shipping_product

        try:
            shipping_product = self.env['product.product'].create({
                'name': 'Shopify Shipping',
                'default_code': 'SHOPIFY-SHIPPING',
                'type': 'service',
                'list_price': 0,
                'sale_ok': True,
                'purchase_ok': False,
                'categ_id': default_product_category(self.env),
            })
            _logger.info("Created Shopify shipping product")
            return shipping_product
        except Exception as e:
            _logger.error("Error creating shipping product: %s", str(e))
            return self.env['product.product'].search([('type', '=', 'service')], limit=1)

    def _get_or_create_discount_product(self):
        """Get or create a discount product for Shopify orders"""
        discount_product = self.env['product.product'].search([
            ('default_code', '=', 'SHOPIFY-DISCOUNT'),
        ], limit=1)

        if discount_product:
            return discount_product

        try:
            discount_product = self.env['product.product'].create({
                'name': 'Shopify Discount',
                'default_code': 'SHOPIFY-DISCOUNT',
                'type': 'service',
                'list_price': 0,
                'sale_ok': True,
                'purchase_ok': False,
                'categ_id': default_product_category(self.env),
            })
            _logger.info("Created Shopify discount product")
            return discount_product
        except Exception as e:
            _logger.error("Error creating discount product: %s", str(e))
            return self.env['product.product'].search([('type', '=', 'service')], limit=1)

    def _get_or_create_tax_product(self):
        """Get or create a tax product for Shopify orders"""
        tax_product = self.env['product.product'].search([
            ('default_code', '=', 'SHOPIFY-TAX'),
        ], limit=1)

        if tax_product:
            return tax_product

        try:
            tax_product = self.env['product.product'].create({
                'name': 'Shopify Tax',
                'default_code': 'SHOPIFY-TAX',
                'type': 'service',
                'list_price': 0,
                'sale_ok': True,
                'purchase_ok': False,
                'categ_id': default_product_category(self.env),
            })
            _logger.info("Created Shopify tax product")
            return tax_product
        except Exception as e:
            _logger.error("Error creating tax product: %s", str(e))
            return self.env['product.product'].search([('type', '=', 'service')], limit=1)

    def _get_or_create_product(self, instance, line_item):
        """Get or create product from Shopify line item

        If sync_products_from_shopify is disabled, only lookup existing products by SKU/Barcode.
        Never create new products in this case.
        """
        Product = self.env['product.product']
        product_id = line_item.get('product_id')
        variant_id = line_item.get('variant_id')
        sku = line_item.get('sku', '').strip()
        product_title = line_item.get('name', line_item.get('title', 'Unknown Product'))

        # ============ PRODUCTION MODE: SKU/Barcode Lookup Only ============
        if not instance.sync_products_from_shopify:
            # Only lookup by SKU or Barcode - never create products
            if not sku:
                _logger.warning("Order line has no SKU: %s", product_title)
                if instance.skip_orders_missing_products:
                    return False
                # Return False to skip this line
                return False

            # Lookup based on configured field
            if instance.product_lookup_field == 'sku':
                product = Product.search([
                    ('default_code', '=', sku),
                    ('active', '=', True)
                ], limit=1)
            else:  # barcode
                product = Product.search([
                    ('barcode', '=', sku),
                    ('active', '=', True)
                ], limit=1)

            # Fallback: try the other field if not found
            if not product:
                if instance.product_lookup_field == 'sku':
                    # Try barcode as fallback
                    product = Product.search([
                        ('barcode', '=', sku),
                        ('active', '=', True)
                    ], limit=1)
                else:
                    # Try SKU as fallback
                    product = Product.search([
                        ('default_code', '=', sku),
                        ('active', '=', True)
                    ], limit=1)

            if not product:
                _logger.warning("Product not found for SKU: %s - Title: %s", sku, product_title)
                # Log the missing product
                self.env['shopify.log'].sudo().create({
                    'name': f'Product Not Found: {sku}',
                    'log_type': 'warning',
                    'message': f"Product not found for SKU: {sku} - Title: {product_title}",
                })
                return False

            return product

        # ============ NORMAL MODE: Full Sync with Product Creation ============
        # Try to find by Shopify mapping
        if product_id:
            product_mapping = self.env['shopify.product'].search([
                ('shopify_product_id', '=', str(product_id)),
                ('instance_id', '=', instance.id)
            ], limit=1)
            if product_mapping and product_mapping.odoo_product_id:
                return product_mapping.odoo_product_id

        # Try to find by variant
        if variant_id:
            variant_mapping = self.env['shopify.product'].search([
                ('shopify_variant_id', '=', str(variant_id)),
                ('instance_id', '=', instance.id)
            ], limit=1)
            if variant_mapping and variant_mapping.odoo_product_id:
                return variant_mapping.odoo_product_id

        # Try to find by SKU
        if sku:
            product = Product.search([('default_code', '=', sku)], limit=1)
            if product:
                return product

        # Create placeholder product (only in normal mode)
        # storable goods: 17 = 'product', 18/19 = 'consu' (see compat.py)
        product = Product.create({
            'name': product_title,
            'default_code': sku,
            'list_price': float(line_item.get('price', 0)),
            'type': STORABLE_TYPE,
            'categ_id': default_product_category(self.env),
        })

        return product

    def _sync_order_line_items(self, shopify_order):
        """Sync line items from Shopify order data to shopify.order.line model"""
        self.ensure_one()
        line_items = shopify_order.get('line_items', [])
        ShopifyOrderLine = self.env['shopify.order.line']

        for item in line_items:
            shopify_line_id = str(item.get('id', ''))
            if not shopify_line_id:
                continue

            # Check if line already exists
            existing_line = ShopifyOrderLine.search([
                ('shopify_line_id', '=', shopify_line_id),
                ('order_id', '=', self.id)
            ], limit=1)

            # Get tax lines for this item
            item_tax_lines = item.get('tax_lines', []) or []
            # Get discount allocations for this item
            discount_allocations = item.get('discount_allocations', []) or []
            # Get properties (custom attributes) for this item
            item_properties = item.get('properties', []) or []

            # ============ FIX: Calculate total discount from both sources ============
            # First try total_discount field
            line_total_discount = float(item.get('total_discount', 0))
            # If total_discount is 0, sum from discount_allocations (for BUNDLE discounts etc.)
            if line_total_discount == 0 and discount_allocations:
                for allocation in discount_allocations:
                    line_total_discount += float(allocation.get('amount', 0))

            # Prepare line values
            vals = {
                'order_id': self.id,
                'shopify_line_id': shopify_line_id,
                'shopify_product_id': str(item.get('product_id') or ''),
                'shopify_variant_id': str(item.get('variant_id') or ''),
                'title': item.get('title', ''),
                'variant_title': item.get('variant_title', ''),
                'sku': item.get('sku', ''),
                'vendor': item.get('vendor', ''),
                'quantity': item.get('quantity', 0),
                'price': float(item.get('price', 0)),
                'total_discount': line_total_discount,
                'fulfillable_quantity': item.get('fulfillable_quantity', 0),
                'taxable': item.get('taxable', False),
                'grams': float(item.get('grams', 0)),
                'requires_shipping': item.get('requires_shipping', True),
                'gift_card': item.get('gift_card', False),
                # === NEW FIELDS ===
                'barcode': item.get('barcode', '') or item.get('sku', ''),
                'total_tax': sum(float(t.get('price', 0) or 0) for t in item_tax_lines),
                'tax_lines_json': json.dumps(item_tax_lines) if item_tax_lines else '',
                'discount_allocations_json': json.dumps(discount_allocations) if discount_allocations else '',
                'properties_json': json.dumps(item_properties) if item_properties else '',
            }

            # Map fulfillment status
            fulfillment_status = item.get('fulfillment_status')
            if fulfillment_status == 'fulfilled':
                vals['fulfillment_status'] = 'fulfilled'
            elif fulfillment_status == 'partial':
                vals['fulfillment_status'] = 'partial'
            elif fulfillment_status == 'not_eligible':
                vals['fulfillment_status'] = 'not_eligible'
            else:
                vals['fulfillment_status'] = 'pending'

            # Link to shopify.product if exists
            if item.get('product_id'):
                product_mapping = self.env['shopify.product'].search([
                    ('shopify_product_id', '=', str(item['product_id'])),
                    ('instance_id', '=', self.instance_id.id)
                ], limit=1)
                if product_mapping:
                    vals['shopify_product_mapping_id'] = product_mapping.id

            if existing_line:
                existing_line.write(vals)
            else:
                ShopifyOrderLine.create(vals)

        _logger.debug("Synced %d line items for order %s", len(line_items), self.name)

    def export_orders_to_shopify(self, instance, orders):
        """Export orders to Shopify (Note: Shopify doesn't support creating orders via API in most cases)"""
        if not instance:
            raise UserError(_('No Shopify instance provided.'))

        job = self.env['shopify.queue.job'].create({
            'name': f'Export Orders ({instance.name})',
            'job_type': 'export_order',
            'instance_id': instance.id,
            'status': 'in_progress',
        })

        # Note: Shopify Admin API doesn't allow creating orders directly
        # This is mainly for updating order status/fulfillment

        exported_count = 0
        error_count = 0

        for order_mapping in orders:
            try:
                if not order_mapping.shopify_order_id:
                    continue

                # Update fulfillment status if needed
                odoo_order = order_mapping.odoo_order_id
                if odoo_order and odoo_order.state == 'done':
                    # Create fulfillment
                    fulfillment_data = {
                        'fulfillment': {
                            'location_id': None,  # Shopify will use default
                            'tracking_number': '',
                            'notify_customer': True,
                        }
                    }

                    try:
                        result = instance._shopify_request(
                            f'orders/{order_mapping.shopify_order_id}/fulfillments.json',
                            method='POST',
                            data=fulfillment_data
                        )
                        if result:
                            order_mapping.write({
                                'fulfillment_status': 'fulfilled',
                                'sync_status': 'synced',
                                'last_sync': fields.Datetime.now(),
                            })
                            exported_count += 1
                    except Exception as e:
                        _logger.warning("Could not create fulfillment: %s", str(e))

            except Exception as e:
                error_count += 1
                self.env['shopify.log'].create({
                    'name': 'Order Export Error',
                    'log_type': 'error',
                    'job_id': job.id,
                    'message': f'Error exporting order: {str(e)}',
                })

        job.write({'status': 'done'})
        self.env['shopify.log'].create({
            'name': 'Order Export Completed',
            'log_type': 'info',
            'job_id': job.id,
            'message': f'Export completed: {exported_count} exported, {error_count} errors',
        })

        return True

    def action_cancel_in_shopify(self):
        """Cancel order in Shopify"""
        self.ensure_one()
        if not self.shopify_order_id:
            raise UserError(_('No Shopify order ID found!'))

        try:
            result = self.instance_id._shopify_request(
                f'orders/{self.shopify_order_id}/cancel.json',
                method='POST'
            )
            if result:
                self.write({
                    'cancelled_at': fields.Datetime.now(),
                    'sync_status': 'synced',
                    'last_sync': fields.Datetime.now(),
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Order Cancelled'),
                        'message': _('Order cancelled in Shopify successfully!'),
                        'type': 'success',
                        'sticky': False,
                    },
                }
        except Exception as e:
            raise UserError(_('Failed to cancel order in Shopify: %s') % str(e))

    def _calculate_shipping_discount(self, shopify_order):
        """Calculate shipping discount from Shopify order data

        Shopify applies shipping discounts via discount_applications.
        We need to check if any discount targets shipping.

        Returns: float - total shipping discount amount
        """
        shipping_discount = 0.0

        try:
            # Get discount applications
            discount_applications = shopify_order.get('discount_applications', []) or []

            # Get shipping lines to check discounts
            shipping_lines = shopify_order.get('shipping_lines', []) or []

            for shipping_line in shipping_lines:
                # Check discount_allocations on shipping line
                discount_allocations = shipping_line.get('discount_allocations', []) or []
                for allocation in discount_allocations:
                    shipping_discount += float(allocation.get('amount', 0))

            # Also check if total shipping discount is available directly
            # Some Shopify setups store it differently
            if shipping_discount == 0:
                # Check discount_codes for shipping type
                discount_codes = shopify_order.get('discount_codes', []) or []
                for dc in discount_codes:
                    if dc.get('type') == 'shipping':
                        shipping_discount += float(dc.get('amount', 0))

            _logger.debug("Calculated shipping discount: %s", shipping_discount)

        except Exception as e:
            _logger.warning("Error calculating shipping discount: %s", str(e))

        return shipping_discount

    def action_resync_from_shopify(self):
        """Re-fetch this order from Shopify and update sale.order"""
        self.ensure_one()

        if not self.shopify_order_id or not self.instance_id:
            raise UserError(_('Missing Shopify Order ID or Instance!'))

        try:
            # Fetch fresh order data from Shopify
            result = self.instance_id._shopify_request(
                f'orders/{self.shopify_order_id}.json'
            )

            if not result or 'order' not in result:
                raise UserError(_('Could not fetch order from Shopify!'))

            shopify_order = result['order']

            # Update the shopify.order record
            self._sync_order_line_items(shopify_order)

            # Update or recreate sale.order
            if self.odoo_order_id:
                self._update_odoo_sale_order(self.odoo_order_id, self.instance_id, shopify_order)
            else:
                odoo_order = self._create_odoo_sale_order(self.instance_id, shopify_order)
                if odoo_order:
                    self.odoo_order_id = odoo_order.id

            self.write({
                'last_sync': fields.Datetime.now(),
                'sync_status': 'synced',
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Order Re-synced'),
                    'message': _('Order %s has been re-synced from Shopify!') % self.name,
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            _logger.error("Error re-syncing order %s: %s", self.name, str(e))
            raise UserError(_('Failed to re-sync order: %s') % str(e))

    @api.model
    def _run_order_import_cron(self):
        """Cron job to import orders from all active instances"""
        instances = self.env['shopify.instance'].search([
            ('state', '=', 'connected'),
            ('active', '=', True),
            ('auto_sync_orders', '=', True)
        ])
        for instance in instances:
            try:
                self.import_orders_from_shopify(instance)
            except Exception as e:
                _logger.error("Cron order import error for %s: %s", instance.name, str(e))