# -*- coding: utf-8 -*-
"""Unified permission-change timeline.

Odoo tracks a profile's own edits in its chatter, but nothing records the
question auditors actually ask: *who gave this user this permission, and
when?* This model logs every grant/revoke of a security group or an access
profile, with the actor, so the whole history is one searchable list.

Writes go through `res.users.write` / profile writes, so both directions of a
many2many change are captured whichever side it was edited from.
"""
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AccessRightsChange(models.Model):
    _name = 'access.rights.change'
    _description = 'Permission Change'
    _order = 'id desc'
    _rec_name = 'display_name'

    user_id = fields.Many2one('res.users', string='User', required=True,
                              ondelete='cascade', index=True, readonly=True)
    change_type = fields.Selection([
        ('group', 'Security Group'),
        ('profile', 'Access Profile'),
    ], required=True, index=True, readonly=True)
    action = fields.Selection([
        ('granted', 'Granted'),
        ('revoked', 'Revoked'),
    ], required=True, index=True, readonly=True)
    item_name = fields.Char(string='Permission', required=True, readonly=True)
    group_id = fields.Many2one('res.groups', string='Group',
                               ondelete='set null', readonly=True)
    profile_id = fields.Many2one('access.rights.profile', string='Profile',
                                 ondelete='set null', readonly=True)
    actor_id = fields.Many2one('res.users', string='Changed By',
                               ondelete='set null', index=True, readonly=True)
    is_admin_change = fields.Boolean(
        string='Administrator Right', readonly=True, index=True,
        help="The change concerns a full-administrator group — the highest "
             "impact kind of grant.")
    display_name = fields.Char(compute='_compute_display_name')

    @api.depends('user_id', 'action', 'item_name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s %s %s" % (
                rec.user_id.name or '?',
                _("granted") if rec.action == 'granted' else _("revoked"),
                rec.item_name or '')

    # ------------------------------------------------------------------
    # recording
    # ------------------------------------------------------------------
    @api.model
    def _record(self, user, change_type, action, item, is_admin=False):
        """Write one timeline line. Never raises — it runs inside write()."""
        try:
            vals = {
                'user_id': user.id,
                'change_type': change_type,
                'action': action,
                'item_name': (item.display_name or str(item.id))[:256],
                'actor_id': self.env.uid,
                'is_admin_change': is_admin,
            }
            if change_type == 'group':
                vals['group_id'] = item.id
            else:
                vals['profile_id'] = item.id
            self.sudo().create(vals)
        except Exception:
            _logger.exception("Could not record a permission change")

    @api.model
    def _record_diff(self, user, change_type, before, after):
        """Log the symmetric difference of two recordsets for one user."""
        try:
            admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
            for item in after - before:
                self._record(user, change_type, 'granted', item,
                             is_admin=bool(admin_group and item == admin_group))
            for item in before - after:
                self._record(user, change_type, 'revoked', item,
                             is_admin=bool(admin_group and item == admin_group))
        except Exception:
            _logger.exception("Could not diff a permission change")

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def action_open_user(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'res_id': self.user_id.id,
            'view_mode': 'form',
        }
