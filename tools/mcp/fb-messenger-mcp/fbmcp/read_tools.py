"""Original read-only Messenger tools (groups / rooms / pages).

Preserved verbatim from the initial server: whoami, list_threads, read_thread,
search_messages, thread_info. Personal 1:1 Messenger DMs are E2EE and are NOT
handled here (see the T4 fb_dm_* tools).
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .common import dump, fb_client


def register_read_tools(mcp: FastMCP) -> None:
    """Register the 5 original read-only tools on `mcp`."""

    @mcp.tool()
    async def whoami() -> str:
        """Confirm which Facebook account the configured cookies belong to."""
        async with fb_client() as c:
            return json.dumps({"uid": c.uid, "name": c.name})

    @mcp.tool()
    async def list_threads(limit: int = 10) -> str:
        """List recent Messenger threads (groups/rooms/pages) with id, name, type."""
        async with fb_client() as c:
            return dump(list(await c.fetch_thread_list(limit=limit)))

    @mcp.tool()
    async def read_thread(thread_id: str, limit: int = 20) -> str:
        """Read the most recent messages from a thread (group/room/page) by id."""
        async with fb_client() as c:
            return dump(await c.fetch_thread_messages(thread_id, message_limit=limit))

    @mcp.tool()
    async def search_messages(thread_id: str, text: str) -> str:
        """Search for messages containing `text` within a group thread."""
        async with fb_client() as c:
            return dump(await c.search_message(text, thread_id))

    @mcp.tool()
    async def thread_info(thread_ids: list[str]) -> str:
        """Get details for one or more threads by id."""
        async with fb_client() as c:
            return dump(list(await c.fetch_thread_info(thread_ids)))
