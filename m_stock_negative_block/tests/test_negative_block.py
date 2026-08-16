# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNegativeStockBlock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.product = cls._make_storable_product('PSNB Test Product')
        cls._set_on_hand(cls.product, cls.stock_location, 5.0)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @classmethod
    def _make_storable_product(cls, name):
        vals = {'name': name, 'type': 'consu'}
        if 'is_storable' in cls.env['product.product']._fields:
            vals['is_storable'] = True          # Odoo 18 / 19
        else:
            vals['type'] = 'product'            # Odoo 17
        return cls.env['product.product'].create(vals)

    @classmethod
    def _set_on_hand(cls, product, location, qty):
        quant = cls.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': location.id,
            'inventory_quantity': qty,
        })
        quant.action_apply_inventory()

    def _on_hand(self, product, location):
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ])
        return sum(quants.mapped('quantity'))

    def _make_picking(self, picking_type, src, dest, product, qty):
        move_vals = {
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': qty,
            'location_id': src.id,
            'location_dest_id': dest.id,
        }
        if 'name' in self.env['stock.move']._fields:   # dropped in Odoo 19
            move_vals['name'] = product.name
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'move_ids': [(0, 0, move_vals)],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = qty
        picking.move_ids.picked = True
        return picking

    def _make_delivery(self, qty, product=None):
        return self._make_picking(
            self.warehouse.out_type_id, self.stock_location,
            self.customer_location, product or self.product, qty)

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------
    def test_01_delivery_over_stock_is_blocked(self):
        """Shipping 8 out of 5 on hand must raise instead of going negative."""
        picking = self._make_delivery(8.0)
        with self.assertRaises(UserError) as err:
            picking.button_validate()
        self.assertIn('negative', err.exception.args[0].lower())
        self.assertNotEqual(picking.state, 'done')
        self.assertEqual(self._on_hand(self.product, self.stock_location), 5.0)

    def test_02_delivery_within_stock_is_allowed(self):
        """Shipping exactly what is on hand still works."""
        picking = self._make_delivery(5.0)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self._on_hand(self.product, self.stock_location), 0.0)

    def test_03_allow_negative_stock_on_location(self):
        """The escape hatch on the source location lets the transfer through."""
        self.stock_location.allow_negative_stock = True
        try:
            picking = self._make_delivery(8.0)
            picking.button_validate()
            self.assertEqual(picking.state, 'done')
            self.assertEqual(self._on_hand(self.product, self.stock_location), -3.0)
        finally:
            self.stock_location.allow_negative_stock = False

    def test_04_allow_negative_stock_is_inherited(self):
        """Ticking the flag on a parent covers its child locations."""
        shelf = self.env['stock.location'].create({
            'name': 'PSNB Shelf',
            'location_id': self.stock_location.id,
            'usage': 'internal',
        })
        product = self._make_storable_product('PSNB Shelf Product')
        self._set_on_hand(product, shelf, 2.0)

        picking = self._make_picking(
            self.warehouse.out_type_id, shelf, self.customer_location, product, 4.0)
        with self.assertRaises(UserError):
            picking.button_validate()

        self.stock_location.allow_negative_stock = True
        try:
            picking.button_validate()
            self.assertEqual(picking.state, 'done')
            self.assertEqual(self._on_hand(product, shelf), -2.0)
        finally:
            self.stock_location.allow_negative_stock = False

    def test_05_receipt_is_never_blocked(self):
        """Vendor receipts come from a virtual location and stay untouched."""
        product = self._make_storable_product('PSNB Receipt Product')
        picking = self._make_picking(
            self.warehouse.in_type_id, self.supplier_location,
            self.stock_location, product, 3.0)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self._on_hand(product, self.stock_location), 3.0)

    def test_07_uom_conversion_is_taken_into_account(self):
        """A move expressed in another UoM is converted before comparing."""
        product = self._make_storable_product('PSNB Dozen Product')
        self._set_on_hand(product, self.stock_location, 5.0)
        dozen = self.env.ref('uom.product_uom_dozen')

        move_vals = {
            'product_id': product.id,
            'product_uom': dozen.id,
            'product_uom_qty': 1.0,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
        }
        if 'name' in self.env['stock.move']._fields:
            move_vals['name'] = product.name
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'move_ids': [(0, 0, move_vals)],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = 1.0        # 1 Dozen = 12 Units
        picking.move_ids.picked = True

        with self.assertRaises(UserError) as err:
            picking.button_validate()
        # The shortage must be reported in the product UoM, not in dozens.
        self.assertIn('12', err.exception.args[0])
        self.assertEqual(self._on_hand(product, self.stock_location), 5.0)

    def test_08_reservation_of_another_transfer_does_not_block(self):
        """Only what this transfer takes out is counted, not other bookings."""
        product = self._make_storable_product('PSNB Shared Product')
        self._set_on_hand(product, self.stock_location, 10.0)

        # A greedy transfer books 12 units out of the 10 available.
        greedy = self._make_delivery(12.0, product=product)
        self.assertEqual(greedy.move_ids.quantity, 12.0)

        # A small transfer for 2 units still leaves 8 on hand: let it through.
        small = self._make_delivery(2.0, product=product)
        small.button_validate()
        self.assertEqual(small.state, 'done')
        self.assertEqual(self._on_hand(product, self.stock_location), 8.0)

    def test_06_sale_order_confirmation_logs_a_warning(self):
        """Selling more than the free stock is allowed but reported."""
        partner = self.env['res.partner'].create({'name': 'PSNB Customer'})
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 9.0,
            })],
        })
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        bodies = ' '.join(order.message_ids.mapped('body'))
        self.assertIn('Stock availability warning', bodies)
        self.assertIn('PSNB Test Product', bodies)
