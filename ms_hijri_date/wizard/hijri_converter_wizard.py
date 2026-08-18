# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from ..models import hijri_converter


class MsHijriConverterWizard(models.TransientModel):
    _name = 'ms.hijri.converter.wizard'
    _description = 'Gregorian / Hijri Date Converter'

    def _default_hijri_part(self, index):
        today = fields.Date.context_today(self)
        return self.env['ms.hijri.converter'].to_hijri(today)[index]

    gregorian_date = fields.Date(
        string="Gregorian Date",
        default=lambda self: fields.Date.context_today(self))
    hijri_result_latin = fields.Char(
        string="Hijri (Latin)", compute='_compute_hijri_result')
    hijri_result_arabic = fields.Char(
        string="Hijri (Arabic)", compute='_compute_hijri_result')
    hijri_result_numeric = fields.Char(
        string="Hijri (Numeric)", compute='_compute_hijri_result')

    hijri_year = fields.Integer(
        string="Hijri Year", default=lambda self: self._default_hijri_part(0))
    hijri_month = fields.Selection(
        [(str(i + 1), "%02d - %s (%s)" % (i + 1, latin, arabic))
         for i, (latin, arabic) in enumerate(
             zip(hijri_converter.MONTHS_LATIN, hijri_converter.MONTHS_ARABIC))],
        string="Hijri Month",
        default=lambda self: str(self._default_hijri_part(1)))
    hijri_day = fields.Integer(
        string="Hijri Day", default=lambda self: self._default_hijri_part(2))
    gregorian_result = fields.Date(
        string="Gregorian Result", compute='_compute_gregorian_result')
    gregorian_weekday = fields.Char(
        string="Weekday", compute='_compute_gregorian_result')
    hijri_error = fields.Char(compute='_compute_gregorian_result')

    @api.depends('gregorian_date')
    def _compute_hijri_result(self):
        converter = self.env['ms.hijri.converter']
        for wizard in self:
            if not wizard.gregorian_date:
                wizard.hijri_result_latin = ''
                wizard.hijri_result_arabic = ''
                wizard.hijri_result_numeric = ''
                continue
            hy, hm, hd = converter.to_hijri(wizard.gregorian_date)
            wizard.hijri_result_latin = "%d %s %d AH" % (
                hd, hijri_converter.MONTHS_LATIN[hm - 1], hy)
            wizard.hijri_result_arabic = "%d %s %d %s" % (
                hd, hijri_converter.MONTHS_ARABIC[hm - 1], hy,
                hijri_converter.HIJRI_ERA_ARABIC)
            wizard.hijri_result_numeric = "%04d/%02d/%02d" % (hy, hm, hd)

    @api.depends('hijri_year', 'hijri_month', 'hijri_day')
    def _compute_gregorian_result(self):
        converter = self.env['ms.hijri.converter']
        for wizard in self:
            wizard.gregorian_result = False
            wizard.gregorian_weekday = ''
            wizard.hijri_error = ''
            if not (wizard.hijri_year and wizard.hijri_month and wizard.hijri_day):
                continue
            hy = wizard.hijri_year
            hm = int(wizard.hijri_month)
            hd = wizard.hijri_day
            month_days = hijri_converter.hijri_month_days(hy, hm)
            if not 1 <= hd <= month_days:
                wizard.hijri_error = _(
                    "%(month)s %(year)s has only %(days)s days.",
                    month=hijri_converter.MONTHS_LATIN[hm - 1],
                    year=hy, days=month_days)
                continue
            greg = converter.from_hijri(hy, hm, hd)
            wizard.gregorian_result = greg
            wizard.gregorian_weekday = greg.strftime('%A')
