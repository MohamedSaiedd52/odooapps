# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestCashOnDelivery(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # On Odoo 19 the COD provider/method are native (delivery module);
        # on 17/18 this module ships its own records.
        cls.provider = cls.env.ref(
            'ms_website_cash_on_delivery.payment_provider_cod',
            raise_if_not_found=False) \
            or cls.env.ref('delivery.payment_provider_cod')
        cls.provider.write({
            'state': 'test',
            'is_published': True,
            'cod_min_order_amount': 100.0,
            'cod_fee_fixed': 10.0,
            'cod_fee_percent': 1.0,
            'cod_allowed_zip_codes': '11511, 21532',
        })
        cls.method = cls.provider.payment_method_ids[:1]
        cls.partner = cls.env['res.partner'].create({
            'name': 'COD Customer',
            'zip': '11511',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'COD Test Product',
            'list_price': 200.0,
        })
        carrier_product = cls.env['product.product'].create({
            'name': 'COD Test Shipping',
        })
        carrier_vals = {
            'name': 'COD Test Carrier',
            'product_id': carrier_product.id,
        }
        # Odoo 19 additionally gates COD behind the delivery method.
        cls.cod_native = 'allow_cash_on_delivery' \
            in cls.env['delivery.carrier']._fields
        if cls.cod_native:
            carrier_vals['allow_cash_on_delivery'] = True
        cls.carrier = cls.env['delivery.carrier'].create(carrier_vals)
        cls.order = cls._make_order(cls.partner)

    @classmethod
    def _make_order(cls, partner):
        return cls.env['sale.order'].create({
            'partner_id': partner.id,
            'carrier_id': cls.carrier.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
            })],
        })

    def _compatible(self, amount, order=None):
        order = order or self.order
        return self.env['payment.provider']._get_compatible_providers(
            self.env.company.id, order.partner_id.id, amount,
            currency_id=self.env.company.currency_id.id,
            sale_order_id=order.id,
        )

    def test_min_amount_rule(self):
        self.assertIn(self.provider, self._compatible(200.0))
        self.assertNotIn(self.provider, self._compatible(50.0))

    def test_zip_rule(self):
        bad_order = self._make_order(self.env['res.partner'].create(
            {'name': 'Far Away', 'zip': '99999'}))
        self.assertNotIn(self.provider, self._compatible(200.0, bad_order))
        no_zip_order = self._make_order(self.env['res.partner'].create(
            {'name': 'No Zip'}))
        self.assertNotIn(self.provider,
                         self._compatible(200.0, no_zip_order))
        self.provider.cod_allowed_zip_codes = False
        self.assertIn(self.provider, self._compatible(200.0, no_zip_order))

    def test_pending_flags_order_and_adds_fee(self):
        amount_before = self.order.amount_total
        tx = self.env['payment.transaction'].create({
            'provider_id': self.provider.id,
            'payment_method_id': self.method.id,
            'amount': amount_before,
            'currency_id': self.order.currency_id.id,
            'partner_id': self.partner.id,
            'reference': 'COD-TEST-1',
            'sale_order_ids': [(6, 0, self.order.ids)],
        })
        tx._set_pending()
        self.assertTrue(self.order.is_cod_order)
        expected_fee = self.order.currency_id.round(
            10.0 + amount_before * 1.0 / 100.0)
        self.assertEqual(self.order.cod_fee_amount, expected_fee)
        fee_product = self.env.ref(
            'ms_website_cash_on_delivery.product_cod_fee')
        fee_lines = self.order.order_line.filtered(
            lambda l: l.product_id == fee_product)
        self.assertEqual(len(fee_lines), 1)
        self.assertEqual(fee_lines.price_unit, expected_fee)
        # a second pending call must not duplicate the fee
        tx._set_pending(extra_allowed_states=('pending',))
        self.assertEqual(len(self.order.order_line.filtered(
            lambda l: l.product_id == fee_product)), 1)
