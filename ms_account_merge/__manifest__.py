# -*- coding: utf-8 -*-
{
    'name': 'MS Account Merge',
    'version': '1.1.0',
    'category': 'Accounting',
    'summary': 'Merge two or more GL accounts like the Contacts merge: '
               'all journal items and references move to one account. '
               'Compatible with Odoo 17, 18 and 19.',
    'description': """
MS Account Merge
=================
Adds a "Merge Accounts" action on the Chart of Accounts (list view,
Actions menu), similar to the native Contacts merge:

* Select 2+ accounts, pick the destination account.
* ALL journal items are repointed to the destination account, so the
  General Ledger / Partner Ledger show one combined account with the
  movements naturally ordered by date and a correct running balance.
* Every other reference in the database is repointed too (journal
  default accounts, taxes, products, partner receivable/payable
  properties, reconciliation models, fiscal positions, assets, ...),
  using a generic foreign-key scan plus company-dependent (jsonb)
  fields handling - the same technique as the native partner merge.
* Source accounts are archived afterwards (not deleted), keeping the
  chart clean while remaining reversible from the archived filter.

Safeguards
----------
* Accountant/Advisor (account manager) group only.
* Accounts must share the same company scope.
* Accounts must have the same Type, unless "Allow different types"
  is explicitly checked.
* Blocks the merge if any journal item on a source account belongs to
  a hashed (inalterable) entry.
* If any source account is reconcilable, the destination is made
  reconcilable automatically so existing reconciliations stay valid.

Compatibility
-------------
One codebase for Odoo 17, 18 and 19:

* Odoo 17: company-dependent values are repointed in ir.property,
  accounts are archived via the "deprecated" flag.
* Odoo 18/19: company-dependent jsonb columns are rewritten,
  accounts are archived via the "active" flag.
* The action's group restriction is applied in a post_init_hook
  (groups_id was renamed to group_ids in Odoo 19).
""",
    'author': 'MohamedSaied',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_merge_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'price': 35.0,
    'currency': 'USD',
}
