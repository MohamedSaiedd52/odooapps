# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMsAnalyticRequired(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.plan = cls.env['account.analytic.plan'].create({'name': 'MS Test Plan'})
        cls.aa_alpha = cls.env['account.analytic.account'].create(
            {'name': 'MS Alpha', 'plan_id': cls.plan.id}
        )
        cls.aa_beta = cls.env['account.analytic.account'].create(
            {'name': 'MS Beta', 'plan_id': cls.plan.id}
        )
        cls.income_account = cls.env['account.account'].create(
            {'code': 'MS4001', 'name': 'MS Revenue', 'account_type': 'income'}
        )
        cls.receivable_account = cls.env['account.account'].create(
            {
                'code': 'MS1101',
                'name': 'MS Receivable',
                'account_type': 'asset_receivable',
                'reconcile': True,
            }
        )
        cls.journal = cls.env['account.journal'].create(
            {'name': 'MS Test Journal', 'code': 'MSTJ', 'type': 'general'}
        )
        cls.full_distribution = {str(cls.aa_alpha.id): 100.0}
        cls.half_distribution = {str(cls.aa_beta.id): 50.0}

    def _make_entry(self, distribution=None, amount=250.0):
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'name': 'income side',
                    'account_id': self.income_account.id,
                    'credit': amount,
                    'analytic_distribution': distribution or {},
                }),
                (0, 0, {
                    'name': 'receivable side',
                    'account_id': self.receivable_account.id,
                    'debit': amount,
                }),
            ],
        })
        return move

    def test_01_optional_by_default(self):
        self._make_entry()
        self._make_entry(distribution=self.full_distribution)

    def test_02_always_blocks_missing_analytic(self):
        self.income_account.ms_analytic_policy = 'always'
        with self.assertRaises(ValidationError):
            self._make_entry()

    def test_03_always_accepts_analytic(self):
        self.income_account.ms_analytic_policy = 'always'
        move = self._make_entry(distribution=self.full_distribution)
        self.assertTrue(move)

    def test_04_always_ignores_zero_lines(self):
        self.income_account.ms_analytic_policy = 'always'
        self._make_entry(amount=0.0)

    def test_05_always_blocks_removal(self):
        self.income_account.ms_analytic_policy = 'always'
        move = self._make_entry(distribution=self.full_distribution)
        line = move.line_ids.filtered(
            lambda l: l.account_id == self.income_account
        )
        with self.assertRaises(ValidationError):
            line.analytic_distribution = {}

    def test_06_posted_allows_draft(self):
        self.income_account.ms_analytic_policy = 'posted'
        move = self._make_entry()
        self.assertEqual(move.state, 'draft')

    def test_07_posted_blocks_posting(self):
        self.income_account.ms_analytic_policy = 'posted'
        move = self._make_entry()
        with self.assertRaises(ValidationError):
            move.action_post()

    def test_08_posted_posts_with_analytic(self):
        self.income_account.ms_analytic_policy = 'posted'
        move = self._make_entry(distribution=self.full_distribution)
        move.action_post()
        self.assertEqual(move.state, 'posted')

    def test_09_forbidden_blocks_analytic(self):
        self.income_account.ms_analytic_policy = 'forbidden'
        with self.assertRaises(ValidationError):
            self._make_entry(distribution=self.full_distribution)

    def test_10_forbidden_accepts_plain_line(self):
        self.income_account.ms_analytic_policy = 'forbidden'
        self._make_entry()

    def test_11_company_default_policy(self):
        self.company.ms_analytic_policy_default = 'always'
        with self.assertRaises(ValidationError):
            self._make_entry()
        # per-account override wins over the company default
        self.income_account.ms_analytic_policy = 'forbidden'
        self.receivable_account.ms_analytic_policy = 'posted'
        self._make_entry()

    def test_12_full_coverage_enforced(self):
        self.income_account.ms_analytic_policy = 'always'
        self.company.ms_analytic_full_coverage = True
        with self.assertRaises(ValidationError):
            self._make_entry(distribution=self.half_distribution)
        self._make_entry(distribution=self.full_distribution)
