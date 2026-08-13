# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApprovalFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        gfield = "group_ids" if "group_ids" in Users._fields else "groups_id"
        base_groups = [
            cls.env.ref("base.group_user").id,
            cls.env.ref("irio_approval_flow.group_approval_user").id,
        ]

        def mk_user(name, login):
            return Users.create({
                "name": name, "login": login, "email": login + "@test.irio",
                gfield: [(6, 0, base_groups)],
            })

        cls.u_l1 = mk_user("Approver Level1", "irio_appr_l1")
        cls.u_l2 = mk_user("Approver Level2", "irio_appr_l2")
        cls.u_deleg = mk_user("Delegate User", "irio_appr_deleg")

        cls.partner = cls.env["res.partner"].create({"name": "Approval Test Partner"})
        cls.service = cls.env["product.product"].create({
            "name": "Approval Test Service", "type": "service",
            "list_price": 100.0,
        })
        storable_vals = {"name": "Approval Test Widget", "standard_price": 600.0}
        if "is_storable" in cls.env["product.product"]._fields:
            storable_vals.update({"type": "consu", "is_storable": True})
        else:
            storable_vals.update({"type": "product"})
        cls.widget = cls.env["product.product"].create(storable_vals)

        Rule = cls.env["irio.approval.rule"]
        # isolate from demo-data rules that could shadow the test matrix
        Rule.search([]).write({"active": False})
        cls.rule_so = Rule.create({
            "name": "SO >= 1000", "model_apply": "sale.order",
            "min_amount": 1000, "max_amount": 0,
            "level_ids": [
                (0, 0, {"sequence": 1, "name": "L1",
                        "user_ids": [(6, 0, cls.u_l1.ids)],
                        "min_approvals": 1, "escalate_days": 3}),
                (0, 0, {"sequence": 2, "name": "L2",
                        "user_ids": [(6, 0, cls.u_l2.ids)],
                        "min_approvals": 1, "escalate_days": 2}),
            ],
        })
        cls.rule_so_big = Rule.create({
            "name": "SO >= 10000", "model_apply": "sale.order",
            "min_amount": 10000, "max_amount": 0,
            "level_ids": [(0, 0, {"sequence": 1, "name": "Big L1",
                                  "user_ids": [(6, 0, cls.u_l2.ids)],
                                  "min_approvals": 1, "escalate_days": 1})],
        })
        cls.rule_po = Rule.create({
            "name": "PO >= 500", "model_apply": "purchase.order",
            "min_amount": 500, "max_amount": 0,
            "level_ids": [(0, 0, {"sequence": 1, "name": "PO L1",
                                  "user_ids": [(6, 0, cls.u_l1.ids)],
                                  "min_approvals": 1, "escalate_days": 3})],
        })
        cls.rule_inv = Rule.create({
            "name": "INV >= 1000", "model_apply": "account.move",
            "min_amount": 1000, "max_amount": 0,
            "level_ids": [(0, 0, {"sequence": 1, "name": "INV L1",
                                  "user_ids": [(6, 0, cls.u_l1.ids)],
                                  "min_approvals": 1, "escalate_days": 3})],
        })
        cls.rule_pick = Rule.create({
            "name": "PICK >= 1000", "model_apply": "stock.picking",
            "min_amount": 1000, "max_amount": 0,
            "level_ids": [(0, 0, {"sequence": 1, "name": "PICK L1",
                                  "user_ids": [(6, 0, cls.u_l1.ids)],
                                  "min_approvals": 1, "escalate_days": 3})],
        })

    def _make_so(self, price):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.service.id,
                "product_uom_qty": 1,
                "price_unit": price,
            })],
        })

    # ------------------------------------------------------------------
    def test_01_rule_matching_most_specific(self):
        so_small = self._make_so(5000)
        so_big = self._make_so(15000)
        self.assertEqual(so_small._irio_find_rule(), self.rule_so)
        self.assertEqual(so_big._irio_find_rule(), self.rule_so_big)

    def test_02_below_threshold_confirms_freely(self):
        so = self._make_so(100)
        self.assertFalse(so._irio_find_rule())
        so.action_confirm()
        self.assertEqual(so.state, "sale")

    def test_03_so_blocked_then_two_level_approval(self):
        so = self._make_so(5000)
        with self.assertRaises(UserError):
            so.action_confirm()
        so.action_irio_request_approval()
        req = so.irio_approval_request_id
        self.assertTrue(req.name.startswith("IRA/"))
        self.assertEqual(req.state, "pending")
        self.assertEqual(len(req.step_ids), 2)
        # still blocked while pending
        with self.assertRaises(UserError):
            so.action_confirm()
        req.with_user(self.u_l1).action_approve()
        self.assertEqual(req.current_step_id.name, "L2")
        req.with_user(self.u_l2).action_approve()
        self.assertEqual(req.state, "approved")
        so.action_confirm()
        self.assertEqual(so.state, "sale")

    def test_04_wrong_user_cannot_approve(self):
        so = self._make_so(5000)
        so.action_irio_request_approval()
        req = so.irio_approval_request_id
        # u_l2 approves level 2, but level 1 is current
        with self.assertRaises(UserError):
            req.with_user(self.u_l2).action_approve()

    def test_05_rejection_blocks_and_resubmit(self):
        so = self._make_so(5000)
        so.action_irio_request_approval()
        req = so.irio_approval_request_id
        req.with_user(self.u_l1).action_reject()
        self.assertEqual(req.state, "rejected")
        with self.assertRaises(UserError):
            so.action_confirm()
        # resubmission creates a fresh request
        so.action_irio_request_approval()
        req2 = so.irio_approval_request_id
        self.assertNotEqual(req2, req)
        self.assertEqual(req2.state, "pending")

    def test_06_purchase_order_flow(self):
        po = self.env["purchase.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "name": self.service.name,
                "product_id": self.service.id,
                "product_qty": 10,
                "price_unit": 100,
            })],
        })
        with self.assertRaises(UserError):
            po.button_confirm()
        po.action_irio_request_approval()
        po.irio_approval_request_id.with_user(self.u_l1).action_approve()
        po.button_confirm()
        self.assertEqual(po.state, "purchase")

    def test_07_invoice_flow(self):
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.service.id,
                "quantity": 1,
                "price_unit": 5000,
            })],
        })
        with self.assertRaises(UserError):
            inv.action_post()
        inv.action_irio_request_approval()
        inv.irio_approval_request_id.with_user(self.u_l1).action_approve()
        inv.action_post()
        self.assertEqual(inv.state, "posted")

    def test_08_picking_cost_basis(self):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1)
        Move = self.env["stock.move"]

        def mk_picking(qty):
            picking = self.env["stock.picking"].create({
                "picking_type_id": warehouse.int_type_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": warehouse.lot_stock_id.id,
            })
            move_vals = {
                "picking_id": picking.id,
                "product_id": self.widget.id,
                "product_uom_qty": qty,
                "product_uom": self.widget.uom_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": warehouse.lot_stock_id.id,
            }
            if "name" in Move._fields:
                move_vals["name"] = self.widget.name
            Move.create(move_vals)
            return picking

        expensive = mk_picking(2)     # 2 x 600 = 1200 >= 1000
        cheap = mk_picking(1)         # 600 < 1000
        self.assertEqual(expensive._irio_approval_amount(), 1200)
        with self.assertRaises(UserError):
            expensive._irio_check_approval()
        cheap._irio_check_approval()  # must not raise

    def test_09_delegation_vacation_mode(self):
        today = fields.Date.context_today(self.env.user)
        self.env["irio.approval.delegation"].create({
            "user_id": self.u_l1.id,
            "delegate_id": self.u_deleg.id,
            "date_from": today - timedelta(days=1),
            "date_to": today + timedelta(days=1),
        })
        so = self._make_so(5000)
        so.action_irio_request_approval()
        req = so.irio_approval_request_id
        req.with_user(self.u_deleg).action_approve()
        step1 = req.step_ids.sorted("sequence")[0]
        self.assertEqual(step1.status, "approved")
        # the DELEGATOR's slot was filled, actor recorded in chatter
        self.assertIn(self.u_l1, step1.approved_user_ids)

    def test_10_delegation_outside_window(self):
        today = fields.Date.context_today(self.env.user)
        self.env["irio.approval.delegation"].create({
            "user_id": self.u_l1.id,
            "delegate_id": self.u_deleg.id,
            "date_from": today - timedelta(days=10),
            "date_to": today - timedelta(days=5),
        })
        so = self._make_so(5000)
        so.action_irio_request_approval()
        req = so.irio_approval_request_id
        with self.assertRaises(UserError):
            req.with_user(self.u_deleg).action_approve()

    def test_11_escalation_cron(self):
        so = self._make_so(5000)
        so.action_irio_request_approval()
        req = so.irio_approval_request_id
        step = req.current_step_id
        today = fields.Date.context_today(self.env.user)
        step.sudo().write({"deadline": today - timedelta(days=1)})
        self.env["irio.approval.request"]._cron_escalate()
        self.assertTrue(step.escalated)
        acts = self.env["mail.activity"].search([
            ("res_model", "=", "irio.approval.request"),
            ("res_id", "=", req.id),
        ])
        self.assertTrue(any("OVERDUE" in (a.summary or "") for a in acts))
