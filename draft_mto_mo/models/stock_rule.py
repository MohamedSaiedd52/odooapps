# -*- coding: utf-8 -*-
# Copyright (C) Mohamed Saied
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.txt).

from odoo import models

class StockRule(models.Model):
    _inherit = "stock.rule"

    def _run_manufacture(self, procurements):
        """Override to create MOs but KEEP them in draft.

        Default Odoo behavior confirms the MO right after creation.
        Here we replicate the upstream logic without calling action_confirm().
        This is intended for MTO flows where the MO should be reviewed first.
        """
        new_productions_values_by_company = {}
        for procurement, rule in procurements:
            bom = rule._get_matching_bom(procurement.product_id, procurement.company_id, procurement.values)
            # prepare MO values the standard way
            new_productions_values_by_company.setdefault(procurement.company_id.id, []).append(
                rule._prepare_mo_vals(*procurement, bom)
            )

        # Create productions PER company, but intentionally DO NOT confirm them.
        for company_id, productions_values in new_productions_values_by_company.items():
            self.env['mrp.production'].with_user(self.env.uid).with_company(company_id).create(productions_values)
            # Intentionally skip: productions.action_confirm()
            # Result: MO remains in 'draft' state.

        return True
