# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from ..models.hijri_converter import hijri_month_days, is_hijri_leap


class TestHijri(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.converter = cls.env['ms.hijri.converter']
        cls.company = cls.env.company
        cls.company.hijri_adjustment = 0
        cls.company.hijri_format = 'latin'
        cls.partner = cls.env['res.partner'].create({'name': 'Hijri Partner'})
        # a demo-less database (e.g. Odoo 19 without --with-demo) has no
        # journals at all - bootstrap the ones the document tests need
        Journal = cls.env['account.journal']
        for jtype, code in (('sale', 'HSAJ'), ('bank', 'HBNK')):
            if not Journal.search(
                [('type', '=', jtype), ('company_id', '=', cls.company.id)],
                limit=1,
            ):
                Journal.create({
                    'name': 'Hijri Test %s' % jtype.capitalize(),
                    'code': code,
                    'type': jtype,
                })

    # ------------------------------------------------------------------
    # engine
    # ------------------------------------------------------------------
    def test_01_anchor_pairs(self):
        self.assertEqual(self.converter.to_hijri(date(2000, 1, 1)), (1420, 9, 24))
        self.assertEqual(self.converter.from_hijri(1420, 9, 24), date(2000, 1, 1))
        self.assertEqual(self.converter.to_hijri(date(2021, 8, 10)), (1443, 1, 1))
        self.assertEqual(self.converter.from_hijri(1443, 1, 1), date(2021, 8, 10))
        self.assertEqual(self.converter.to_hijri(date(2024, 3, 11)), (1445, 9, 1))

    def test_02_round_trip(self):
        day = date(1990, 1, 1)
        end = date(2077, 1, 1)
        while day < end:
            hy, hm, hd = self.converter.to_hijri(day)
            self.assertTrue(1 <= hd <= hijri_month_days(hy, hm))
            self.assertEqual(self.converter.from_hijri(hy, hm, hd), day,
                             "round trip failed for %s" % day)
            day += timedelta(days=17)

    def test_03_leap_pattern(self):
        leaps = {y for y in range(1, 31) if is_hijri_leap(y)}
        self.assertEqual(leaps, {2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29})
        self.assertEqual(len(leaps), 11)

    def test_04_year_and_month_lengths(self):
        # 1444 % 30 = 4 -> common year; 1445 % 30 = 5 -> leap year
        self.assertFalse(is_hijri_leap(1444))
        self.assertTrue(is_hijri_leap(1445))
        length_1444 = (self.converter.from_hijri(1445, 1, 1)
                       - self.converter.from_hijri(1444, 1, 1)).days
        length_1445 = (self.converter.from_hijri(1446, 1, 1)
                       - self.converter.from_hijri(1445, 1, 1)).days
        self.assertEqual(length_1444, 354)
        self.assertEqual(length_1445, 355)
        self.assertEqual(hijri_month_days(1445, 1), 30)
        self.assertEqual(hijri_month_days(1445, 2), 29)
        self.assertEqual(hijri_month_days(1444, 12), 29)
        self.assertEqual(hijri_month_days(1445, 12), 30)

    def test_05_adjustment(self):
        # If the local sighting declared Muharram one day after the tabular
        # calendar, adjustment -1 shifts both directions consistently.
        self.company.hijri_adjustment = -1
        self.assertEqual(self.converter.to_hijri(date(2021, 8, 11)), (1443, 1, 1))
        self.assertEqual(self.converter.from_hijri(1443, 1, 1), date(2021, 8, 11))
        # round trip stays consistent under adjustment
        for offset in range(0, 40):
            day = date(2024, 2, 1) + timedelta(days=offset)
            hy, hm, hd = self.converter.to_hijri(day)
            self.assertEqual(self.converter.from_hijri(hy, hm, hd), day)

    def test_06_formats(self):
        sample = date(2000, 1, 1)  # 24 Ramadan 1420
        self.company.hijri_format = 'latin'
        self.assertEqual(self.converter.format_date(sample), "24 Ramadan 1420 AH")
        self.company.hijri_format = 'arabic'
        self.assertEqual(self.converter.format_date(sample), "24 رمضان 1420 هـ")
        self.company.hijri_format = 'numeric'
        self.assertEqual(self.converter.format_date(sample), "1420/09/24")
        self.assertEqual(self.converter.format_date(False), '')

    def test_07_adjustment_bounds(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.company.hijri_adjustment = 5
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.company.hijri_adjustment = -4

    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    def test_08_invoice_hijri_dates(self):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date(2000, 1, 1),
        })
        self.assertEqual(move.hijri_invoice_date, "24 Ramadan 1420 AH")
        move.invoice_date_due = date(2024, 3, 11)  # 1 Ramadan 1445
        self.assertEqual(move.hijri_invoice_date_due, "1 Ramadan 1445 AH")

    def test_09_payment_hijri_date(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'date': date(2000, 1, 1),
        })
        self.assertEqual(payment.hijri_date, "24 Ramadan 1420 AH")

    def test_10_sale_order_hijri_date_tz(self):
        # 2024-03-11 22:00 UTC is already 2024-03-12 in Riyadh (UTC+3),
        # i.e. 2 Ramadan 1445 - the compute must honour the user timezone.
        self.env.user.tz = 'Asia/Riyadh'
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'date_order': '2024-03-11 22:00:00',
        })
        self.assertEqual(order.hijri_date_order, "2 Ramadan 1445 AH")

    # ------------------------------------------------------------------
    # wizard + mixin
    # ------------------------------------------------------------------
    def test_11_wizard_gregorian_to_hijri(self):
        wizard = self.env['ms.hijri.converter.wizard'].create({
            'gregorian_date': date(2000, 1, 1),
        })
        self.assertEqual(wizard.hijri_result_latin, "24 Ramadan 1420 AH")
        self.assertEqual(wizard.hijri_result_arabic, "24 رمضان 1420 هـ")
        self.assertEqual(wizard.hijri_result_numeric, "1420/09/24")

    def test_12_wizard_hijri_to_gregorian(self):
        wizard = self.env['ms.hijri.converter.wizard'].create({
            'hijri_year': 1445,
            'hijri_month': '9',
            'hijri_day': 1,
        })
        self.assertFalse(wizard.hijri_error)
        self.assertEqual(wizard.gregorian_result, date(2024, 3, 11))
        self.assertEqual(wizard.gregorian_weekday, 'Monday')

    def test_13_wizard_invalid_day_and_mixin(self):
        wizard = self.env['ms.hijri.converter.wizard'].create({
            'hijri_year': 1444,
            'hijri_month': '2',
            'hijri_day': 30,  # Safar has 29 days
        })
        self.assertTrue(wizard.hijri_error)
        self.assertFalse(wizard.gregorian_result)
        # mixin helper falls back to env.company when there is no company field
        self.company.hijri_format = 'latin'
        self.assertEqual(
            self.env['ms.hijri.mixin']._ms_hijri_display(date(2000, 1, 1)),
            "24 Ramadan 1420 AH")
