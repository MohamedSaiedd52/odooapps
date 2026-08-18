# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    hijri_invoice_date = fields.Char(
        string="Hijri Date", compute='_compute_hijri_dates')
    hijri_invoice_date_due = fields.Char(
        string="Hijri Due Date", compute='_compute_hijri_dates')

    @api.depends('invoice_date', 'invoice_date_due',
                 'company_id.hijri_adjustment', 'company_id.hijri_format')
    def _compute_hijri_dates(self):
        converter = self.env['ms.hijri.converter']
        for move in self:
            company = move.company_id
            move.hijri_invoice_date = converter.format_date(
                move.invoice_date, company=company)
            move.hijri_invoice_date_due = converter.format_date(
                move.invoice_date_due, company=company)
