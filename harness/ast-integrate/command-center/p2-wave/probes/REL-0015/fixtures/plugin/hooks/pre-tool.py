#!/usr/bin/env python3
"""Canary PreToolUse hook: write an observable side-effect, not a listing."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

out = Path(os.environ["REL0015_SIDE_EFFECT"])
out.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "event": os.environ.get("REL0015_EVENT", "PreToolUse"),
    "observed_client_build_string": os.environ.get("REL0015_CLIENT_BUILD", ""),
    "t": time.time(),
}
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
