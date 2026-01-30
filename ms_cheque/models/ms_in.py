# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class Msin(models.Model):
    _name = 'ms.in'
    _description = 'in'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    type = fields.Selection([('in', 'In'), ('out', 'Out')],
                            default='in', readonly=True, required=True)

    name = fields.Char(string='Sequence', copy=False, readonly=True)
    cheque_no = fields.Char(string='Cheque Number', required=True)
    payer_id = fields.Many2one('res.partner', string='Customer', required=True)

    cheque_date = fields.Date(string='Cheque Date')
    receive_date = fields.Date(string='Receive Date')
    deposit_date = fields.Date(string='Deposit Date', copy=False)
    cashed_date = fields.Date(string='Cashed Date', copy=False)

    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)
    move_count = fields.Integer(
        compute='_compute_move_count',
        string='Journal Entry'
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        default=lambda self: self.env.company.in_cheque_journal_id
    )
    # bank account selected when depositing; and cash_bank_account_id used when cashing
    bank_account_id = fields.Many2one('account.account', string='Bank Account',
                                      domain="[('deprecated','=',False)]")
    cash_bank_account_id = fields.Many2one('account.account', string='Cash / Bank Account',
                                           help='Bank account used while cashing the cheque')


    credit_account_id = fields.Many2one(
        'account.account',
        string='Credit Account',
        default=lambda self: self.env.company.out_cheque_credit_account_id
    )

    debit_account_id = fields.Many2one(
        'account.account',
        string='Debit Account',
        default=lambda self: self.env.company.in_cheque_debit_account_id
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('deposit', 'Deposited'),
        ('cashed', 'Cashed'),
        ('cancel', 'Cancelled')
    ], default='draft', tracking=True)

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    move_id = fields.Many2one('account.move', string='Journal Entry', copy=False)
    move_line_ids = fields.One2many('account.move.line', 'in_cheque_id', string='Journal Items', copy=False)

    show_debit = fields.Boolean(compute='_compute_show_side', store=True)
    show_credit = fields.Boolean(compute='_compute_show_side', store=True)
    move_line_count = fields.Integer(
        compute='_compute_move_line_count',
        string='Journal Items'
    )

    customer_name = fields.Char(
        compute='_compute_customer_name'
    )

    customer_short_name = fields.Char(
        compute='_compute_customer_short_name',
        string='Customer'
    )

    _sql_constraints = [
        ('cheque_in_unique',
         'unique(cheque_no, company_id)',
         'Cheque number must be unique per company.')
    ]

    def _compute_move_count(self):
        for rec in self:
            rec.move_count = 1 if rec.move_id else 0

    def action_open_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }

    def _compute_move_line_count(self):
        for rec in self:
            rec.move_line_count = len(rec.move_line_ids)

    def _compute_customer_name(self):
        for rec in self:
            rec.customer_name = rec.payer_id.name if rec.payer_id else ''

    def _compute_customer_short_name(self):
        for rec in self:
            name = rec.customer_name or ''
            rec.customer_short_name = name[:10] + '…' if len(name) > 10 else name

    def action_open_journal_items(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Items',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [('in_cheque_id', '=', self.id)],
        }

    def action_open_customer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.payer_id.id,
            'view_mode': 'form',
        }

    def action_open_debit_account(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Debit Journal Items',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [
                ('account_id', '=', self.debit_account_id.id),
                ('move_id.state', '=', 'posted'),
            ],
            'context': {
                'search_default_account_id': self.debit_account_id.id,
            }
        }

    def action_open_credit_account(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.account',
            'res_id': self.credit_account_id.id,
            'view_mode': 'form',
        }

    def action_return(self):
        for rec in self:
            moves = rec.move_line_ids.mapped('move_id').filtered(lambda m: m.state == 'posted')
            for move in moves:
                reverse = move._reverse_moves(
                    default_values_list=[{
                        'date': fields.Date.today(),
                        'ref': 'Return %s' % rec.name,
                    }],
                    cancel=False
                )
                reverse.action_post()
            rec.state = 'draft'

    @api.onchange('company_id')
    def _onchange_company_set_default_debit(self):
        self.debit_account_id = (
            self.company_id.in_cheque_debit_account_id
        )

    @api.model
    def create(self, vals):
        if not vals.get('debit_account_id'):
            company = self.env['res.company'].browse(
                vals.get('company_id', self.env.company.id)
            )
            vals['debit_account_id'] = (
                company.in_cheque_debit_account_id.id
            )
        return super().create(vals)
    @api.model
    def create(self, vals):
        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code('seq.ms.in') or '/'
        return super().create(vals)

    @api.depends('type')
    def _compute_show_side(self):
        for rec in self:
            rec.show_debit = rec.type == 'in'
            rec.show_credit = rec.type == 'out'

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft cheques can be submitted.'))

            # create initial move (registered) between receivable and debit account
            move = rec._create_move(
                debit_account=rec.debit_account_id or rec.bank_account_id,
                credit_account=rec.payer_id.property_account_receivable_id
            )
            rec.move_id = move.id
            rec.state = 'submit'
        return True

    def action_deposit(self):
        for rec in self:
            if rec.state != 'submit':
                raise UserError(_('Only submitted cheques can be deposited.'))
            if not rec.debit_account_id:
                raise UserError(_('Please set Debit Account on the cheque.'))
            if not rec.bank_account_id:
                raise UserError(_('Please select Bank Account to deposit into.'))

            Move = self.env['account.move']

            move_vals = {
                'date': fields.Date.today(),
                'journal_id': rec.journal_id.id,
                'ref': rec.name + ' - Deposit',
                'line_ids': [
                    # credit: debit_account_id (remove registered debit)
                    (0, 0, {
                        'account_id': rec.debit_account_id.id,
                        'partner_id': rec.payer_id.id,
                        'credit': rec.amount,
                        'debit': 0,
                        'in_cheque_id': rec.id,
                    }),
                    # debit: bank_account_id
                    (0, 0, {
                        'account_id': rec.bank_account_id.id,
                        'partner_id': rec.payer_id.id,
                        'debit': rec.amount,
                        'credit': 0,
                        'in_cheque_id': rec.id,
                    }),
                ]
            }
            move = Move.create(move_vals)
            move.action_post()

            rec.write({
                'state': 'deposit',
                'deposit_date': fields.Date.today(),
            })
        return True

    def action_cashed(self):
        for rec in self:
            if rec.state not in ['submit', 'deposit']:
                raise UserError(_('Cheque must be submitted or deposited first.'))
            if not rec.cash_bank_account_id:
                raise UserError(_('Select Cash / Bank Account first.'))
            if not rec.debit_account_id:
                raise UserError(_('Please set Debit Account.'))

            Move = self.env['account.move']
            move_vals = {
                'date': fields.Date.today(),
                'journal_id': rec.journal_id.id,
                'ref': rec.name + ' - Cash',
                'line_ids': [
                    # credit: debit_account_id (clear registered debit)
                    (0, 0, {
                        'account_id': rec.bank_account_id.id,
                        'partner_id': rec.payer_id.id,
                        'credit': rec.amount,
                        'debit': 0,
                        'in_cheque_id': rec.id,
                    }),
                    # debit: cash_bank_account_id
                    (0, 0, {
                        'account_id': rec.cash_bank_account_id.id,
                        'partner_id': rec.payer_id.id,
                        'debit': rec.amount,
                        'credit': 0,
                        'in_cheque_id': rec.id,
                    }),
                ]
            }
            move = Move.create(move_vals)
            move.action_post()

            rec.write({
                'state': 'cashed',
                'cashed_date': fields.Date.today(),
                'move_id': move.id,
            })
        return True

    def action_cancel(self):
        for rec in self:
            moves = rec.move_line_ids.mapped('move_id')
            for move in moves:
                move.sudo().button_draft()
                move.sudo().unlink()

            rec.sudo().write({
                'state': 'cancel',
                'move_id': False,
            })


    def _create_move(self, debit_account, credit_account):
        Move = self.env['account.move']
        for rec in self:
            move_vals = {
                'date': fields.Date.today(),
                'journal_id': rec.journal_id.id,
                'ref': rec.name + ' - Registered',
                'line_ids': [
                    (0, 0, {
                        'account_id': debit_account.id,
                        'partner_id': rec.payer_id.id,
                        'debit': rec.amount,
                        'credit': 0,
                        'in_cheque_id': rec.id,
                    }),
                    (0, 0, {
                        'account_id': credit_account.id,
                        'partner_id': rec.payer_id.id,
                        'debit': 0,
                        'credit': rec.amount,
                        'in_cheque_id': rec.id,
                    }),
                ]
            }
            move = Move.create(move_vals)
            move.action_post()
            return move
    
    def action_set_draft(self):
        for rec in self:
            moves = rec.move_line_ids.mapped('move_id')
            for move in moves:
                if move.state == 'posted':
                    move.button_draft()
            rec.state = 'draft'
