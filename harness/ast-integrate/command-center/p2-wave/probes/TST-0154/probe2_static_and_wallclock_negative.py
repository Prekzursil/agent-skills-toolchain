#!/usr/bin/env python3
"""Probe 2: static check that elapsed computation does not read wall-clock."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lab import measure_static  # noqa: E402

ART = REPO / "command-center/receipts/TST-0154.json"
SENTINEL = "SUCCESS:TST-0154"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0154-probe2 {msg}")
    return 1


def main() -> int:
    live = measure_static()
    print(json.dumps(live, indent=2, sort_keys=True, default=str))
    if not live.get("pass"):
        return fail("static wall-clock scan did not pass")
    if live.get("elapsed_wall_hits"):
        return fail(f"elapsed.py wall hits {live.get('elapsed_wall_hits')}")
    if not live.get("detector_fires_on_planted_wall_clock"):
        return fail("detector silent on planted time.time() (dead detector)")
    if not live.get("detector_silent_on_elapsed_py"):
        return fail("detector flagged elapsed.py")
    if not live.get("heartbeat_hang_uses_monotonic"):
        return fail("heartbeat hang window does not use time.monotonic")
    if live.get("heartbeat_uses_time_time"):
        return fail("heartbeat.py reads time.time()")
    if not live.get("longrun_sh_delegates_heartbeat"):
        return fail("scripts/longrun.sh does not delegate to heartbeat.py")
    if not live.get("longrun_ps1_delegates_heartbeat"):
        return fail("scripts/longrun.ps1 does not delegate to heartbeat.py")
    if not live.get("longrun_sh_no_date"):
        return fail("scripts/longrun.sh reads date(1)")
    if not live.get("longrun_ps1_no_utcnow"):
        return fail("scripts/longrun.ps1 reads UtcNow/Get-Date")

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            return fail("receipt-sentinel-absent")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt-self-declared {st}")
        if not doc.get("elapsed_uses_monotonic"):
            return fail("receipt missing elapsed_uses_monotonic")

    print(
        "elapsed.py wall_hits=0; planted time.time flagged; "
        "heartbeat hang uses monotonic; longrun scripts delegate"
    )
    print("SUCCESS:TST-0154-probe2 static-and-wallclock-negative")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
