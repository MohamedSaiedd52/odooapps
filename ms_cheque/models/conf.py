# -*- coding: utf-8 -*-
from odoo import models, fields, api , _


class ChequeSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    in_debit_account_id = fields.Many2one(
        'account.account',
        related='company_id.in_cheque_debit_account_id',
        readonly=False,
        domain="[('deprecated', '=', False)]"
    )

    out_credit_account_id = fields.Many2one(
        'account.account',
        related='company_id.out_cheque_credit_account_id',
        readonly=False,
        domain="[('deprecated', '=', False)]"
    )

    in_cheque_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.in_cheque_journal_id',
        readonly=False
    )

    out_cheque_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.out_cheque_journal_id',
        readonly=False
    )


class ResCompany(models.Model):
    _inherit = 'res.company'

    in_cheque_debit_account_id = fields.Many2one(
        'account.account', string='Incoming Cheque Debit Account'
    )
    out_cheque_credit_account_id = fields.Many2one(
        'account.account', string='Outgoing Cheque Credit Account'
    )

    in_cheque_journal_id = fields.Many2one(
        'account.journal', string='Incoming Cheques Journal'
    )
    out_cheque_journal_id = fields.Many2one(
        'account.journal', string='Outgoing Cheques Journal'
    )



class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    in_cheque_id = fields.Many2one('ms.in', string='MS IN Cheque')
    out_cheque_id = fields.Many2one('ms.out', string='MS OUT Cheque')