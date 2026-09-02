#!/usr/bin/env python3
"""PreToolUse: inject a distinctive context line (independent of the dispatcher)."""
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
line = "AUD-0059-INJECT:pre-tool context line is observable"
inject = sess / "context_inject.txt"
inject.write_text(line + "\n", encoding="utf-8")
payload = R.emit_effect(
    "inject-context",
    {
        "event": event.get("event") or "PreToolUse",
        "injected_line": line,
        "inject_path": str(inject),
    },
)
print(json.dumps({"ok": True, "effect": payload["effect"]}, sort_keys=True))
