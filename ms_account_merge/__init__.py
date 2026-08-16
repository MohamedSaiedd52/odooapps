# -*- coding: utf-8 -*-
from . import wizard


def post_init_hook(env):
    """Restrict the contextual 'Merge Accounts' action to the Accounting
    Administrator group. Done in Python instead of XML because the m2m
    field on ir.actions.act_window is named 'groups_id' up to Odoo 18
    and 'group_ids' since Odoo 19."""
    action = env.ref('ms_account_merge.action_ms_account_merge_wizard',
                     raise_if_not_found=False)
    group = env.ref('account.group_account_manager',
                    raise_if_not_found=False)
    if action and group:
        field = 'group_ids' if 'group_ids' in action._fields else 'groups_id'
        action.write({field: [(4, group.id)]})
