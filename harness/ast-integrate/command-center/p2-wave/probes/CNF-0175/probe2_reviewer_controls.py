#!/usr/bin/env python3
"""Named probe 2: reviewer fourth seed, closest cases, empty/weak/planted controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fusion_core as fc  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0175.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0175-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0175" not in json.dumps(doc):
        print("FAILED:CNF-0175-probe2 sentinel absent")
        return 1
    src_fp = (doc.get("source_probe") or {}).get("fingerprint")
    ver_fp = (doc.get("verifier_probe") or {}).get("fingerprint")
    if not src_fp or not ver_fp or src_fp == ver_fp:
        print("FAILED:CNF-0175-probe2 fingerprints missing or identical")
        return 1

    refuse = fc.refuse_empty_run([])
    empty = fc.empty_input_control()
    if refuse.get("green") is not False or not empty.get("ok"):
        print("FAILED:CNF-0175-probe2 empty-input did not refuse")
        return 1

    cases = fc.matched_cases()
    by_id = {c["id"]: c for c in cases}
    recorded_closest = list(doc["tests"]["reviewer_closest_cases"])
    rows0 = fc.run_matrix(
        (fc.CONFIRM_SEEDS[0],),
        [fc.SUBSTRATE_INPROCESS],
        [fc.FUSION, fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C],
    )
    margins0 = fc.per_case_margins(rows0, fc.CONFIRM_SEEDS[0], fc.SUBSTRATE_INPROCESS)
    closest = fc.closest_cases(margins0, n=2)
    if closest != recorded_closest:
        print("FAILED:CNF-0175-probe2 closest-case drift", closest, recorded_closest)
        return 1
    subset = [by_id[i] for i in closest]
    review_rows = fc.run_matrix(
        (fc.REVIEWER_SEED,),
        [fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS],
        [fc.FUSION, fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C],
        cases=subset,
    )
    for sub in (fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS):
        s = fc.summarize_condition(review_rows, fc.REVIEWER_SEED, sub)
        means = s["mean_f1"]
        if not (
            means[fc.FUSION] >= means[fc.SOURCE_A]
            and means[fc.FUSION] >= means[fc.SOURCE_B]
            and means[fc.FUSION] > means[fc.SOURCE_C]
        ):
            print("FAILED:CNF-0175-probe2 fourth-seed fusion lost", sub, means)
            return 1
        if not s["weak_source_loses"]:
            print("FAILED:CNF-0175-probe2 weak source did not lose on reviewer seed")
            return 1
    agree = fc.substrate_agreement(review_rows, (fc.REVIEWER_SEED,))
    if not agree["agree"]:
        print("FAILED:CNF-0175-probe2 reviewer substrates disagree")
        return 1

    planted_rows = fc.run_matrix(
        (fc.CONFIRM_SEEDS[0],),
        [fc.SUBSTRATE_INPROCESS],
        [fc.PLANTED_WORSE, fc.SOURCE_A, fc.SOURCE_B, fc.FUSION],
    )
    means = {}
    for wid in (fc.PLANTED_WORSE, fc.SOURCE_A, fc.SOURCE_B, fc.FUSION):
        vals = [r["f1"] for r in planted_rows if r["workflow_id"] == wid]
        means[wid] = fc.mean(vals)
    if not (
        means[fc.PLANTED_WORSE] < means[fc.SOURCE_A]
        and means[fc.PLANTED_WORSE] < means[fc.SOURCE_B]
        and means[fc.PLANTED_WORSE] < means[fc.FUSION]
    ):
        print("FAILED:CNF-0175-probe2 planted worse fusion not detected", means)
        return 1

    out = {
        "probe": "probe2-reviewer-controls",
        "unit_id": "CNF-0175",
        "closest_cases": closest,
        "reviewer_seed": fc.REVIEWER_SEED,
        "empty_refused": True,
        "weak_loses": True,
        "planted_detected": True,
        "substrate_agree": True,
        "fingerprints_distinct": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0175-probe2 reviewer fourth-seed and controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
