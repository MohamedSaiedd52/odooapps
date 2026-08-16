# -*- coding: utf-8 -*-
{
    'name': 'Salesperson Sales & Invoice Report',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': (
        'Adds Invoice-based Salesperson to Sale Report, '
        'and adds Salesperson filter to Journal Items (Accounting).'
    ),
    'description': """
MS Salesperson Report & Filter
================================
Features:
1. تقرير المبيعات (Sales Analysis):
   - إضافة حقل "مندوب المبيعات (الفاتورة)" بناءً على الفاتورة المرتبطة
     بأمر البيع (invoice_user_id من account.move).

2. قيود الحسابات (Journal Items):
   - إضافة فلتر "مندوب المبيعات" في قائمة الفلاتر/التجميع
     حتى يمكن الفلترة بسهولة على مستوى المندوب.
    """,
    'author': 'Mohamed Saied',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'account',
    ],
    'data': [
        'views/sale_report_views.xml',
        'views/account_move_line_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'price': 25.0,
    'currency': 'USD',
    'images': ['static/description/banner.gif'],
    'summary': 'Invoice-based salesperson in Sales Analysis plus salesperson filters on journal items & invoices.',
}
