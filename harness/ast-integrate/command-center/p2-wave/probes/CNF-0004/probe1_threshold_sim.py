#!/usr/bin/env python3
"""Probe 1: threshold minus epsilon is silent; plus epsilon fires and lists ids.

The two live simulations must differ. Artifact values must match the engine,
not a stored flag.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import escalate as E  # noqa: E402
from policy_view import fields  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0004-escalation-policy.json"
SENTINEL_HEAD = "SUCCESS:CNF-0004 emitted only when the artifact at output_path exists"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0004-probe1 {msg}")
    return 1


def main() -> int:
    minus, plus = E.epsilon_pair()
    below, above = E.integer_pair()
    at = E.exactly_at()
    print(
        json.dumps(
            {
                "minus_fired": minus.fired,
                "plus_fired": plus.fired,
                "plus_additional": plus.additional_count,
                "plus_requeued_n": len(plus.requeued_ids),
                "differ": E.decisions_differ(minus, plus),
                "integer_below_fired": below.fired,
                "integer_above_fired": above.fired,
                "exactly_at_fired": at.fired,
            },
            sort_keys=True,
        )
    )
    if minus.fired:
        return fail("minus-epsilon fired")
    if minus.requeued_ids or minus.additional_count:
        return fail("minus-epsilon enumerated requeue")
    if not plus.fired:
        return fail("plus-epsilon silent")
    if plus.additional_count <= 0 or not plus.requeued_ids:
        return fail("plus-epsilon did not enumerate requeued ids")
    if set(plus.requeued_ids) != set(E.SYNTH_POPULATION):
        return fail("plus-epsilon requeue is not the whole class")
    extra = [i for i in plus.additional_ids if i in set(E.SYNTH_SAMPLE)]
    if extra:
        return fail("additional_ids includes sample members")
    if not E.decisions_differ(minus, plus):
        return fail("simulations identical")
    if below.fired or at.fired or not above.fired:
        return fail("integer/at-threshold comparison not evaluated")
    if minus.rate == plus.rate:
        return fail("injected rates equal")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL_HEAD not in text:
        return fail("sentinel-absent")
    view = fields(doc)
    sims = view.get("simulations") or {}
    art_minus = sims.get("minus_epsilon") or {}
    art_plus = sims.get("plus_epsilon") or {}
    if art_minus.get("fired") is not False:
        return fail("artifact minus_epsilon.fired")
    if art_plus.get("fired") is not True:
        return fail("artifact plus_epsilon.fired")
    if art_plus.get("requeued_ids") != plus.requeued_ids:
        return fail("artifact plus requeued_ids != live engine")
    if abs(float(art_minus.get("rate")) - float(minus.rate)) > 1e-15:
        return fail("artifact minus rate != live engine")
    if abs(float(art_plus.get("rate")) - float(plus.rate)) > 1e-15:
        return fail("artifact plus rate != live engine")
    if sims.get("differ") is not True:
        return fail("artifact differ flag")
    thr = view.get("threshold") or {}
    if abs(float(thr.get("value")) - E.THRESHOLD) > 1e-15:
        return fail("artifact threshold drifted from engine constant")
    print(
        f"minus_fired={minus.fired} plus_fired={plus.fired} "
        f"plus_additional={plus.additional_count} "
        f"requeued={plus.requeued_ids[:3]}..."
    )
    print("SUCCESS:CNF-0004-probe1 threshold minus/plus epsilon simulations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
