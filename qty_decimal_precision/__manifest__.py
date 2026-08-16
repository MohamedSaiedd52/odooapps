{
    'name': 'Quantity Decimal Precision Control',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Limit quantity decimal places on Sale & Purchase order lines - clean, configurable rounding precision.',
    'description': """
        This module limits the quantity field decimal precision to 2 decimal places
        in Sales Orders and Purchase Orders.
    """,
    'author': 'Mohamed Saied',
    'depends': ['sale', 'purchase'],
    'data': [
        'report/sale_report_templates.xml',
        'report/purchase_report_templates.xml',
        'report/account_report_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'price': 15.0,
    'currency': 'USD',
    'images': ['static/description/banner.gif'],
}
