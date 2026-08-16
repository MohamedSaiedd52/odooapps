# -*- coding: utf-8 -*-
"""Small helpers that keep a single code base working on Odoo 17, 18 and 19.

Only the differences this module actually relies on are abstracted here, and
they are resolved from the live field definitions rather than from
``odoo.release`` so that the code also survives back-ports.
"""


def is_storable(product):
    """Return True when stock is actually tracked for ``product``.

    Odoo 17 models this with ``type == 'product'``; Odoo 18/19 dropped that
    selection value and introduced the ``is_storable`` boolean instead.
    """
    if 'is_storable' in product._fields:
        return product.is_storable
    return product.type == 'product'


def line_uom(order_line):
    """Return the UoM of a ``sale.order.line``.

    Renamed ``product_uom`` -> ``product_uom_id`` in Odoo 19.
    """
    if 'product_uom_id' in order_line._fields:
        return order_line.product_uom_id
    return order_line.product_uom
