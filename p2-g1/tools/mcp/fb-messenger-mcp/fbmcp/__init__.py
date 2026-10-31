"""fb-messenger MCP server package.

Tiers:
  * read_tools     - original read-only Messenger tools (groups/rooms/pages).
  * messenger_send - T3: non-E2EE SEND/react in group/room/page threads (fbchat-muqit).
  * graph          - T1: Facebook Graph API (Page + professional Instagram), ToS-clean.
  * dm_e2ee        - T4: personal 1:1 E2EE Messenger DM bridge (AGPL-3.0 component).
"""

__all__ = ["build_server"]


def build_server():
    """Construct the FastMCP server with every tier registered."""
    from mcp.server.fastmcp import FastMCP

    from .read_tools import register_read_tools
    from .messenger_send import register_send_tools
    from .graph import register_graph_tools
    from .dm_e2ee import register_dm_tools

    mcp = FastMCP("fb-messenger")
    register_read_tools(mcp)
    register_send_tools(mcp)
    register_graph_tools(mcp)
    register_dm_tools(mcp)
    return mcp
