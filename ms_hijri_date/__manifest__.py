# -*- coding: utf-8 -*-
{
    'name': 'Hijri Date Everywhere',
    'summary': 'Hijri dates beside every Gregorian date - invoice, payment and '
               'quotation forms and PDF reports, live two-way converter, '
               'Arabic / Latin / numeric formats, moon-sighting adjustment.',
    'description': 'Show Hijri (Islamic) dates everywhere in Odoo.',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'author': 'Mohamed Saied',
    'support': 'MohamedSaiedd53@gmail.com',
    'website': '',
    'license': 'OPL-1',
    'price': 47.0,
    'currency': 'USD',
    'depends': ['sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/sale_order_views.xml',
        'views/hijri_wizard_views.xml',
        'report/report_templates.xml',
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': True,
}
