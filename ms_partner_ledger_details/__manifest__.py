# -*- coding: utf-8 -*-
{
    'name': 'Partner Ledger Invoice Details Drill-Down',
    'summary': 'Expand any invoice inside the Partner Ledger to see its lines, taxes & payments inline - ledger drill-down.',
    'description': """
MS Partner Ledger - Invoice Details Drill-down
===============================================
Extends the Enterprise Partner Ledger report (account_reports) so that every
invoice / journal-item line becomes unfoldable. When you click its arrow, the
report expands into the invoice's PRODUCT LINES, showing:

    Product name  -  Quantity (UoM)   |   Line Total

How it works (framework-safe):
------------------------------
* Inherits the report custom handler
  'account.partner.ledger.report.handler'.
* After the standard partner expansion runs, each move line that belongs to
  an invoice is tagged unfoldable with a custom expand function.
* Child (product) lines are built with the OFFICIAL
  account.report._get_generic_line_id() helper - no hand-crafted line IDs,
  so _parse_line_id never breaks.
* No change to the account.report data record and no new columns: the line
  total is rendered in the existing Balance column, and the quantity is shown
  in the line label (the Partner Ledger has fixed Debit/Credit/Balance
  columns).

Requires: Odoo Enterprise (account_reports).

Developed by MohamedSaied
WhatsApp: +20 101 390 7174
    """,
    'author': 'Mohamed Saied',
    'website': 'https://wa.me/201013907174',
    'category': 'Accounting',
    'version': '17.0.1.0.0',
    'license': 'OPL-1',
    'depends': ['account_reports'],
    'data': [],
    'installable': True,
    'application': False,
    'price': 30.0,
    'currency': 'USD',
    'images': ['static/description/banner.gif'],
}
