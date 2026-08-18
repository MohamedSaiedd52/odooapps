# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    hijri_date = fields.Char(
        string="Hijri Date", compute='_compute_hijri_date')

    @api.depends('date', 'company_id.hijri_adjustment',
                 'company_id.hijri_format')
    def _compute_hijri_date(self):
        converter = self.env['ms.hijri.converter']
        for payment in self:
            payment.hijri_date = converter.format_date(
                payment.date, company=payment.company_id)
