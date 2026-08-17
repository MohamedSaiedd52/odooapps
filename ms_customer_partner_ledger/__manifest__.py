# -*- coding: utf-8 -*-
{
    'name': 'Customer Account Statement - Arabic Partner Ledger',
    'version': '18.0.1.1.0',
    'category': 'Accounting',
    'summary': 'Print an Arabic customer statement of account from the Partner Ledger with running balance & totals. كشف حساب عميل',
    'description': """
Customer Partner Ledger With New Layout
=======================================

Adds a **PL** button to the Partner Ledger toolbar that prints a simplified,
right-to-left Arabic customer account statement (ÙƒØ´Ù Ø­Ø³Ø§Ø¨ Ø§Ù„Ø²Ø¨Ø§Ø¦Ù†) for the
partners selected in the report:

* five columns only - Date, Type, Reference, Amount, Running Balance;
* the opening balance of each partner is carried in from before the period;
* invoice lines are dated by ``invoice_date`` instead of the accounting date;
* a summary box under each statement with the opening balance, the period
  debit/credit totals, the closing balance and the **Total Due** - the amount
  still unpaid by the partner whatever the printed period is;
* one A4-landscape page per selected partner.
""",
    'author': 'Mohamed Saied',
    'support': 'MohamedSaiedd53@gmail.com',
    'website': '',
    'license': 'LGPL-3',


    'depends': ['account_reports'],
    'data': [
        'views/cus_acc_report.xml',
        'views/report_template.xml'

    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'price': 45.0,
    'currency': 'USD',
}
