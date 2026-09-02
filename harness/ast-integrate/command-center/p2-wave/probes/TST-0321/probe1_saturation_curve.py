#!/usr/bin/env python3
"""Probe 1: saturation curve to >=10x planned rate; first failure mode named.

1x against stub workers must be healthy (zero 429s). The curve must include
a 10x point. First failure is named, not a bare pass/fail. Receipt must
already exist with SUCCESS:TST-0321.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scheduler import FC_11318, saturation_curve  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0321.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0321-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    if doc.get("unit_id") != "TST-0321":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:TST-0321" not in text:
        return fail("sentinel absent")

    live = saturation_curve(n_per_point=256)
    print(json.dumps({k: live[k] for k in live if k != "points"}, sort_keys=True))
    for p in live["points"]:
        print(
            f"mult={p['offered_mult']} offered={p['offered_rate']} "
            f"completed={p['completed_rate']} n_429={p['n_429']} "
            f"exhausted={p['n_exhausted']} mode={p['failure_mode']} "
            f"invariant={p['invariant_ok']}"
        )

    if not live["healthy_1x"]:
        return fail("1x was not healthy (stagger must prevent 429 at planned rate)")
    if not live["reached_10x"]:
        return fail("curve does not include a 10x offered-rate point")
    if not live["first_failure_mode"]:
        return fail("first failure mode unnamed")
    if live["first_failure_mode"] != FC_11318:
        return fail(
            f"first failure mode {live['first_failure_mode']!r} is not {FC_11318}"
        )
    if live["first_failure_mult"] is None or float(live["first_failure_mult"]) < 2.0:
        return fail(f"first failure mult {live['first_failure_mult']}")
    p10 = next(p for p in live["points"] if float(p["offered_mult"]) >= 10.0)
    if int(p10["n_429"]) <= 0:
        return fail("10x point recorded no 429s; cliff was not observed")
    if not all(p.get("invariant_ok") for p in live["points"]):
        return fail("accounting invariant broken on a curve point")

    sat = doc.get("saturation") or {}
    if sat.get("first_failure_mode") != live["first_failure_mode"]:
        return fail(
            "receipt/live first_failure_mode drift "
            f"receipt={sat.get('first_failure_mode')} live={live['first_failure_mode']}"
        )
    if sat.get("first_failure_mult") != live["first_failure_mult"]:
        return fail(
            "receipt/live first_failure_mult drift "
            f"receipt={sat.get('first_failure_mult')} live={live['first_failure_mult']}"
        )

    tests = doc.get("tests") or []
    t1 = next((t for t in tests if t.get("id") == "saturation-curve-to-10x"), None)
    if not t1 or t1.get("result") != "PASS":
        return fail("receipt did not record saturation-curve-to-10x as PASS")

    print(
        f"first_failure_mode={live['first_failure_mode']} "
        f"first_failure_mult={live['first_failure_mult']} "
        f"healthy_1x={live['healthy_1x']} reached_10x={live['reached_10x']}"
    )
    print("SUCCESS:TST-0321-probe1 saturation curve to 10x; first failure named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
