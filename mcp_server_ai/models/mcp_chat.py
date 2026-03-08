from odoo import _, api, fields, models
from odoo.exceptions import UserError

import json
import logging

try:
    import requests
except Exception:  # pragma: no cover - requests is part of Odoo deps in practice
    requests = None


_logger = logging.getLogger(__name__)


class MCPChatSession(models.Model):
    _name = "mcp.chat.session"
    _description = "MCP AI Chat Session"
    _order = "create_date desc"

    name = fields.Char(string="Title", default=lambda self: _("New Chat"), required=True)
    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )
    message_ids = fields.One2many(
        "mcp.chat.message",
        "session_id",
        string="Messages",
        readonly=True,
    )
    user_input = fields.Text(string="Your Message")

    def action_send(self):
        """Send user_input to the configured AI provider and store the reply."""
        for session in self:
            content = (session.user_input or "").strip()
            if not content:
                continue

            self.env["mcp.chat.message"].create(
                {
                    "session_id": session.id,
                    "role": "user",
                    "content": content,
                }
            )

            reply = session._call_ai_with_history()

            self.env["mcp.chat.message"].create(
                {
                    "session_id": session.id,
                    "role": "assistant",
                    "content": reply or _("(No reply from AI)"),
                }
            )

            session.user_input = False

        return True

    def _get_odoo_context_for_ai(self):
        """Dynamically fetch Odoo data from all models configured in MCP Model Access.

        Includes:
        - Record data with ALL fields (including financial: amount_total, price_unit, etc.)
        - Aggregation summaries (totals, counts) via read_group for numeric fields
        - Time-based context (current month counts/totals)

        Respects read_access, allowed_fields, and group_ids permissions.
        """
        from odoo import fields as odoo_fields

        MAX_MODELS = 10
        MAX_RECORDS_PER_MODEL = 20
        MAX_TOTAL_CHARS = 12000

        user = self.env.user
        access_records = self.env["mcp.model.access"].sudo().search(
            [("active", "=", True), ("read_access", "=", True)],
            limit=MAX_MODELS,
        )

        sections = []
        total_chars = 0

        # Get current month start for time-based queries
        try:
            today = odoo_fields.Date.context_today(self)
            month_start = today.replace(day=1)
        except Exception:
            today = None
            month_start = None

        for acc in access_records:
            if not acc.check_user_groups(user):
                continue

            model_name = acc.model_name
            if not model_name:
                continue

            try:
                model_obj = self.env[model_name]
            except KeyError:
                continue

            # Determine fields to read
            allowed_fields = acc.get_allowed_fields_list()
            if not allowed_fields:
                try:
                    fields_info = model_obj.fields_get(
                        attributes=["type", "store"]
                    )
                    allowed_fields = [
                        fname
                        for fname, finfo in fields_info.items()
                        if finfo.get("store", True)
                        and finfo.get("type")
                        not in ("binary", "image", "one2many", "many2many")
                        and fname
                        not in (
                            "__last_update",
                            "write_uid",
                            "write_date",
                            "create_uid",
                            "create_date",
                            "message_ids",
                            "activity_ids",
                        )
                    ]
                except Exception:
                    allowed_fields = ["name"]

            for key_field in ("id", "name", "display_name"):
                if key_field not in allowed_fields:
                    allowed_fields.append(key_field)

            read_fields = allowed_fields[:20]

            # ---- Fetch records ----
            try:
                records = model_obj.search_read(
                    [], fields=read_fields, limit=MAX_RECORDS_PER_MODEL
                )
                total_count = model_obj.search_count([])
            except Exception:
                continue

            if not records:
                continue

            model_label = acc.model_id.name or model_name
            lines = [
                f"=== {model_label} ({model_name}) — showing {len(records)}/{total_count} records ==="
            ]

            for rec in records:
                parts = []
                for f in read_fields:
                    val = rec.get(f)
                    if val is None or val is False:
                        continue
                    if isinstance(val, (list, tuple)) and len(val) == 2:
                        val = val[1]
                    # Truncate very long string values
                    if isinstance(val, str) and len(val) > 100:
                        val = val[:100] + "..."
                    parts.append(f"{f}={val}")
                if parts:
                    lines.append("  - " + ", ".join(parts))

            # ---- Aggregation summaries for numeric fields ----
            try:
                fields_info = model_obj.fields_get(attributes=["type", "store"])
                numeric_fields = [
                    fname
                    for fname, finfo in fields_info.items()
                    if finfo.get("type") in ("float", "integer", "monetary")
                    and finfo.get("store", True)
                    and fname in read_fields
                ]

                if numeric_fields:
                    # Overall aggregation
                    agg_data = model_obj.read_group(
                        [], numeric_fields, [], lazy=False
                    )
                    if agg_data:
                        agg = agg_data[0]
                        agg_parts = []
                        for nf in numeric_fields:
                            val = agg.get(nf)
                            if val:
                                agg_parts.append(f"{nf}_total={val}")
                        agg_parts.append(f"total_count={agg.get('__count', total_count)}")
                        if agg_parts:
                            lines.append("  [TOTALS] " + ", ".join(agg_parts))

                    # Time-based: current month aggregation
                    if month_start:
                        date_fields = [
                            fname
                            for fname, finfo in fields_info.items()
                            if finfo.get("type") in ("date", "datetime")
                            and finfo.get("store", True)
                            and fname in read_fields
                        ]
                        for df in date_fields[:1]:  # Use first date field
                            try:
                                month_agg = model_obj.read_group(
                                    [(df, ">=", month_start)],
                                    numeric_fields,
                                    [],
                                    lazy=False,
                                )
                                if month_agg and month_agg[0].get("__count", 0) > 0:
                                    magg = month_agg[0]
                                    m_parts = [
                                        f"month_count={magg.get('__count', 0)}"
                                    ]
                                    for nf in numeric_fields:
                                        val = magg.get(nf)
                                        if val:
                                            m_parts.append(
                                                f"{nf}_this_month={val}"
                                            )
                                    lines.append(
                                        f"  [THIS MONTH since {month_start}] "
                                        + ", ".join(m_parts)
                                    )
                            except Exception:
                                pass
            except Exception:
                pass

            section_text = "\n".join(lines)

            if total_chars + len(section_text) > MAX_TOTAL_CHARS:
                break

            sections.append(section_text)
            total_chars += len(section_text)

        if not sections:
            return ""
        return "\n\n".join(sections)

    # ----------------------------------------------------------------
    # AI Function-Calling: tool definitions + execution
    # ----------------------------------------------------------------

    def _get_available_tools_for_ai(self):
        """Return OpenAI-style function/tool definitions based on MCP Model Access.

        Only includes operations the user has permission for.
        """
        user = self.env.user
        access_records = self.env["mcp.model.access"].sudo().search(
            [("active", "=", True)], limit=20,
        )

        has_create = False
        has_write = False
        has_delete = False
        has_read = False
        model_names = []

        for acc in access_records:
            if not acc.check_user_groups(user):
                continue
            model_names.append(acc.model_name)
            if acc.read_access:
                has_read = True
            if acc.create_access:
                has_create = True
            if acc.write_access:
                has_write = True
            if acc.delete_access:
                has_delete = True

        models_hint = ", ".join(model_names[:15]) if model_names else "(none)"

        tools = []

        if has_read:
            tools.append({
                "type": "function",
                "function": {
                    "name": "odoo_search",
                    "description": (
                        f"Search/read records from Odoo. Available models: {models_hint}. "
                        "Returns matching records with their field values."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {
                                "type": "string",
                                "description": "Odoo model technical name, e.g. 'res.partner', 'sale.order'",
                            },
                            "domain": {
                                "type": "string",
                                "description": 'Odoo domain filter as JSON string, e.g. \'[["name","ilike","ahmed"]]\'. Default: "[]"',
                            },
                            "fields": {
                                "type": "string",
                                "description": "Comma-separated field names to read, e.g. 'name,email,phone'. Empty = default fields.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max records to return (default 20)",
                            },
                        },
                        "required": ["model"],
                    },
                },
            })

        if has_create:
            tools.append({
                "type": "function",
                "function": {
                    "name": "odoo_create",
                    "description": (
                        f"Create a new record in Odoo. Available models: {models_hint}. "
                        "Pass field values as a JSON object."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {
                                "type": "string",
                                "description": "Odoo model technical name, e.g. 'res.partner'",
                            },
                            "values": {
                                "type": "string",
                                "description": 'JSON object of field values, e.g. \'{"name": "Ahmed", "email": "ahmed@test.com"}\'',
                            },
                        },
                        "required": ["model", "values"],
                    },
                },
            })

        if has_write:
            tools.append({
                "type": "function",
                "function": {
                    "name": "odoo_write",
                    "description": (
                        f"Update existing records in Odoo. Available models: {models_hint}. "
                        "Specify record IDs and new field values."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {
                                "type": "string",
                                "description": "Odoo model technical name, e.g. 'res.partner'",
                            },
                            "ids": {
                                "type": "string",
                                "description": "Comma-separated record IDs, e.g. '1,2,3'",
                            },
                            "values": {
                                "type": "string",
                                "description": 'JSON object of field values to update, e.g. \'{"name": "New Name"}\'',
                            },
                        },
                        "required": ["model", "ids", "values"],
                    },
                },
            })

        if has_delete:
            tools.append({
                "type": "function",
                "function": {
                    "name": "odoo_delete",
                    "description": (
                        f"Delete records from Odoo. Available models: {models_hint}. "
                        "Specify record IDs to delete."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {
                                "type": "string",
                                "description": "Odoo model technical name, e.g. 'res.partner'",
                            },
                            "ids": {
                                "type": "string",
                                "description": "Comma-separated record IDs to delete, e.g. '5,6'",
                            },
                        },
                        "required": ["model", "ids"],
                    },
                },
            })

        # Always add call_method if any write-type access exists
        if has_create or has_write:
            tools.append({
                "type": "function",
                "function": {
                    "name": "odoo_call_method",
                    "description": (
                        "Call a method on Odoo records. Use this for workflow actions like: "
                        "action_confirm (confirm sale/purchase orders), "
                        "action_create_invoices (create invoices from confirmed orders), "
                        "action_post (post/validate invoices), "
                        "button_validate (validate stock pickings/receipts). "
                        f"Available models: {models_hint}"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {
                                "type": "string",
                                "description": "Odoo model technical name, e.g. 'sale.order'",
                            },
                            "ids": {
                                "type": "string",
                                "description": "Comma-separated record IDs to call the method on, e.g. '4'",
                            },
                            "method": {
                                "type": "string",
                                "description": (
                                    "Method name to call, e.g. 'action_confirm', "
                                    "'action_create_invoices', 'action_post', 'button_validate'"
                                ),
                            },
                        },
                        "required": ["model", "ids", "method"],
                    },
                },
            })

        return tools

    def _execute_tool_call(self, tool_name, arguments):
        """Execute an AI tool call against Odoo and return the result as a string.

        Respects MCP Model Access permissions.
        """
        try:
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "Invalid arguments JSON"})

        model_name = arguments.get("model", "")
        if not model_name:
            return json.dumps({"error": "Missing 'model' parameter"})

        # Check MCP access
        user = self.env.user
        access = self.env["mcp.model.access"].get_access_for_model(model_name, user)

        try:
            model_obj = self.env[model_name]
        except KeyError:
            return json.dumps({"error": f"Model '{model_name}' does not exist."})

        # ---------- odoo_search ----------
        if tool_name == "odoo_search":
            if access and not access.read_access:
                return json.dumps({"error": f"Read access denied on {model_name}"})

            domain_str = arguments.get("domain", "[]")
            try:
                domain = json.loads(domain_str) if domain_str else []
            except (json.JSONDecodeError, TypeError):
                domain = []

            fields_str = arguments.get("fields", "")
            fields_list = [f.strip() for f in fields_str.split(",") if f.strip()] if fields_str else None
            limit = min(int(arguments.get("limit", 20)), 50)

            records = model_obj.search_read(domain, fields=fields_list, limit=limit)
            # Simplify many2one tuples
            for rec in records:
                for k, v in list(rec.items()):
                    if isinstance(v, (list, tuple)) and len(v) == 2 and isinstance(v[0], int):
                        rec[k] = {"id": v[0], "name": v[1]}
                    elif isinstance(v, bytes):
                        rec[k] = "(binary data)"
            return json.dumps({"success": True, "count": len(records), "records": records}, default=str)

        # ---------- odoo_create ----------
        if tool_name == "odoo_create":
            if not access or not access.create_access:
                return json.dumps({"error": f"Create access denied on {model_name}"})

            values_str = arguments.get("values", "{}")
            try:
                values = json.loads(values_str) if isinstance(values_str, str) else values_str
            except (json.JSONDecodeError, TypeError):
                return json.dumps({"error": "Invalid 'values' JSON"})

            record = model_obj.create(values)
            return json.dumps({"success": True, "created_id": record.id, "name": record.display_name}, default=str)

        # ---------- odoo_write ----------
        if tool_name == "odoo_write":
            if not access or not access.write_access:
                return json.dumps({"error": f"Write access denied on {model_name}"})

            ids_str = arguments.get("ids", "")
            try:
                record_ids = [int(i.strip()) for i in ids_str.split(",") if i.strip()]
            except ValueError:
                return json.dumps({"error": "Invalid 'ids' — must be comma-separated integers"})

            values_str = arguments.get("values", "{}")
            try:
                values = json.loads(values_str) if isinstance(values_str, str) else values_str
            except (json.JSONDecodeError, TypeError):
                return json.dumps({"error": "Invalid 'values' JSON"})

            records = model_obj.browse(record_ids).exists()
            if not records:
                return json.dumps({"error": f"No records found with IDs {record_ids}"})
            records.write(values)
            return json.dumps({"success": True, "updated_ids": records.ids}, default=str)

        # ---------- odoo_delete ----------
        if tool_name == "odoo_delete":
            if not access or not access.delete_access:
                return json.dumps({"error": f"Delete access denied on {model_name}"})

            ids_str = arguments.get("ids", "")
            try:
                record_ids = [int(i.strip()) for i in ids_str.split(",") if i.strip()]
            except ValueError:
                return json.dumps({"error": "Invalid 'ids' — must be comma-separated integers"})

            records = model_obj.browse(record_ids).exists()
            if not records:
                return json.dumps({"error": f"No records found with IDs {record_ids}"})
            deleted_ids = records.ids
            records.unlink()
            return json.dumps({"success": True, "deleted_ids": deleted_ids}, default=str)

        # ---------- odoo_call_method ----------
        if tool_name == "odoo_call_method":
            if not access or not (access.write_access or access.create_access):
                return json.dumps({"error": f"Write/create access denied on {model_name}"})

            ids_str = arguments.get("ids", "")
            method_name = arguments.get("method", "")
            if not method_name:
                return json.dumps({"error": "Missing 'method' parameter"})

            # Safety: block dangerous methods
            blocked_methods = [
                'unlink', 'write', 'create', 'copy', 'with_context',
                'sudo', 'with_user', 'with_env', 'with_company',
            ]
            if method_name.startswith('_') or method_name in blocked_methods:
                return json.dumps({"error": f"Method '{method_name}' is not allowed for security reasons."})

            try:
                record_ids = [int(i.strip()) for i in ids_str.split(",") if i.strip()]
            except ValueError:
                return json.dumps({"error": "Invalid 'ids' — must be comma-separated integers"})

            records = model_obj.browse(record_ids).exists()
            if not records:
                return json.dumps({"error": f"No records found with IDs {record_ids}"})

            if not hasattr(records, method_name):
                return json.dumps({"error": f"Method '{method_name}' does not exist on {model_name}"})

            try:
                result = getattr(records, method_name)()
                # Convert result to something serializable
                if result is None or result is True or result is False:
                    return json.dumps({"success": True, "result": result, "message": f"Method '{method_name}' executed successfully on IDs {record_ids}"}, default=str)
                if isinstance(result, dict):
                    return json.dumps({"success": True, "result": result}, default=str)
                if hasattr(result, 'ids'):
                    return json.dumps({"success": True, "result_ids": result.ids, "result_model": result._name, "message": f"Method '{method_name}' returned {len(result.ids)} record(s)"}, default=str)
                return json.dumps({"success": True, "message": f"Method '{method_name}' executed successfully"}, default=str)
            except Exception as e:
                _logger.exception("Tool odoo_call_method error: %s.%s", model_name, method_name)
                return json.dumps({"error": f"Error calling {method_name}: {str(e)}"}, default=str)

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def _call_ai_with_history(self):
        """Call external AI provider using full conversation history."""
        self.ensure_one()

        if requests is None:
            raise UserError(
                _(
                    "The Python 'requests' library is required for AI chat calls "
                    "but is not available on this server."
                )
            )

        icp = self.env["ir.config_parameter"].sudo()
        enabled = icp.get_param("mcp_server_ai.ai_chat_enabled", "False") == "True"
        if not enabled:
            raise UserError(
                _(
                    "In-app AI chat is not enabled. Please enable it in Settings > MCP Server."
                )
            )

        base_url = (icp.get_param("mcp_server_ai.ai_chat_endpoint") or "").strip()
        api_key = (icp.get_param("mcp_server_ai.ai_chat_api_key") or "").strip()
        model = (icp.get_param("mcp_server_ai.ai_chat_model") or "").strip()
        provider = (icp.get_param("mcp_server_ai.ai_chat_provider") or "openai").strip() or "openai"

        if not base_url:
            raise UserError(
                _(
                    "AI chat endpoint URL is not configured. "
                    "Please configure it in Settings > MCP Server."
                )
            )

        if not api_key and provider not in ("ollama",):
            raise UserError(
                _(
                    "AI chat API key is not configured. "
                    "Please configure it in Settings > MCP Server."
                )
            )

        # Build system prompt with optional Odoo data context (MCP-style)
        odoo_context = self._get_odoo_context_for_ai()
        tools = self._get_available_tools_for_ai()
        system_prompt = _(
            "You are an AI assistant inside an Odoo ERP system. Answer in the same language as the user. "
            "You can READ, CREATE, UPDATE, and DELETE records using the tools provided. "
            "You can also call workflow methods (confirm orders, create invoices, etc.) using odoo_call_method. "
            "Use the Odoo data below as context, and use the tools to perform any operations the user requests. "
            "When the user asks to create, modify, or delete a record, USE THE APPROPRIATE TOOL — do not refuse. "
            "For sale orders: create the order header on sale.order, then add lines on sale.order.line with order_id, product_id, product_uom_qty, and price_unit. "
            "To confirm an order use odoo_call_method with method='action_confirm'. "
            "After performing an operation, confirm what was done with the record ID."
        )
        if odoo_context:
            system_prompt += "\n\n--- Odoo data (context) ---\n" + odoo_context
        else:
            system_prompt += "\n\n(No cached Odoo data. Use the odoo_search tool if you need to look up data.)"
        reply = ""

        _logger.info(
            "MCP Chat: calling AI provider '%s' (endpoint=%s, model=%s) for session %s",
            provider,
            base_url,
            model,
            self.id,
        )

        if provider == "ollama":
            reply = self._call_ollama_with_tools(
                base_url, model, system_prompt, tools,
            )
        elif provider == "gemini":
            reply = self._call_gemini_with_tools(
                base_url, api_key, system_prompt, tools,
            )
        else:
            reply = self._call_openai_with_tools(
                base_url, api_key, model, system_prompt, tools,
            )

        return (reply or "").strip()

    # ----------------------------------------------------------------
    # Provider implementations with function-calling / tool-use
    # ----------------------------------------------------------------

    def _build_history_messages(self):
        """Build message history list from stored messages."""
        msgs = []
        for msg in self.message_ids.sorted(key=lambda m: m.create_date):
            if msg.role not in ("user", "assistant"):
                continue
            msgs.append({"role": msg.role, "content": msg.content or ""})
        return msgs

    # ---------- OpenAI-compatible (with function calling) ----------

    def _call_openai_with_tools(self, base_url, api_key, model, system_prompt, tools):
        url = base_url.rstrip("/")
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._build_history_messages())

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        MAX_TOOL_ROUNDS = 5
        for _round in range(MAX_TOOL_ROUNDS):
            payload = {
                "model": model or "gpt-4o-mini",
                "messages": messages,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            _logger.info(
                "MCP Chat OpenAI: POST %s (round=%s, messages=%d)",
                url, _round, len(messages),
            )
            try:
                response = requests.post(
                    url, headers=headers,
                    data=json.dumps(payload), timeout=120,
                )
            except Exception as exc:
                raise UserError(_("Failed to call AI provider: %s") % exc) from exc

            if response.status_code >= 400:
                _logger.error("OpenAI ERROR %s: %s", response.status_code, response.text[:500])
                raise UserError(
                    _("AI provider error (%s): %s") % (response.status_code, response.text[:500])
                )

            try:
                data = response.json()
            except Exception as exc:
                raise UserError(_("AI returned invalid JSON: %s") % response.text) from exc

            choices = data.get("choices") or []
            if not choices:
                return data.get("reply", "")

            msg = choices[0].get("message") or {}
            finish_reason = choices[0].get("finish_reason", "")

            # Check for tool calls
            tool_calls = msg.get("tool_calls")
            if tool_calls and finish_reason in ("tool_calls", "stop", ""):
                # Append assistant message with tool calls
                messages.append(msg)
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    tool_args = fn.get("arguments", "{}")
                    _logger.info("MCP Chat: executing tool %s(%s)", tool_name, tool_args[:200])
                    result = self._execute_tool_call(tool_name, tool_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result,
                    })
                continue  # Send results back to AI

            # Normal text response
            return (msg.get("content") or "").strip()

        return _("Max tool-calling rounds reached. Please try a simpler request.")

    # ---------- Gemini (with function calling) ----------

    def _call_gemini_with_tools(self, base_url, api_key, system_prompt, tools):
        base_url_strip = base_url.rstrip("/")
        url = base_url_strip + ":generateContent"

        contents = [{"role": "user", "parts": [{"text": system_prompt}]}]
        for msg in self.message_ids.sorted(key=lambda m: m.create_date):
            if not msg.content:
                continue
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        # Convert OpenAI tool format to Gemini format
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

            _logger.info("MCP Chat Gemini: POST %s (round=%s)", f"{url}?key=***", _round)
            try:
                response = requests.post(
                    f"{url}?key={api_key}",
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=120,
                )
            except Exception as exc:
                raise UserError(_("Failed to call Gemini: %s") % exc) from exc

            # Retry v1 if v1beta 404
            if response.status_code == 404 and "v1beta" in base_url_strip:
                url_v1 = base_url_strip.replace("/v1beta/", "/v1/") + ":generateContent"
                response = requests.post(
                    f"{url_v1}?key={api_key}",
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=120,
                )

            if response.status_code >= 400:
                _logger.error("Gemini ERROR %s: %s", response.status_code, response.text[:500])
                raise UserError(
                    _("Gemini error (%s): %s") % (response.status_code, response.text[:500])
                )

            try:
                data = response.json()
            except Exception as exc:
                raise UserError(_("Gemini returned invalid JSON: %s") % response.text) from exc

            candidates = data.get("candidates") or []
            if not candidates:
                return ""

            content_obj = candidates[0].get("content") or {}
            parts = content_obj.get("parts") or []

            # Check for function calls in parts
            has_function_call = any("functionCall" in p for p in parts)
            if has_function_call:
                # Append the model response
                contents.append({"role": "model", "parts": parts})
                # Execute each function call and build function response parts
                fn_response_parts = []
                for p in parts:
                    fc = p.get("functionCall")
                    if fc:
                        tool_name = fc.get("name", "")
                        tool_args = fc.get("args", {})
                        _logger.info("MCP Chat Gemini: executing tool %s", tool_name)
                        # Gemini sends args as dict, our executor expects string or dict
                        result_str = self._execute_tool_call(tool_name, tool_args)
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
                continue  # Send results back

            # Normal text response
            for p in parts:
                text = p.get("text")
                if text:
                    return text.strip()
            return ""

        return _("Max tool-calling rounds reached. Please try a simpler request.")

    # ---------- Ollama (with tool support for compatible models) ----------

    def _call_ollama_with_tools(self, base_url, model, system_prompt, tools):
        url = base_url.rstrip("/")
        if "/v1/" not in url and "/api/" not in url:
            url = url + "/api/chat"

        # Truncate prompt for small models
        MAX_PROMPT = 4000
        if len(system_prompt) > MAX_PROMPT:
            marker = "--- Odoo data (context) ---"
            if marker in system_prompt:
                idx = system_prompt.index(marker)
                head = system_prompt[: idx + len(marker) + 1]
                tail = system_prompt[idx + len(marker) + 1 :]
                avail = MAX_PROMPT - len(head)
                if avail > 200:
                    system_prompt = head + tail[:avail] + "\n... (truncated)"
                else:
                    system_prompt = system_prompt[:MAX_PROMPT]
            else:
                system_prompt = system_prompt[:MAX_PROMPT]

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._build_history_messages())

        headers = {"Content-Type": "application/json"}

        # Convert tools to Ollama format (same as OpenAI format for Ollama >= 0.4)
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

            _logger.info("MCP Chat Ollama: POST %s (round=%s, model=%s)", url, _round, model)
            try:
                response = requests.post(
                    url, headers=headers,
                    data=json.dumps(payload), timeout=600,
                )
            except requests.exceptions.Timeout:
                raise UserError(
                    _("Ollama timeout — الموديل أخذ وقت طويل. "
                      "جرب موديل أصغر أو قلل الموديلات في Model Access.")
                )
            except Exception as exc:
                raise UserError(_("Failed to connect to Ollama at %s: %s") % (url, exc)) from exc

            if response.status_code >= 400:
                raise UserError(
                    _("Ollama error (%s): %s") % (response.status_code, response.text[:500])
                )

            try:
                data = response.json()
            except Exception as exc:
                raise UserError(_("Ollama returned invalid JSON: %s") % response.text) from exc

            # Native Ollama format: {"message": {"role": ..., "content": ..., "tool_calls": [...]}}
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls")

            if tool_calls:
                messages.append(msg)
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    tool_args = fn.get("arguments", {})
                    _logger.info("MCP Chat Ollama: executing tool %s", tool_name)
                    result = self._execute_tool_call(tool_name, tool_args)
                    messages.append({
                        "role": "tool",
                        "content": result,
                    })
                continue

            # Normal text response
            content = (msg.get("content") or "").strip()
            if content:
                return content

            # Fallback: OpenAI-compat format
            choices = data.get("choices") or []
            if choices:
                return (choices[0].get("message", {}).get("content") or "").strip()
            return data.get("response", "") or ""

        return _("Max tool-calling rounds reached. Please try a simpler request.")


class MCPChatMessage(models.Model):
    _name = "mcp.chat.message"
    _description = "MCP AI Chat Message"
    _order = "create_date asc, id asc"

    session_id = fields.Many2one(
        "mcp.chat.session",
        string="Session",
        required=True,
        ondelete="cascade",
    )
    role = fields.Selection(
        [
            ("user", "User"),
            ("assistant", "Assistant"),
            ("system", "System"),
        ],
        string="Role",
        required=True,
        default="user",
    )
    content = fields.Text(string="Content", required=True)

