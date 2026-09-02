#!/usr/bin/env python3
"""PreToolUse advisory hook.

Exit 1 is guidance (inject-do-not-block). The dispatcher must not turn that
into a session block. Exit 2 is forbidden here even on scary-looking commands.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def mark(hook_id: str) -> None:
    d = os.environ.get("TST0086_SESSION_DIR") or ""
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        (Path(d) / f"{hook_id}.fired").write_text(hook_id, encoding="utf-8")


def main() -> int:
    hook_id = "hook.pre-tool"
    mark(hook_id)
    payload = json.loads(sys.stdin.read() or "{}")
    tool = str(payload.get("tool_name") or "")
    cmd = str((payload.get("tool_input") or {}).get("command") or "")
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": f"{hook_id} tool={tool}",
                },
            }
        )
    )
    if "TST0086_ADVISORY_NUDGE" in cmd:
        print(f"{hook_id}: advisory nudge, do not block", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
