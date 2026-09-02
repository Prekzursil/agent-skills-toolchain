#!/usr/bin/env python3
"""Probe 2: a refining council must NOT fire.

Negative control plus the labelled repetition-vs-refinement sample
(evidence requirement 2). Also asserts that a round adding evidence but
no new claims is treated as gain.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from corpus import labelled_pairs, recorded_councils  # noqa: E402
from tools.council.antifail.no_gain import (  # noqa: E402
    classify_relation,
    evaluate_council,
)

UNIT = "IMP-0322"


def main() -> int:
    councils = {c["id"]: c for c in recorded_councils()}
    refining = councils["C09-progressive-refinement"]
    evidence_only = councils["C11-evidence-only"]

    ref_result = evaluate_council(refining)
    if ref_result["fired"]:
        print(f"FAILED:{UNIT}-probe2 refining council fired")
        print(json.dumps(ref_result, indent=2)[:4000])
        return 1

    silent = [c for c in recorded_councils() if c.get("expect_fire") is False]
    false_pos = []
    for council in silent:
        got = evaluate_council(council)
        if got["fired"]:
            false_pos.append({"id": council["id"], "reason": got.get("reason")})
    if false_pos:
        print(f"FAILED:{UNIT}-probe2 false positives {len(false_pos)}")
        print(json.dumps(false_pos, indent=2)[:4000])
        return 1

    ev_result = evaluate_council(evidence_only)
    if ev_result["fired"]:
        print(f"FAILED:{UNIT}-probe2 evidence-only council fired")
        print(json.dumps(ev_result, indent=2)[:4000])
        return 1
    later = ev_result["per_round"][1:]
    if not later or any(r["new_claim_count"] != 0 for r in later):
        print(f"FAILED:{UNIT}-probe2 evidence-only later rounds grew claims")
        return 1
    if any(r["new_evidence_count"] < 1 or r["gain"] is not True for r in later):
        print(f"FAILED:{UNIT}-probe2 evidence without new claims was not gain")
        print(json.dumps(ev_result["per_round"], indent=2)[:4000])
        return 1

    pairs = labelled_pairs()
    scored = []
    correct = 0
    for pair in pairs:
        predicted = classify_relation(pair["old"], pair["new"])
        want = pair["label"]
        ok = predicted == want
        if ok:
            correct += 1
        scored.append(
            {
                "id": pair["id"],
                "label": want,
                "predicted": predicted,
                "ok": ok,
            }
        )
    rate = correct / len(pairs) if pairs else 0.0
    if rate < 0.85:
        print(f"FAILED:{UNIT}-probe2 discrimination rate {rate:.3f} < 0.85")
        print(json.dumps(scored, indent=2))
        return 1

    summary = {
        "probe": "probe2-refining-must-not-fire",
        "unit_id": UNIT,
        "pass": True,
        "refining_fired": False,
        "false_positives": 0,
        "silent_total": len(silent),
        "evidence_only_fired": False,
        "evidence_without_new_claims_is_gain": True,
        "labelled_n": len(pairs),
        "labelled_correct": correct,
        "discrimination_rate": rate,
        "labelled_sample": scored,
        "refining_per_round": ref_result["per_round"],
        "evidence_only_per_round": ev_result["per_round"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        f"refining_silent=True evidence_only_gain=True "
        f"discrimination={correct}/{len(pairs)}={rate:.3f} "
        f"false_pos=0/{len(silent)}"
    )
    print(f"SUCCESS:{UNIT}-probe2 refining council must NOT fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
