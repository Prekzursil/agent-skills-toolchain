#!/usr/bin/env python3
r"""memory-spool/spool.py — write-ahead spool for basic-memory writes (PreToolUse).

Matcher: mcp__basic-memory__write_note | mcp__basic-memory__edit_note

BEFORE the MCP call runs, persist the intended note payload to a local spool file.
If the call fails, or the server is dead, or the whole session is killed mid-write,
the payload survives on disk and flush_check.py (PostToolUse/SessionStart) re-surfaces
it. This is the TRUE fix for the silent 4h-memory-loss: mcp-liveness heals the server,
this saves the note you were writing while it was down.

SILENT recorder (never injects, never blocks). FAIL-OPEN: any error -> exit 0.
Opt-out: MEMORY_SPOOL=off or a .disabled file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("MEMORY_SPOOL", "").lower() in ("off", "0", "false")


def main() -> int:
    try:
        if _disabled():
            return 0
        data = C.read_stdin()
        tool = str(data.get("tool_name") or "")
        if tool not in C.SPOOLED_TOOLS:
            return 0
        ti = data.get("tool_input") or {}
        key = C.payload_key(tool, ti)
        rec = {
            "ts": C.now(),
            "key": key,
            "tool": tool,
            "title": C.title_of(tool, ti),
            "payload": ti,
            "session": C.session_id(data),
            "tool_use_id": str(data.get("tool_use_id") or "") or None,
            "status": "pending",
        }
        C.write_spool(rec)
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
