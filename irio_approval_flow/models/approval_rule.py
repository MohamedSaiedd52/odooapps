# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class IrioApprovalRule(models.Model):
    _name = "irio.approval.rule"
    _description = "Approval Rule"
    # highest min_amount first so the most specific rule wins during matching
    _order = "model_apply, min_amount desc, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    model_apply = fields.Selection([
        ("sale.order", "Sales Order"),
        ("purchase.order", "Purchase Order"),
        ("account.move", "Invoice / Bill"),
        ("stock.picking", "Stock Transfer"),
    ], string="Applies To", required=True)
    min_amount = fields.Monetary(
        string="Minimum Amount",
        help="Documents with a total (in company currency) at or above this "
             "amount require approval under this rule.")
    max_amount = fields.Monetary(
        string="Maximum Amount",
        help="Upper bound of this rule. 0 means no upper limit.")
    level_ids = fields.One2many(
        "irio.approval.rule.level", "rule_id", string="Approval Levels",
        copy=True)
    level_count = fields.Integer(compute="_compute_level_count")

    @api.depends("level_ids")
    def _compute_level_count(self):
        for rule in self:
            rule.level_count = len(rule.level_ids)

    @api.constrains("min_amount", "max_amount")
    def _check_amounts(self):
        for rule in self:
            if rule.min_amount < 0 or rule.max_amount < 0:
                raise ValidationError(_("Amounts cannot be negative."))
            if rule.max_amount and rule.max_amount < rule.min_amount:
                raise ValidationError(
                    _("Maximum amount must be 0 (no limit) or greater than "
                      "the minimum amount."))

    @api.constrains("level_ids")
    def _check_levels(self):
        for rule in self:
            if not rule.level_ids:
                raise ValidationError(
                    _("Rule '%s' needs at least one approval level.") % rule.name)


class IrioApprovalRuleLevel(models.Model):
    _name = "irio.approval.rule.level"
    _description = "Approval Rule Level"
    _order = "sequence, id"

    rule_id = fields.Many2one(
        "irio.approval.rule", required=True, ondelete="cascade")
    sequence = fields.Integer(default=1)
    name = fields.Char(string="Level Name", required=True)
    user_ids = fields.Many2many(
        "res.users", "irio_approval_level_user_rel", string="Approvers")
    min_approvals = fields.Integer(
        string="Required Approvals", default=1,
        help="How many of the approvers must approve before this level is "
             "complete (any-of quorum).")
    escalate_days = fields.Integer(
        string="Escalate After (Days)", default=3,
        help="If the level is still pending after this many days, approvers "
             "are reminded and the next level gets a heads-up.")

    @api.constrains("user_ids", "min_approvals")
    def _check_quorum(self):
        for level in self:
            if not level.user_ids:
                raise ValidationError(
                    _("Level '%s' needs at least one approver.") % level.name)
            if not (1 <= level.min_approvals <= len(level.user_ids)):
                raise ValidationError(
                    _("Level '%s': required approvals must be between 1 and "
                      "the number of approvers.") % level.name)
