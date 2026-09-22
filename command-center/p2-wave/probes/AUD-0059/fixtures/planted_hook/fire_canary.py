#!/usr/bin/env python3
"""Planted canary hook for AUD-0059 both-states control.

When enabled: reads stdin JSON, appends one fire receipt to AUD0059_FIRE_LEDGER.
When disabled (.disabled sibling OR AUD0059_HOOK_DISABLED=1): exits 0 with no write.
Also prints an injectable context line on stdout when it fires (observable effect).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
MARKER = "AUD-0059-PLANTED-FIRE"


def main() -> int:
    if DISABLED.is_file() or os.environ.get("AUD0059_HOOK_DISABLED", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return 0
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        data = {}
    ledger = os.environ.get("AUD0059_FIRE_LEDGER")
    if not ledger:
        return 0
    path = Path(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hook": "planted/fire_canary",
        "marker": MARKER,
        "event": data.get("hook_event_name") or data.get("event") or "unknown",
        "session_id": data.get("session_id") or "aud-0059",
        "tool_name": data.get("tool_name"),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    # Observable non-ledger effect: inject a context line the host would see.
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": row["event"],
                    "additionalContext": f"[{MARKER}] planted canary fired",
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
