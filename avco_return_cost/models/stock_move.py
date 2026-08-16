# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models
from odoo.tools import float_is_zero


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _avco_return_origin_cost_applicable(self):
        """Return True when this outgoing move is a return of a valued move
        of an AVCO product, i.e. when the layer it creates should be valued
        at the original layer cost instead of the current average cost."""
        self.ensure_one()
        return bool(
            self.origin_returned_move_id
            and self.origin_returned_move_id.sudo().stock_valuation_layer_ids
            and self.with_company(self.company_id).product_id.cost_method == 'average'
        )

    def _get_out_svl_vals(self, forced_quantity):
        svl_vals_list = super()._get_out_svl_vals(forced_quantity)
        # Track per-product totals already taken by this batch so the guards
        # stay correct when several returns of the same product are validated
        # together (the layers are only created after this method returns).
        taken_qty = defaultdict(float)
        taken_value = defaultdict(float)
        for vals in svl_vals_list:
            move = self.browse(vals.get('stock_move_id'))
            if not move or not move._avco_return_origin_cost_applicable():
                continue
            move = move.with_company(move.company_id)
            product = move.product_id.sudo().with_company(move.company_id)
            currency = move.company_id.currency_id
            rounding = product.uom_id.rounding
            qty = abs(vals.get('quantity', 0.0))
            if float_is_zero(qty, precision_rounding=rounding):
                continue
            key = (product.id, move.company_id.id)
            unit_cost = move._get_price_unit()  # returns the origin layers' unit cost
            value = currency.round(unit_cost * qty)
            available_qty = product.quantity_svl - taken_qty[key]
            available_value = product.value_svl - taken_value[key]
            if float_is_zero(available_qty - qty, precision_rounding=rounding):
                # Returning the last units on hand: empty the valuation
                # completely so no residual value stays at zero quantity.
                value = currency.round(available_value)
            elif currency.compare_amounts(value, available_value) > 0 and \
                    currency.compare_amounts(available_value, 0.0) > 0:
                # Never drive the remaining valuation negative.
                value = currency.round(available_value)
            vals['unit_cost'] = value / qty
            vals['value'] = -value
            taken_qty[key] += qty
            taken_value[key] += value
        return svl_vals_list

    def _create_out_svl(self, forced_quantity=None):
        layers = super()._create_out_svl(forced_quantity)
        # Taking a return out at its origin cost (instead of the average)
        # changes the value of the remaining stock: realign the standard
        # price with value_svl / quantity_svl, as the core does after price
        # difference layers (see purchase_stock/models/account_invoice.py).
        products_per_company = defaultdict(set)
        for layer in layers:
            move = layer.stock_move_id
            if move and move._avco_return_origin_cost_applicable():
                products_per_company[move.company_id.id].add(move.product_id.id)
        for company_id, product_ids in products_per_company.items():
            products = self.env['product.product'].sudo().browse(product_ids).with_company(company_id)
            for product in products:
                if float_is_zero(product.quantity_svl, precision_rounding=product.uom_id.rounding):
                    continue
                if product.quantity_svl < 0:
                    continue
                product.with_context(disable_auto_svl=True).write({
                    'standard_price': product.value_svl / product.quantity_svl,
                })
        return layers
