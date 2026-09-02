#!/usr/bin/env python3
"""Probe 1: constructed looping councils must FIRE.

Also publishes per-round new-claim and new-evidence counts on the 15
recorded councils (evidence requirement 1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from corpus import recorded_councils  # noqa: E402
from tools.council.antifail.no_gain import evaluate_council  # noqa: E402

UNIT = "IMP-0322"


def main() -> int:
    councils = recorded_councils()
    if len(councils) != 15:
        print(f"FAILED:{UNIT}-probe1 corpus size {len(councils)} != 15")
        return 1

    looping = [c for c in councils if c.get("expect_fire") is True]
    silent = [c for c in councils if c.get("expect_fire") is False]
    if len(looping) < 1 or len(silent) < 1:
        print(f"FAILED:{UNIT}-probe1 corpus missing both labels")
        return 1

    rows = []
    misses = []
    for council in councils:
        result = evaluate_council(council)
        fired = bool(result["fired"])
        expect = bool(council["expect_fire"])
        ok = fired is expect
        if not ok:
            misses.append(
                {
                    "id": council["id"],
                    "expect_fire": expect,
                    "fired": fired,
                    "reason": result.get("reason"),
                    "per_round": result.get("per_round"),
                }
            )
        rows.append(
            {
                "id": council["id"],
                "kind": council.get("kind"),
                "expect_fire": expect,
                "fired": fired,
                "fire_round": result.get("fire_round"),
                "per_round": [
                    {
                        "round": r["round"],
                        "new_claim_count": r["new_claim_count"],
                        "refined_claim_count": r["refined_claim_count"],
                        "repeated_claim_count": r["repeated_claim_count"],
                        "new_evidence_count": r["new_evidence_count"],
                        "gain": r["gain"],
                    }
                    for r in result["per_round"]
                ],
            }
        )

    looping_fired = sum(1 for r in rows if r["expect_fire"] and r["fired"])
    looping_total = sum(1 for r in rows if r["expect_fire"])
    if looping_fired != looping_total:
        print(
            f"FAILED:{UNIT}-probe1 looping TPR {looping_fired}/{looping_total}"
        )
        print(json.dumps(misses, indent=2)[:4000])
        return 1

    summary = {
        "probe": "probe1-looping-must-fire",
        "unit_id": UNIT,
        "pass": True,
        "recorded_councils": 15,
        "looping_total": looping_total,
        "looping_fired": looping_fired,
        "true_positive_rate": looping_fired / looping_total,
        "silent_total": sum(1 for r in rows if not r["expect_fire"]),
        "per_council": rows,
        "misses": misses,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        f"looping_fired={looping_fired}/{looping_total} "
        f"recorded=15 misses={len(misses)}"
    )
    print(f"SUCCESS:{UNIT}-probe1 constructed looping council FIRE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
