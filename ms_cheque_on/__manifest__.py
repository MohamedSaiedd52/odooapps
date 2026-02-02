{
    'name': 'MS Management Cheque',
    'author': 'Mohamed Saied',
    'category': 'Accounting',
    'depends': ['base', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/seq_data.xml',
        'views/ms_manage.xml',
        'views/reports.xml',
    ],
    'website': 'https://apps.odoo.com/apps/modules/18.0/ms_cheque_on',
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'price': 30.00,
    'currency': 'USD',
    'images': [
        'static/description/banner.gif',
        'static/description/screenshot_incoming.png'
    ],
    'summary': 'Advanced Cheque Management for Odoo 18',
    'description': """
MS Cheque Management is a professional Odoo 18 module for managing incoming and outgoing cheques.

This module is fully compatible with Odoo Community and Enterprise editions.

Key Features:
- Incoming & Outgoing Cheque Management
- Full Accounting Automation
- Multi-company Support
- Audit-safe Workflow
- Bilingual Interface (Arabic / English)
- Odoo 18 Compatible
    """,
}
