# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccessRightsCopyWizard(models.TransientModel):
    """Copy the access setup (security groups and/or access profiles) of one
    user onto other users — the classic "give him the same rights as her"
    request, done in one step instead of ticking dozens of boxes."""
    _name = 'access.rights.copy.wizard'
    _description = 'Copy User Access'

    source_user_id = fields.Many2one(
        'res.users', string='Copy From', required=True,
        domain=[('share', '=', False)])
    target_user_ids = fields.Many2many(
        'res.users', string='Copy To', required=True,
        domain=[('share', '=', False)])
    copy_groups = fields.Boolean(string='Security Groups', default=True)
    copy_profiles = fields.Boolean(string='Access Profiles', default=True)
    mode = fields.Selection([
        ('add', 'Add to the existing access'),
        ('replace', 'Replace the existing access'),
    ], required=True, default='add',
        help="'Add' keeps what the target users already have; 'Replace' makes "
             "their access an exact copy of the source user's.")

    source_summary = fields.Char(compute='_compute_source_summary')

    @api.depends('source_user_id')
    def _compute_source_summary(self):
        for wizard in self:
            source = wizard.source_user_id
            wizard.source_summary = source and _(
                "%(groups)s groups, %(profiles)s access profiles",
                groups=len(source.group_ids),
                profiles=len(source.access_profile_ids)) or False

    def action_apply(self):
        self.ensure_one()
        if not self.copy_groups and not self.copy_profiles:
            raise UserError(_("Select what to copy: groups, profiles or both."))
        targets = self.target_user_ids - self.source_user_id
        if not targets:
            raise UserError(_("Select at least one target user other than the source."))
        if (self.mode == 'replace' and self.copy_groups
                and self.env.user in targets
                and not self.source_user_id.has_group(
                    'access_rights_management.group_access_rights_manager')):
            raise UserError(_(
                "You cannot replace your own groups with those of a user who "
                "is not an access rights manager — you would lock yourself "
                "out of this app."))

        if self.copy_groups:
            if self.mode == 'replace':
                targets.write({'group_ids': [(6, 0, self.source_user_id.group_ids.ids)]})
            else:
                targets.write({'group_ids': [(4, gid) for gid in self.source_user_id.group_ids.ids]})

        if self.copy_profiles:
            profiles = self.source_user_id.access_profile_ids
            if self.mode == 'replace':
                extra = self.env['access.rights.profile'].search(
                    [('user_ids', 'in', targets.ids)]) - profiles
                for profile in extra:
                    profile.write({'user_ids': [(3, uid) for uid in targets.ids]})
            for profile in profiles:
                profile.write({'user_ids': [(4, uid) for uid in targets.ids]})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _("Access copied"),
                # NB: `_()` names its first parameter `source`, so a
                # `%(source)s` placeholder cannot be filled by keyword.
                'message': _(
                    "The access of %(user)s was copied to %(count)s user(s).",
                    user=self.source_user_id.name, count=len(targets)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
