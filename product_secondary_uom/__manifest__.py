# -*- coding: utf-8 -*-
{
    'name': 'Product Secondary Unit of Measure',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Products',
    'summary': 'Add secondary unit of measure to products',
    'description': """
Product Secondary Unit of Measure
=================================
This module adds a secondary unit of measure capability to products.

Features:
* Define a secondary UoM for any product (independent from primary UoM)
* Manual quantity entry for both primary and secondary quantities
* Integration with Sales, Purchases, Inventory, and Invoicing

The secondary UoM is completely independent - no automatic conversion.
    """,
    'author': 'Custom Development',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'sale',
        'sale_management',
        'sale_stock',
        'purchase',
        'stock',
        'account',
        'uom',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/account_move_views.xml',
        'views/stock_move_views.xml',
        'views/stock_quant_views.xml', 
        'views/account_invoice_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'price': 35.0,
    'currency': 'USD',
}


