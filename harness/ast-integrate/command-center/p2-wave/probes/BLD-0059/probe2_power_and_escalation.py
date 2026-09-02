#!/usr/bin/env python3
"""Probe 2: independent power recompute + escalation both-states.

The catalog reviewer_requirement is that an independent reviewer recomputes the
power calculation from the stated parameters and reaches the same sample size.
This probe does that with the closed-form path, then shows the escalation rule
fires on an over-threshold sample and is silent at and below threshold.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import params as P  # noqa: E402
import simulate as S  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0059.json"


def independent_min_n(p: float, confidence: float) -> int:
    """Recompute n* without calling power.min_sample_size.

    n = ceil(log(1-confidence)/log(1-p)), then walk to the exact inequality.
    """
    n = int(math.ceil(math.log(1.0 - confidence) / math.log(1.0 - p)))
    n = max(n, 1)
    miss = 1.0 - p
    budget = 1.0 - confidence

    def miss_n(k: int) -> float:
        return miss**k

    while miss_n(n) > budget:
        n += 1
    while n > 1 and miss_n(n - 1) <= budget:
        n -= 1
    return n


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0059-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:BLD-0059-probe2 self-declared", doc.get("state"))
        return 1
    if P.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0059-probe2 sentinel absent")
        return 1

    p = float((doc.get("sampling") or {}).get("prevalence") or P.DESIGN_PREVALENCE)
    conf = float((doc.get("sampling") or {}).get("confidence") or P.CLAIMED_CONFIDENCE)
    rec_n = int((doc.get("sampling") or {}).get("n_per_stratum") or 0)
    live_n = independent_min_n(p, conf)
    print(f"independent n*={live_n} receipt n*={rec_n} p={p} confidence={conf}")
    if live_n != rec_n:
        print("FAILED:BLD-0059-probe2 independent n does not match receipt")
        return 1
    if live_n != 14:
        print("FAILED:BLD-0059-probe2 expected n=14")
        return 1
    miss_13 = (1.0 - p) ** 13
    miss_14 = (1.0 - p) ** 14
    print(f"hand_check miss_13={miss_13:.12f} miss_14={miss_14:.12f}")
    if miss_13 <= (1.0 - conf) or miss_14 > (1.0 - conf):
        print("FAILED:BLD-0059-probe2 hand-check inequality")
        return 1

    theta = P.ESCALATION_THRESHOLD
    over = S.escalation_fixture(14, 3, theta)
    under = S.escalation_fixture(14, 0, theta)
    exact = S.escalation_fixture(20, 1, theta)
    just_over = S.escalation_fixture(20, 2, theta)
    print(
        f"over 3/14 rate={over['sample_error_rate']:.4f} fired={over['fired']}"
    )
    print(f"under 0/14 fired={under['fired']}")
    print(f"exact 1/20=0.05 fired={exact['fired']}")
    print(f"just_over 2/20 fired={just_over['fired']}")
    if not over["fired"]:
        print("FAILED:BLD-0059-probe2 over-threshold sample did not fire")
        return 1
    if under["fired"]:
        print("FAILED:BLD-0059-probe2 zero-error sample fired")
        return 1
    if exact["fired"]:
        print("FAILED:BLD-0059-probe2 exact-threshold sample fired (must be silent)")
        return 1
    if not just_over["fired"]:
        print("FAILED:BLD-0059-probe2 just-over-threshold sample did not fire")
        return 1

    esc = (doc.get("sampling") or {}).get("escalation") or {}
    if esc.get("exactly_at_threshold_fires") is not False:
        print("FAILED:BLD-0059-probe2 receipt did not pin exact-threshold silence")
        return 1
    if abs(float(esc.get("threshold") or 0) - theta) > 1e-12:
        print("FAILED:BLD-0059-probe2 receipt threshold drift")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("verdict") != "PASS":
        print("FAILED:BLD-0059-probe2 reviewer field")
        return 1
    if int(rev.get("recomputed_n") or 0) != live_n:
        print("FAILED:BLD-0059-probe2 reviewer recomputed_n drift")
        return 1

    print("SUCCESS:BLD-0059-probe2 independent power recompute and escalation both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
