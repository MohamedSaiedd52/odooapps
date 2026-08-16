# -*- coding: utf-8 -*-
"""Cross-version helpers so the same Python runs on Odoo 17, 18 and 19."""
from odoo import release

VERSION = release.version_info[0]

# storable goods: 17 uses type='product'; 18/19 use type='consu' (+ is_storable)
STORABLE_TYPE = 'product' if VERSION < 18 else 'consu'

# HTTP route type for JSON-RPC endpoints: 'json' is a deprecated alias in 19
JSON_ROUTE_TYPE = 'jsonrpc' if VERSION >= 19 else 'json'

# sale.order.line taxes m2m: renamed tax_id -> tax_ids in Odoo 19
SO_LINE_TAX_FIELD = 'tax_ids' if VERSION >= 19 else 'tax_id'


def default_product_category(env):
    """Default product.category id across versions.

    'product.product_category_all' was removed in Odoo 19 (replaced by
    'product.product_category_goods'); fall back to any existing category.
    """
    for xmlid in ('product.product_category_all', 'product.product_category_goods'):
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            return rec.id
    return env['product.category'].search([], limit=1).id


def default_tax_group(env, company):
    """A tax group id for manual account.tax creation (NOT NULL in Odoo 19).

    Databases without a localization chart have no tax group at all —
    create a bare one in that case (name + company are the only
    required fields on account.tax.group in 17/18/19).
    """
    Group = env['account.tax.group'].sudo()
    group = Group.search([('company_id', '=', company.id)], limit=1) or Group.search([], limit=1)
    if not group:
        group = Group.create({'name': 'Taxes', 'company_id': company.id})
    return group.id
