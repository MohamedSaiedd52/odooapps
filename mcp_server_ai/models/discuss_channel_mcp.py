# Part of MCP Server AI. See LICENSE for details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError

import json

try:
    import requests
except Exception:
    requests = None


class DiscussChannelMCP(models.Model):
    _inherit = "discuss.channel"

    is_mcp_ai_channel = fields.Boolean(
        string="MCP AI Channel",
        default=False,
        help="When enabled, messages posted here are answered by the MCP AI using Odoo data.",
    )

    @api.model
    def get_or_create_mcp_ai_channel(self):
        """Return the single MCP AI channel, create it if missing."""
        channel = self.search([("is_mcp_ai_channel", "=", True)], limit=1)
        if channel:
            return channel
        return self.sudo().create({
            "name": _("MCP AI"),
            "channel_type": "channel",
            "is_mcp_ai_channel": True,
        })

    def action_open_mcp_ai_discuss(self):
        """Open Discuss app with the MCP AI channel focused."""
        channel = self.get_or_create_mcp_ai_channel()
        return {
            "type": "ir.actions.client",
            "tag": "mail.action_discuss",
            "context": {"active_id": channel.id},
        }

    def message_post(self, *, message_type="notification", **kwargs):
        # First, let standard behaviour run
        res = super().message_post(message_type=message_type, **kwargs)

        # Avoid infinite recursion when we are posting the AI's own reply
        if self.env.context.get("mcp_ai_reply"):
            return res

        if not self.is_mcp_ai_channel or message_type != "comment":
            return res
        body = kwargs.get("body") or kwargs.get("message")
        if not body or not body.strip():
            return res
        reply = self._mcp_ai_reply_for_channel(body)
        if reply:
            bot_partner = self.env.ref("base.partner_root", raise_if_not_found=False) or self.env.user.partner_id
            # Post AI reply once, marking context to skip our own hook
            self.sudo().with_context(
                mail_create_nosubscribe=True,
                mcp_ai_reply=True,
            ).message_post(
                body=reply,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                author_id=bot_partner.id,
            )
        return res

    def _mcp_ai_reply_for_channel(self, user_message):
        """Call AI with channel message history and Odoo context; return reply text or empty."""
        if not requests:
            return _("(MCP AI: requests library not available)")
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("mcp_server_ai.ai_chat_enabled", "False") != "True":
            return _("(MCP AI chat is disabled in Settings > MCP Server)")
        base_url = (icp.get_param("mcp_server_ai.ai_chat_endpoint") or "").strip()
        api_key = (icp.get_param("mcp_server_ai.ai_chat_api_key") or "").strip()
        provider = (icp.get_param("mcp_server_ai.ai_chat_provider") or "openai").strip() or "openai"
        if not base_url or not api_key:
            return _("(MCP AI: endpoint or API key not configured)")
        # Odoo context
        odoo_ctx = self.env["mcp.chat.session"]._get_odoo_context_for_ai()
        system_prompt = _(
            "You are an AI assistant inside Odoo Discuss. Answer in the same language as the user. "
            "Use the Odoo data below to answer questions about the business data. "
            "Each section shows records from models the user has access to."
        )
        if odoo_ctx:
            system_prompt += "\n\n--- Odoo data ---\n" + odoo_ctx
        # Build history from last channel messages (comment only)
        messages = []
        try:
            last = self.env["mail.message"].search(
                [
                    ("model", "=", "discuss.channel"),
                    ("res_id", "=", self.id),
                    ("message_type", "=", "comment"),
                ],
                order="id desc",
                limit=20,
            )
            for msg in reversed(last):
                text = (msg.body or "").strip()
                if not text:
                    continue
                if msg.author_id == self.env.ref("base.partner_root", raise_if_not_found=False):
                    role = "model"
                else:
                    role = "user"
                messages.append({"role": role, "content": text})
        except Exception:
            messages = []
        if not messages:
            messages = [{"role": "user", "content": user_message}]
        # Call Gemini (same logic as mcp.chat.session) (same logic as mcp.chat.session)
        if provider != "gemini":
            return _("(MCP AI in Discuss is configured for Gemini only.)")
        base_url_strip = base_url.rstrip("/")
        url = base_url_strip + ":generateContent"
        contents = [{"role": "user", "parts": [{"text": system_prompt}]}]
        for m in messages:
            contents.append({
                "role": "user" if m["role"] == "user" else "model",
                "parts": [{"text": m["content"]}],
            })
        payload = {"contents": contents}
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(
                f"{url}?key={api_key}",
                headers=headers,
                data=json.dumps(payload),
                timeout=60,
            )
        except Exception as e:
            return _("(MCP AI error: %s)") % e
        if response.status_code == 404 and "v1beta" in base_url_strip:
            url_v1 = base_url_strip.replace("/v1beta/", "/v1/") + ":generateContent"
            response = requests.post(
                f"{url_v1}?key={api_key}",
                headers=headers,
                data=json.dumps(payload),
                timeout=60,
            )
        if response.status_code >= 400:
            return _("(AI error %s)") % response.status_code
        try:
            data = response.json()
        except Exception:
            return _("(Invalid AI response)")
        candidates = data.get("candidates") or []
        if not candidates:
            return _("(No reply from AI)")
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            return _("(No reply from AI)")
        return (parts[0].get("text") or "").strip()
