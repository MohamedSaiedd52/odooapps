# -*- coding: utf-8 -*-
{
    'name': 'Letter of Credit Management (LC)',

    'summary': 'Manage documentary letters of credit (LC): bank, amount, currency, bank expenses & automatic journal entries.',

    'description': """
Long description of module's purpose
    """,

    'author': 'Mohamed Saied',

    'support': 'MohamedSaiedd53@gmail.com',
    

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account'],

    # always loaded
    'data': [
        'data/data.xml',
        'security/ir.model.access.csv',
        'security/groups.xml',
        'views/views.xml',
    ],
    'price': 25.0,
    'currency': 'USD',
    'images': ['static/description/banner.gif'],
}
