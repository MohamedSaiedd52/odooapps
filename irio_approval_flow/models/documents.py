# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "irio.approval.mixin"]

    def action_confirm(self):
        self._irio_check_approval()
        return super().action_confirm()


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "irio.approval.mixin"]

    def button_confirm(self):
        self._irio_check_approval()
        return super().button_confirm()


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "irio.approval.mixin"]

    def _irio_applicable(self):
        self.ensure_one()
        return self.move_type in (
            "out_invoice", "in_invoice", "out_refund", "in_refund")

    def _irio_find_rule(self):
        if not self._irio_applicable():
            return self.env["irio.approval.rule"]
        return super()._irio_find_rule()

    def action_post(self):
        self.filtered(lambda m: m._irio_applicable())._irio_check_approval()
        return super().action_post()


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "irio.approval.mixin"]

    def _irio_approval_amount(self):
        # pickings have no monetary total: use inventory cost value of the
        # demand (standard_price is already in company currency)
        self.ensure_one()
        return sum(move.product_id.standard_price * move.product_uom_qty
                   for move in self.move_ids)

    def button_validate(self):
        self._irio_check_approval()
        return super().button_validate()
