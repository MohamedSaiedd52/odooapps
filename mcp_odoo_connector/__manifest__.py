{
    'name': 'MCP Server - AI Assistant Integration',
    'version': '19.0.2.0.0',
    'author': 'Mohamed Saied',
    'category': 'Productivity',
    'summary': 'Model Context Protocol server: connect Claude, ChatGPT & AI agents to Odoo securely. AI automation & chatbot toolkit.',
    'price': 30.0,
    'currency': 'USD',
    'description': """
MCP Server - AI Assistant Integration for Odoo
================================================

Enables AI assistants (Claude, Cursor, VS Code Copilot, etc.)
to securely access and interact with Odoo data via the Model Context Protocol.

Features:
---------
* REST API endpoints with Bearer token authentication
* XML-RPC proxy with MCP permission checks
* Fine-grained per-model CRUD access control
* Field-level access restrictions
* Complete audit trail logging
* Configurable rate limiting
* Response caching with per-model TTL
* LLM-optimized output formatting
* IP whitelisting
* YOLO development mode
* Smart field defaults (excludes binary fields)
* Summary generator for browse/search results
* OWL Chatbot widget with Ollama/OpenAI/Gemini support
    """,
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/mcp_security.xml',
        'security/ir.model.access.csv',
        'data/default_data.xml',
        'views/mcp_model_access_views.xml',
        'views/mcp_audit_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/mcp_chat_views.xml',
        'views/mcp_discuss_menu.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mcp_odoo_connector/static/src/components/mcp_chatbot.css',
            'mcp_odoo_connector/static/src/components/mcp_chatbot.js',
            'mcp_odoo_connector/static/src/components/mcp_chatbot.xml',
        ],
    },
    'images': ['static/description/banner.gif'],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}

