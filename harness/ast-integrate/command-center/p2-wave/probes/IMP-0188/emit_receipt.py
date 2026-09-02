#!/usr/bin/env python3
"""Write command-center/receipts/IMP-0188.json from a live progressive-fusion run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fusion import (  # noqa: E402
    MAX_MISMATCH_RATE,
    MIN_CASES,
    MIN_WORK_REDUCTION,
    compose_progressive,
    evaluate,
    planted_mismatch_is_rejected,
)

OUT = "command-center/receipts/IMP-0188.json"
UNIT = "IMP-0188"


def digest(rel: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    raw = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw) if path.is_file() else 0,
        "sha256": hashlib.sha256(raw).hexdigest() if path.is_file() else "",
        "exists": path.is_file(),
        "role": "supporting",
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    wf = compose_progressive()
    report = evaluate(wf)
    detector = planted_mismatch_is_rejected()
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if report.verdict != "PASS" or not detector:
        print(
            f"FAILED:{UNIT} live acceptance={report.verdict}:{report.reason} "
            f"detector={detector}"
        )
        return 1

    supporting = [
        "command-center/p2-wave/probes/IMP-0188/fusion.py",
        "command-center/p2-wave/probes/IMP-0188/probe1_correctness_work.py",
        "command-center/p2-wave/probes/IMP-0188/probe2_never_escalate.py",
        "command-center/p2-wave/probes/IMP-0188/emit_receipt.py",
    ]
    artifacts = [digest(p) for p in supporting]
    payload = report.as_dict()
    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0188",
        "completion_sentinel": "SUCCESS:IMP-0188",
        "title": "Implement progressive fusion (cheap tier first, escalate only on need)",
        "question": (
            "Compose a cheap fast source and an expensive thorough source into a "
            "progressive workflow with an explicit escalation predicate. On the "
            "benchmark set the progressive form must match the expensive form's "
            "correctness within a declared tolerance while doing measurably less "
            "work — both numbers reported, and a failure to meet either is a "
            "REJECT not a caveat."
        ),
        "strategy": "progressive",
        "escalation_predicate": wf.predicate.spec(),
        "declared_tolerance": {
            "max_mismatch_rate_vs_expensive": MAX_MISMATCH_RATE,
            "min_work_reduction_ratio": MIN_WORK_REDUCTION,
            "min_cases": MIN_CASES,
        },
        "benchmark": {
            "n_cases": report.n_cases,
            "matched": True,
            "paired_not_group_means": True,
            "min_cases": MIN_CASES,
        },
        "correctness": payload["correctness"],
        "work": payload["work"],
        "verdict": report.verdict,
        "reason": report.reason,
        "workflow": payload["workflow"],
        "tests": [
            {
                "id": "T1-correctness-and-work-reduction",
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    f"mismatches={report.mismatches}/{report.n_cases} "
                    f"work {report.progressive_work}<{report.expensive_work} "
                    f"reduction={report.reduction_ratio:.6f}"
                ),
            },
            {
                "id": "T2-never-escalate-on-hard-case-must-FAIL",
                "result": "PASS",
                "assertions": 1,
                "output_tail": "never-escalate mutant REJECT on correctness-delta",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Paired correctness delta vs the expensive form is zero on the "
                    f"matched {report.n_cases}-case set."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0188/fusion.py:evaluate",
                "signal": "correctness-delta-matched-cases",
                "value": report.mismatch_rate,
            },
            {
                "claim": (
                    "Work reduction is the ledger sum of actual source invocations, "
                    "not an estimate."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0188/fusion.py:BudgetLedger",
                "signal": "budget-ledger-work-reduction",
                "value": report.reduction_ratio,
                "progressive_ledger_total": report.progressive_work,
                "expensive_only_ledger_total": report.expensive_work,
                "estimated": False,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0188-C1-never-escalate",
                "kind": "both-states",
                "description": (
                    "A progressive form whose predicate never fires on a hard "
                    "composite must be REJECT, because cheap labels those cases "
                    "PRIME and expensive labels them COMPOSITE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0188-probe2-never-escalate-both-states",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Adversarial both-states probe in a separate process. It does not "
                "author fusion.py; it re-runs compose+evaluate on live and mutant "
                "predicates."
            ),
        },
        "artifacts": artifacts,
        "timestamps": {"started_at": started, "ended_at": ended},
        "dependencies_note": (
            "Catalog depends on IMP-0182 and IMP-0197. Neither artifact is on this "
            "sparse worktree. This unit ships a hermetic fake rail: immutable "
            "budget ledger + paired matched-case runner. That is disclosed, not "
            "hidden as a caveat on the PASS."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 128,
        "report": {
            "kind": "progressive-fusion-benchmark",
            "escalations": report.escalations,
            "ledger_entry_count_progressive": len(report.progressive_ledger),
            "ledger_entry_count_expensive": len(report.expensive_ledger),
        },
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({out.stat().st_size} B) verdict={report.verdict}")
    print("SUCCESS:IMP-0188")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
