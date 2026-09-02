#!/usr/bin/env python3
"""Named probe 1: every chosen stage cites a benchmark run id.

Live fusion over the complete-evidence fixture. An independent score-only
winner table must match the operator. Mutating a selection record to drop a
run id must make the citation detector fail (detector control).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_forge.best_of_breed import (  # noqa: E402
    ablate_second_best,
    fuse_best_of_breed,
    independent_winners,
    selection_cites_run_ids,
)
import fixtures as F  # noqa: E402

EXPECTED = {
    "retrieve": "wf.source.alpha-retriever",
    "rank": "wf.source.beta-ranker",
    "synthesize": "wf.source.alpha-retriever",
}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0185-probe1 {msg}")
    return 1


def _validate_workflow(workflow: dict) -> list[str]:
    sys.path.insert(0, str(REPO / "command-center" / "schema"))
    import validate_workflow as VW  # noqa: E402

    schema_errs = []
    try:
        import jsonschema

        schema = VW.load_schema()
        schema_errs = [
            e.message for e in jsonschema.Draft7Validator(schema).iter_errors(workflow)
        ]
    except Exception as exc:  # pragma: no cover - environment
        schema_errs = [f"schema-load:{type(exc).__name__}:{exc}"]
    semantic, _ = VW.semantic_validate(workflow)
    return schema_errs + [f"{v['id']}:{v['detail']}" for v in semantic]


def main() -> int:
    srcs = F.sources()
    evidence = F.evidence_complete()
    result = fuse_best_of_breed(srcs, evidence)
    if not result.get("ok"):
        return fail(f"complete evidence refused: {result}")

    selection = result["selection_record"]
    cited = selection_cites_run_ids(selection)
    if not cited["ok"] or cited["cited"] != cited["total"] or cited["total"] != 3:
        return fail(f"run-id coverage {cited}")

    chosen = {row["slot_id"]: row["chosen_source_id"] for row in selection}
    if chosen != EXPECTED:
        return fail(f"chosen {chosen} want {EXPECTED}")

    winners = independent_winners(evidence)
    independent = {
        slot: str(row["source_id"]) for slot, row in winners.items()
    }
    if independent != chosen:
        return fail(f"independent winners {independent} != operator {chosen}")

    for row in selection:
        if not row.get("benchmark_run_id"):
            return fail(f"slot {row['slot_id']} missing run id in record")
        if not row.get("losers"):
            return fail(f"slot {row['slot_id']} missing losing alternative scores")

    sources_used = set(chosen.values())
    if len(sources_used) < 2:
        return fail(f"fusion collapsed to one parent {sources_used}")

    fused = result["workflow"]
    parent_ids = [wf["id"] for wf in srcs]
    if fused["id"] in parent_ids:
        return fail("fused id equals a parent")
    parent_stage_blobs = [
        json.dumps([s.get("tools") for s in wf["stages"]], sort_keys=True) for wf in srcs
    ]
    fused_blob = json.dumps([s.get("tools") for s in fused["stages"]], sort_keys=True)
    if fused_blob in parent_stage_blobs:
        return fail("fused stage-tool vector equals a parent (no-op fusion)")

    wf_errs = _validate_workflow(fused)
    if wf_errs:
        return fail(f"fused workflow invalid {wf_errs[:4]}")

    mutated = copy.deepcopy(selection)
    mutated[0]["benchmark_run_id"] = ""
    mutated_cited = selection_cites_run_ids(mutated)
    if mutated_cited["ok"] or "retrieve" not in mutated_cited["missing_slots"]:
        return fail(f"citation detector silent on dropped run id: {mutated_cited}")

    ablation = ablate_second_best(result, "rank")
    if not ablation["composite_moved"] or ablation["delta"] >= 0:
        return fail(f"rank ablation did not drop score: {ablation}")

    payload = {
        "probe": "probe1-run-ids",
        "unit_id": "IMP-0185",
        "chosen": chosen,
        "cited": cited,
        "independent_match": True,
        "mixed_parents": True,
        "detector_fired_on_dropped_run_id": True,
        "ablation_rank_delta": ablation["delta"],
        "composite_score": result["composite_score"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "cited=3/3 independent_match=True mixed_parents=True "
        f"detector_dropped_run_id=True ablation_delta={ablation['delta']}"
    )
    print("SUCCESS:IMP-0185-probe1 every chosen stage cites a benchmark run id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
