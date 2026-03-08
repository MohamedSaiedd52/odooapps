def pre_init_hook(env_or_cr):
    """Add missing columns for compat with other modules and our discuss channel.

    Depending on how Odoo is invoked, `pre_init_hook` may receive a database
    cursor (`cr`) or an `Environment` (`env`). Support both.
    """
    cr = getattr(env_or_cr, "cr", env_or_cr)

    def _safe_execute(query):
        # Any failure inside pre_init_hook aborts the transaction and breaks module install.
        # Using savepoints allows us to ignore non-critical DDL issues safely.
        try:
            with cr.savepoint():
                cr.execute(query)
        except Exception:
            return False
        return True

    # ir_model.abstract: compat with simplify_access_management
    _safe_execute("""
        ALTER TABLE ir_model
        ADD COLUMN IF NOT EXISTS abstract boolean DEFAULT false
    """)
    # Copy values if the source column exists in this DB
    _safe_execute("""
        UPDATE ir_model SET abstract = is_abstract
        WHERE is_abstract IS NOT NULL
    """)

    # discuss_channel.is_mcp_ai_channel: our MCP AI channel flag
    _safe_execute("""
        ALTER TABLE discuss_channel
        ADD COLUMN IF NOT EXISTS is_mcp_ai_channel boolean DEFAULT false
    """)


from . import models
from . import controllers
from . import utils
