# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

from .compat import is_storable


def _fmt(qty):
    """Format a quantity without trailing zeros, for error messages."""
    return ('%.4f' % qty).rstrip('0').rstrip('.') or '0'


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _pre_action_done_hook(self):
        """Block the validation when it would drive a source location negative."""
        res = super()._pre_action_done_hook()
        if res is not True:
            # Standard Odoo still has a wizard to show (backorder, SMS, ...).
            # That wizard calls back into ``button_validate``, so the check
            # below runs again once the user has answered it.
            return res

        error = self._check_negative_stock()
        if error:
            raise UserError(error)
        return True

    def _get_negative_stock_candidates(self):
        """Aggregate what this picking is about to take out of stock.

        Only the move lines that ``_action_done`` will really process are
        counted (unpicked moves and unpicked lines are dropped by standard
        Odoo), and only when the source is a real stock location that is not
        excluded through ``allow_negative_stock``.

        :return: dict keyed by (product, location, lot, package, owner) ids,
                 each value holding the records plus the total quantity leaving
                 that exact quant, expressed in the product UoM.
        """
        self.ensure_one()
        candidates = {}

        for move in self.move_ids:
            if move.state in ('done', 'cancel'):
                continue
            if not move.picked:
                # ``_action_done`` cancels / backorders those moves.
                continue
            if not is_storable(move.product_id):
                continue

            rounding = move.product_id.uom_id.rounding
            for line in move.move_line_ids:
                if not line.picked:
                    # ``_action_done`` unlinks those lines.
                    continue
                source = line.location_id
                if source.usage not in ('internal', 'transit'):
                    # Supplier, customer, production, inventory ... those
                    # virtual locations are meant to go negative.
                    continue
                if source._is_negative_stock_allowed():
                    continue

                # ``quantity_product_uom`` is what standard Odoo removes from
                # the quant - ``quantity`` alone is expressed in the line UoM.
                qty = line.quantity_product_uom
                if float_compare(qty, 0.0, precision_rounding=rounding) <= 0:
                    continue

                key = (
                    move.product_id.id,
                    source.id,
                    line.lot_id.id,
                    line.package_id.id,
                    line.owner_id.id,
                )
                entry = candidates.get(key)
                if entry is None:
                    entry = candidates[key] = {
                        'product': move.product_id,
                        'location': source,
                        'lot': line.lot_id,
                        'package': line.package_id,
                        'owner': line.owner_id,
                        'qty': 0.0,
                    }
                entry['qty'] += qty

        return candidates

    def _check_negative_stock(self):
        """Return an error message when validating ``self`` would push the
        on-hand quantity of a source location below zero, else ``False``.
        """
        Quant = self.env['stock.quant'].sudo()
        blocks = []

        for picking in self:
            lines = []
            for entry in picking._get_negative_stock_candidates().values():
                product = entry['product']
                location = entry['location']

                # Same set of quants ``_action_done`` will decrement.
                quants = Quant._gather(
                    product, location,
                    lot_id=entry['lot'],
                    package_id=entry['package'],
                    owner_id=entry['owner'],
                    strict=True,
                )
                on_hand = sum(quants.mapped('quantity'))
                resulting = on_hand - entry['qty']

                rounding = product.uom_id.rounding
                if float_compare(resulting, 0.0, precision_rounding=rounding) >= 0:
                    continue

                lines.append(_(
                    "- %(product)s%(lot)s%(package)s at %(location)s: "
                    "on hand %(on_hand)s %(uom)s, this transfer takes out "
                    "%(taken)s %(uom)s, resulting quantity %(result)s %(uom)s.",
                    product=product.display_name,
                    lot=_(" (lot/serial %s)", entry['lot'].name) if entry['lot'] else "",
                    package=_(" (package %s)", entry['package'].name) if entry['package'] else "",
                    location=location.display_name,
                    on_hand=_fmt(on_hand),
                    taken=_fmt(entry['qty']),
                    result=_fmt(resulting),
                    uom=product.uom_id.name,
                ))

            if lines:
                blocks.append(_(
                    "%(picking)s cannot be validated: it would make the stock "
                    "of the following products negative.\n\n%(lines)s",
                    picking=picking.display_name,
                    lines="\n".join(lines),
                ))

        if not blocks:
            return False
        return "%s\n\n%s" % (
            "\n\n".join(blocks),
            _("Receive or adjust the missing quantity first, or tick "
              "\"Allow Negative Stock\" on the source location."),
        )
