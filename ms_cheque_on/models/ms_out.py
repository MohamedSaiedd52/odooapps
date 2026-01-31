from odoo import models, fields, api, _
from odoo.exceptions import UserError
from lxml import etree
from datetime import date
class Msout(models.Model):
    _name = 'ms.out'
    _description = 'Out'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    type = fields.Selection([('in', 'In'), ('out', 'Out')],
                            default='out', readonly=True, required=True)

    name = fields.Char(default='/', copy=False, readonly=True)
    cheque_no = fields.Char(string='Cheque Number', required=True)
    payee_id = fields.Many2one('res.partner', string='Vendor', required=True)
    cheque_date = fields.Date(string='Cheque Date', default=fields.Date.context_today)
    cashed_date = fields.Date(string='Cashed Date', copy=False)

    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)
    description = fields.Char(string='Description')
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        default=lambda self: self.env.company.out_cheque_journal_id
    )
    bank_account_id = fields.Many2one('account.account', string='Bank Account',
                                      domain="[('deprecated','=',False)]")
    cash_bank_account_id = fields.Many2one('account.account', string='Cash / Bank Account',
                                           help='Bank account used while cashing the cheque')

    debit_account_id = fields.Many2one('account.account', string='Debit Account', default=lambda self: self.env.company.in_cheque_debit_account_id)
    credit_account_id = fields.Many2one('account.account', string='Credit Account', default=lambda self: self.env.company.out_cheque_credit_account_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('cashed', 'Cashed'),
        ('cancel', 'Cancelled'),
    ], default='draft', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    move_id = fields.Many2one('account.move', string='Journal Entry', copy=False)
    move_line_ids = fields.One2many('account.move.line', 'out_cheque_id', string='Journal Items', copy=False)
    show_debit = fields.Boolean(compute='_compute_show_side', store=True)
    show_credit = fields.Boolean(compute='_compute_show_side', store=True)
    move_line_count = fields.Integer(compute='_compute_move_line_count', string='Journal Items')
    vendor_name = fields.Char(compute='_compute_vendor_name')

    def _compute_move_line_count(self):
        for rec in self:
            rec.move_line_count = len(rec.move_line_ids)

    def _compute_vendor_name(self):
        for rec in self:
            rec.vendor_name = rec.payee_id.name if rec.payee_id else ''

    def action_open_journal_items(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Items',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [('out_cheque_id', '=', self.id)],
        }

    move_count = fields.Integer(
        compute='_compute_move_count',
        string='Journal Entries'
    )

    def _compute_move_count(self):
        for rec in self:
            rec.move_count = len(rec.move_line_ids.mapped('move_id'))

    def action_open_journal_entry(self):
        self.ensure_one()
        move_ids = self.move_line_ids.mapped('move_id').ids
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entries',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', move_ids)],
        }
        if len(move_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': move_ids[0],
            })
        return action

    def action_open_vendor(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.payee_id.id,
            'view_mode': 'form',
        }

    _sql_constraints = [
        ('cheque_out_unique', 'unique(cheque_no, company_id)', 'Cheque number must be unique per company.')
    ]

    @api.onchange('company_id')
    def _onchange_company_set_default_credit(self):
        self.credit_account_id = (
            self.company_id.out_cheque_credit_account_id
        )

    @api.model
    def create(self, vals):
        company = self.env['res.company'].browse(
            vals.get('company_id', self.env.company.id)
        )

        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('seq.ms.out') or '/'

        if not vals.get('credit_account_id') and company.out_cheque_credit_account_id:
            vals['credit_account_id'] = company.out_cheque_credit_account_id.id

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
            if rec.amount <= 0:
                raise UserError(_('Amount must be greater than zero.'))

            move = rec._create_move(
                debit_account=rec.payee_id.property_account_payable_id,
                credit_account=rec.credit_account_id or rec.bank_account_id
            )
            rec.move_id = move.id
            rec.state = 'submit'
        return True

    def action_cashed(self):
        for rec in self:
            if rec.state != 'submit':
                raise UserError(_('Only submitted cheques can be cashed.'))
            if not rec.cash_bank_account_id:
                raise UserError(_('Please select Cash / Bank Account before cashing.'))
            if not rec.credit_account_id:
                raise UserError(_('Please set Credit Account (Accounts Payable) before cashing.'))

            Move = self.env['account.move']
            move_vals = {
                'date': fields.Date.today(),
                'journal_id': rec.journal_id.id,
                'ref': rec.name + ' - Cash',
                'line_ids': [
                    # Debit: Accounts Payable / Credit account (reduce liability)
                    (0, 0, {
                        'account_id': rec.credit_account_id.id,
                        'partner_id': rec.payee_id.id,
                        'debit': rec.amount,
                        'credit': 0,
                        'out_cheque_id': rec.id,
                    }),
                    # Credit: Bank / Cash account (money leaves)
                    (0, 0, {
                        'account_id': rec.cash_bank_account_id.id,
                        'partner_id': rec.payee_id.id,
                        'debit': 0,
                        'credit': rec.amount,
                        'out_cheque_id': rec.id,
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
            moves = rec.move_line_ids.mapped('move_id').sudo()
            for move in moves:
                move.button_draft()
                move.unlink()

            rec.sudo().write({
                'state': 'cancel',
                'move_id': False,
            })

    def action_open_credit_account(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Journal Items',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [
                ('account_id', '=', self.credit_account_id.id),
                ('move_id.state', '=', 'posted'),
            ],
            'context': {
                'search_default_account_id': self.credit_account_id.id,
            }
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

    def action_set_draft(self):
        for rec in self:
            moves = rec.move_line_ids.mapped('move_id').sudo()
            for move in moves:
                move.button_draft()
                move.unlink()
            rec.state = 'draft'

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
                        'partner_id': rec.payee_id.id,
                        'debit': rec.amount,
                        'credit': 0,
                        'out_cheque_id': rec.id,
                    }),
                    (0, 0, {
                        'account_id': credit_account.id,
                        'partner_id': rec.payee_id.id,
                        'debit': 0,
                        'credit': rec.amount,
                        'out_cheque_id': rec.id,
                    }),
                ]
            }
            move = Move.create(move_vals)
            move.action_post()
            return move

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        journal = self.env.company.out_cheque_journal_id
        if journal and journal.default_account_id:
            res['journal_id'] = journal.id
            res['bank_account_id'] = journal.default_account_id.id
        return res

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            for node in arch.xpath("//field"):
                if node.get('name') not in ('state', 'name','cash_bank_account_id'):
                    node.set('readonly', "state != 'draft'")
        return arch, view
