#!/usr/bin/env python3
"""Hook body: write THIS event's observable side effect, nothing else.

Acceptance is the existence of this file after a client trigger. The script
refuses to run unless CANARY_EFFECTS is set (so a mis-aimed HOME cannot
silently drop a receipt into the owner's tree).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HOOK_EVENT", "")
    effects = os.environ.get("CANARY_EFFECTS", "")
    if not event:
        sys.stderr.write("effect.py: missing event name\n")
        return 2
    if not effects:
        sys.stderr.write("effect.py: CANARY_EFFECTS unset; refusing to write\n")
        return 2
    root = Path(effects)
    root.mkdir(parents=True, exist_ok=True)
    doc = {
        "event": event,
        "home": os.environ.get("HOME"),
        "nonce": os.environ.get("CANARY_NONCE"),
        "pid": os.getpid(),
        "plugin_root": os.environ.get("CLAUDE_PLUGIN_ROOT"),
        "ts_ns": time.time_ns(),
        "ts_unix": time.time(),
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = root / f"{event}.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
