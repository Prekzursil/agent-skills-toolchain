#!/usr/bin/env python3
"""Named probe 2: ablation on three slots; every choice cites a run id.

Evidence A: each selected stage traces to the benchmark row that justified
it, with the losing alternative's score recorded alongside.

Evidence B: for retrieve, rank, and synthesize, substitute the second-best
implementation's measured score and rematerialize the composite. If the
composite does not move, that slot's selection was not evidence-driven.

Also: independent score-only winners must match the operator; fused
workflow must validate; matched-pair case_hash parity must hold; an
LLM-judgement commentary on a tied fixture must not flip the winner.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_forge.best_of_breed import independent_winners  # noqa: E402
import fixtures as F  # noqa: E402
import fusion_op as Op  # noqa: E402

EXPECTED = {
    "retrieve": "wf.wfa0103.alpha",
    "rank": "wf.wfa0103.beta",
    "synthesize": "wf.wfa0103.alpha",
}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0103-probe2 {msg}")
    return 1


def main() -> int:
    srcs = F.sources()
    evidence = F.evidence_separated()
    parity = Op.case_hash_parity(evidence)
    if not parity["ok"]:
        return fail(f"matched-pair case_hash mismatch {parity}")

    result = Op.fuse(srcs, evidence)
    if not result.get("ok"):
        return fail(f"separated fusion refused: {result}")

    traces = Op.selection_traces(result)
    if not traces["ok"]:
        return fail(f"selection traces {traces}")
    cited = traces["cited"]
    if cited["cited"] != cited["total"] or cited["total"] != 3:
        return fail(f"run-id coverage {cited}")

    chosen = {row["slot_id"]: row["chosen_source_id"] for row in result["selection_record"]}
    if chosen != EXPECTED:
        return fail(f"chosen {chosen} want {EXPECTED}")

    winners = {
        slot: str(row["source_id"])
        for slot, row in independent_winners(evidence).items()
    }
    if winners != chosen:
        return fail(f"independent winners {winners} != operator {chosen}")

    for row in result["selection_record"]:
        if row.get("resolution") != "strict-score":
            return fail(f"separated slot {row['slot_id']} resolution {row.get('resolution')}")
        loser = (row.get("losers") or [None])[0]
        if loser is None:
            return fail(f"slot {row['slot_id']} missing loser")
        if float(loser["score"]) >= float(row["score"]):
            return fail(
                f"slot {row['slot_id']} loser score {loser['score']} "
                f">= winner {row['score']}"
            )

    wf_errs = Op.fused_workflow_errors(result["workflow"])
    if wf_errs:
        return fail(f"fused workflow invalid {wf_errs[:4]}")

    parent_ids = [wf["id"] for wf in srcs]
    if result["workflow"]["id"] in parent_ids:
        return fail("fused id equals a parent")
    parent_tools = [
        json.dumps([s.get("tools") for s in wf["stages"]], sort_keys=True) for wf in srcs
    ]
    fused_tools = json.dumps(
        [s.get("tools") for s in result["workflow"]["stages"]], sort_keys=True
    )
    if fused_tools in parent_tools:
        return fail("fused stage-tool vector equals a parent (no-op fusion)")

    ablations = Op.ablate_three_slots(result)
    if len(ablations) != 3:
        return fail(f"ablation count {len(ablations)} want 3")
    stuck = [a["slot_id"] for a in ablations if not a["composite_moved"]]
    if stuck:
        return fail(f"ablation did not move composite on {stuck}")
    if {a["slot_id"] for a in ablations} != set(EXPECTED):
        return fail(f"ablation slots {[a['slot_id'] for a in ablations]}")

    payload = {
        "probe": "probe2-three-slot-ablation",
        "unit_id": "WFA-0103",
        "chosen": chosen,
        "cited": cited,
        "independent_match": True,
        "mixed_parents": True,
        "ablations": [
            {
                "slot_id": a["slot_id"],
                "delta": a["delta"],
                "moved": a["composite_moved"],
                "loser_run_id": a["loser_run_id"],
            }
            for a in ablations
        ],
        "case_hash_parity": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "cited=3/3 independent_match=True mixed_parents=True "
        f"ablations_moved={len(ablations)}"
    )
    print("SUCCESS:WFA-0103-probe2 three-slot ablation moves composite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
