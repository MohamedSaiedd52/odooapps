# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.salla_api import verify_webhook_signature


def product_payload(pid=1001, name="Luxury Abaya", price=350.0,
                    sku="ABAYA-001"):
    return {
        'id': pid,
        'name': name,
        'price': {'amount': price, 'currency': 'SAR'},
        'sku': sku,
        'description': 'Premium black abaya, hand-stitched.',
        'urls': {'customer': f'https://demo-store.salla.sa/p/{pid}'},
    }


def order_payload(oid=7001, items=None):
    return {
        'id': oid,
        'status': {'name': 'Under Review'},
        'customer': {
            'first_name': 'Sara',
            'last_name': 'Alqahtani',
            'mobile': '+966501234567',
            'email': 'sara@example.com',
        },
        'items': items if items is not None else [{
            'product': {'id': 1001},
            'sku': 'ABAYA-001',
            'name': 'Luxury Abaya',
            'quantity': 2,
            'amounts': {'price_without_tax': {'amount': 350.0}},
        }],
    }


@tagged('post_install', '-at_install')
class TestSallaSync(TransactionCase):

    def test_product_create_then_update(self):
        Template = self.env['product.template']
        Template._import_salla_product(product_payload())
        product = Template.search([('salla_product_id', '=', '1001')])
        self.assertEqual(len(product), 1)
        self.assertEqual(product.name, 'Luxury Abaya')
        self.assertEqual(product.list_price, 350.0)
        self.assertEqual(product.default_code, 'ABAYA-001')
        self.assertTrue(product.salla_url)

        Template._import_salla_product(
            product_payload(name="Luxury Abaya v2", price=399.0))
        product2 = Template.search([('salla_product_id', '=', '1001')])
        self.assertEqual(product2, product)  # updated, not duplicated
        self.assertEqual(product2.name, 'Luxury Abaya v2')
        self.assertEqual(product2.list_price, 399.0)

    def test_product_linked_by_sku(self):
        Template = self.env['product.template']
        existing = Template.create(
            {'name': 'Local Abaya', 'default_code': 'ABAYA-XYZ'})
        Template._import_salla_product(
            product_payload(pid=2002, sku='ABAYA-XYZ'))
        existing.invalidate_recordset()
        self.assertEqual(existing.salla_product_id, '2002')
        self.assertEqual(
            Template.search_count([('default_code', '=', 'ABAYA-XYZ')]), 1)

    def test_order_import_and_dedup(self):
        self.env['product.template']._import_salla_product(product_payload())
        Order = self.env['sale.order']
        Order._import_salla_order(order_payload())
        order = Order.search([('salla_order_id', '=', '7001')])
        self.assertEqual(len(order), 1)
        self.assertEqual(order.salla_status, 'Under Review')
        self.assertEqual(order.partner_id.name, 'Sara Alqahtani')
        phone_field = 'mobile' \
            if 'mobile' in self.env['res.partner']._fields else 'phone'
        self.assertEqual(order.partner_id[phone_field], '+966501234567')
        line = order.order_line
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_uom_qty, 2)
        self.assertEqual(line.price_unit, 350.0)
        self.assertEqual(line.product_id.default_code, 'ABAYA-001')

        Order._import_salla_order(order_payload())  # same order again
        self.assertEqual(
            Order.search_count([('salla_order_id', '=', '7001')]), 1)

    def test_order_creates_missing_product(self):
        Order = self.env['sale.order']
        items = [{
            'product': {'id': 3003},
            'sku': 'NEW-SKU-1',
            'name': 'Unknown Salla Product',
            'quantity': 1,
            'amounts': {'price_without_tax': {'amount': 75.0}},
        }]
        Order._import_salla_order(order_payload(oid=7002, items=items))
        order = Order.search([('salla_order_id', '=', '7002')])
        self.assertEqual(len(order.order_line), 1)
        product = order.order_line.product_id
        self.assertTrue(product, "missing product must be created on the fly")
        self.assertEqual(product.default_code, 'NEW-SKU-1')
        self.assertEqual(
            product.product_tmpl_id.salla_product_id, '3003')

    def test_partner_dedup_by_mobile(self):
        Order = self.env['sale.order']
        self.env['product.template']._import_salla_product(product_payload())
        Order._import_salla_order(order_payload(oid=7010))
        Order._import_salla_order(order_payload(oid=7011))
        orders = Order.search(
            [('salla_order_id', 'in', ['7010', '7011'])])
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].partner_id, orders[1].partner_id)

    def test_webhook_signature(self):
        import hashlib
        import hmac as hmac_lib
        secret, body = 'top-secret', b'{"event": "order.created"}'
        good = hmac_lib.new(secret.encode(), body,
                            hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(secret, body, good))
        self.assertFalse(verify_webhook_signature(secret, body, 'bad-sig'))
        self.assertFalse(verify_webhook_signature(secret, body, None))
        # verification disabled when no secret is configured
        self.assertTrue(verify_webhook_signature(None, body, None))
