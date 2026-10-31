"""FB / Messenger MCP server entrypoint.

Wraps four tiers behind one MCP server ("fb-messenger"):

  * read_tools     - read-only Messenger (groups/rooms/pages), cookie auth.
  * messenger_send - T3: SEND / react in NON-E2EE threads, cookie auth.
  * graph          - T1: Facebook Graph API (Page + professional Instagram),
                     official token auth (ToS-clean, no app review for own assets).
  * dm_e2ee        - T4: personal 1:1 E2EE Messenger DM bridge (AGPL-3.0 module).

Personal 1:1 Messenger DMs are end-to-end encrypted: the read/send tools that
use facebook.com cookies (fbchat-muqit) only reach groups/rooms/pages. The
fb_dm_* tools handle E2EE 1:1 DMs via a separate bridge (see NOTICE / LICENSE).

Auth setup for every tier lives in README.md.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fbmcp import build_server  # noqa: E402

mcp = build_server()

if __name__ == "__main__":
    mcp.run()
