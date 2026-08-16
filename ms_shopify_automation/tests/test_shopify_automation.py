# -*- coding: utf-8 -*-
import json
from datetime import datetime
from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.ms_shopify_automation.models.shopify_order import parse_shopify_date


def _order_payload(order_id=990001, order_number=1001, sku='TEST-SKU-1'):
    """A realistic (trimmed) Shopify REST Admin API order payload."""
    return {
        'id': order_id,
        'order_number': order_number,
        'name': f'#{order_number}',
        'email': 'jane.doe@example.com',
        'created_at': '2026-08-01T10:30:00+03:00',
        'currency': 'USD',
        'financial_status': 'paid',
        'fulfillment_status': None,
        'total_price': '253.00',
        'subtotal_price': '230.00',
        'total_tax': '33.00',
        'total_discounts': '0.00',
        'customer': {
            'id': 555001,
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'jane.doe@example.com',
        },
        'shipping_address': {
            'first_name': 'Jane',
            'last_name': 'Doe',
            'name': 'Jane Doe',
            'address1': '12 Nile St',
            'city': 'Cairo',
            'country': 'Egypt',
            'country_code': 'EG',
            'phone': '+201000000001',
        },
        'billing_address': {},
        'line_items': [{
            'id': 880001,
            'product_id': 770001,
            'variant_id': 660001,
            'title': 'Test Widget',
            'name': 'Test Widget',
            'sku': sku,
            'quantity': 2,
            'price': '115.00',
            'total_discount': '0.00',
            'taxable': True,
            'requires_shipping': True,
            'tax_lines': [{'title': 'VAT', 'rate': 0.15, 'price': '30.00'}],
        }],
        'shipping_lines': [{'title': 'Standard Shipping', 'price': '23.00'}],
        'tax_lines': [{'title': 'VAT', 'rate': 0.15, 'price': '33.00'}],
        'discount_codes': [],
        'fulfillments': [],
    }


