#!/usr/bin/env python3
"""Probe 2: both-states negative control.

GREEN: live artifact reports WEAK after a literature miss; elicited not promoted.
RED: ADOPTED-despite-miss mutant, and elicited-promoted-to-measured mutant.
Silent-in-both-states is a detector failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import protocol as P  # noqa: E402


def main() -> int:
    if not P.ART.is_file():
        print("FAILED:RES-0182-probe2 artifact missing")
        return 1
    live_doc = P.load_json(P.ART)
    good = P.evaluate(live_doc)
    adopt = P.mutant_adopt_despite_miss(live_doc)
    bad_adopt = P.evaluate(adopt)
    promo = P.mutant_promote_elicited(live_doc)
    bad_promo = P.evaluate(promo)

    adopt_fired = (not bad_adopt["pass"]) and any(
        e in {"literature-miss-adopted", "literature-miss-not-weak", "adoption-drift:ADOPTED!=WEAK"}
        or e.startswith("adoption-drift:")
        or e.startswith("literature-miss")
        for e in bad_adopt["errors"]
    )
    promo_fired = (not bad_promo["pass"]) and any(
        e in {"elicited-promoted", "promotion-rule"} or e.startswith("row-promoted") or e.startswith("nl-promoted")
        for e in bad_promo["errors"]
    )
    payload = {
        "probe": "probe2-negative-control",
        "unit_id": P.UNIT,
        "live_pass": good["pass"],
        "live_errors": good["errors"],
        "adopt_mutant_pass": bad_adopt["pass"],
        "adopt_mutant_errors": bad_adopt["errors"][:8],
        "adopt_fired": adopt_fired,
        "promo_mutant_pass": bad_promo["pass"],
        "promo_mutant_errors": bad_promo["errors"][:8],
        "promo_fired": promo_fired,
        "lit_misses": good.get("lit_misses"),
        "derivation": "mutant-adoption-and-promotion-detector",
    }
    print(json.dumps(payload, sort_keys=True))
    if not good["pass"]:
        print("FAILED:RES-0182-probe2 live rejected")
        return 1
    if bad_adopt["pass"] or bad_promo["pass"]:
        print("FAILED:RES-0182-probe2 mutant accepted (silent in both states)")
        return 1
    if not adopt_fired or not promo_fired:
        print("FAILED:RES-0182-probe2 mutant red for the wrong reason")
        return 1
    print(
        f"fired_on_adopt_mutant={adopt_fired} fired_on_promo_mutant={promo_fired} "
        f"silent_on_good={good['pass']}"
    )
    print("SUCCESS:RES-0182-probe2 both-states literature-miss and promotion guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
