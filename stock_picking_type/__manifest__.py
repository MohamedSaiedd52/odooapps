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
    'price': 13.98,
    'currency': 'USD',
    'depends': ['stock'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/res_users.xml',
    ],
    'installable': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
