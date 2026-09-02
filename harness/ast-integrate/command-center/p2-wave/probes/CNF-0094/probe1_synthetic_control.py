#!/usr/bin/env python3
"""Named probe 1: synthetic control vs independently stored hand-computed fractions.

Mechanism: exact Fraction equality on Brier/accuracy/mean-p/counts.
Does not implement the weighted-as-unweighted detector (that is probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import recompute as R  # noqa: E402
import schema_ctl as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0094-council-calibration-recompute.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0094 emitted only when"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0094-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0094":
        print("FAILED:CNF-0094-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0094-probe1 self-declared", doc.get("state"))
        return 1
    if SENTINEL_PREFIX not in json.dumps(doc):
        print("FAILED:CNF-0094-probe1 sentinel absent")
        return 1

    run = R.load_run(HERE / "fixtures" / "synthetic-control.json")
    hand = json.loads((HERE / "fixtures" / "hand_computed.json").read_text(encoding="utf-8"))
    scores = R.score_run(run)
    if not scores.weight_conserved:
        print("FAILED:CNF-0094-probe1 weight not conserved")
        return 1
    cmp = R.compare_to_hand(scores, hand)
    if not cmp["matched"]:
        print("FAILED:CNF-0094-probe1 hand-computed mismatch")
        print(json.dumps(cmp, indent=2))
        return 1
    payload = S.payload(doc)
    if not payload.get("synthetic_control", {}).get("matched"):
        print("FAILED:CNF-0094-probe1 artifact did not record control match")
        return 1

    out = {
        "probe": "probe1-synthetic-control",
        "unit_id": "CNF-0094",
        "matched": True,
        "brier_weighted": str(scores.brier_weighted),
        "brier_unweighted": str(scores.brier_unweighted),
        "scored_n": scores.scored_n,
        "weight_conserved": scores.weight_conserved,
        "pass": True,
    }
    (HERE / "probe1-synthetic-control.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0094-probe1 synthetic hand-computed control matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
