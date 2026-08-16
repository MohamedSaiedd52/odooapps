{
    'name': 'Stock Location Restrictions - User Access',
    'summary': 'Restrict stock locations & operation types per user - location-based warehouse access control.',
    'description': """
Stock Location Restriction for Users
====================================

This Odoo module allows you to restrict warehouse stock locations visible to each user.

Features:

- Assign allowed stock locations per user
- Hide unauthorized warehouse locations
- Improve security in multi-warehouse environments
- Supports incoming/outgoing transfers

Ideal for companies with multiple warehouses.
""",
    'author': 'Mohamed Saied',
    'maintainer': 'Mohamed Saied <mohamedsaiedd53@gmail.com>',
    'license': 'LGPL-3',
    'version': '19.0.1.0.0',
    'price': 13.99,
    'currency': 'USD',
    'category': 'Inventory',
    'depends': ['stock', 'stock_sms'],
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'views/res_users.xml',
        'views/res_config_settings.xml',
        'views/stock_warehouse.xml',
    ],
    'installable': True,
    'auto_install': False,
    'images': ['static/description/banner.gif'],
}
