{
    'name': 'MS Management Cheque',
    'version': '2.0',
    'author': 'Mohamed Saied',
    'category': 'Accounting',
    'depends': ['base', 'account','mail','account_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'data/seq_data.xml',
        'views/ms_manage.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'maintainer': 'Mohamed Saied',
    'price': 30,
    'currency': 'USD',
    'summary': 'Manage Customer and Supplier Cheques',
    'description': """
        This module allows you to manage customer and supplier cheques efficiently.
    """,    
    'images': ['static/description/banner.png'],
}
