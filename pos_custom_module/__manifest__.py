{
    'name': 'POS Custom Module',
    'version': '1.0',
    'summary': 'Adds a button to convert paid POS orders to invoices.',
    'description': 'This module adds a custom button to convert paid POS orders to invoices and post them.',
    'version': '17.0.0.1.0',
    'author': 'Mohamed Saied',
    'category': 'Point of Sale',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_order_views.xml',
    ],
    'price': 20.00,
    'currency': 'USD',
    'installable': True,
    'application': False,
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
}