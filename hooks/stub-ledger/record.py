#!/usr/bin/env python3
r"""stub-ledger/record.py — PostToolUse hook (matcher: Write|Edit|MultiEdit).

RECORD-ONLY (never injects). Scans the content the agent just wrote/edited for
placeholder markers (see stubscan.py) and appends each to a durable per-session
ledger:  ~/.claude/stub-ledger/<session_id>.ndjson  with {file, marker, line,
snippet, ts}. report.py (Stop) reads it back and surfaces still-open stubs.

WHY (gap vs B1 dark-surface): dark-surface only nags when the final message makes a
COMPLETION CLAIM *and* an edited file holds a stub — it has no persistent memory of
placeholders introduced across the session. This ledger is that memory, so a stub the
agent writes and then silently moves on from (no "done" claim) is not lost. The two are
complementary: report.py defers to dark-surface whenever a completion claim is present.

FAIL-OPEN (try/except -> exit 0). Stdlib + sibling stubscan.py only. No output ever.
Opt-out: STUB_LEDGER=off in env, or a hooks/stub-ledger/.disabled file.

settings.json (PostToolUse, matcher "Write|Edit|MultiEdit"):
  {"type":"command",
   "command":"python C:/Users/Prekzursil/.claude/hooks/stub-ledger/record.py",
   "timeout":6,"statusMessage":"Stub-ledger: recording placeholders written"}
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
if str(THIS) not in sys.path:
    sys.path.insert(0, str(THIS))

DISABLED = THIS / ".disabled"
LEDGER_ROOT = Path(
    os.environ.get("STUB_LEDGER_ROOT", str(Path.home() / ".claude" / "stub-ledger"))
)


def _ledger_file(session_id: str) -> Path:
    LEDGER_ROOT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    return LEDGER_ROOT / f"{safe or 'unknown'}.ndjson"


def _written_content(tool_name: str, tool_input: dict) -> str:
    """Extract the text the agent just wrote, across Write/Edit/MultiEdit shapes."""
    if not isinstance(tool_input, dict):
        return ""
    if tool_name == "Write":
        return str(tool_input.get("content") or "")
    if tool_name == "Edit":
        return str(tool_input.get("new_string") or "")
    if tool_name == "MultiEdit":
        parts = []
        for e in tool_input.get("edits") or []:
            if isinstance(e, dict):
                parts.append(str(e.get("new_string") or ""))
        return "\n".join(parts)
    # fallback: try common keys
    return str(tool_input.get("content") or tool_input.get("new_string") or "")


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("STUB_LEDGER", "").lower() in (
            "off",
            "0",
            "false",
        ):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        tool_name = str(data.get("tool_name") or "")
        if tool_name not in ("Write", "Edit", "MultiEdit"):
            return 0
        tool_input = data.get("tool_input") or {}
        file_path = (
            str(tool_input.get("file_path") or tool_input.get("path") or "")
            if isinstance(tool_input, dict)
            else ""
        )
        content = _written_content(tool_name, tool_input)
        if not content:
            return 0

        import stubscan  # sibling module

        if stubscan.is_test_file(file_path):
            return 0  # test/fixture files legitimately contain stub/TODO fixtures
        # Pass the write TARGET. Without it stubscan's `_discriminator` returns None and the
        # use-vs-mention filter is never armed at RECORD time, so every marker the agent writes
        # is banked unconditionally and only report.py's re-scan can drop it -- which it cannot
        # do for an unsaved/unreadable path. Measured 2026-07-24: 53 records banked, 20 surfaced,
        # 20/20 false positives.
        hits = stubscan.find_stubs(content, file_path)
        if not hits:
            return 0

        session_id = str(data.get("session_id") or "unknown")
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path = _ledger_file(session_id)
        with path.open("a", encoding="utf-8", errors="replace") as fh:
            for marker, line_no, snippet in hits:
                fh.write(
                    json.dumps(
                        {
                            "ts": ts,
                            "file": file_path,
                            "marker": marker,
                            "line": line_no,
                            "snippet": snippet,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
