# -*- coding: utf-8 -*-
import logging

from psycopg2 import IntegrityError, sql

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MsAccountMergeWizard(models.TransientModel):
    _name = 'ms.account.merge.wizard'
    _description = 'Merge Accounts'

    account_ids = fields.Many2many(
        'account.account',
        string='Accounts to Merge',
        required=True,
    )
    destination_account_id = fields.Many2one(
        'account.account',
        string='Destination Account',
        required=True,
        help='All journal items and references of the other selected '
             'accounts will be moved to this account.',
    )
    allow_different_types = fields.Boolean(
        string='Allow Different Types',
        help='By default the merge is blocked when the selected accounts '
             'have different types (e.g. Expenses vs Receivable). Tick '
             'this only if you are sure.',
    )
    line_count = fields.Integer(
        compute='_compute_line_count',
        string='Journal Items to Move',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'account.account':
            active_ids = self.env.context.get('active_ids') or []
            if active_ids:
                res['account_ids'] = [Command.set(active_ids)]
                res['destination_account_id'] = active_ids[0]
        return res

    @api.depends('account_ids', 'destination_account_id')
    def _compute_line_count(self):
        for wizard in self:
            sources = wizard.account_ids - wizard.destination_account_id
            wizard.line_count = self.env['account.move.line'].search_count(
                [('account_id', 'in', sources.ids)]) if sources else 0

    # =============================================================
    # Main action
    # =============================================================
    def action_merge(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_(
                'Only Accounting Administrators can merge accounts.'))

        accounts = self.account_ids
        destination = self.destination_account_id
        if destination not in accounts:
            raise UserError(_(
                'The destination account must be one of the selected '
                'accounts.'))
        sources = accounts - destination
        if not sources:
            raise UserError(_('Select at least two different accounts.'))

        self._check_companies(sources, destination)
        self._check_types(sources, destination)
        self._check_hashed_entries(sources)

        # Keep reconciliations valid
        if any(a.reconcile for a in sources) and not destination.reconcile:
            destination.reconcile = True

        moved_lines = self.env['account.move.line'].search_count(
            [('account_id', 'in', sources.ids)])

        # Repoint everything in the database
        self._update_foreign_keys(sources, destination)
        self._update_company_dependent_fields(sources, destination)
        self._update_ir_property_references(sources, destination)

        # Archive the source accounts (never delete history holders)
        self._archive_accounts(sources)

        self.env.invalidate_all()
        self.env.registry.clear_cache()
        _logger.info(
            'MS Account Merge: %s merged into %s (%s journal items) '
            'by user %s',
            sources.mapped('code'), destination.code,
            moved_lines, self.env.user.login)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Accounts Merged'),
                'message': _(
                    '%(count)s journal items and all references were '
                    'moved to %(dest)s. Source accounts were archived.',
                    count=moved_lines, dest=destination.display_name),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # =============================================================
    # Safeguards
    # =============================================================
    def _check_companies(self, sources, destination):
        def company_key(account):
            if 'company_ids' in account._fields:
                return tuple(sorted(account.company_ids.ids))
            return (account.company_id.id,)

        dest_key = company_key(destination)
        for account in sources:
            if company_key(account) != dest_key:
                raise UserError(_(
                    'All selected accounts must belong to the same '
                    'company scope. "%(src)s" and "%(dest)s" differ.',
                    src=account.display_name,
                    dest=destination.display_name))

    def _check_types(self, sources, destination):
        if self.allow_different_types:
            return
        bad = sources.filtered(
            lambda a: a.account_type != destination.account_type)
        if bad:
            raise UserError(_(
                'The following accounts have a different type than the '
                'destination (%(dest_type)s):\n%(accounts)s\n\n'
                'Tick "Allow Different Types" if you really intend to '
                'merge them.',
                dest_type=destination.account_type,
                accounts='\n'.join(
                    '- %s (%s)' % (a.display_name, a.account_type)
                    for a in bad)))

    def _check_hashed_entries(self, sources):
        hashed = self.env['account.move.line'].sudo().search_count([
            ('account_id', 'in', sources.ids),
            ('move_id.inalterable_hash', '!=', False),
        ])
        if hashed:
            raise UserError(_(
                '%(count)s journal items on the source accounts belong '
                'to hashed (inalterable) entries and cannot be moved. '
                'The merge is not possible for these accounts.',
                count=hashed))

    def _archive_accounts(self, sources):
        if 'active' in sources._fields:
            sources.write({'active': False})
        elif 'deprecated' in sources._fields:
            sources.write({'deprecated': True})

    # =============================================================
    # Generic repointing - same technique as the native partner merge
    # =============================================================
    def _update_foreign_keys(self, sources, destination):
        """Repoint every FK in the database referencing
        account_account(id) from the source accounts to the
        destination."""
        self.env.flush_all()
        cr = self.env.cr
        own_tables = (self._table,)

        cr.execute("""
            SELECT cl1.relname AS table_name, att1.attname AS column_name
              FROM pg_constraint AS con
              JOIN pg_class AS cl1 ON con.conrelid = cl1.oid
              JOIN pg_class AS cl2 ON con.confrelid = cl2.oid
              JOIN pg_attribute AS att1
                   ON att1.attrelid = cl1.oid
                  AND att1.attnum = con.conkey[1]
              JOIN pg_attribute AS att2
                   ON att2.attrelid = cl2.oid
                  AND att2.attnum = con.confkey[1]
             WHERE cl2.relname = 'account_account'
               AND att2.attname = 'id'
               AND con.contype = 'f'
               AND array_length(con.conkey, 1) = 1
        """)
        relations = cr.fetchall()
        src_ids = tuple(sources.ids)

        for table, column in relations:
            if table in own_tables or table.startswith(
                    'ms_account_merge'):
                continue

            cr.execute("""
                SELECT column_name FROM information_schema.columns
                 WHERE table_name = %s
            """, (table,))
            columns = [c for (c,) in cr.fetchall()]
            has_id = 'id' in columns

            tbl = sql.Identifier(table)
            col = sql.Identifier(column)

            if not has_id:
                # Many2many relation table: remove rows that would
                # duplicate an existing (destination) row, then update.
                other_cols = [c for c in columns if c != column]
                if other_cols:
                    conditions = sql.SQL(' AND ').join(
                        sql.SQL('t2.{c} = t1.{c}').format(
                            c=sql.Identifier(c)) for c in other_cols)
                    cr.execute(sql.SQL("""
                        DELETE FROM {tbl} t1
                         WHERE t1.{col} IN %s
                           AND EXISTS (SELECT 1 FROM {tbl} t2
                                        WHERE t2.{col} = %s AND {cond})
                    """).format(tbl=tbl, col=col, cond=conditions),
                        (src_ids, destination.id))
                cr.execute(sql.SQL(
                    'UPDATE {tbl} SET {col} = %s WHERE {col} IN %s'
                ).format(tbl=tbl, col=col), (destination.id, src_ids))
                continue

            # Regular many2one column
            try:
                with cr.savepoint():
                    cr.execute(sql.SQL(
                        'UPDATE {tbl} SET {col} = %s WHERE {col} IN %s'
                    ).format(tbl=tbl, col=col),
                        (destination.id, src_ids))
            except IntegrityError:
                # Unique constraint hit: retry row by row, dropping the
                # rows that conflict with an existing destination row.
                cr.execute(sql.SQL(
                    'SELECT id FROM {tbl} WHERE {col} IN %s'
                ).format(tbl=tbl, col=col), (src_ids,))
                for (row_id,) in cr.fetchall():
                    try:
                        with cr.savepoint():
                            cr.execute(sql.SQL(
                                'UPDATE {tbl} SET {col} = %s '
                                'WHERE id = %s'
                            ).format(tbl=tbl, col=col),
                                (destination.id, row_id))
                    except IntegrityError:
                        cr.execute(sql.SQL(
                            'DELETE FROM {tbl} WHERE id = %s'
                        ).format(tbl=tbl), (row_id,))

    def _update_company_dependent_fields(self, sources, destination):
        """Company-dependent Many2one fields (e.g. partner receivable/
        payable accounts, product income/expense accounts) are stored
        as jsonb {company_id: account_id} since Odoo 18 - the FK scan
        cannot see them, so handle them explicitly.

        On Odoo 17 and earlier those values live in ir.property instead
        (see _update_ir_property_references) and ir.model.fields has no
        'company_dependent' column, so this pass is skipped there."""
        if 'company_dependent' not in self.env['ir.model.fields']._fields:
            return
        cr = self.env.cr
        field_records = self.env['ir.model.fields'].sudo().search([
            ('relation', '=', 'account.account'),
            ('company_dependent', '=', True),
            ('ttype', '=', 'many2one'),
            ('store', '=', True),
        ])
        for field_rec in field_records:
            model = self.env.get(field_rec.model)
            if (model is None or not getattr(model, '_auto', False)
                    or field_rec.name not in model._fields):
                continue
            cr.execute("""
                SELECT 1 FROM information_schema.columns
                 WHERE table_name = %s AND column_name = %s
                   AND udt_name = 'jsonb'
            """, (model._table, field_rec.name))
            if not cr.fetchone():
                continue
            tbl = sql.Identifier(model._table)
            col = sql.Identifier(field_rec.name)
            for src_id in sources.ids:
                cr.execute(sql.SQL("""
                    UPDATE {tbl}
                       SET {col} = (
                           SELECT jsonb_object_agg(
                               e.key,
                               CASE WHEN e.value = to_jsonb(%s::int)
                                    THEN to_jsonb(%s::int)
                                    ELSE e.value END)
                             FROM jsonb_each({col}) AS e)
                     WHERE {col} IS NOT NULL
                       AND EXISTS (
                           SELECT 1 FROM jsonb_each({col}) AS e
                            WHERE e.value = to_jsonb(%s::int))
                """).format(tbl=tbl, col=col),
                    (src_id, destination.id, src_id))

    def _update_ir_property_references(self, sources, destination):
        """Odoo 17 and earlier store company-dependent Many2one values
        (partner receivable/payable accounts, product income/expense
        accounts, ...) in ir.property as 'account.account,<id>' text
        references - invisible to both the FK scan and the jsonb pass.
        The model was removed in Odoo 18, hence the guard."""
        if 'ir.property' not in self.env:
            return
        cr = self.env.cr
        refs = tuple('account.account,%d' % i for i in sources.ids)
        cr.execute("""
            UPDATE ir_property
               SET value_reference = %s
             WHERE value_reference IN %s
        """, ('account.account,%d' % destination.id, refs))
