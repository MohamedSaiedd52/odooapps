# -*- coding: utf-8 -*-
{
    'name': 'Salla Connector | Salla Odoo Integration - Products & Orders Sync',
    'version': '18.0.1.0.0',
    'summary': 'Salla eCommerce integration: OAuth2 connect, sync products & orders from your Salla store to Odoo, live webhooks with signature verification. تكامل أودو مع منصة سلة',
    'description': """
Salla Connector
===============
- Connect Odoo to your Salla store with OAuth2 (one click, automatic token refresh).
- Import products from Salla: name, price, SKU, description and store URL.
- Import orders with their customers and lines; missing products are created automatically.
- Live webhooks keep products and orders in sync (HMAC signature verification).
- Salla data is visible on each product and order in a dedicated tab.
""",
    'category': 'eCommerce',
    'author': 'Mohamed Saied',
    'license': 'OPL-1',
    'price': 79.0,
    'currency': 'USD',
    'depends': ['sale_management', 'stock', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
