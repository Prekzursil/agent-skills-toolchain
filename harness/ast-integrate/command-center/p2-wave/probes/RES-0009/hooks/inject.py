#!/usr/bin/env python3
"""Exit 0 JSON hook returning additionalContext inside hookSpecificOutput."""
from __future__ import annotations

import json
import sys

raw = sys.stdin.read()
try:
    doc = json.loads(raw) if raw.strip() else {}
except json.JSONDecodeError:
    doc = {}
event = doc.get("hook_event_name") or "PostToolUse"
sys.stdout.write(
    json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": "RES-0009-INJECT-MARKER",
            }
        },
        separators=(",", ":"),
    )
)
sys.exit(0)
