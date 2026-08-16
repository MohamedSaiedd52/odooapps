{
    'name': 'Quantity Decimal Precision',
    'version': '19.0.1.0.0',
    'category': 'Sales/Purchase',
    'summary': 'Limit quantity decimal places to 2 in Sales and Purchase Orders',
    'description': """
        This module limits the quantity field decimal precision to 2 decimal places
        in Sales Orders and Purchase Orders.
    """,
    'author': 'Punalu',
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
}
