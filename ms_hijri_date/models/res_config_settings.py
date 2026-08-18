# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hijri_format = fields.Selection(
        related='company_id.hijri_format', readonly=False)
    hijri_adjustment = fields.Integer(
        related='company_id.hijri_adjustment', readonly=False)
    hijri_today = fields.Char(
        string="Today (Hijri)", compute='_compute_hijri_today')

    @api.depends('hijri_format', 'hijri_adjustment')
    def _compute_hijri_today(self):
        converter = self.env['ms.hijri.converter']
        for settings in self:
            settings.hijri_today = converter.format_date(
                fields.Date.context_today(settings),
                company=settings.company_id)
