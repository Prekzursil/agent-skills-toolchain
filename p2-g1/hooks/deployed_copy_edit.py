#!/usr/bin/env python3
"""PreToolUse hook: warn when an edit targets a deployed copy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "tools" / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))
import deployed_copy_guard as g  # noqa: E402


def main() -> int:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        event = {}
    payload = g.handle_event(event if isinstance(event, dict) else {})
    print(json.dumps(payload), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
