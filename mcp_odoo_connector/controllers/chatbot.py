# Part of MCP Server AI. See LICENSE for details.

import json
import logging

from odoo import _, http, release
from odoo.http import request

_logger = logging.getLogger(__name__)

# Odoo 19 renamed route type 'json' to 'jsonrpc'
JSON_ROUTE_TYPE = "jsonrpc" if release.version_info[0] >= 19 else "json"

try:
    import requests as py_requests
except Exception:
    py_requests = None


class MCPChatbotController(http.Controller):
    """JSON-RPC controller for the OWL chatbot widget."""

    @http.route("/mcp/chatbot/send", type=JSON_ROUTE_TYPE, auth="user", methods=["POST"])
    def chatbot_send(self, message="", session_id=None):
        """Receive a user message, call AI with full context, return the reply."""
        user = request.env.user
        content = (message or "").strip()
        if not content:
            return {"success": False, "error": "الرسالة فارغة."}

        # Check MCP group
        if not (
            user.has_group("mcp_odoo_connector.group_mcp_user")
            or user.has_group("mcp_odoo_connector.group_mcp_admin")
        ):
            return {"success": False, "error": "ليس لديك صلاحية الوصول."}

        # Check AI chat enabled
        icp = request.env["ir.config_parameter"].sudo()
        if icp.get_param("mcp_odoo_connector.ai_chat_enabled", "False") != "True":
            return {
                "success": False,
                "error": "الشات غير مفعل. فعّله من الإعدادات > MCP Server.",
            }

        # Get or create session
        Session = request.env["mcp.chat.session"]
        if session_id:
            session = Session.browse(int(session_id)).exists()
            if not session or session.user_id.id != user.id:
                session = Session.create({"name": content[:50]})
        else:
            session = Session.create({"name": content[:50]})

        # Store user message
        request.env["mcp.chat.message"].create(
            {"session_id": session.id, "role": "user", "content": content}
        )

        # Build context and call AI
        try:
            reply = self._call_ai(session, content)
        except Exception as e:
            _logger.exception("MCP Chatbot AI error")
            reply = f"⚠️ خطأ: {e}"

        # Store AI reply
        request.env["mcp.chat.message"].create(
            {
                "session_id": session.id,
                "role": "assistant",
                "content": reply or _("(بدون رد)"),
            }
        )

        return {"success": True, "reply": reply, "session_id": session.id}

    def _call_ai(self, session, user_message):
        """Call the configured AI provider with conversation history + Odoo context."""
        if py_requests is None:
            return _("مكتبة requests غير متاحة على الخادم.")

        icp = request.env["ir.config_parameter"].sudo()
        base_url = (icp.get_param("mcp_odoo_connector.ai_chat_endpoint") or "").strip()
        api_key = (icp.get_param("mcp_odoo_connector.ai_chat_api_key") or "").strip()
        model = (icp.get_param("mcp_odoo_connector.ai_chat_model") or "").strip()
        provider = (
            (icp.get_param("mcp_odoo_connector.ai_chat_provider") or "openai").strip()
            or "openai"
        )

        if not base_url:
            return _("لم يتم تكوين عنوان AI endpoint في الإعدادات.")

        # Build Odoo data context
        odoo_context = session._get_odoo_context_for_ai()
        tools = session._get_available_tools_for_ai()
        system_prompt = _(
            "You are an AI assistant inside an Odoo ERP system. "
            "Answer in the same language as the user. "
            "You can READ, CREATE, UPDATE, and DELETE records using the tools provided. "
            "You can also call workflow methods (confirm orders, create invoices, etc.) using odoo_call_method. "
            "Use the Odoo data below as context, and use the tools to perform any operations the user requests. "
            "When the user asks to create, modify, or delete a record, USE THE APPROPRIATE TOOL — do not refuse. "
            "For sale orders: create the order header on sale.order, then add lines on sale.order.line with order_id, product_id, product_uom_qty, and price_unit. "
            "To confirm an order use odoo_call_method with method='action_confirm'. "
            "After performing an operation, confirm what was done with the record ID."
        )
        if odoo_context:
            system_prompt += "\n\n--- Odoo Data ---\n" + odoo_context
        else:
            system_prompt += (
                "\n\n(No cached Odoo data. Use the odoo_search tool if you need to look up data.)"
            )

        # Build conversation history
        history_msgs = session.message_ids.sorted(key=lambda m: m.create_date)

        # ---------- Provider: Ollama ----------
        if provider == "ollama":
            return self._call_ollama(
                session, base_url, model, system_prompt, history_msgs, tools
            )

        # ---------- Provider: Gemini ----------
        if provider == "gemini":
            return self._call_gemini(
                session, base_url, api_key, system_prompt, history_msgs, tools
            )

        # ---------- Provider: OpenAI-compatible ----------
        return self._call_openai(
            session, base_url, api_key, model, system_prompt, history_msgs, tools
        )

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _call_openai(self, session, base_url, api_key, model, system_prompt, history, tools):
        url = base_url.rstrip("/")
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            if msg.role not in ("user", "assistant"):
                continue
            messages.append({"role": msg.role, "content": msg.content or ""})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        MAX_TOOL_ROUNDS = 5
        for _round in range(MAX_TOOL_ROUNDS):
            payload = {"model": model or "gpt-4o-mini", "messages": messages}
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            resp = py_requests.post(
                url, headers=headers, data=json.dumps(payload), timeout=120
            )
            if resp.status_code >= 400:
                return f"خطأ من مزود AI ({resp.status_code}): {resp.text[:300]}"

            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return data.get("reply", "") or ""

            msg_obj = choices[0].get("message") or {}
            finish_reason = choices[0].get("finish_reason", "")

            tool_calls = msg_obj.get("tool_calls")
            if tool_calls and finish_reason in ("tool_calls", "stop", ""):
                messages.append(msg_obj)
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    tool_args = fn.get("arguments", "{}")
                    _logger.info("MCP Chatbot: executing tool %s", tool_name)
                    result = session._execute_tool_call(tool_name, tool_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result,
                    })
                continue

            return (msg_obj.get("content") or "").strip()

        return "تم الوصول للحد الأقصى من استدعاءات الأدوات. حاول طلب أبسط."

    def _call_gemini(self, session, base_url, api_key, system_prompt, history, tools):
        base_url_strip = base_url.rstrip("/")
        url = base_url_strip + ":generateContent"

        contents = [{"role": "user", "parts": [{"text": system_prompt}]}]
        for msg in history:
            if not msg.content:
                continue
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        # Convert to Gemini tool format
        gemini_tools = []
        if tools:
            fn_declarations = []
            for t in tools:
                fn = t.get("function", {})
                fn_declarations.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                })
            gemini_tools = [{"functionDeclarations": fn_declarations}]

        headers = {"Content-Type": "application/json"}

        MAX_TOOL_ROUNDS = 5
        for _round in range(MAX_TOOL_ROUNDS):
            payload = {"contents": contents}
            if gemini_tools:
                payload["tools"] = gemini_tools

            resp = py_requests.post(
                f"{url}?key={api_key}",
                headers=headers,
                data=json.dumps(payload),
                timeout=120,
            )
            # Retry v1 if v1beta 404
            if resp.status_code == 404 and "v1beta" in base_url_strip:
                url_v1 = base_url_strip.replace("/v1beta/", "/v1/") + ":generateContent"
                resp = py_requests.post(
                    f"{url_v1}?key={api_key}",
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=120,
                )
            if resp.status_code >= 400:
                return f"خطأ Gemini ({resp.status_code}): {resp.text[:300]}"

            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return ""

            content_obj = candidates[0].get("content", {})
            parts = content_obj.get("parts") or []

            has_function_call = any("functionCall" in p for p in parts)
            if has_function_call:
                contents.append({"role": "model", "parts": parts})
                fn_response_parts = []
                for p in parts:
                    fc = p.get("functionCall")
                    if fc:
                        tool_name = fc.get("name", "")
                        tool_args = fc.get("args", {})
                        _logger.info("MCP Chatbot Gemini: executing tool %s", tool_name)
                        result_str = session._execute_tool_call(tool_name, tool_args)
                        try:
                            result_obj = json.loads(result_str)
                        except Exception:
                            result_obj = {"result": result_str}
                        fn_response_parts.append({
                            "functionResponse": {
                                "name": tool_name,
                                "response": result_obj,
                            }
                        })
                contents.append({"role": "user", "parts": fn_response_parts})
                continue

            for p in parts:
                text = p.get("text")
                if text:
                    return text.strip()
            return ""

        return "تم الوصول للحد الأقصى من استدعاءات الأدوات."

    def _call_ollama(self, session, base_url, model, system_prompt, history, tools):
        """Call local Ollama server with tool support."""
        url = base_url.rstrip("/")
        if "/v1/" not in url and "/api/" not in url:
            url = url + "/api/chat"

        # Truncate for small models
        MAX_PROMPT_CHARS = 4000
        if len(system_prompt) > MAX_PROMPT_CHARS:
            marker = "--- Odoo Data ---"
            if marker in system_prompt:
                idx = system_prompt.index(marker)
                instruction_part = system_prompt[: idx + len(marker) + 1]
                data_part = system_prompt[idx + len(marker) + 1 :]
                available = MAX_PROMPT_CHARS - len(instruction_part)
                if available > 200:
                    system_prompt = (
                        instruction_part
                        + data_part[:available]
                        + "\n... (data truncated for performance)"
                    )
                else:
                    system_prompt = system_prompt[:MAX_PROMPT_CHARS]
            else:
                system_prompt = system_prompt[:MAX_PROMPT_CHARS]

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            if msg.role not in ("user", "assistant"):
                continue
            messages.append({"role": msg.role, "content": msg.content or ""})

        headers = {"Content-Type": "application/json"}
        ollama_tools = tools if tools else None

        MAX_TOOL_ROUNDS = 5
        for _round in range(MAX_TOOL_ROUNDS):
            payload = {
                "model": model or "llama3",
                "messages": messages,
                "stream": False,
            }
            if ollama_tools:
                payload["tools"] = ollama_tools

            _logger.info(
                "MCP Chatbot Ollama: POST %s (model=%s, messages=%d, round=%d)",
                url, model, len(messages), _round,
            )

            try:
                resp = py_requests.post(
                    url, headers=headers, data=json.dumps(payload), timeout=600
                )
            except py_requests.exceptions.Timeout:
                return (
                    "⚠️ Ollama timeout — الموديل أخذ وقت طويل.\n"
                    "جرب موديل أصغر أو قلل عدد الموديلات في Model Access."
                )
            except Exception as e:
                return f"⚠️ تعذر الاتصال بـ Ollama على {url}. تأكد أنه يعمل.\nخطأ: {e}"

            if resp.status_code >= 400:
                return f"خطأ Ollama ({resp.status_code}): {resp.text[:300]}"

            data = resp.json()
            msg_obj = data.get("message", {})
            tool_calls = msg_obj.get("tool_calls")

            if tool_calls:
                messages.append(msg_obj)
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    tool_args = fn.get("arguments", {})
                    _logger.info("MCP Chatbot Ollama: executing tool %s", tool_name)
                    result = session._execute_tool_call(tool_name, tool_args)
                    messages.append({"role": "tool", "content": result})
                continue

            content = (msg_obj.get("content") or "").strip()
            if content:
                return content

            choices = data.get("choices") or []
            if choices:
                return (choices[0].get("message", {}).get("content") or "").strip()
            return data.get("response", "") or ""

        return "تم الوصول للحد الأقصى من استدعاءات الأدوات."
