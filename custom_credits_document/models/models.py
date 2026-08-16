# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CreditsDocument(models.Model):
    _name = 'letter.credit'

    name = fields.Char(string='Name', default='/', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', track_visibility='onchange', copy=False)

    bank_account_id = fields.Many2one('account.account', string='حساب البنك', required=True,
                                      related='bank_journal_id.default_account_id',
                                      domain=[('account_type', '=', 'asset_cash')])
    bank_journal_id = fields.Many2one('account.journal', string='دفتر حساب البنك', required=True,
                                      domain=[('type', '=', 'bank')])
    credit_number = fields.Char(string='رقم الإعتماد', required=True)
    credit_date = fields.Date(string='تاريخ الإعتماد', required=True)
    credit_value = fields.Float(string='مبلغ الإعتماد', required=True)
    credit_currency = fields.Many2one('res.currency', string='عملة الإعتماد المستندي', required=True)
    credit_bank_expense = fields.Float(string='مصروفات الإعتماد البنكية', required=True)
    current_account_id = fields.Many2one('account.account', string='الحساب المقابل', required=True,
                                         domain=[('account_type', '=', 'asset_current')])
    expense_account_id = fields.Many2one('account.account', string='حساب المصروفات', required=True,
                                         domain=[('account_type', '=', 'expense')])
    running_move_id = fields.Many2one('account.move', string='القيد الجاري', copy=False)
    done_move_id = fields.Many2one('account.move', string='القيد المنفذ', copy=False)

    @api.model
    def create(self, vals):
        res = super(CreditsDocument, self).create(vals)
        for rec in res:
            rec.name = self.env['ir.sequence'].next_by_code('letter.credit') or '/'
        return res

    def action_running(self):
        running_move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.today(),
            'journal_id': self.bank_journal_id.id,
            'currency_id': self.credit_currency.id,
            'line_ids': [
                (0, 0, {
                    'name': self.credit_number,
                    'account_id': self.current_account_id.id,
                    'amount_currency': self.credit_value,
                    'currency_id': self.credit_currency.id,
                }),
                (0, 0, {
                    'name': self.credit_number,
                    'account_id': self.expense_account_id.id,
                    'amount_currency': self.credit_bank_expense,
                    'currency_id': self.credit_currency.id,

                }),
                (0, 0, {
                    'name': self.credit_number,
                    'account_id': self.bank_account_id.id,
                    'amount_currency': - (self.credit_value + self.credit_bank_expense),
                    'currency_id': self.credit_currency.id,

                }),
            ],
        })
        self.running_move_id = running_move.id
        self.state = 'running'

    def action_done(self):
        done_move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.today(),
            'journal_id': self.bank_journal_id.id,
            'currency_id': self.credit_currency.id,
            'line_ids': [
                (0, 0, {
                    'name': self.credit_number,
                    'account_id': self.bank_account_id.id,
                    'amount_currency': self.credit_value,
                    'currency_id': self.credit_currency.id,

                }),
                (0, 0, {
                    'name': self.credit_number,
                    'account_id': self.current_account_id.id,
                    'amount_currency': - self.credit_value,
                    'currency_id': self.credit_currency.id,

                }),
            ],
        })
        self.done_move_id = done_move.id
        self.state = 'done'

    def action_cancel(self):
        self.state = 'cancel'

    def view_running_move(self):
        return {
            'name': 'القيد الجاري',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.running_move_id.id,
            'target': 'current',
        }

    def view_done_move(self):
        return {
            'name': 'القيد المنفذ',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.done_move_id.id,
            'target': 'current',
        }
