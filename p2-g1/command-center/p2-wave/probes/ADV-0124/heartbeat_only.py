#!/usr/bin/env python3
"""Known-broken single-signal classifier: heartbeat freshness only.

Live work with a dead heartbeat is reported DEAD. That is the false-dead
control the catalog names (NC-SINGLE-SIGNAL-FALSE-DEAD).
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def classify_heartbeat_only(path: Path, wait_s: float = 0.14) -> dict:
    def _seq() -> int | None:
        if not path.is_file():
            return None
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        seq = doc.get("seq")
        return int(seq) if isinstance(seq, int) else None

    a = _seq()
    time.sleep(max(0.08, float(wait_s)))
    b = _seq()
    fresh = a is not None and b is not None and b > a
    verdict = "LIVE" if fresh else "DEAD"
    return {
        "verdict": verdict,
        "mtime_used": False,
        "hb_fresh": fresh,
        "seq_first": a,
        "seq_second": b,
        "data_source": f"heartbeat-only:{path}:fresh={fresh}",
    }
