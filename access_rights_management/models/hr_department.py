# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrDepartment(models.Model):
    """Reuse the real company departments (hr.department) to group access
    roles: a role (access profile) belongs to the department of the job it
    represents. No separate department list is maintained by this app."""
    _inherit = 'hr.department'

    arm_icon = fields.Char(
        string='Access Icon', default='fa-building',
        help="Font Awesome 4 icon class shown on the Access Rights dashboard "
             "card, e.g. fa-calculator, fa-cubes, fa-users.")
    access_profile_ids = fields.One2many(
        'access.rights.profile', 'department_id', string='Access Roles',
        help="The access profiles (roles) belonging to this department, "
             "e.g. Accounting Manager, Accountant, Auditor.")

    arm_profile_count = fields.Integer(
        compute='_compute_arm_counts', string='Role Count')
    arm_user_count = fields.Integer(
        compute='_compute_arm_counts', string='Access Users')
    arm_rule_count = fields.Integer(
        compute='_compute_arm_counts', string='Access Rules')

    @api.depends('access_profile_ids', 'access_profile_ids.user_ids',
                 'access_profile_ids.hide_menu_ids',
                 'access_profile_ids.model_line_ids',
                 'access_profile_ids.field_line_ids',
                 'access_profile_ids.domain_line_ids',
                 'access_profile_ids.node_line_ids',
                 'access_profile_ids.search_line_ids',
                 'access_profile_ids.chatter_line_ids')
    def _compute_arm_counts(self):
        for department in self:
            profiles = department.access_profile_ids
            department.arm_profile_count = len(profiles)
            # recordset union: a user holding several roles is counted once
            department.arm_user_count = len(profiles.user_ids)
            department.arm_rule_count = sum(profiles.mapped('total_rules'))

    def action_view_access_profiles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("%s — Access Roles", self.name),
            'res_model': 'access.rights.profile',
            'view_mode': 'tree,form',
            'domain': [('department_id', '=', self.id)],
            'context': {'default_department_id': self.id},
        }

    def action_create_access_profile(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("New Role"),
            'res_model': 'access.rights.profile',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_department_id': self.id},
        }
