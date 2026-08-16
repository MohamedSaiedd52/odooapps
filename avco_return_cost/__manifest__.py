# -*- coding: utf-8 -*-
{
    'name': 'AVCO Vendor Return at Original Cost',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Value vendor returns at the original receipt cost instead of the current average cost',
    'description': """
Values outgoing return moves (returns to vendor) of Average Cost (AVCO)
products at the unit cost of the original receipt layer instead of the
current average cost, then realigns the product average cost with the
remaining stock value. This removes the valuation gap and the residue
left in the Stock Interim (Received) account when goods bought at
different prices are returned without lot tracking.
""",
    'author': 'Mohamed Saied',
    'license': 'LGPL-3',
    'depends': ['purchase_stock'],
    'data': [],
    'installable': True,
    'application': False,
    'price': 45.0,
    'currency': 'USD',
}