class TestShopifyAutomation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.instance = cls.env['shopify.instance'].create({
            'name': 'Test Store',
            'shop_url': 'https://test-store.myshopify.com',
            'access_token': 'shpat_dummy_token',
            'state': 'connected',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Test Widget',
            'default_code': 'TEST-SKU-1',
            'type': 'consu',
            'list_price': 100.0,
        })

    def test_all_models_registered(self):
        for model in ('shopify.instance', 'shopify.product', 'shopify.order',
                      'shopify.order.line', 'shopify.customer', 'shopify.queue.job',
                      'shopify.log', 'shopify.webhook', 'shopify.payout',
                      'shopify.carrier', 'shopify.risk', 'shopify.analytics',
                      'shopify.workflow', 'shopify.cron',
                      'shopify.manual.sync.wizard'):
            self.assertIn(model, self.env, f'{model} missing from registry')

    def test_dashboard_kpis_on_empty_instance(self):
        inst = self.instance
        self.assertEqual(inst.order_count, 0)
        self.assertEqual(inst.product_count, 0)
        self.assertEqual(inst.customer_count, 0)
        self.assertEqual(inst.total_sales, 0.0)
        self.assertIsInstance(inst.sales_chart_data, dict)
        self.assertIn('labels', inst.sales_chart_data)
        self.assertIn('values', inst.sales_chart_data)

    def test_queue_processing_cron(self):
        job = self.env['shopify.queue.job'].create({
            'name': 'Test Job',
            'job_type': 'import_order',
            'instance_id': self.instance.id,
            'status': 'pending',
        })
        # must not raise; stub process_job leaves the job pending
        self.env['shopify.queue.job']._cron_process_queue()
        self.assertIn(job.status, ('pending', 'done'))

    def test_log_cleanup_cron(self):
        Log = self.env['shopify.log']
        old_log = Log.create({'name': 'Old', 'log_type': 'info', 'message': 'old'})
        fresh_log = Log.create({'name': 'Fresh', 'log_type': 'info', 'message': 'new'})
        # backdate the first log 60 days
        self.env.cr.execute(
            "UPDATE shopify_log SET create_date = now() - interval '60 days' WHERE id = %s",
            [old_log.id])
        Log.invalidate_model(['create_date'])
        Log._cron_cleanup_old_logs(days=30)
        self.assertFalse(old_log.exists())
        self.assertTrue(fresh_log.exists())

    def test_product_barcode_name_search(self):
        Product = self.env['product.product']
        target = Product.create({
            'name': 'Widget With Barcode',
            'barcode': '9998887776665',
            'default_code': 'BW-01',
            'type': 'consu',
        })
        Product.create({
            'name': '9998887776665 lookalike name',
            'type': 'consu',
        })
        res = Product.name_search('9998887776665')
        self.assertEqual(res[0][0], target.id,
                         'exact barcode match must be returned first')
        res_code = Product.name_search('BW-01')
        self.assertEqual(res_code[0][0], target.id,
                         'exact default_code match must be returned first')

    def test_sale_order_shopify_display_fields(self):
        partner = self.env['res.partner'].create({'name': 'Shopify Buyer'})
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'is_shopify_order': True,
            'shopify_discount_code': 'SUMMER10',
            'shopify_shipping_method': 'Standard Shipping',
            'shopify_tax_name': 'VAT',
            'shopify_tax_rate': 15.0,
        })
        self.assertEqual(order.shopify_discount_display, 'SUMMER10')
        self.assertEqual(order.shopify_shipping_display, 'Standard Shipping')
        self.assertEqual(order.shopify_tax_display, 'VAT 15%')

    def test_order_parsing_helpers(self):
        ShopifyOrder = self.env['shopify.order']
        payload = _order_payload()
        self.assertEqual(ShopifyOrder._build_customer_full_name(payload), 'Jane Doe')
        self.assertEqual(ShopifyOrder._get_shipping_method_title(payload), 'Standard Shipping')
        self.assertEqual(ShopifyOrder._get_first_tracking_number(payload), '')
        # name fallback: no first/last names anywhere -> use address "name"
        self.assertEqual(
            ShopifyOrder._build_customer_full_name(
                {'shipping_address': {'name': 'Full Name Only'}}),
            'Full Name Only')
        self.assertEqual(
            ShopifyOrder._build_customer_full_name({}), 'Unknown Customer')
        dt = parse_shopify_date('2026-08-01T10:30:00+03:00')
        self.assertEqual(dt, datetime(2026, 8, 1, 10, 30, 0))
        self.assertFalse(parse_shopify_date(None))
        self.assertFalse(parse_shopify_date('not-a-date'))

    def test_special_service_products_idempotent(self):
        ShopifyOrder = self.env['shopify.order']
        ship1 = ShopifyOrder._get_or_create_shipping_product()
        ship2 = ShopifyOrder._get_or_create_shipping_product()
        self.assertEqual(ship1, ship2)
        self.assertEqual(ship1.default_code, 'SHOPIFY-SHIPPING')
        self.assertEqual(ship1.type, 'service')
        disc = ShopifyOrder._get_or_create_discount_product()
        self.assertEqual(disc.default_code, 'SHOPIFY-DISCOUNT')
        tax = ShopifyOrder._get_or_create_tax_product()
        self.assertEqual(tax.default_code, 'SHOPIFY-TAX')
        # all three are excluded from scheme discounts
        excluded = self.env['sale.order.line'].EXCLUDED_FROM_SCHEME_DISCOUNT
        for code in ('SHOPIFY-SHIPPING', 'SHOPIFY-DISCOUNT', 'SHOPIFY-TAX'):
            self.assertIn(code, excluded)

    def test_get_or_create_tax_idempotent(self):
        ShopifyOrder = self.env['shopify.order']
        company = self.env.company
        tax1 = ShopifyOrder._get_or_create_tax_for_shopify(14.0, 'VAT', company)
        tax2 = ShopifyOrder._get_or_create_tax_for_shopify(14.0, 'VAT', company)
        self.assertEqual(tax1, tax2)
        self.assertEqual(tax1.amount, 14.0)
        self.assertEqual(tax1.type_tax_use, 'sale')
        self.assertFalse(tax1.price_include)

    def test_import_orders_creates_sale_order(self):
        payload = _order_payload()

        def fake_request(inst, endpoint, method='GET', data=None, params=None):
            return {'orders': [payload]}, None

        # production code commits per batch; commits are forbidden inside tests
        with patch.object(type(self.instance), '_shopify_request_with_link',
                          fake_request), \
             patch.object(self.env.cr, 'commit', lambda: None):
            self.env['shopify.order'].import_orders_from_shopify(self.instance)

        mapping = self.env['shopify.order'].search([
            ('shopify_order_id', '=', '990001'),
            ('instance_id', '=', self.instance.id),
        ])
        self.assertEqual(len(mapping), 1, 'one shopify.order mapping expected')
        self.assertEqual(mapping.name, '#1001')
        self.assertEqual(mapping.financial_status, 'paid')
        self.assertEqual(mapping.customer_name, 'Jane Doe')

        # shopify.order.line rows synced
        self.assertEqual(len(mapping.line_ids), 1)
        self.assertEqual(mapping.line_ids.sku, 'TEST-SKU-1')
        self.assertEqual(mapping.line_ids.quantity, 2)

        # real sale.order created
        order = mapping.odoo_order_id
        self.assertTrue(order, 'sale order must be created')
        self.assertTrue(order.is_shopify_order)
        self.assertEqual(order.shopify_order_number, '1001')
        self.assertEqual(order.partner_id.email, 'jane.doe@example.com')

        # product line: 115 incl. 15% VAT -> 100 untaxed
        product_line = order.order_line.filtered(
            lambda l: l.product_id == self.product)
        self.assertEqual(len(product_line), 1,
                         'order line must reuse existing product by SKU')
        self.assertAlmostEqual(product_line.price_unit, 100.0, places=2)
        self.assertEqual(product_line.product_uom_qty, 2)

        # shipping line: 23 incl. VAT -> 20 untaxed
        ship_line = order.order_line.filtered(
            lambda l: l.product_id.default_code == 'SHOPIFY-SHIPPING')
        self.assertEqual(len(ship_line), 1)
        self.assertAlmostEqual(ship_line.price_unit, 20.0, places=2)

        # queue job finished + sync timestamp updated
        job = self.env['shopify.queue.job'].search([
            ('instance_id', '=', self.instance.id),
            ('job_type', '=', 'import_order')], limit=1)
        self.assertEqual(job.status, 'done')
        self.assertTrue(self.instance.last_order_sync)

        # completion log written
        log = self.env['shopify.log'].search([
            ('name', '=', 'Order Import Completed')], limit=1)
        self.assertTrue(log)

    def test_import_orders_requires_connection(self):
        draft_instance = self.env['shopify.instance'].create({
            'name': 'Draft Store',
            'shop_url': 'https://draft-store.myshopify.com',
            'access_token': 'shpat_other_token',
            'state': 'draft',
        })
        with self.assertRaises(Exception):
            self.env['shopify.order'].import_orders_from_shopify(draft_instance)


@tagged('post_install', '-at_install')
class TestShopifyWebhookEndpoint(HttpCase):

    def test_webhook_order_endpoint_creates_job(self):
        instance = self.env['shopify.instance'].create({
            'name': 'Webhook Store',
            'shop_url': 'https://webhook-store.myshopify.com',
            'access_token': 'shpat_webhook_token',
        })
        body = json.dumps({
            'jsonrpc': '2.0', 'method': 'call',
            'params': {'id': 12345, 'name': '#2001'},
        })
        resp = self.url_open(
            '/shopify/webhook/order', data=body,
            headers={
                'Content-Type': 'application/json',
                'X-Shopify-Shop-Domain': 'webhook-store.myshopify.com',
            })
        self.assertEqual(resp.status_code, 200)
        result = resp.json().get('result')
        self.assertEqual(result.get('status'), 'ok')
        job = self.env['shopify.queue.job'].browse(result['job_id'])
        self.assertTrue(job.exists())
        self.assertEqual(job.job_type, 'import_order')
        self.assertEqual(job.instance_id, instance)
        self.assertEqual(job.status, 'pending')
