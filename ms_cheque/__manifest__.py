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
        'views/reports.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'price': 30.00,
    'currency': 'USD',
    'images': ['static/description/banner.png', 'static/description/screenshot_incoming.png'],
}
