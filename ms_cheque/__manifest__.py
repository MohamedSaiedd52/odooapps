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
    "author": "Mohamed Saied",
    "website": "https://apps.odoo.com/apps/modules/18.0/ms_cheque",
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'price': 30.00,
    'currency': 'USD',
    'images': ['static/description/banner.png', 'static/description/screenshot_incoming.png'],
       "summary": "Advanced Cheque Management for Odoo 18",
    "description": """
MS Cheque Management is a professional Odoo 18 module for managing incoming and outgoing cheques.

Key Features:
- Incoming & Outgoing Cheque Management
- Full Accounting Automation
- Multi-company Support
- Audit-safe Workflow
- Bilingual Interface (Arabic / English)
- Odoo 18 Compatible

Keywords:
Odoo Cheque Management
Odoo Cheques
Odoo Accounting Automation
Post Dated Cheques Odoo
Bank Cheques Odoo
    """,
}
