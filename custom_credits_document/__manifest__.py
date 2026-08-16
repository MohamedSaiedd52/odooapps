# -*- coding: utf-8 -*-
{
    'name': "custom_credits_document",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "Ebrahiem Abdellatef",
    'website': "https://www.linkedin.com/in/ebrahiem-abdellatef-105547102/",

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
}
