#!/usr/bin/env python3
"""Named probe 1: every stage proof obligation has a named script/test id and goes green.

Reads proof_evaluator / proof_test_id / gate predicate booleans. Probe 2 reads git
tree equality after revert — a different field. Unnamed-evaluator plant must be caught.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gates import check_testability, run_all_gates, unnamed_gate_plant_caught  # noqa: E402
from stages import GATES_REL, STAGES  # noqa: E402

ART = REPO / "command-center/phase3/A9/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0063-probe1 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0063":
        print("FAILED:ARC-0063-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:ARC-0063" not in text:
        print("FAILED:ARC-0063-probe1 sentinel absent")
        return 1
    if doc.get("release_mode") != "PR-ONLY":
        print("FAILED:ARC-0063-probe1 release_mode not PR-ONLY")
        return 1
    stages = doc.get("stages") or []
    if len(stages) < 7:
        print(f"FAILED:ARC-0063-probe1 stages={len(stages)} want>=7")
        return 1
    live = run_all_gates("S7")
    testability = check_testability(stages)
    unnamed_caught = unnamed_gate_plant_caught(stages)
    if not live.get("pass"):
        print("FAILED:ARC-0063-probe1 live gates")
        print(json.dumps(live, indent=2, default=str)[:3000])
        return 1
    if not testability.get("pass"):
        print("FAILED:ARC-0063-probe1 artifact stages not testable")
        print(json.dumps(testability, indent=2))
        return 1
    if not unnamed_caught:
        print("FAILED:ARC-0063-probe1 unnamed-gate plant was not caught")
        return 1
    for row in stages:
        if str(row.get("proof_evaluator") or "").replace("\\", "/") != GATES_REL:
            print("FAILED:ARC-0063-probe1 evaluator path drift", row.get("id"))
            return 1
        if str(row.get("lands_via") or "") != "pull-request":
            print("FAILED:ARC-0063-probe1 stage not a PR", row.get("id"))
            return 1
        cmds = row.get("rollback_commands") or []
        if len(cmds) < 3 or not any("revert" in c for c in cmds):
            print("FAILED:ARC-0063-probe1 rollback not a command sequence", row.get("id"))
            return 1
        pred = str(row.get("proof_predicate") or "")
        if len(pred) < 16:
            print("FAILED:ARC-0063-probe1 proof_predicate missing", row.get("id"))
            return 1
    tests_block = doc.get("tests")
    if isinstance(tests_block, dict):
        recorded = tests_block.get("stage_gate_testability") or {}
    else:
        recorded = (doc.get("report") or {}).get("stage_gate_testability") or doc.get("stage_gate_testability") or {}
    if recorded.get("stages_total") != len(stages):
        print("FAILED:ARC-0063-probe1 artifact stages_total drift")
        return 1
    if recorded.get("stages_with_named_evaluator") != len(stages):
        print("FAILED:ARC-0063-probe1 artifact named-evaluator drift")
        return 1
    if recorded.get("unnamed_gate_plant_caught") is not True:
        print("FAILED:ARC-0063-probe1 artifact missing unnamed plant catch")
        return 1
    if recorded.get("pass") is not True:
        print("FAILED:ARC-0063-probe1 artifact test not pass")
        return 1
    rows = doc.get("capability_to_authority") or []
    classes = [r.get("capability_class") for r in rows]
    if len(classes) != len(set(classes)):
        print("FAILED:ARC-0063-probe1 duplicate capability_class in authority table")
        return 1
    authorities = [r.get("authority") for r in rows]
    if len(authorities) != len(set(authorities)):
        print("FAILED:ARC-0063-probe1 duplicate authority tokens")
        return 1

    out = {
        "probe": "probe1-stage-gate-testability",
        "unit_id": "ARC-0063",
        "stages_total": len(stages),
        "stages_with_named_evaluator": testability["stages_with_named_evaluator"],
        "unnamed_gate_plant_caught": True,
        "duplicate_authority_plant_caught": live.get("duplicate_authority_plant_caught"),
        "files_failed": [],
        "pass": True,
        "field": "proof_evaluator+gate-predicate-boolean",
    }
    print(json.dumps(out, sort_keys=True))
    for rec in live["gate_results"]:
        print(
            f"stage {rec['stage_id']} pass={rec.get('pass')} "
            f"test_id={rec.get('proof_test_id')}"
        )
    print("SUCCESS:ARC-0063-probe1 stage-gate testability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
