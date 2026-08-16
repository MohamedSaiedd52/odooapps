# -*- coding: utf-8 -*-
{
    'name': 'Stock Negative Quantity Block',
    'version': '18.0.1.0.0',
    'summary': 'Refuse to validate a transfer that would create negative stock',
    'description': """
Stock Negative Quantity Block
=============================

Standard Odoo lets you validate a delivery or an internal transfer even when
the source location does not hold enough goods, silently creating a negative
on-hand quantity.

This module blocks that validation: before a transfer is done, the quantity
about to leave each source location is compared with what is really on hand,
and a clear error lists every product that would end up negative.

* Applies to every transfer taking goods out of an internal or transit
  location (deliveries, internal transfers, multi-step receipts, returns to
  vendor, ...). Receipts from a vendor and moves coming from production or
  inventory locations are untouched.
* Lot / serial numbers, packages and owners are checked separately, exactly
  like Odoo decrements them.
* A location (and everything below it) can be excluded with the new
  "Allow Negative Stock" checkbox.
* Confirming a sales order for more than the free stock is still allowed, but
  the shortage is logged in the order chatter.
""",
    'author': 'Mohamed Saied',
    'category': 'Inventory/Inventory',
    'depends': ['stock', 'sale_stock'],
    'data': [
        'views/stock_location_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'price': 25.0,
    'currency': 'USD',
    'images': ['static/description/banner.gif'],
}
