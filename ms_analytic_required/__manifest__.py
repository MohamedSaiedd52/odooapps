# -*- coding: utf-8 -*-
{
    'name': 'Mandatory Analytic Account | Analytic Distribution Required per Account',
    'summary': 'Force or forbid analytic distribution per GL account: always required, required on posting, or forbidden. Company-wide default policy and optional 100% full-coverage validation.',
    'description': """
Mandatory Analytic Account
==========================

- Per-account analytic policy: Always Required, Required on Posting, or Forbidden.
- Company-wide default policy from Accounting Settings, overridable per account.
- Optional rule: the analytic distribution must cover the full 100% of the line.
- Clear blocking messages listing every journal item that violates the policy.
""",
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.0',
    'author': 'Mohamed Saied',
    'support': 'MohamedSaiedd53@gmail.com',
    'license': 'OPL-1',
    'price': 15.0,
    'currency': 'USD',
    'depends': ['account'],
    'data': [
        'views/account_account_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
