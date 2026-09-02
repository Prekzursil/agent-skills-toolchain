#!/usr/bin/env python3
"""Probe 2: always-top-3 baseline-defeat + both-states easy-corpus control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import baseline as B  # noqa: E402
import schema_util as SU  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0398.json"
SENTINEL = "SENTINEL:IMP-0398:ROUTER-CORPUS-BASELINE-DEFEATING"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0398-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    try:
        report = SU.report_of(doc)
    except ValueError as exc:
        return fail(str(exc))
    queries = list(report.get("queries") or [])
    pop = report.get("popularity") or {}
    caps = list(pop.get("capabilities") or [])
    top3 = B.top3_from_caps(caps)
    declared_top3 = list(pop.get("top3") or [])
    if top3 != declared_top3:
        return fail(f"top3 recomputed={top3} declared={declared_top3}")
    if top3 != list((report.get("baseline") or {}).get("top3") or []):
        return fail("baseline.top3 disagrees with popularity.top3")

    scored = B.score_corpus(queries, top3)
    base = report.get("baseline") or {}
    if "declared_floor" not in base:
        return fail("declared_floor missing")
    floor = float(base["declared_floor"])
    if not (0.05 <= floor <= 0.35):
        return fail(f"declared_floor={floor} outside [0.05, 0.35]")
    if "score" not in base:
        return fail("baseline.score missing")
    declared_score = float(base["score"])
    if abs(scored["score"] - declared_score) > 1e-9:
        return fail(f"score mismatch live={scored['score']} declared={declared_score}")
    if scored["score"] >= floor:
        return fail(f"corpus-too-easy score={scored['score']} floor={floor}")
    if not (report.get("baseline") or {}).get("defeated"):
        return fail("baseline.defeated is not true")

    # Metric vacuity: a NEGATIVE row must be an exact-match miss against top-3.
    neg = next(
        q for q in queries if str(q.get("polarity") or "").upper() == "NEGATIVE"
    )
    if B.exact_match(neg.get("expected_capability_ids") or [], top3):
        return fail("negative query exact-matched top-3 (metric vacuous)")
    if B.jaccard(neg.get("expected_capability_ids") or [], top3) != 0.0:
        return fail("negative query jaccard is not 0 against top-3")

    # Popularity must not be the gold-label histogram (popularity-bias gaming).
    label_top = B.label_frequency_top3(queries)
    if set(label_top) == set(top3):
        return fail("usage top-3 equals label-frequency top-3")

    easy = B.score_corpus(B.easy_mutant(queries, top3), top3)
    if easy["score"] < floor:
        return fail(
            f"easy mutant score={easy['score']} < floor (detector silent on too-easy)"
        )

    out = {
        "pass": True,
        "probe": "probe2-baseline-defeat",
        "unit_id": "IMP-0398",
        "top3": top3,
        "score": scored["score"],
        "mean_jaccard": scored["mean_jaccard"],
        "n_exact_hits": scored["n_exact_hits"],
        "declared_floor": floor,
        "defeated": True,
        "easy_mutant_score": easy["score"],
        "label_frequency_top3": label_top,
        "negative_is_miss": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"score={scored['score']:.4f} floor={floor} easy={easy['score']:.4f} "
        f"top3={top3} label_top3={label_top}"
    )
    print("SUCCESS:IMP-0398-probe2 always-top-3 baseline defeated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
