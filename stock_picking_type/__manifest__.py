{
    'name': 'User Location Permission',
    'summary': 'Restrict stock locations visible to each user based on configuration',
    'description': """
        User Location Permission
        ========================
        This module allows restricting the stock locations that each user can access or view in warehouse operations.
        It helps in organizing warehouse security by allowing each storekeeper to interact only with their assigned locations.
            """,
    'author': 'Mohamed Saied',
    'maintainer': 'Mohamed Saied <mohamedsaiedd53@gmail.com>',
    'license': 'LGPL-3',
    'version': '1.0',
    'price': 13.99,
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
