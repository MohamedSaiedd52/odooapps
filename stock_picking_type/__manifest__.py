{
    'name': 'Stock Location Restriction by User - Warehouse Security',
    'summary': 'Restrict stock locations visible to each user based on configuration',
   'description': """
Stock Location Restriction for Users
====================================

This Odoo module allows you to **restrict warehouse stock locations** visible to each user.

### Key Features:
- Assign allowed stock locations per user
- Automatically hide unauthorized warehouse locations
- Improve security and control in multi-warehouse environments
- Supports Inventory, Incoming/Outgoing transfers, and more

Ideal for businesses with **multiple warehouses** or branches, where each **storekeeper** should only access their assigned stock locations.

**Compatible with Odoo Enterprise & Community editions.**
""",

    'author': 'Mohamed Saied',
    'maintainer': 'Mohamed Saied <mohamedsaiedd53@gmail.com>',
    'license': 'LGPL-3',
    'version': '1.0',
    'price': 13.99,
    'keywords': ['stock', 'warehouse', 'location', 'restriction', 'user access', 'security', 'multi warehouse'],
    'currency': 'USD',
    'depends': ['stock','stock_sms'],
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'views/res_users.xml',
        'views/res_config_settings.xml',
        'views/stock_warehouse.xml',

    ],
    'installable': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
