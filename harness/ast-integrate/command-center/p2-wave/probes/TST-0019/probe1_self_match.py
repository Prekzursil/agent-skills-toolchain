#!/usr/bin/env python3
"""Named probe 1: reproduce self-match before the guard and its absence after.

Records both PIDs. Does not take the receipt's conclusion as the measurement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / "command-center/receipts/TST-0019.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0019-probe1 {msg}")
    return 1


def main() -> int:
    live = S.self_match_both_states()
    if not live.get("ok"):
        return fail("live self-match both-states failed")
    t = S.test_probe_excludes_own_pid()
    if not t.get("ok"):
        return fail("test_probe_excludes_own_pid failed")
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    pay = SL.payload(doc)
    if str(pay.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {pay.get('state')}")
    if "SUCCESS:TST-0019" not in text:
        return fail("sentinel absent")
    if pay.get("unit_id") != "TST-0019":
        return fail("unit_id")
    pids = pay.get("pids") or {}
    if not pids.get("before_probe_pid") or not pids.get("after_probe_pid"):
        return fail("artifact missing recorded PIDs")
    tell = pay.get("tell") or {}
    if not tell.get("probe_start_key") or not tell.get("reported_start_key"):
        return fail("artifact missing start-key tell")
    if str(tell.get("probe_start_key")) != str(tell.get("reported_start_key")):
        return fail("artifact tell is not start-key equality")
    out = {
        "probe": "probe1-self-match",
        "before_probe_pid": live["before_probe_pid"],
        "after_probe_pid": live["after_probe_pid"],
        "decoy_pid": live["decoy_pid"],
        "self_before": True,
        "self_after": False,
        "artifact_before_pid": pids.get("before_probe_pid"),
        "artifact_after_pid": pids.get("after_probe_pid"),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"before pid={live['before_probe_pid']} matched itself; "
        f"after pid={live['after_probe_pid']} excluded; "
        f"decoy pid={live['decoy_pid']}"
    )
    print("SUCCESS:TST-0019-probe1 self-match before, guarded after, both PIDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
