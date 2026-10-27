"""Router hook contract: fail-open on forced exceptions (IMP-0404)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _log(event: dict[str, Any], exit_code: int, extra: dict[str, Any]) -> None:
    path = os.environ.get("IMP0404_HOOK_LOG")
    if not path:
        return
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "hook_event_name": event.get("hook_event_name"),
        "tool_name": event.get("tool_name"),
        "exit_code": exit_code,
        **extra,
    }
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def handle(event: dict[str, Any]) -> dict[str, Any]:
    fault = os.environ.get("IMP0404_ROUTER_FAULT") or ""
    raised = fault in {"raise", "sys-exit-2", "return-deny"}
    # Fail-open: catch forced exceptions / exit-2 / deny and still allow.
    payload = {
        "ok": True,
        "failOpen": True if raised else False,
        "permissionDecision": "allow",
        "hookSpecificOutput": {
            "permissionDecision": "allow",
            "additionalContext": "cap.router-audit additive context",
        },
    }
    _log(event, 0, {"failOpen": payload["failOpen"]})
    return payload


def main() -> int:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        event = {}
    payload = handle(event)
    sys.stdout.write(json.dumps(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
