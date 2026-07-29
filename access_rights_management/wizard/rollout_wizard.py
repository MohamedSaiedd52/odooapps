# -*- coding: utf-8 -*-
"""Fast profile adoption.

A fully-built access-rights app is useless while nobody is covered by a
profile. This wizard closes that gap in one screen: pick departments, pick a
starter template (or an existing profile), and every internal user of those
departments gets covered — one profile per department, so each stays editable
on its own afterwards.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Starter templates. Each is a coarse but safe baseline: it restricts the
# destructive UI actions and the data-leak paths, and leaves the actual
# business rights to the user's Odoo groups. Managers refine from there.
# (key, label, icon, profile flags, hint)
TEMPLATE_DEFS = [
    ('viewer', 'Read-Only Viewer', 'fa-eye', {
        'readonly': True,
        'disable_debug_mode': True,
        'hide_export': True,
        'hide_import': True,
        'hide_spreadsheet': True,
        'hide_add_property': True,
    }, "Can open and read everything their groups allow, but cannot create, "
       "edit or delete anything, and cannot export data. Ideal for auditors, "
       "trainees and viewers."),

    ('staff', 'Standard Staff', 'fa-user', {
        'disable_debug_mode': True,
        'hide_export': True,
        'hide_spreadsheet': True,
        'hide_add_property': True,
        'hide_import': True,
    }, "Normal day-to-day work: can create and edit, but cannot export or "
       "import data, and has no developer mode. The safe default for most "
       "employees."),

    ('supervisor', 'Supervisor', 'fa-user-plus', {
        'disable_debug_mode': True,
        'hide_import': True,
        'hide_add_property': True,
    }, "Like Standard Staff but allowed to export (for their own reporting). "
       "Still no import and no developer mode."),

    ('sensitive', 'Restricted — Sensitive Data', 'fa-user-secret', {
        'disable_debug_mode': True,
        'hide_export': True,
        'hide_import': True,
        'hide_spreadsheet': True,
        'hide_add_property': True,
        'require_2fa': True,
    }, "For people who handle salaries, costs or margins: no export at all "
       "and two-factor authentication required."),
]

TEMPLATE_FLAGS = {key: flags for key, _label, _icon, flags, _hint in TEMPLATE_DEFS}
TEMPLATE_LABELS = {key: label for key, label, _icon, _flags, _hint in TEMPLATE_DEFS}
TEMPLATE_HINTS = {key: hint for key, _label, _icon, _flags, hint in TEMPLATE_DEFS}


class AccessRightsRolloutWizard(models.TransientModel):
    _name = 'access.rights.rollout.wizard'
    _description = 'Roll Out Access Profiles'

    mode = fields.Selection([
        ('template', 'Create from a template'),
        ('existing', 'Use an existing profile'),
    ], default='template', required=True)

    template = fields.Selection(
        [(key, label) for key, label, _i, _f, _h in TEMPLATE_DEFS],
        default='staff')
    template_hint = fields.Char(compute='_compute_template_hint')
    profile_id = fields.Many2one(
        'access.rights.profile', string='Existing Profile',
        domain=[('apply_to_all_users', '=', False)])

    cover_all_uncovered = fields.Boolean(
        string='Cover Every Uncovered User',
        help="Cover all internal users who have no profile at all, whether or "
             "not their employee record is linked to a department. Users whose "
             "department is known are grouped under it; the rest go into one "
             "shared profile.")
    department_ids = fields.Many2many(
        'hr.department', string='Departments',
        help="Every internal user who is an employee of these departments "
             "gets covered.")
    include_children = fields.Boolean(
        string='Include Sub-Departments', default=True)
    extra_user_ids = fields.Many2many(
        'res.users', string='Extra Users', domain=[('share', '=', False)],
        help="Users to cover on top of the selected departments.")
    skip_covered = fields.Boolean(
        string='Skip Already Covered', default=True,
        help="Leave users who already have a profile untouched.")
    skip_admins = fields.Boolean(
        string='Skip Administrators', default=True,
        help="System administrators are exempt from profile restrictions "
             "anyway — covering them only adds noise.")

    preview_count = fields.Integer(compute='_compute_preview', string='Users To Cover')
    preview_text = fields.Text(compute='_compute_preview', string='Preview')
    uncovered_total = fields.Integer(compute='_compute_uncovered', string='Uncovered Users')

    @api.depends('template')
    def _compute_template_hint(self):
        for wizard in self:
            wizard.template_hint = _(TEMPLATE_HINTS.get(wizard.template, ''))

    def _compute_uncovered(self):
        for wizard in self:
            wizard.uncovered_total = len(wizard._uncovered_users())

    @api.model
    def _uncovered_users(self):
        """Internal, active users with no access profile at all."""
        users = self.env['res.users'].sudo().search(
            [('share', '=', False), ('active', '=', True)])
        return users.filtered(lambda u: not u.access_profile_ids)

    def _target_departments(self):
        self.ensure_one()
        departments = self.department_ids
        if self.include_children and departments:
            departments |= self.env['hr.department'].search(
                [('id', 'child_of', departments.ids)])
        return departments

    def _users_of(self, departments):
        """Internal users linked (through hr.employee) to `departments`."""
        if not departments:
            return self.env['res.users']
        employees = self.env['hr.employee'].sudo().search(
            [('department_id', 'in', departments.ids), ('user_id', '!=', False)])
        return employees.mapped('user_id').filtered(lambda u: not u.share)

    def _resolve_targets(self):
        """{department: users} for the selection, after the skip filters.
        Users with no department land under the key `False`."""
        self.ensure_one()
        departments = self._target_departments()
        admin_group = self.env.ref('base.group_system')

        def keep(user):
            if not user.active:
                return False
            if self.skip_covered and user.access_profile_ids:
                return False
            if self.skip_admins and admin_group in user.all_group_ids:
                return False
            return True

        result = {}
        for department in departments:
            users = self._users_of(department).filtered(keep)
            if users:
                result[department] = users

        extra = self.extra_user_ids.filtered(keep)
        if self.cover_all_uncovered:
            # everybody with no profile, grouped by their employee's department
            # when we know it, so each department keeps its own profile
            remaining = self._uncovered_users().filtered(keep)
            by_department = {}
            for employee in self.env['hr.employee'].sudo().search(
                    [('user_id', 'in', remaining.ids),
                     ('department_id', '!=', False)]):
                by_department.setdefault(employee.department_id, self.env['res.users'])
                by_department[employee.department_id] |= employee.user_id
            for department, users in by_department.items():
                result[department] = result.get(
                    department, self.env['res.users']) | users
                remaining -= users
            extra |= remaining

        # do not cover the same user twice
        already = self.env['res.users']
        for users in result.values():
            already |= users
        extra -= already
        if extra:
            result[self.env['hr.department']] = extra
        return result

    @api.depends('department_ids', 'include_children', 'extra_user_ids',
                 'skip_covered', 'skip_admins', 'cover_all_uncovered')
    def _compute_preview(self):
        for wizard in self:
            try:
                targets = wizard._resolve_targets()
            except Exception:
                wizard.preview_count = 0
                wizard.preview_text = ''
                continue
            lines = []
            total = 0
            for department, users in targets.items():
                total += len(users)
                lines.append("• %s — %s %s" % (
                    department.name or _("(no department)"),
                    len(users), _("user(s)")))
            wizard.preview_count = total
            wizard.preview_text = '\n'.join(lines) or _(
                "Nothing to do: pick departments (or extra users) that have "
                "uncovered users.")

    def _profile_vals(self, department, users):
        self.ensure_one()
        vals = {
            'department_id': department.id or False,
            'user_ids': [(6, 0, users.ids)],
        }
        if self.mode == 'template':
            label = _(TEMPLATE_LABELS[self.template])
            vals['name'] = ("%s — %s" % (department.name, label)
                            if department else label)
            vals.update(TEMPLATE_FLAGS[self.template])
        return vals

    def action_apply(self):
        self.ensure_one()
        if self.mode == 'existing' and not self.profile_id:
            raise UserError(_("Pick the existing profile to assign."))
        targets = self._resolve_targets()
        if not targets:
            raise UserError(_(
                "No user to cover. Check the selected departments — their "
                "employees must be linked to Odoo users."))

        Profile = self.env['access.rights.profile']
        created = Profile
        assigned_users = self.env['res.users']
        for department, users in targets.items():
            assigned_users |= users
            if self.mode == 'existing':
                self.profile_id.write({'user_ids': [(4, uid) for uid in users.ids]})
                continue
            existing = Profile.search([
                ('department_id', '=', department.id or False),
                ('name', '=', self._profile_vals(department, users)['name']),
            ], limit=1)
            if existing:
                existing.write({'user_ids': [(4, uid) for uid in users.ids]})
                created |= existing
            else:
                created |= Profile.create(self._profile_vals(department, users))

        message = _("%(users)s user(s) covered", users=len(assigned_users))
        if self.mode == 'template':
            message += _(" across %(profiles)s profile(s).", profiles=len(created))
            target_profiles = created
        else:
            message += "."
            target_profiles = self.profile_id
        _logger.info("Access rollout: %s", message)

        return {
            'type': 'ir.actions.act_window',
            'name': _("Rolled-Out Profiles"),
            'res_model': 'access.rights.profile',
            'view_mode': 'list,form' if len(target_profiles) != 1 else 'form',
            'res_id': target_profiles.id if len(target_profiles) == 1 else False,
            'domain': [('id', 'in', target_profiles.ids)],
        }

    def action_view_uncovered(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Users Without A Profile"),
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self._uncovered_users().ids)],
        }
