#!/usr/bin/env python3
"""Named probe 1: (a) the second attempt's observed network call.

After a transient fetch failure is negatively cached, a call inside the
short ttl must not hit the transport. After that ttl expires the next
fetch must be observed on the network. Independent of probe 2's on-disk
type/ttl inspection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

UID = "TST-0176"
ART = REPO / "command-center" / "receipts" / "TST-0176.json"
SENTINEL = "SUCCESS:TST-0176"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0176-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("unit_id") != UID:
        return fail(f"unit_id {doc.get('unit_id')}")

    live = S.measure_retry_after_negative_ttl()
    if not live.get("pass"):
        print(json.dumps(live, indent=2, default=str)[:4000])
        return fail("live post-ttl retry did not hit the network")
    if live.get("second_attempt_observed_network") is not True:
        return fail("second attempt was not observed on the network")
    if int(live.get("within_ttl_calls") or -1) != 1:
        return fail("in-ttl fetch issued a network call")
    if int(live.get("after_ttl_calls") or -1) != 2:
        return fail("post-ttl fetch did not add a network call")

    rec = (doc.get("tests") or {}).get("retry_after_negative_ttl") or {}
    if rec.get("pass") is not True:
        return fail("artifact retry_after_negative_ttl.pass is not true")
    if rec.get("second_attempt_observed_network") is not True:
        return fail("artifact missing observed second-attempt network call")

    evidence = doc.get("evidence") or []
    signals = {e.get("id") or e.get("signal") for e in evidence if isinstance(e, dict)}
    if "a" not in signals and "second-attempt-network-call" not in signals:
        return fail("artifact missing evidence signal (a)")

    out = {
        "probe": "probe1-second-attempt-network",
        "unit_id": UID,
        "pass": True,
        "within_ttl_calls": live["within_ttl_calls"],
        "after_ttl_calls": live["after_ttl_calls"],
        "second_attempt_observed_network": True,
        "first_type": live["first_type"],
        "after_ttl_type": live["after_ttl_type"],
        "observed_calls": live["observed_calls"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"within_ttl_calls={live['within_ttl_calls']} "
        f"after_ttl_calls={live['after_ttl_calls']} "
        f"second_attempt_network=True type={live['after_ttl_type']}"
    )
    print("SUCCESS:TST-0176-probe1 second attempt observed on the network after negative-ttl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
