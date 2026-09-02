#!/usr/bin/env python3
"""SessionStart advisory hook. Never blocks."""
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
    hook_id = "hook.session-start"
    mark(hook_id)
    payload = json.loads(sys.stdin.read() or "{}")
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": f"{hook_id} saw source={payload.get('source')}",
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
