#!/usr/bin/env python3
"""Probe 2: scaling 1x/4x/16x and O(n) vs unbounded-index detector.

Mechanically independent of probe 1 (cold vs warm). Re-runs the live
scaling curve and requires the quadratic mutant to fire so a linear
index build is characterized, not assumed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0239.json"
UID = "TST-0239"
SENTINEL = "SUCCESS:TST-0239"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0239-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UID:
        return fail(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.measure_scaling()
    if not live.get("pass"):
        return fail(f"live scaling did not pass {json.dumps(live)}")
    if live.get("characterization") != "O(n)":
        return fail(f"characterization {live.get('characterization')}")
    if live.get("quadratic_mutant_detected") is not True:
        return fail("quadratic mutant did not fire — detector is inert")
    if live.get("linear_on") is not True:
        return fail("linear path not characterized as O(n)")

    rec = doc.get("scaling") or doc.get("measurements", {}).get("scaling") or {}
    if rec.get("pass") is not True:
        return fail("artifact scaling.pass is not true")
    if rec.get("quadratic_mutant_detected") is not True:
        return fail("artifact quadratic detector did not fire")
    if rec.get("linear_on") is not True:
        return fail("artifact linear_on is not true")
    if rec.get("characterization") != "O(n)":
        return fail(f"artifact characterization {rec.get('characterization')}")
    if list(rec.get("scales") or []) != [1, 4, 16]:
        return fail(f"artifact scales {rec.get('scales')}")
    if int(rec.get("base_n") or 0) != int(live.get("base_n") or -1):
        return fail("base_n drift")

    ans = doc.get("answer") or {}
    if ans.get("index_build_is_unbounded") is not False:
        return fail("artifact claims unbounded index build")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-scaling",
                "unit_id": UID,
                "exponent_1x_16x": live["exponent_1x_16x"],
                "t16_over_t1": live["t16_over_t1"],
                "characterization": live["characterization"],
                "quadratic_mutant_detected": live["quadratic_mutant_detected"],
                "quadratic_exponent_1x_4x": live["quadratic_exponent_1x_4x"],
                "linear_on": live["linear_on"],
            },
            sort_keys=True,
        )
    )
    print(
        f"exp16={live['exponent_1x_16x']} t16/t1={live['t16_over_t1']} "
        f"q_exp4={live['quadratic_exponent_1x_4x']} char={live['characterization']}"
    )
    print("SUCCESS:TST-0239-probe2 scaling O(n) and quadratic-mutant detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
