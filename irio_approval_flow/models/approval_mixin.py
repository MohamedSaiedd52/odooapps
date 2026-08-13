# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class IrioApprovalMixin(models.AbstractModel):
    """Plug amount-based approval control into any business document.

    Concrete models may override `_irio_approval_amount()` (company-currency
    total used for rule matching). The blocking entry point is
    `_irio_check_approval()`, called from the document's confirm/post/validate
    method BEFORE super(). It never creates records: a UserError would roll
    such a request back, so submission is a separate explicit button.
    """
    _name = "irio.approval.mixin"
    _description = "Approval Mixin"

    irio_approval_request_id = fields.Many2one(
        "irio.approval.request", string="Approval Request", copy=False,
        readonly=True)
    irio_approval_state = fields.Selection(
        related="irio_approval_request_id.state", string="Approval Status")
    irio_needs_approval = fields.Boolean(
        compute="_compute_irio_needs_approval")

    @api.depends("irio_approval_request_id")
    def _compute_irio_needs_approval(self):
        for rec in self:
            has_open_request = rec.irio_approval_request_id and \
                rec.irio_approval_request_id.state in ("pending", "approved")
            rec.irio_needs_approval = (
                not has_open_request and bool(rec._irio_find_rule()))

    def _irio_approval_amount(self):
        """Document total converted to company currency."""
        self.ensure_one()
        amount = self.amount_total
        currency = getattr(self, "currency_id", False)
        company_currency = self.company_id.currency_id
        if currency and currency != company_currency:
            amount = currency._convert(
                amount, company_currency, self.company_id,
                fields.Date.context_today(self))
        return amount

    def _irio_find_rule(self):
        self.ensure_one()
        amount = self._irio_approval_amount()
        rules = self.env["irio.approval.rule"].sudo().search([
            ("model_apply", "=", self._name),
            ("company_id", "=", self.company_id.id),
        ])  # ordered min_amount desc -> first match is the most specific
        for rule in rules:
            if amount >= rule.min_amount and (
                    not rule.max_amount or amount <= rule.max_amount):
                return rule
        return self.env["irio.approval.rule"]

    def action_irio_request_approval(self):
        for rec in self:
            existing = rec.irio_approval_request_id
            if existing and existing.state in ("pending", "approved"):
                raise UserError(_(
                    "'%(doc)s' already has approval request %(req)s (%(state)s).",
                    doc=rec.display_name, req=existing.name,
                    state=existing.state))
            rule = rec._irio_find_rule()
            if not rule:
                raise UserError(_(
                    "No approval rule matches '%s'.") % rec.display_name)
            request = self.env["irio.approval.request"].sudo().create({
                "company_id": rec.company_id.id,
                "res_model": rec._name,
                "res_id": rec.id,
                "document_ref": rec.display_name,
                "amount": rec._irio_approval_amount(),
                "rule_id": rule.id,
                "requester_id": self.env.uid,
                "step_ids": [(0, 0, {
                    "sequence": level.sequence,
                    "name": level.name,
                    "approver_ids": [(6, 0, level.user_ids.ids)],
                    "min_approvals": level.min_approvals,
                    "escalate_days": level.escalate_days,
                }) for level in rule.level_ids],
            })
            rec.write({"irio_approval_request_id": request.id})
            first_step = request.step_ids.sorted("sequence")[:1]
            if first_step:
                request._start_step(first_step)
            if hasattr(rec, "message_post"):
                rec.message_post(body=_(
                    "Approval request %(req)s submitted (rule '%(rule)s', "
                    "amount %(amount).2f).", req=request.name, rule=rule.name,
                    amount=request.amount))
        return True

    def _irio_check_approval(self):
        for rec in self:
            request = rec.irio_approval_request_id
            if request and request.state == "approved":
                continue
            if request and request.state == "pending":
                raise UserError(_(
                    "'%(doc)s' is waiting for approval (%(req)s). It can "
                    "proceed once the request is approved.",
                    doc=rec.display_name, req=request.name))
            if request and request.state in ("rejected", "cancelled"):
                raise UserError(_(
                    "Approval request %(req)s for '%(doc)s' was %(state)s. "
                    "Submit a new approval request first.",
                    req=request.name, doc=rec.display_name,
                    state=request.state))
            rule = rec._irio_find_rule()
            if rule:
                raise UserError(_(
                    "'%(doc)s' requires approval (rule '%(rule)s'). Click "
                    "'Submit for Approval' first.",
                    doc=rec.display_name, rule=rule.name))
