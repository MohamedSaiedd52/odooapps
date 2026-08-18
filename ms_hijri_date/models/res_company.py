# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    hijri_format = fields.Selection(
        [
            ('latin', "Latin (14 Muharram 1447 AH)"),
            ('arabic', "Arabic (14 محرم 1447 هـ)"),
            ('numeric', "Numeric (1447/01/14)"),
        ],
        string="Hijri Display Format", default='latin', required=True)
    hijri_adjustment = fields.Integer(
        string="Hijri Adjustment (days)", default=0,
        help="Shift the computed Hijri date by up to 3 days to match "
             "local moon sighting or the Umm al-Qura calendar.")

    @api.constrains('hijri_adjustment')
    def _check_hijri_adjustment(self):
        for company in self:
            if not -3 <= company.hijri_adjustment <= 3:
                raise ValidationError(
                    _("The Hijri adjustment must be between -3 and +3 days."))
