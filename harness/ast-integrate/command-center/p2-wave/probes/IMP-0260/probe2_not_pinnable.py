#!/usr/bin/env python3
"""Probe 2: seed-ignoring vendor must be NOT-PINNABLE, not claimed deterministic.

Both-states: the honest classifier is silent (NOT-PINNABLE) on a vendor
that exposes a seed and ignores it. A mutant that treats seed_exposed as
proof of determinism labels that vendor PINNED — the control FIREs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.determinism import (  # noqa: E402
    NOT_PINNABLE,
    PINNED,
    SamplingParams,
    SeatSpec,
    SeedHonouringVendor,
    SeedIgnoringVendor,
    classify,
    liar_classify_if_seed_exposed,
    record_seat,
)

RAW = HERE / "probe2-not-pinnable.raw.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0260-probe2 {msg}")
    return 1


def main() -> int:
    ignoring = SeedIgnoringVendor("seed-ignoring-mutant")
    honouring = SeedHonouringVendor("seed-honouring-control")
    spec = SeatSpec(
        "neg-seat",
        ignoring.vendor_id,
        "echo-v1",
        SamplingParams(seed=99, temperature=0.0),
    )
    hon_spec = SeatSpec(
        "pos-seat",
        honouring.vendor_id,
        "echo-v1",
        SamplingParams(seed=99, temperature=0.0),
    )

    honest_bad = record_seat(spec, ignoring, classifier=classify)
    liar_bad = record_seat(spec, ignoring, classifier=liar_classify_if_seed_exposed)
    honest_good = record_seat(hon_spec, honouring, classifier=classify)
    liar_good = record_seat(hon_spec, honouring, classifier=liar_classify_if_seed_exposed)

    if honest_bad["pin_status"] != NOT_PINNABLE:
        return _fail(
            f"honest classifier claimed {honest_bad['pin_status']} on seed-ignoring vendor"
        )
    if honest_bad["pin_reason"] != "seed-ignored":
        return _fail(f"honest reason={honest_bad['pin_reason']}")
    if honest_bad["identical_output_rate"] >= 1.0:
        return _fail("seed-ignoring vendor was identical across repeats")
    if honest_bad["sampling"]["seed"] != 99:
        return _fail("pinned seed was not recorded on the NOT-PINNABLE seat")

    if liar_bad["pin_status"] != PINNED:
        return _fail("liar mutant did not claim PINNED on seed-ignoring vendor")
    if liar_bad["pin_reason"] != "assumed-from-seed-parameter":
        return _fail(f"liar reason={liar_bad['pin_reason']}")

    if honest_good["pin_status"] != PINNED:
        return _fail("honest classifier failed to PIN a seed-honouring vendor")
    if liar_good["pin_status"] != PINNED:
        return _fail("liar disagreed on the honouring vendor (control broken)")

    fired_on_bad = liar_bad["pin_status"] == PINNED and honest_bad["pin_status"] == NOT_PINNABLE
    silent_on_good = honest_good["pin_status"] == PINNED
    if not fired_on_bad:
        return _fail("negative control did not FIRE on seed-ignoring+liar")
    if not silent_on_good:
        return _fail("honest path was not silent on seed-honouring vendor")

    decision = classify(
        seed_exposed=True,
        rate=honest_bad["identical_output_rate"],
    )
    if decision["pin_status"] != NOT_PINNABLE:
        return _fail("classify(seed_exposed, rate<1) did not return NOT-PINNABLE")

    doc = {
        "fired_on_bad": fired_on_bad,
        "honest_ignoring": {
            "pin_reason": honest_bad["pin_reason"],
            "pin_status": honest_bad["pin_status"],
            "rate": honest_bad["identical_output_rate"],
            "seed": honest_bad["sampling"]["seed"],
        },
        "honest_honouring": {
            "pin_reason": honest_good["pin_reason"],
            "pin_status": honest_good["pin_status"],
            "rate": honest_good["identical_output_rate"],
        },
        "liar_ignoring": {
            "pin_reason": liar_bad["pin_reason"],
            "pin_status": liar_bad["pin_status"],
            "rate": liar_bad["identical_output_rate"],
        },
        "pass": True,
        "probe": "probe2-not-pinnable",
        "silent_on_good": silent_on_good,
        "unit_id": "IMP-0260",
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print(
        f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
        f"honest_ignoring={honest_bad['pin_status']} "
        f"liar_ignoring={liar_bad['pin_status']}"
    )
    print("SUCCESS:IMP-0260-probe2 seed-ignoring vendor recorded NOT-PINNABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
