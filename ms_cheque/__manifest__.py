{
    'name': 'MS Management Cheque',
    'version': '1.0',
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
}
