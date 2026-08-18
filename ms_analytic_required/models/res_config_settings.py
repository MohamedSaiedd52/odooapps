# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ms_analytic_policy_default = fields.Selection(
        related='company_id.ms_analytic_policy_default',
        readonly=False,
    )
    ms_analytic_full_coverage = fields.Boolean(
        related='company_id.ms_analytic_full_coverage',
        readonly=False,
    )
