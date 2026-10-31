#!/usr/bin/env python3
"""Shard-22 wave-4 builder: WFA-0114 support files (fixtures).

Re-materializes the recorded-run fixture lost with the prior builder's probe
dir. Per-case integers are RE-DERIVED from the RECORDED component values in
WFA-0114-headtohead-scoring-rubric.json (correctness/coverage/recovery/usability
per arm pin the counts); rubric.py recomputes and must reproduce every recorded
number exactly.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
PD = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0114"
(PD / "fixtures").mkdir(parents=True, exist_ok=True)

MATCHED = ["c01", "c02", "c03", "c04", "c05", "c06"]
CORPUS = MATCHED + ["c07", "c08", "c09", "c10"]


def case(attempted, first, retry, tele):
    """tele = checkpoints+abort+budget_exhausted count (term = 1-min(1,tele/4))."""
    return {"attempted": attempted,
            "first_attempt_oracle": first,
            "retry_oracle": retry,
            "checkpoints": tele, "abort": 0, "budget_exhausted": 0}


def arm_from_pattern(pattern):
    return {cid: case(*row) for cid, row in zip(MATCHED, pattern)}


FP, FF = "pass", "fail"

# fusion_complement sources: source_a c=5/6 cov=6/6 rec=5/6 use=13/24
#   (terms .75,.75,.5,.5,.5,.25 -> 3.25/6); source_b c=3/6 cov=6/6 rec=3/6 use=.375
SRC_A_COMPLEMENT = [
    (True, FF, FP, 1), (True, FF, FP, 1), (True, FF, FP, 2),
    (True, FF, FP, 2), (True, FF, FP, 2), (True, FF, FF, 3),
]
SRC_B_COMPLEMENT = [
    (True, FF, FP, 1), (True, FF, FP, 1), (True, FF, FP, 3),
    (True, FF, FF, 3), (True, FF, FF, 3), (True, FF, FF, 4),
]
# fusion_padded fusion: same recorded components as source_a above
PADDED_FUSION = [
    (True, FF, FP, 1), (True, FF, FP, 1), (True, FF, FP, 2),
    (True, FF, FP, 2), (True, FF, FP, 2), (True, FF, FF, 3),
]

SCEN = {}
# --- fusion_complement: fusion c=1/6 cov=6/6 rec=0/5 use=.5; unique c07-c09
SCEN["fusion_complement"] = {
    "fusion": arm_from_pattern([
        (True, FF, FF, 1), (True, FP, None, 1), (True, FF, FF, 1),
        (True, FF, FF, 3), (True, FF, FF, 3), (True, FF, FF, 3),
    ]),
    "source_a": arm_from_pattern(SRC_A_COMPLEMENT),
    "source_b": arm_from_pattern(SRC_B_COMPLEMENT),
    "fusion_extra_solves": ["c07", "c08", "c09"],
    "source_extra_solves": [],
    "stages": {"fusion": 6, "source_a": 4, "source_b": 3},
}
# --- fusion_no_attempts: fusion all-unattempted; sources c 5/6 & 4/6
SCEN["fusion_no_attempts"] = {
    "fusion": {cid: case(False, None, None, 0) for cid in MATCHED},
    "source_a": arm_from_pattern([
        (True, FF, FP, 1), (True, FF, FP, 1), (True, FF, FP, 3),
        (True, FF, FP, 3), (True, FF, FP, 3), (True, FF, FF, 4),
    ]),
    "source_b": arm_from_pattern([
        (True, FF, FP, 1), (True, FF, FP, 1), (True, FF, FP, 3),
        (True, FF, FP, 3), (True, FF, FF, 3), (False, None, None, 0),
    ]),
    "fusion_extra_solves": [],
    "source_extra_solves": [],
    "stages": {"fusion": 8, "source_a": 4, "source_b": 3},
}
# --- fusion_outperforms: fusion all-first-pass (recovery removed), use=1.0;
#     sources c=6/6 cov=6/6, use 17/24 (5x.75+1x.5) and .375
SCEN["fusion_outperforms"] = {
    "fusion": arm_from_pattern([
        (True, FP, None, 0), (True, FP, None, 0), (True, FP, None, 0),
        (True, FP, None, 0), (True, FP, None, 0), (True, FP, None, 0),
    ]),
    "source_a": arm_from_pattern([
        (True, FF, FP, 1), (True, FF, FP, 1), (True, FF, FP, 1),
        (True, FF, FP, 1), (True, FF, FP, 2), (True, FP, None, 1),
    ]),
    "source_b": arm_from_pattern([
        (True, FF, FP, 1), (True, FF, FP, 1), (True, FF, FP, 3),
        (True, FP, None, 3), (True, FP, None, 3), (True, FP, None, 4),
    ]),
    "fusion_extra_solves": [],
    "source_extra_solves": [],
    "stages": {"fusion": 5, "source_a": 4, "source_b": 3},
}
# --- fusion_padded: fusion rec=0.5 (1 recovered of 2 recoverable), use=.875,
#     stages padded to 12; sources reproduce the same recorded component
#     values as the complement scenario while also failing c02, so the padded
#     clone earns NO unique solve (delta 0) - stage count alone never qualifies
SCEN["fusion_padded"] = {
    "fusion": arm_from_pattern([
        (True, FF, FP, 0), (True, FF, FF, 0), (True, FP, None, 0),
        (True, FP, None, 0), (True, FP, None, 1), (True, FP, None, 2),
    ]),
    "source_a": arm_from_pattern([
        (True, FF, FP, 1), (True, FF, FF, 3), (True, FF, FP, 2),
        (True, FF, FP, 2), (True, FF, FP, 2), (True, FF, FP, 1),
    ]),
    "source_b": arm_from_pattern([
        (True, FF, FP, 1), (True, FF, FF, 4), (True, FF, FP, 3),
        (True, FF, FF, 3), (True, FF, FF, 3), (True, FF, FP, 1),
    ]),
    "fusion_extra_solves": [],
    "source_extra_solves": [],
    "stages": {"fusion": 12, "source_a": 4, "source_b": 3},
}

fixture = {
    "schema_version": 1,
    "unit_id": "WFA-0114",
    "note": (
        "Recorded-run fixture re-derived 2026-10-26 by the shard22 wave-4 builder "
        "from the RECORDED component values in "
        "WFA-0114-headtohead-scoring-rubric.json; the prior builder lost this "
        "fixture with its probe dir."
    ),
    "corpus_ids": CORPUS,
    "matched_intersection": MATCHED,
    "scenarios": SCEN,
    "inter_rater": {
        "scale": [0, 1, 2, 3, 4],
        "high_agreement": {
            "rater_1": [4, 3, 3, 2, 2, 4, 3, 3, 3, 2],
            "rater_2": [4, 3, 3, 2, 2, 4, 3, 3, 3, 2],
        },
        "low_agreement": {
            "rater_1": [4, 0, 4, 0, 4, 0, 4, 0, 4, 0],
            "rater_2": [0, 4, 0, 4, 0, 4, 0, 4, 0, 4],
        },
    },
}
fx_path = PD / "fixtures" / "recorded_runs.json"
fx_path.write_text(json.dumps(fixture, indent=1) + "\n", encoding="utf-8", newline="\n")
print("fixture written", fx_path, fx_path.stat().st_size, "bytes")
