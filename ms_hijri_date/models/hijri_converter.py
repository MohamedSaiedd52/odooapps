# -*- coding: utf-8 -*-
"""Tabular (civil) Islamic calendar engine.

Pure-Python conversion between the proleptic Gregorian calendar and the
tabular Hijri calendar (epoch JDN 1948440, 11 leap years per 30-year cycle),
plus a per-company day adjustment so the result can be aligned with local
moon sighting or the Umm al-Qura calendar.
"""
from datetime import date, datetime, timedelta

from odoo import api, fields, models

HIJRI_EPOCH_JDN = 1948440  # JDN of 1 Muharram 1 AH (civil epoch)
CYCLE_DAYS = 10631         # days in a 30-year Hijri cycle (19*354 + 11*355)

MONTHS_LATIN = [
    "Muharram", "Safar", "Rabi' al-Awwal", "Rabi' al-Thani",
    "Jumada al-Awwal", "Jumada al-Thani", "Rajab", "Sha'ban",
    "Ramadan", "Shawwal", "Dhu al-Qi'dah", "Dhu al-Hijjah",
]
MONTHS_ARABIC = [
    "محرم", "صفر", "ربيع الأول", "ربيع الآخر",
    "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان",
    "رمضان", "شوال", "ذو القعدة", "ذو الحجة",
]
HIJRI_ERA_ARABIC = "هـ"


def greg_to_jdn(y, m, d):
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def jdn_to_greg(jdn):
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - 146097 * b // 4
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return year, month, day


def is_hijri_leap(hy):
    # leap iff the cumulative-leap count (11*y + 3) // 30 increases at y,
    # i.e. cycle positions {2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29}
    return (11 * hy + 3) % 30 >= 19


def hijri_month_days(hy, hm):
    if hm == 12:
        return 30 if is_hijri_leap(hy) else 29
    return 30 if hm % 2 == 1 else 29


def hijri_to_jdn(hy, hm, hd):
    days_before_year = 354 * (hy - 1) + (11 * hy + 3) // 30
    days_before_month = 29 * (hm - 1) + hm // 2
    return HIJRI_EPOCH_JDN + days_before_year + days_before_month + hd - 1


def jdn_to_hijri(jdn):
    days = jdn - HIJRI_EPOCH_JDN
    cycle = days // CYCLE_DAYS
    rem = days - cycle * CYCLE_DAYS
    hy = 30 * cycle + 1
    while True:
        year_len = 355 if is_hijri_leap(hy) else 354
        if rem < year_len:
            break
        rem -= year_len
        hy += 1
    hm = 1
    while True:
        month_len = hijri_month_days(hy, hm)
        if rem < month_len:
            break
        rem -= month_len
        hm += 1
    return hy, hm, rem + 1


class MsHijriConverter(models.AbstractModel):
    _name = 'ms.hijri.converter'
    _description = 'Hijri Date Converter'

    @api.model
    def _adjustment(self, company=None):
        company = company or self.env.company
        return company.hijri_adjustment or 0

    @api.model
    def to_hijri(self, greg_date, company=None):
        """date -> (hijri_year, hijri_month, hijri_day), with company adjustment."""
        jdn = greg_to_jdn(greg_date.year, greg_date.month, greg_date.day)
        return jdn_to_hijri(jdn + self._adjustment(company))

    @api.model
    def from_hijri(self, hy, hm, hd, company=None):
        """(hy, hm, hd) -> datetime.date, inverse of to_hijri (round-trip safe)."""
        y, m, d = jdn_to_greg(hijri_to_jdn(hy, hm, hd) - self._adjustment(company))
        return date(y, m, d)

    @api.model
    def format_hijri(self, hy, hm, hd, company=None):
        company = company or self.env.company
        fmt = company.hijri_format or 'latin'
        if fmt == 'arabic':
            return "%d %s %d %s" % (hd, MONTHS_ARABIC[hm - 1], hy, HIJRI_ERA_ARABIC)
        if fmt == 'numeric':
            return "%04d/%02d/%02d" % (hy, hm, hd)
        return "%d %s %d AH" % (hd, MONTHS_LATIN[hm - 1], hy)

    @api.model
    def format_date(self, value, company=None):
        """Format a date/datetime as a Hijri string ('' when empty).

        Datetimes are first moved to the user's timezone so the Hijri day
        matches what the user sees on the Gregorian side.
        """
        if not value:
            return ''
        if isinstance(value, datetime):
            value = fields.Datetime.context_timestamp(self, value).date()
        hy, hm, hd = self.to_hijri(value, company=company)
        return self.format_hijri(hy, hm, hd, company=company)


class MsHijriMixin(models.AbstractModel):
    """Inherit this mixin to expose Hijri displays on any model.

    class MyModel(models.Model):
        _inherit = ['my.model', 'ms.hijri.mixin']

        hijri_my_date = fields.Char(compute='_compute_hijri_my_date')

        @api.depends('my_date', 'company_id.hijri_adjustment',
                     'company_id.hijri_format')
        def _compute_hijri_my_date(self):
            for rec in self:
                rec.hijri_my_date = rec._ms_hijri_display(rec.my_date)
    """
    _name = 'ms.hijri.mixin'
    _description = 'Hijri Display Mixin'

    def _ms_hijri_display(self, value):
        company = self.company_id if 'company_id' in self._fields and self.company_id else None
        return self.env['ms.hijri.converter'].format_date(value, company=company)
