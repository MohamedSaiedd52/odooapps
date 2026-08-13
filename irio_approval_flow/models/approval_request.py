# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class IrioApprovalRequest(models.Model):
    _name = "irio.approval.request"
    _description = "Approval Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    # approvers only need READ access to comment/approve via the buttons
    _mail_post_access = "read"

    name = fields.Char(default=lambda self: _("New"), copy=False, readonly=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    res_model = fields.Char(string="Document Model", readonly=True, required=True)
    res_id = fields.Integer(string="Document ID", readonly=True, required=True)
    document_ref = fields.Char(string="Document", readonly=True)
    amount = fields.Monetary(string="Amount (Company Currency)", readonly=True)
    rule_id = fields.Many2one("irio.approval.rule", string="Rule", readonly=True)
    requester_id = fields.Many2one(
        "res.users", string="Requested By", readonly=True,
        default=lambda self: self.env.user)
    state = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ], default="pending", tracking=True, copy=False)
    step_ids = fields.One2many("irio.approval.step", "request_id", string="Levels")
    current_step_id = fields.Many2one(
        "irio.approval.step", compute="_compute_current", store=True)
    current_approver_ids = fields.Many2many(
        "res.users", "irio_approval_request_waiting_rel", string="Waiting On",
        compute="_compute_current", store=True)
    can_user_approve = fields.Boolean(compute="_compute_can_user_approve")

    # ------------------------------------------------------------------
    # computes
    # ------------------------------------------------------------------
    @api.depends("step_ids.status", "step_ids.approver_ids", "state")
    def _compute_current(self):
        for req in self:
            step = req.step_ids.filtered(
                lambda s: s.status == "pending").sorted("sequence")[:1]
            req.current_step_id = step
            req.current_approver_ids = (
                (step.approver_ids - step.approved_user_ids)
                if step and req.state == "pending" else False)

    @api.depends_context("uid")
    @api.depends("current_step_id", "state")
    def _compute_can_user_approve(self):
        for req in self:
            req.can_user_approve = bool(req._approval_slots_for(self.env.user))

    def _approval_slots_for(self, user):
        """Users whose approval slot `user` may fill on the current step:
        themselves, plus anyone who delegated to them (vacation mode)."""
        self.ensure_one()
        step = self.current_step_id
        if self.state != "pending" or not step:
            return self.env["res.users"]
        remaining = step.approver_ids - step.approved_user_ids
        slots = self.env["res.users"]
        if user in remaining:
            slots |= user
        today = fields.Date.context_today(self)
        delegations = self.env["irio.approval.delegation"].sudo().search([
            ("delegate_id", "=", user.id),
            ("date_from", "<=", today),
            ("date_to", ">=", today),
            ("user_id", "in", remaining.ids),
        ])
        slots |= delegations.mapped("user_id") & remaining
        return slots

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = (self.env["ir.sequence"].sudo()
                                .next_by_code("irio.approval.request") or "IRA/new")
        return super().create(vals_list)

    def _start_step(self, step):
        """Arm a level: set its escalation deadline and notify its approvers."""
        self.ensure_one()
        deadline = fields.Date.context_today(self) + timedelta(
            days=max(step.escalate_days, 0))
        step.sudo().write({"deadline": deadline})
        # scheduling an activity subscribes its assignee (needs write on the
        # request) - approvers may only have read access, so go through sudo
        for user in step.approver_ids:
            self.sudo().activity_schedule(
                "mail.mail_activity_data_todo", user_id=user.id,
                summary=_("Approve %s") % (self.document_ref or self.name),
                date_deadline=deadline)
        self.message_post(body=_(
            "Level '%(level)s' started. Waiting on: %(users)s.",
            level=step.name, users=", ".join(step.approver_ids.mapped("name"))))

    def action_approve(self):
        for req in self:
            req._do_approve(self.env.user)
        return True

    def _do_approve(self, user):
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("Request %s is not pending.") % self.name)
        slots = self._approval_slots_for(user)
        if not slots:
            raise UserError(_(
                "You are not an eligible approver for the current level of %s.")
                % self.name)
        step = self.current_step_id
        slot = user if user in slots else slots[:1]
        step.sudo().write({"approved_user_ids": [(4, slot.id)]})
        if slot == user:
            self.message_post(body=_(
                "%(level)s: approved by %(user)s.",
                level=step.name, user=user.name))
        else:
            self.message_post(body=_(
                "%(level)s: approved by %(actor)s on behalf of %(slot)s "
                "(delegation).", level=step.name, actor=user.name,
                slot=slot.name))
        if len(step.approved_user_ids) >= step.min_approvals:
            step.sudo().write({"status": "approved"})
            self.sudo().activity_unlink(["mail.mail_activity_data_todo"])
            next_step = self.step_ids.filtered(
                lambda s: s.status == "pending").sorted("sequence")[:1]
            if next_step:
                self._start_step(next_step)
            else:
                self.sudo().write({"state": "approved"})
                self.message_post(
                    body=_("Request approved. The document can now proceed."),
                    partner_ids=self.requester_id.partner_id.ids)
                self._notify_document(_(
                    "Approval request %s APPROVED.") % self.name)

    def action_reject(self):
        for req in self:
            if req.state != "pending":
                raise UserError(_("Request %s is not pending.") % req.name)
            if not req._approval_slots_for(self.env.user):
                raise UserError(_(
                    "You are not an eligible approver for the current level "
                    "of %s.") % req.name)
            step = req.current_step_id
            step.sudo().write({"status": "rejected"})
            req.sudo().write({"state": "rejected"})
            req.sudo().activity_unlink(["mail.mail_activity_data_todo"])
            req.message_post(
                body=_("%(level)s: REJECTED by %(user)s.",
                       level=step.name, user=self.env.user.name),
                partner_ids=req.requester_id.partner_id.ids)
            req._notify_document(_(
                "Approval request %s was REJECTED.") % req.name)
        return True

    def action_cancel(self):
        for req in self:
            if req.state != "pending":
                raise UserError(_("Only pending requests can be cancelled."))
            if (self.env.user != req.requester_id
                    and not self.env.user.has_group(
                        "irio_approval_flow.group_approval_manager")):
                raise UserError(_(
                    "Only the requester or an Approval Manager can cancel."))
            req.sudo().write({"state": "cancelled"})
            req.sudo().activity_unlink(["mail.mail_activity_data_todo"])
            req.message_post(body=_("Request cancelled by %s.")
                             % self.env.user.name)
        return True

    def action_open_document(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    def _notify_document(self, body):
        self.ensure_one()
        doc = self.env[self.res_model].sudo().browse(self.res_id)
        if doc.exists() and hasattr(doc, "message_post"):
            doc.message_post(body=body)

    # ------------------------------------------------------------------
    # escalation cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_escalate(self):
        today = fields.Date.context_today(self)
        for req in self.search([("state", "=", "pending")]):
            step = req.current_step_id
            if not step or not step.deadline or step.deadline >= today \
                    or step.escalated:
                continue
            step.sudo().write({"escalated": True})
            waiting = step.approver_ids - step.approved_user_ids
            for user in waiting:
                req.sudo().activity_schedule(
                    "mail.mail_activity_data_todo", user_id=user.id,
                    summary=_("OVERDUE: approve %s")
                    % (req.document_ref or req.name),
                    date_deadline=today)
            req.message_post(body=_(
                "Level '%(level)s' is overdue (deadline %(dl)s). Waiting on: "
                "%(users)s.", level=step.name, dl=step.deadline,
                users=", ".join(waiting.mapped("name"))))
            next_step = req.step_ids.filtered(
                lambda s: s.status == "pending" and s.id != step.id
            ).sorted("sequence")[:1]
            if next_step:
                req.message_post(
                    partner_ids=next_step.approver_ids.partner_id.ids,
                    body=_("Heads-up: level '%(cur)s' of %(req)s is overdue; "
                           "your level '%(nxt)s' is next.",
                           cur=step.name, req=req.name, nxt=next_step.name))


class IrioApprovalStep(models.Model):
    _name = "irio.approval.step"
    _description = "Approval Step"
    _order = "sequence, id"

    request_id = fields.Many2one(
        "irio.approval.request", required=True, ondelete="cascade")
    sequence = fields.Integer(default=1)
    name = fields.Char(string="Level", required=True)
    approver_ids = fields.Many2many(
        "res.users", "irio_approval_step_user_rel", string="Approvers")
    approved_user_ids = fields.Many2many(
        "res.users", "irio_approval_step_done_rel", string="Approved By")
    min_approvals = fields.Integer(default=1)
    escalate_days = fields.Integer(default=3)
    status = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ], default="pending")
    deadline = fields.Date()
    escalated = fields.Boolean()
