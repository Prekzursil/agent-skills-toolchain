"""T3 - non-E2EE Messenger SEND / react (groups, rooms, pages).

Extends the existing fbchat-muqit integration to WRITE to threads that are not
end-to-end encrypted. Uses the SAME facebook.com cookies as the read tools
(data/cookies.json or FB_COOKIES_PATH). Personal 1:1 DMs are E2EE and are NOT
handled here - use the T4 fb_dm_* tools for those.
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .common import dump, fb_client


def register_send_tools(mcp: FastMCP) -> None:
    """Register the non-E2EE send/react tools on `mcp`."""

    @mcp.tool()
    async def fb_send_message(
        thread_id: str,
        text: str,
        reply_to_message: Optional[str] = None,
    ) -> str:
        """Send a text message to a NON-E2EE thread (group/room/page).

        Optionally reply to an existing message by id. Returns the sent
        message id. Does NOT work on personal 1:1 DMs (E2EE) - use fb_dm_send.
        """
        async with fb_client() as c:
            mid = await c.send_message(
                text, thread_id, reply_to_message=reply_to_message
            )
        return dump({"sent": True, "message_id": mid, "thread_id": thread_id})

    @mcp.tool()
    async def fb_send_file(
        thread_id: str,
        file_path: Optional[list[str]] = None,
        file_url: Optional[list[str]] = None,
        text: Optional[str] = None,
    ) -> str:
        """Send local files (paths) and/or remote files (urls) to a non-E2EE
        thread, optionally with a text caption. At least one of file_path or
        file_url is required.
        """
        if not file_path and not file_url:
            return dump({"error": "provide file_path and/or file_url"})
        async with fb_client() as c:
            mid = await c.send_message(
                text, thread_id, file_path=file_path, file_url=file_url
            )
        return dump({"sent": True, "message_id": mid, "thread_id": thread_id})

    @mcp.tool()
    async def fb_react_to_message(
        thread_id: str, message_id: str, emoji: str
    ) -> str:
        """React to a message in a non-E2EE thread with an emoji (e.g. '❤️')."""
        async with fb_client() as c:
            await c.react(emoji, message_id, thread_id)
        return dump(
            {"reacted": True, "message_id": message_id, "emoji": emoji}
        )

    @mcp.tool()
    async def fb_unsend_message(thread_id: str, message_id: str) -> str:
        """Unsend (remove for everyone) one of YOUR messages in a non-E2EE thread."""
        async with fb_client() as c:
            await c.unsend(message_id, thread_id)
        return dump({"unsent": True, "message_id": message_id})

    @mcp.tool()
    async def fb_forward_message(message_id: str, to_thread_id: str) -> str:
        """Forward a message to another non-E2EE thread."""
        async with fb_client() as c:
            await c.forward_message(message_id, to_thread_id)
        return dump(
            {
                "forwarded": True,
                "message_id": message_id,
                "to_thread_id": to_thread_id,
            }
        )

    @mcp.tool()
    async def fb_mark_read(thread_id: str) -> str:
        """Mark a non-E2EE thread as read."""
        async with fb_client() as c:
            await c.mark_as_read(thread_id)
        return dump({"marked_read": True, "thread_id": thread_id})

    @mcp.tool()
    async def fb_send_typing(thread_id: str, is_typing: bool = True) -> str:
        """Send (or clear) a typing indicator in a non-E2EE thread."""
        async with fb_client() as c:
            await c.typing(thread_id, is_typing)
        return dump({"typing": is_typing, "thread_id": thread_id})

    @mcp.tool()
    async def fb_create_group(participant_ids: list[str]) -> str:
        """Create a new group thread with the given user ids. Returns thread id."""
        async with fb_client() as c:
            tid = await c.create_group_thread(participant_ids)
        return dump({"created": True, "thread_id": tid})
