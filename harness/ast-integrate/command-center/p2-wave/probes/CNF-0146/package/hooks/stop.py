#!/usr/bin/env python3
"""Stop canary: writes a beacon only this hook writes."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

EVENT = "Stop"
HOOK_ID = "cnf0146.stop"


def main() -> int:
    root = Path(os.environ["USERPROFILE"])
    dest = root / ".cnf0146-runtime" / "fired"
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "event": EVENT,
        "hook_id": HOOK_ID,
        "writer": "hook-script-only",
        "pid": os.getpid(),
        "ts_ns": time.time_ns(),
    }
    (dest / f"{EVENT}.beacon").write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
