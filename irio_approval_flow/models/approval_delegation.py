# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class IrioApprovalDelegation(models.Model):
    _name = "irio.approval.delegation"
    _description = "Approval Delegation (Vacation Mode)"
    _order = "date_from desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one(
        "res.users", string="Approver (Away)", required=True,
        default=lambda self: self.env.user)
    delegate_id = fields.Many2one(
        "res.users", string="Delegate To", required=True)
    date_from = fields.Date(
        required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True)

    @api.depends("user_id", "delegate_id", "date_from", "date_to")
    def _compute_name(self):
        for d in self:
            d.name = _("%(user)s delegates to %(delegate)s",
                       user=d.user_id.name or "?",
                       delegate=d.delegate_id.name or "?")

    @api.constrains("date_from", "date_to", "user_id", "delegate_id")
    def _check_delegation(self):
        for d in self:
            if d.date_to < d.date_from:
                raise ValidationError(_("End date must be after start date."))
            if d.user_id == d.delegate_id:
                raise ValidationError(_("You cannot delegate to yourself."))
