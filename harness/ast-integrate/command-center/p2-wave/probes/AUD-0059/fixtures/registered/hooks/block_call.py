#!/usr/bin/env python3
"""PreToolUse: block a call with an on-disk deny record (independent of the dispatcher)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

root = Path(os.environ["AUD0059_ROOT"])
sys.path.insert(0, str(root))
import runtime as R  # noqa: E402

event = R.read_event()
sess = R.session_dir()
blocked = {
    "blocked": True,
    "tool": event.get("tool") or "Bash",
    "reason": "AUD-0059-BLOCK:deliberate-deny",
}
block_path = sess / "blocked.json"
block_path.write_text(json.dumps(blocked, indent=2, sort_keys=True) + "\n", encoding="utf-8")
payload = R.emit_effect(
    "blocked-call",
    {
        "event": event.get("event") or "PreToolUse",
        "blocked": True,
        "block_path": str(block_path),
        "tool": blocked["tool"],
    },
)
print(
    json.dumps(
        {
            "ok": True,
            "effect": payload["effect"],
            "permissionDecision": "deny",
            "blocked": True,
        },
        sort_keys=True,
    )
)
