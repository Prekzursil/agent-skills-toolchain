#!/usr/bin/env python3
"""Stop: write a ledger row as the observable effect."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

root = Path(os.environ["AUD0059_ROOT"])
sys.path.insert(0, str(root))
import runtime as R  # noqa: E402

event = R.read_event()
payload = R.emit_effect(
    "ledger-row",
    {
        "event": event.get("event") or "Stop",
        "reason": event.get("reason") or "session-stop",
    },
)
print(json.dumps({"ok": True, "effect": payload["effect"]}, sort_keys=True))
