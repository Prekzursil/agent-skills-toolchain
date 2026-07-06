"""T4 - personal 1:1 E2EE Messenger DM bridge.

======================================================================
LICENSING: AGPL-3.0  (USER-APPROVED)
This module integrates with an AGPL-3.0 Messenger bridge (mautrix/meta,
"Labyrinth" E2EE client). If this MCP server is ever DISTRIBUTED, the
AGPL-3.0 copyleft applies to the combined work. See LICENSE-AGPL-3.0 and
NOTICE at the repo root. Kept modular so it can be excluded from a
non-copyleft distribution.
======================================================================

Personal 1:1 Messenger conversations are end-to-end encrypted (Meta's
Labyrinth protocol). The cookie-based private API (fbchat-muqit) CANNOT read
or send them - only groups/rooms/pages. These tools use a dedicated E2EE
backend instead.

Backend is pluggable via FB_DM_BACKEND:
  * "fbchat_v2" (default) - the pip `fbchat-v2` library (wraps the mautrix/meta
    Go client; authenticates with the SAME facebook.com cookies: datr/c_user/xs).
  * "bridge_daemon"       - talk to a locally-run mautrix-meta bridge daemon
    over its local API (thin launcher pattern; see bridge_daemon.py).

If the backend is not installed / not configured, the tools return a clear,
non-fabricated "needs setup" payload (they NEVER fake a send).

Account-ban-risk guidance (personal-account automation, same posture as the
social skill): use a WARMED account, one STATIC residential/ISP proxy
(FB_DM_PROXY), HUMAN cadence, and LOW volume. Automating a personal account is
against Meta ToS and risks action on the account.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .common import COOKIES_PATH, dump

DEFAULT_BACKEND = "fbchat_v2"

_SETUP_HELP = (
    "E2EE DM backend not available. Install/enable it, then set the env vars. "
    "See README.md 'T4 setup' and NOTICE (AGPL-3.0). Required: facebook.com "
    "cookies at "
    + COOKIES_PATH
    + " containing datr/c_user/xs, FB_E2EE_ENABLED=1, and (recommended) "
    "FB_DM_PROXY=<static residential/ISP proxy>."
)


class DMNotConfigured(RuntimeError):
    """Raised when the E2EE backend is missing or not enabled."""


# --------------------------------------------------------------------------- #
# Backend loader
# --------------------------------------------------------------------------- #
def _load_backend() -> "E2EEBackend":
    """Return a ready E2EE backend or raise DMNotConfigured (never fake it)."""
    if os.environ.get("FB_E2EE_ENABLED", "").strip() not in ("1", "true", "yes"):
        raise DMNotConfigured("FB_E2EE_ENABLED is not set. " + _SETUP_HELP)
    name = os.environ.get("FB_DM_BACKEND", DEFAULT_BACKEND).strip()
    if name in ("fbchat_v2", "bridge_daemon"):
        # fbchat-v2's internal _BridgeProcess IS the Go-bridge (mautrix/meta)
        # daemon launcher + stdio JSON-RPC client, so both selectors resolve to
        # the same backend. FBCHAT_E2EE_BIN overrides the bridge binary path.
        from .backends.fbchat_v2_backend import FbchatV2Backend

        return FbchatV2Backend(
            cookies_path=COOKIES_PATH,
            proxy=os.environ.get("FB_DM_PROXY") or None,
            binary_path=os.environ.get("FBCHAT_E2EE_BIN") or None,
        )
    raise DMNotConfigured(f"unknown FB_DM_BACKEND '{name}'. " + _SETUP_HELP)


# --------------------------------------------------------------------------- #
# Tool registration
# --------------------------------------------------------------------------- #
def register_dm_tools(mcp: FastMCP) -> None:
    """Register the T4 E2EE 1:1 DM tools on `mcp`."""

    @mcp.tool()
    async def fb_dm_status() -> str:
        """Report whether the E2EE 1:1 DM backend is installed and configured.
        Honest diagnostic - does not send anything."""
        info: dict[str, Any] = {
            "backend": os.environ.get("FB_DM_BACKEND", DEFAULT_BACKEND),
            "enabled": os.environ.get("FB_E2EE_ENABLED", "") in ("1", "true", "yes"),
            "cookies_path": COOKIES_PATH,
            "cookies_present": os.path.exists(COOKIES_PATH),
            "proxy_set": bool(os.environ.get("FB_DM_PROXY")),
            "license": "AGPL-3.0",
        }
        try:
            backend = _load_backend()
            info.update(await backend.status())
        except DMNotConfigured as exc:
            info["ready"] = False
            info["reason"] = str(exc)
        except Exception as exc:  # backend import / init failure
            info["ready"] = False
            info["reason"] = f"backend error: {exc!r}"
        return dump(info)

    @mcp.tool()
    async def fb_dm_list(limit: int = 20) -> str:
        """List recent personal 1:1 E2EE Messenger DM threads."""
        try:
            backend = _load_backend()
            return dump(await backend.list_threads(limit=limit))
        except DMNotConfigured as exc:
            return dump({"error": "not_configured", "help": str(exc)})

    @mcp.tool()
    async def fb_dm_read(thread_id: str, limit: int = 20) -> str:
        """Read recent messages from a personal 1:1 E2EE DM thread by id."""
        try:
            backend = _load_backend()
            return dump(await backend.read_thread(thread_id, limit=limit))
        except DMNotConfigured as exc:
            return dump({"error": "not_configured", "help": str(exc)})

    @mcp.tool()
    async def fb_dm_send(thread_id: str, text: str) -> str:
        """Send a text message to a personal 1:1 E2EE DM thread. NEVER reports
        success unless the backend confirms the send."""
        try:
            backend = _load_backend()
            res = await backend.send(thread_id, text)
            ok = isinstance(res, dict) and res.get("success") == 1
            return dump({"sent": ok, "thread_id": thread_id, "result": res})
        except DMNotConfigured as exc:
            return dump({"sent": False, "error": "not_configured", "help": str(exc)})

    @mcp.tool()
    async def fb_dm_react(thread_id: str, message_id: str, emoji: str) -> str:
        """React to a message in a personal 1:1 E2EE DM thread with an emoji."""
        try:
            backend = _load_backend()
            res = await backend.react(thread_id, message_id, emoji)
            return dump({"reacted": True, "message_id": message_id, "result": res})
        except DMNotConfigured as exc:
            return dump({"reacted": False, "error": "not_configured", "help": str(exc)})


# --------------------------------------------------------------------------- #
# Backend protocol (concrete backends live in fbmcp/backends/)
# --------------------------------------------------------------------------- #
class E2EEBackend:  # pragma: no cover - interface only
    """Interface every E2EE backend implements."""

    async def status(self) -> dict:
        raise NotImplementedError

    async def list_threads(self, limit: int = 20) -> Any:
        raise NotImplementedError

    async def read_thread(self, thread_id: str, limit: int = 20) -> Any:
        raise NotImplementedError

    async def send(self, thread_id: str, text: str) -> Any:
        raise NotImplementedError

    async def react(self, thread_id: str, message_id: str, emoji: str) -> Any:
        raise NotImplementedError
