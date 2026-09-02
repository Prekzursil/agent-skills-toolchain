#!/usr/bin/env python3
"""Probe 2: negative control — silent last-good fallback must fail.

Two independent signals at TTL+1:
  (a) rendered pane text (honest UNKNOWN vs mutant last-good)
  (b) cache file mtime from a separate process
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
    STALE_SENTINEL,
    last_good_silent_control,
)


def main() -> int:
    now = time.time()
    with tempfile.TemporaryDirectory(prefix="tst0153-p2-") as raw:
        result = last_good_silent_control(Path(raw), now=now)
    payload = {
        "pass": bool(result["pass"]),
        "probe": "probe2-last-good-silent",
        "unit_id": "TST-0153",
        "honest": result["honest"],
        "honest_ok": result["honest_ok"],
        "mutant": result["mutant"],
        "mutant_fails_detector": result["mutant_fails_detector"],
        "mutant_leaks_without_age_marker": result["mutant_leaks_without_age_marker"],
        "mtime_ok": result["mtime_ok"],
        "mtime_signal": result["mtime_signal"],
        "ttl_plus_one": result["ttl_plus_one"],
        "signal_a": "rendered pane text at TTL+1",
        "signal_b": "cache file mtime via separate process",
        "stale_sentinel": STALE_SENTINEL,
        "same_code_path": "monitor.panel_cache.render_pane vs render_last_good_silent",
    }
    print(json.dumps(payload, sort_keys=True))
    if not result["pass"]:
        print(
            "FAILED:TST-0153-probe2 silent last-good mutant must fail; "
            "honest TTL+1 pane must be UNKNOWN"
        )
        return 1
    print(
        "SUCCESS:TST-0153-probe2 honest="
        f"{result['honest']['text']!r} mutant={result['mutant']['text']!r} "
        f"mutant_fails={result['mutant_fails_detector']} "
        f"mtime_age={result['mtime_signal']['age_seconds']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
