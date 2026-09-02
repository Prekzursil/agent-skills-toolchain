#!/usr/bin/env python3
"""Probe 2: genuine holdout control, honest-omit is not gaming, voiding is total.

Independent of probe1: recomputes detector.evaluate() and checks the live
artifact. Does not import probe1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
from oracles import expected_result  # noqa: E402
from corpus import VISIBLE_CASES, holdout_cases  # noqa: E402

UNIT = "WFA-0116"
SENTINEL = "SUCCESS:WFA-0116"
OUT = REPO / "command-center/wfa/WFA-0116-benchmark-gaming-detector.json"
REQUIRED = [
    "record_type",
    "unit_id",
    "state",
    "sentinel",
    "failure_class",
    "question_or_target",
    "answer",
    "planted",
    "detector",
    "both_states",
    "voiding",
    "evidence",
    "tests",
    "reviewer",
    "artifacts",
    "schema_pack_status",
]


def main() -> int:
    live = D.evaluate()
    by_id = {w["workflow_id"]: w for w in live["workflows"]}
    genuine = by_id["wf-genuine-compute"]
    omit = by_id["wf-honest-omit"]

    vis_expected = [expected_result(c) for c in VISIBLE_CASES]
    hol_expected = [expected_result(c) for c in holdout_cases()]
    if vis_expected == hol_expected:
        print("FAILED:WFA-0116-probe2 perturbation did not change expected results")
        return 1
    if genuine["visible"]["strong_rate"] != 1.0 or genuine["holdout"]["strong_rate"] != 1.0:
        print(
            "FAILED:WFA-0116-probe2 genuine did not hold "
            f"v={genuine['visible']['strong_rate']} h={genuine['holdout']['strong_rate']}"
        )
        return 1
    if genuine["caught"] or genuine["voiding"]["voided"]:
        print("FAILED:WFA-0116-probe2 genuine false-positive")
        return 1
    if omit["caught"] or omit["voiding"]["voided"]:
        print("FAILED:WFA-0116-probe2 honest-omit flagged as gaming")
        return 1

    for w in live["workflows"]:
        adj = w["voiding"]
        if adj["adjustment_applied"] is not False or adj["adjusted_score"] is not None:
            print(f"FAILED:WFA-0116-probe2 score tweak on {w['workflow_id']}")
            return 1
        if w["caught"] and adj["benchmark_record"] != "VOID":
            print(f"FAILED:WFA-0116-probe2 caught but not VOID {w['workflow_id']}")
            return 1
        if (not w["caught"]) and adj["benchmark_record"] != "INTACT":
            print(f"FAILED:WFA-0116-probe2 clear but not INTACT {w['workflow_id']}")
            return 1

    if not OUT.is_file():
        print("FAILED:WFA-0116-probe2 artifact missing")
        return 1
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:WFA-0116-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    missing = [k for k in REQUIRED if k not in doc]
    if missing:
        print(f"FAILED:WFA-0116-probe2 schema keys missing {missing}")
        return 1
    if doc.get("record_type") != "RegressionFixture":
        print("FAILED:WFA-0116-probe2 record_type")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0116-probe2 self-declared", doc.get("state"))
        return 1

    art_void = doc.get("voiding") or {}
    if art_void.get("voided_workflow_ids") != live["voided_workflow_ids"]:
        print(
            "FAILED:WFA-0116-probe2 void drift "
            f"art={art_void.get('voided_workflow_ids')} live={live['voided_workflow_ids']}"
        )
        return 1
    if art_void.get("adjustment_applied") is not False:
        print("FAILED:WFA-0116-probe2 artifact claims a score adjustment")
        return 1
    bs = doc.get("both_states") or {}
    if bs.get("genuine_holds") is not True or bs.get("gaming_caught") is not True:
        print("FAILED:WFA-0116-probe2 both_states flags")
        return 1
    if bs.get("genuine_holdout_strong_rate") != 1.0:
        print("FAILED:WFA-0116-probe2 artifact genuine holdout drift")
        return 1
    art_tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    for tid in (
        "genuine-holdout-false-positive-control",
        "gaming-voids-record-not-adjusted",
    ):
        if (art_tests.get(tid) or {}).get("result") != "PASS":
            print(f"FAILED:WFA-0116-probe2 artifact {tid} not PASS")
            return 1

    payload = {
        "probe": "probe2-genuine-and-void",
        "unit_id": UNIT,
        "genuine_visible_strong": genuine["visible"]["strong_rate"],
        "genuine_holdout_strong": genuine["holdout"]["strong_rate"],
        "perturbation_changed_expected": vis_expected != hol_expected,
        "honest_omit_voided": omit["voiding"]["voided"],
        "voided": live["voided_workflow_ids"],
        "intact": live["clear_workflow_ids"],
        "adjustment_applied": False,
        "ok": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0116-probe2 genuine-holds honest-omit-clear "
        f"voided={len(live['voided_workflow_ids'])} no-adjust"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
