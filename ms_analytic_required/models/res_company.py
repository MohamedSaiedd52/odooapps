# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    ms_analytic_policy_default = fields.Selection(
        selection=[
            ('optional', 'Optional'),
            ('always', 'Always Required'),
            ('posted', 'Required on Posting'),
            ('forbidden', 'Forbidden'),
        ],
        string='Default Analytic Requirement',
        default='optional',
        help="Applied to every account that has no specific policy of its own.",
    )
    ms_analytic_full_coverage = fields.Boolean(
        string='Require 100% Analytic Coverage',
        help=(
            "When a line is required to carry analytics, also require the "
            "analytic distribution to cover at least 100% of the amount."
        ),
    )
