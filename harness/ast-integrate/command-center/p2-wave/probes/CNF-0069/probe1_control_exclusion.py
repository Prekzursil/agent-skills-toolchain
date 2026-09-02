#!/usr/bin/env python3
"""Probe 1: synthetic perfect control, unsettled exclusion, n<5 insufficient-data, schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import control as C  # noqa: E402
import schemautil as SU  # noqa: E402
import scorer as S  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0069-band-calibration.json"
TOL = 1e-12
SENTINEL = (
    "SUCCESS:CNF-0069 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and the synthetic perfectly-calibrated "
    "control returned the expected score, validating the scorer. Any other terminal "
    "state is FAILED:CNF-0069 <classification> with the diagnostic tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0069-probe1 {msg}")
    return 1


def main() -> int:
    perfect = C.make_perfect_set()
    expected = C.expected_brier(perfect)
    observed, n = S.brier_of(perfect)
    if observed is None:
        return fail("control produced no score")
    if abs(observed - expected) > TOL:
        return fail(f"control mismatch expected={expected} observed={observed}")
    scored = S.score(perfect, min_n=5)
    for row in scored["bands"]:
        if row["n_settled"] >= 5 and row["status"] != "scored":
            return fail(f"perfect band {row['band']} not scored")
    print(f"control expected={expected} observed={observed} n={n} match=True")

    bad = C.miscalibrated_set()
    bad_b, _ = S.brier_of(bad)
    if bad_b is None or abs(bad_b - expected) <= TOL:
        return fail("negative control did not differ from expected Brier")
    print(f"negative_control brier={bad_b} differs=True")

    plants = []
    for i in range(4):
        plants.append(
            {
                "id": f"PLANT-UNSETTLED-{i}",
                "band": "likely",
                "outcome": "UNSETTLED",
                "settlement_kind": "unsettled",
            }
        )
    plants.append(
        {
            "id": "PLANT-PARTIAL",
            "band": "likely",
            "outcome": "PARTIAL",
            "settlement_kind": "unsettled",
        }
    )
    for i in range(3):
        plants.append(
            {
                "id": f"PLANT-REMOTE-{i}",
                "band": "remote",
                "outcome": "CONFIRMED" if i < 2 else "REFUTED",
                "settlement_kind": "later-refute",
            }
        )
    planted = S.score(plants, min_n=5)
    if planted["unsettled"]["count"] != 5:
        return fail(f"unsettled count {planted['unsettled']['count']} != 5")
    if planted["brier"]["n"] != 3:
        return fail(f"unsettled leaked into Brier n={planted['brier']['n']}")
    remote = next(b for b in planted["bands"] if b["band"] == "remote")
    if remote["status"] != "insufficient-data" or remote["n_settled"] != 3:
        return fail(f"remote not insufficient-data: {remote}")
    likely = next(b for b in planted["bands"] if b["band"] == "likely")
    if likely["n_settled"] != 0 or likely["n_unsettled"] != 5:
        return fail(f"likely unsettled not counted separately: {likely}")
    # Treating unsettled as misses would change n and the score.
    miss_treated = []
    for p in plants:
        q = dict(p)
        if q["outcome"] in {"UNSETTLED", "PARTIAL"}:
            q["outcome"] = "REFUTED"
        miss_treated.append(q)
    wrong, n_wrong = S.brier_of(miss_treated)
    right, n_right = S.brier_of(plants)
    if n_wrong == n_right:
        return fail("miss-imputation did not change n; exclusion untested")
    if wrong == right:
        return fail("miss-imputation did not change Brier")
    print(
        f"unsettled_excluded count=5 brier_n=3 remote=insufficient-data "
        f"imputed_n={n_wrong} vs honest_n={n_right}"
    )

    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact absent")
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    errs = SU.schema_errors(doc)
    if errs:
        return fail(f"schema-invalid {errs[0]}")
    garbage = SU.validator()
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(garbage.iter_errors(g)):
            return fail("schema-vacuous accepted garbage")
    body = SU.payload(doc)
    ctrl = body.get("control") or {}
    if ctrl.get("match") is not True or ctrl.get("scorer_validated") is not True:
        return fail("artifact control not validated")
    if abs(float(ctrl["expected_brier"]) - expected) > TOL:
        return fail("artifact expected_brier drifted from live control")
    if abs(float(ctrl["observed_brier"]) - expected) > TOL:
        return fail("artifact observed_brier drifted from live control")
    if body.get("unsettled", {}).get("excluded_from_score") is not True:
        return fail("artifact unsettled not excluded")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    kind = body.get("kind") or (doc.get("report") or {}).get("kind")
    if kind != "calibration-report":
        return fail("report.kind is not calibration-report")
    print("artifact schema-valid sentinel-present control-match")
    print("SUCCESS:CNF-0069-probe1 control exclusion insufficient-data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
