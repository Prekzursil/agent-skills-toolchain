#!/usr/bin/env python3
"""PreToolUse danger hook: exit 2 only for irreversible operations.

Inspects the proposed tool_input. Never executes the command. A non-match is
exit 0. Internal errors are the dispatcher's fail-open problem, not ours.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HOOK_ID = "hook.danger-block"

# Patterns for operations that cannot be undone if the client actually runs them.
IRREVERSIBLE = (
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/(?:\s|$)", re.I),
    re.compile(r"\brm\s+--recursive\s+--force\s+/(?:\s|$)", re.I),
    re.compile(r"\bmkfs(?:\.\w+)?\b", re.I),
    re.compile(r"\bdd\s+.*\bof=/dev/", re.I),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*;\s*\}\s*;"),
)


def mark() -> None:
    d = os.environ.get("TST0086_SESSION_DIR") or ""
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        (Path(d) / f"{HOOK_ID}.fired").write_text(HOOK_ID, encoding="utf-8")


def command_text(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or "")
    return ""


def is_dangerous(payload: dict) -> bool:
    if payload.get("tool_name") != "Bash":
        return False
    cmd = command_text(payload)
    return any(p.search(cmd) for p in IRREVERSIBLE)


def main() -> int:
    mark()
    payload = json.loads(sys.stdin.read() or "{}")
    if is_dangerous(payload):
        reason = (
            f"{HOOK_ID}: refusing irreversible command "
            f"{command_text(payload)!r}"
        )
        print(reason, file=sys.stderr)
        print(json.dumps({"continue": False, "reason": reason}))
        return 2
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": f"{HOOK_ID}: no irreversible danger",
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
