from odoo.tests.common import TransactionCase


class TestMCPServerAI(TransactionCase):
    """Basic sanity tests for mcp_odoo_connector module.

    These do NOT call external AI APIs; they only verify that:
    - core models and fields load correctly
    - Discuss integration for the MCP AI channel can be created
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env["res.config.settings"]
        cls.ChatSession = cls.env["mcp.chat.session"]
        cls.DiscussChannel = cls.env["discuss.channel"]

    def test_settings_fields_exist(self):
        """res.config.settings should expose MCP and AI chat fields."""
        settings = self.Settings.create({})
        for fname in [
            "mcp_enabled",
            "mcp_logging_enabled",
            "mcp_rate_limit",
            "mcp_ai_chat_enabled",
            "mcp_ai_chat_provider",
        ]:
            self.assertIn(fname, settings._fields, f"Missing field on res.config.settings: {fname}")

    def test_chat_session_model_basic(self):
        """Create an MCP chat session and ensure basic fields behave."""
        session = self.ChatSession.create({"name": "Test Session"})
        self.assertTrue(session.user_id, "Chat session should have a user_id by default")
        self.assertFalse(session.message_ids, "New chat session should start with no messages")

    def test_discuss_ai_channel_action(self):
        """MCP AI Discuss channel action should create/return a channel and a proper client action."""
        channel = self.DiscussChannel.get_or_create_mcp_ai_channel()
        self.assertTrue(channel.is_mcp_ai_channel, "Channel should be flagged as MCP AI channel")
        action = self.DiscussChannel.action_open_mcp_ai_discuss()
        self.assertEqual(action.get("type"), "ir.actions.client")
        self.assertEqual(action.get("tag"), "mail.action_discuss")
        self.assertIn("active_id", action.get("context", {}), "Discuss action should focus the AI channel")

