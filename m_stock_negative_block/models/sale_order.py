# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import models, _
from odoo.tools.float_utils import float_compare

from .compat import is_storable, line_uom


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Log a chatter warning when the order sells more than what is on hand.

        The confirmation is never blocked here: the order may legitimately be
        taken before the goods arrive. The hard stop happens later, when the
        delivery is validated.
        """
        for order in self:
            warnings = order._check_stock_availability_warnings()
            if warnings:
                order.message_post(
                    body=Markup("<strong>%s</strong><ul>%s</ul>") % (
                        _("Stock availability warning"),
                        Markup("").join(Markup("<li>%s</li>") % msg for msg in warnings),
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
        return super().action_confirm()

    def _check_stock_availability_warnings(self):
        """Return the list of order lines asking for more than the free stock."""
        self.ensure_one()
        warnings = []
        Quant = self.env['stock.quant'].sudo()

        warehouse = self.warehouse_id
        if not warehouse:
            return warnings
        stock_location = warehouse.lot_stock_id

        for line in self.order_line:
            product = line.product_id
            if not product or not is_storable(product):
                continue

            uom = line_uom(line)
            qty_ordered = uom._compute_quantity(line.product_uom_qty, product.uom_id)
            rounding = product.uom_id.rounding

            # Free stock of the whole warehouse (child locations included).
            available_qty = Quant._get_available_quantity(
                product, stock_location, strict=False, allow_negative=False,
            )

            if float_compare(qty_ordered, available_qty, precision_rounding=rounding) <= 0:
                continue

            warnings.append(_(
                "%(product)s: ordered %(ordered)s %(uom)s, only %(available)s "
                "%(uom)s available in %(warehouse)s.",
                product=product.display_name,
                ordered=('%.4f' % line.product_uom_qty).rstrip('0').rstrip('.') or '0',
                available=('%.4f' % product.uom_id._compute_quantity(
                    available_qty, uom)).rstrip('0').rstrip('.') or '0',
                uom=uom.name,
                warehouse=warehouse.name,
            ))

        return warnings
