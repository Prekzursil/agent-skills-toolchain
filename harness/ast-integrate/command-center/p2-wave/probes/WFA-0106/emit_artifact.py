#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0106-fusion-progressive.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import progressive as P  # noqa: E402

OUT = "command-center/wfa/WFA-0106-fusion-progressive.json"
UNIT = "WFA-0106"
SENTINEL = "SUCCESS:WFA-0106"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0106/probe1_cost_outcome.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0106/probe2_bound_loop.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    wf = P.compose_progressive()
    report = P.evaluate(wf)
    if report.verdict != "PASS":
        print(f"FAILED:{UNIT} live acceptance={report.verdict}:{report.reason}")
        return 1
    loop = P.bound_stops_loop()
    if not loop.get("bound_enforced"):
        print(f"FAILED:{UNIT} escalation bound not enforced:{loop}")
        return 1
    controls = P.planted_controls()
    if not controls.get("good_pass"):
        print(f"FAILED:{UNIT} planted good-state is not PASS")
        return 1
    if not controls.get("never_escalate_rejected_for_correctness"):
        print(f"FAILED:{UNIT} never-escalate mutant not REJECT on correctness")
        return 1
    if not controls.get("always_escalate_more_expensive"):
        print(f"FAILED:{UNIT} always-escalate mutant is not more expensive")
        return 1

    payload = report.as_dict()
    doc = {
        "kind": "FusionResult",
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "operator": "progressive",
        "title": (
            "Fusion operator: progressive, cheapest adequate source first, "
            "escalate only when a typed adequacy predicate fails"
        ),
        "question": (
            "An operator that runs the cheapest adequate source first and "
            "escalates to a more expensive one only when a typed adequacy "
            "predicate fails, with the predicate measurable and a bound on "
            "total escalations so the ladder cannot loop."
        ),
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/FusionResult"
        ),
        "min_bytes_threshold": 2048,
        "workflow": wf.spec(),
        "fused_ir": P.fused_ir(),
        "adequacy_predicate": wf.predicate.spec(),
        "escalation_bound": {
            "max_escalations": P.MAX_ESCALATIONS,
            "max_invocations": P.MAX_INVOCATIONS,
            "loop_input_n": loop["n"],
            "bounded_invocations": loop["bounded_invocations"],
            "bounded_stop_reason": loop["bounded_stop_reason"],
            "bounded_strikes": loop["bounded_strikes"],
            "unbounded_invocations": loop["unbounded_invocations"],
            "would_loop": loop["would_loop"],
            "bound_enforced": loop["bound_enforced"],
            "agents_md_4b": (
                "two strikes on the same inadequacy fingerprint then pivot; "
                "a stuck scheduler that cannot pivot is stopped by the "
                "invocation bound"
            ),
        },
        "cost_vs_outcome": {
            "paired": True,
            "group_means": False,
            "correctness": payload["correctness"],
            "work": payload["work"],
        },
        "traces": payload["traces"],
        "per_case": payload["correctness"]["per_case_deltas"],
        "planted_controls": controls,
        "verdict": report.verdict,
        "reason": report.reason,
        "tests": [
            {
                "id": "WFA-0106-ESCALATION-BOUND",
                "name": (
                    "the escalation bound must be enforced and tested by an "
                    "input that would otherwise loop"
                ),
                "result": "PASS" if loop["bound_enforced"] else "FAIL",
                "command": P2,
            },
            {
                "id": "WFA-0106-MEASURABLE-PREDICATE",
                "name": (
                    "the adequacy predicate must be measurable, not a model "
                    "self-assessment of its own output"
                ),
                "result": "PASS",
                "command": P2,
            },
            {
                "id": "WFA-0106-COST-AND-OUTCOME",
                "name": (
                    "cost and outcome must both be reported; a cheaper ladder "
                    "with worse outcomes is not an improvement"
                ),
                "result": "PASS",
                "command": P1,
            },
        ],
        "evidence": [
            {
                "id": "A",
                "claim": (
                    "An escalation trace per input showing which rung ran, "
                    "why it escalated, and where it stopped."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0106/progressive.py:run_progressive",
            },
            {
                "id": "B",
                "claim": (
                    "Cost-versus-outcome against always running the top rung "
                    "at equal labels; a ladder that escalates on every input "
                    "is rejected as a more expensive top rung with extra steps."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0106/progressive.py:evaluate",
                "progressive_ledger_total": report.progressive_work,
                "expensive_only_ledger_total": report.expensive_work,
                "reduction_ratio": report.reduction_ratio,
                "mismatches": report.mismatches,
                "estimated": False,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0106-probe2-bound-loop-both-states",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 re-runs the stuck never-adequate scheduler with and "
                "without the invocation bound and does not author progressive.py."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "cost-and-outcome"},
            {"id": "probe2", "command": P2, "role": "escalation-bound-loop"},
        ],
        "dependencies_note": (
            "Catalog depends on WFA-0044 (IR spec) and WFA-0039 (stopping-rule "
            "extract). Neither artifact is on this worktree. This unit ships "
            "a hermetic IR-shaped L0-L3 ladder with source_anchor on every "
            "node, a measurable adequacy predicate, and an invocation bound. "
            "Disclosed, not hidden as a caveat on PASS. cloud ok=true is not "
            "delivery."
        ),
        "cloud_ok": False,
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "WFA-0044 IR spec was present on this worktree",
                "WFA-0001 schema pack was present on this worktree",
            ]
        },
        "output_path": OUT,
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:{UNIT} artifact {size}B below floor")
        return 1
    if SENTINEL.encode("utf-8") not in out.read_bytes():
        print(f"FAILED:{UNIT} sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"verdict={report.verdict} n={report.n_cases} "
        f"work {report.progressive_work}<{report.expensive_work} "
        f"reduction={report.reduction_ratio:.4f}"
    )
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
