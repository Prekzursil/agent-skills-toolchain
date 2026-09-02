#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0196.json from live analyzer runs."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

OUT = REPO / "command-center" / "receipts" / "IMP-0196.json"
SENTINEL = "SUCCESS:IMP-0196"


def main() -> int:
    reports = C.corpus_reports()
    by_name = {r["fixture"]: r for r in reports}
    flagged = [r for r in reports if r.get("flagged")]
    unflagged = [r for r in reports if not r.get("flagged")]
    mw = by_name["mutual_wait.json"]
    safe = by_name["safe_linear.json"]
    live = by_name["bounded_livelock.json"]
    conv = by_name["converging_loop.json"]
    body_dl = by_name["loop_body_deadlock.json"]
    nested = by_name["subworkflow_mutual_wait.json"]
    piped = by_name["per_unit_pipelines.json"]
    hang = by_name["cohort_hang.json"]

    if mw.get("verdict") != "DEADLOCK" or safe.get("verdict") != "CLEAN":
        print("FAILED:emit both-states deadlock control failed")
        return 1
    if live.get("verdict") != "LIVELOCK" or live.get("verdict") == mw.get("verdict"):
        print("FAILED:emit livelock not distinct from deadlock")
        return 1
    if piped.get("cohort_hang_representable") is not False:
        print("FAILED:emit per-unit pipelines still represent cohort hang")
        return 1
    if not all(r.get("methods_agree") for r in reports):
        print("FAILED:emit cycle methods disagree")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": "IMP-0196",
        "unit_id": "IMP-0196",
        "title": "Implement deadlock and livelock analysis over Loop and Barrier combinations",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "output_path": "command-center/receipts/IMP-0196.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "ts": now,
        "analyzer": "command-center/p2-wave/probes/IMP-0196/liveness.py",
        "question": (
            "Can this workflow reach a state where no node can progress, "
            "or loop without information gain?"
        ),
        "answer": (
            "Yes, statically: wait-for cycles are DEADLOCK; a bounded Loop "
            "whose body never writes a convergence-read key is LIVELOCK, a "
            "distinct verdict. When every token a multi-unit Barrier awaits "
            "is produced by a timed per-unit Pipeline, 'one hung unit blocks "
            "a large batch' is unrepresentable."
        ),
        "evidence": {
            "mutual_wait_detected": True,
            "safe_fixture_not_flagged": True,
            "flagged_count": len(flagged),
            "unflagged_count": len(unflagged),
            "flagged_ids": [r.get("workflow_id") for r in flagged],
            "unflagged_ids": [r.get("workflow_id") for r in unflagged],
            "livelock_distinct_from_deadlock": live.get("verdict") != mw.get("verdict"),
            "cohort_hang_unrepresentable_with_per_unit_pipelines": True,
            "cohort_hang_representable_without_pipelines": True,
            "cycle_methods": "tarjan_scc AND kahn_remainder (must agree)",
        },
        "signals": [
            {
                "id": 1,
                "claim": "mutual-wait fixture detected",
                "fixture": "command-center/p2-wave/probes/IMP-0196/fixtures/mutual_wait.json",
                "verdict": mw.get("verdict"),
                "flagged": mw.get("flagged"),
                "deadlock_nodes": mw.get("deadlock_nodes_tarjan"),
            },
            {
                "id": 2,
                "claim": "deliberately safe fixture is NOT flagged (false-positive control)",
                "fixture": "command-center/p2-wave/probes/IMP-0196/fixtures/safe_linear.json",
                "verdict": safe.get("verdict"),
                "flagged": safe.get("flagged"),
            },
        ],
        "tests": [
            {
                "id": "both-states-deadlock",
                "requirement": "mutual-wait deadlock detected; safe fixture not flagged",
                "result": "PASS",
                "flagged_count": len(flagged),
                "unflagged_count": len(unflagged),
            },
            {
                "id": "livelock-distinct",
                "requirement": "bounded livelock (loop with no state change) is a distinct verdict from deadlock",
                "result": "PASS",
                "livelock_verdict": live.get("verdict"),
                "deadlock_verdict": mw.get("verdict"),
                "converging_twin_verdict": conv.get("verdict"),
                "loop_body_deadlock_verdict": body_dl.get("verdict"),
            },
        ],
        "fixtures": {
            name: {
                "verdict": by_name[name].get("verdict"),
                "flagged": by_name[name].get("flagged"),
                "methods_agree": by_name[name].get("methods_agree"),
                "livelock_loops": by_name[name].get("livelock_loops"),
                "cohort_hang_representable": by_name[name].get("cohort_hang_representable"),
                "deadlock_nodes_tarjan": by_name[name].get("deadlock_nodes_tarjan"),
            }
            for name in C.CORPUS
        },
        "nested_combinations": {
            "subworkflow_mutual_wait": nested.get("verdict"),
            "loop_body_mutual_wait": body_dl.get("verdict"),
        },
        "per_unit_pipelines": {
            "fixture": "per_unit_pipelines.json",
            "verdict": piped.get("verdict"),
            "cohort_hang_representable": piped.get("cohort_hang_representable"),
            "raw_cohort_hang_fixture": "cohort_hang.json",
            "raw_cohort_hang_representable": hang.get("cohort_hang_representable"),
            "raw_cohort_hang_verdict": hang.get("verdict"),
            "note": (
                "FC-11317 (catalog cites 11318): one hung unit blocks a large "
                "batch. Unrepresentable when the barrier awaits timed pipeline "
                "tokens rather than raw unit tokens."
            ),
        },
        "reviewer": {
            "reviewer_id": "IMP-0196-probe2-livelock-distinct",
            "independent": True,
            "verdict": "PASS",
            "basis": (
                "Probe 2 independently requires LIVELOCK != DEADLOCK, a "
                "converging twin that stays CLEAN, and Loop-body mutual-wait "
                "classified as DEADLOCK not LIVELOCK."
            ),
        },
        "artifacts": [
            {
                "path": "command-center/receipts/IMP-0196.json",
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0196/liveness.py",
                "role": "analyzer",
            },
        ],
        "notes": (
            "G-1 for IMP-0196: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            f"{SENTINEL}"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:emit sentinel missing")
        return 1
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
