# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests import tagged
from odoo.addons.stock_account.tests.test_anglo_saxon_valuation_reconciliation_common import (
    ValuationReconciliationTestCommon,
)


@tagged('post_install', '-at_install')
class TestAvcoReturnCost(ValuationReconciliationTestCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.avco_categ = cls.env['product.category'].create({
            'name': 'AVCO category',
            'property_valuation': 'real_time',
            'property_cost_method': 'average',
            'property_stock_valuation_account_id': cls.company_data['default_account_stock_valuation'].id,
            'property_stock_account_input_categ_id': cls.company_data['default_account_stock_in'].id,
            'property_stock_account_output_categ_id': cls.company_data['default_account_stock_out'].id,
        })
        cls.vendor = cls.env['res.partner'].create({'name': 'AVCO Vendor'})
        cls.customer = cls.env['res.partner'].create({'name': 'AVCO Customer'})

    def _make_product(self, name):
        return self.env['product.product'].create({
            'name': name,
            'type': 'product',
            'categ_id': self.avco_categ.id,
            'purchase_method': 'receive',
        })

    def _buy(self, product, qty, price):
        """Confirm a PO of `qty` @ `price` and validate its receipt."""
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_qty': qty,
                'price_unit': price,
            })],
        })
        po.button_confirm()
        picking = po.picking_ids
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        return po, picking

    def _return(self, picking, qty, to_refund=False):
        wiz = self.env['stock.return.picking'].with_context(
            active_id=picking.id, active_ids=picking.ids,
            active_model='stock.picking').create({})
        for line in wiz.product_return_moves:
            line.quantity = qty
            line.to_refund = to_refund
        res = wiz.create_returns()
        ret = self.env['stock.picking'].browse(res['res_id'])
        ret.move_ids.picked = True
        ret.button_validate()
        self.assertEqual(ret.state, 'done')
        return ret

    def _bill(self, po):
        po.action_create_invoice()
        inv = po.invoice_ids.filtered(lambda m: m.state == 'draft')
        inv.invoice_date = fields.Date.today()
        inv.action_post()
        return inv

    def _deliver(self, product, qty):
        pick_type = self.company_data['default_warehouse'].out_type_id
        customers = self.env.ref('stock.stock_location_customers')
        picking = self.env['stock.picking'].create({
            'picking_type_id': pick_type.id,
            'partner_id': self.customer.id,
            'location_id': pick_type.default_location_src_id.id,
            'location_dest_id': customers.id,
            'move_ids': [(0, 0, {
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': pick_type.default_location_src_id.id,
                'location_dest_id': customers.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = qty
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        return picking

    def _interim_balance(self, product):
        amls = self.env['account.move.line'].search([
            ('account_id', '=', self.company_data['default_account_stock_in'].id),
            ('product_id', '=', product.id),
            ('parent_state', '=', 'posted'),
        ])
        return sum(amls.mapped('balance'))

    def test_return_expensive_batch(self):
        """Buy 10 @ 100 then 10 @ 200, return the 200 batch: the remaining
        10 units must be worth 1000 (not 1500) and the average must be 100."""
        product = self._make_product('P expensive return')
        self._buy(product, 10, 100.0)
        po2, pick2 = self._buy(product, 10, 200.0)
        self.assertEqual(product.standard_price, 150.0)
        self.assertEqual(product.value_svl, 3000.0)

        self._return(pick2, 10)

        self.assertEqual(product.quantity_svl, 10.0)
        self.assertEqual(product.value_svl, 1000.0, "remaining stock must keep the 100-batch value")
        self.assertEqual(product.standard_price, 100.0, "average must realign with remaining stock")

        # COGS of a subsequent delivery must use the corrected average
        self._deliver(product, 5)
        out_svl = self.env['stock.valuation.layer'].search(
            [('product_id', '=', product.id)], order='id desc', limit=1)
        self.assertEqual(out_svl.value, -500.0)

    def test_return_cheap_batch(self):
        """Buy 10 @ 30 then 10 @ 50, return the 30 batch: remaining stock
        must be worth 500 (not 400)."""
        product = self._make_product('P cheap return')
        po1, pick1 = self._buy(product, 10, 30.0)
        self._buy(product, 10, 50.0)
        self.assertEqual(product.standard_price, 40.0)

        self._return(pick1, 10)

        self.assertEqual(product.value_svl, 500.0)
        self.assertEqual(product.standard_price, 50.0)

    def test_partial_return(self):
        """Buy 10 @ 100 then 10 @ 200, return only 4 of the 200 batch:
        out layer = 4 x 200, remaining 16 units worth 2200, avg 137.5."""
        product = self._make_product('P partial return')
        self._buy(product, 10, 100.0)
        po2, pick2 = self._buy(product, 10, 200.0)

        ret = self._return(pick2, 4)

        ret_svl = ret.move_ids.stock_valuation_layer_ids
        self.assertEqual(ret_svl.value, -800.0)
        self.assertEqual(ret_svl.unit_cost, 200.0)
        self.assertEqual(product.quantity_svl, 16.0)
        self.assertEqual(product.value_svl, 2200.0)
        self.assertAlmostEqual(product.standard_price, 137.5)

    def test_return_everything(self):
        """Returning all stock must leave exactly zero value (no residue)."""
        product = self._make_product('P return all')
        po1, pick1 = self._buy(product, 10, 100.0)
        po2, pick2 = self._buy(product, 10, 200.0)

        self._return(pick2, 10)
        self._return(pick1, 10)

        self.assertEqual(product.quantity_svl, 0.0)
        self.assertEqual(product.value_svl, 0.0)

    def test_return_with_bills_and_credit_note(self):
        """Full accounting flow: bills at PO prices, return the 90 batch with
        to_refund, credit note from the PO. The interim (received) account
        must net to zero and the remaining stock must be worth 600."""
        product = self._make_product('P billed return')
        po1, pick1 = self._buy(product, 10, 60.0)
        po2, pick2 = self._buy(product, 10, 90.0)
        self._bill(po1)
        self._bill(po2)
        self.assertAlmostEqual(self._interim_balance(product), 0.0)

        self._return(pick2, 10, to_refund=True)
        credit_note = self._bill(po2)  # negative qty to invoice -> refund
        self.assertEqual(credit_note.move_type, 'in_refund')
        self.assertEqual(credit_note.amount_untaxed, 900.0)

        self.assertAlmostEqual(self._interim_balance(product), 0.0,
                               msg="no residue may stay in the interim account")
        self.assertEqual(product.value_svl, 600.0)
        self.assertEqual(product.standard_price, 60.0)

    def test_normal_delivery_unaffected(self):
        """A plain delivery (not a return) must still go out at the average."""
        product = self._make_product('P normal delivery')
        self._buy(product, 10, 100.0)
        self._buy(product, 10, 200.0)

        delivery = self._deliver(product, 4)

        out_svl = delivery.move_ids.stock_valuation_layer_ids
        self.assertEqual(out_svl.value, -600.0, "4 units at the 150 average")
        self.assertEqual(product.standard_price, 150.0)
