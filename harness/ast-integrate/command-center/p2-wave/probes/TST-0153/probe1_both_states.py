#!/usr/bin/env python3
"""Probe 1: both-states — fresh number vs TTL+1 UNKNOWN.

Required: a fresh cache value renders normally; at TTL+1 the pane is UNKNOWN
and the last-good number is absent. Signal (b) is the cache mtime from a
separate process.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from monitor.panel_cache import (  # noqa: E402
    FRESH_VALUE,
    STALE_SENTINEL,
    UNKNOWN,
    both_states_control,
)


def main() -> int:
    now = time.time()
    with tempfile.TemporaryDirectory(prefix="tst0153-p1-") as raw:
        result = both_states_control(Path(raw), now=now)
    payload = {
        "pass": bool(result["pass"]),
        "probe": "probe1-both-states",
        "unit_id": "TST-0153",
        "fresh": result["fresh"],
        "expired": result["expired"],
        "fresh_ok": result["fresh_ok"],
        "expired_ok": result["expired_ok"],
        "mtime_ok": result["mtime_ok"],
        "mtime_signal": result["mtime_signal"],
        "ttl_plus_one": result["ttl_plus_one"],
        "same_code_path": "monitor.panel_cache.render_pane",
        "stale_sentinel": STALE_SENTINEL,
        "fresh_value": FRESH_VALUE,
        "unknown_token": UNKNOWN,
    }
    print(json.dumps(payload, sort_keys=True))
    if not result["pass"]:
        print("FAILED:TST-0153-probe1 fresh must render the number; TTL+1 must be UNKNOWN")
        return 1
    print(
        "SUCCESS:TST-0153-probe1 both-states fresh="
        f"{result['fresh']['text']!r} expired={result['expired']['text']!r} "
        f"mtime_age={result['mtime_signal']['age_seconds']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
