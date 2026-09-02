#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0100-fusion-stage-splice.json (FusionResult)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from decompose import decompose, host_stages_match  # noqa: E402
from ir import untouched_host_stages, validate_ir  # noqa: E402
from scenario import (  # noqa: E402
    DONOR_INDEX,
    INSERT_INDEX,
    declared_insertion,
    host_workflow,
    matching_donor,
    successor_mismatch_donor,
    unsatisfiable_donor,
    write_fixtures,
)
from stage_splice import coerce_splice, stage_splice  # noqa: E402
from typecheck import insertion_type_check  # noqa: E402

OUT = "command-center/wfa/WFA-0100-fusion-stage-splice.json"
SCHEMA_REF = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/FusionResult"
QUESTION = (
    "Implementation target: an operator that inserts a donor workflow's stage "
    "into a host pipeline at a typed insertion point, rewiring inputs and "
    "outputs, and that REFUSES when the donor stage's input type is unsatisfied "
    "at the chosen point rather than coercing it."
)


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write_fixtures()
    host = host_workflow()
    match = matching_donor()
    bad = unsatisfiable_donor()
    bad_succ = successor_mismatch_donor()
    declared = declared_insertion()

    check_good = insertion_type_check(host, match, INSERT_INDEX, DONOR_INDEX)
    check_bad = insertion_type_check(host, bad, INSERT_INDEX, DONOR_INDEX)
    good = stage_splice(host, match, INSERT_INDEX, DONOR_INDEX)
    refused = stage_splice(host, bad, INSERT_INDEX, DONOR_INDEX)
    refused_out = stage_splice(host, bad_succ, INSERT_INDEX, DONOR_INDEX)
    mutant = coerce_splice(host, bad, INSERT_INDEX, DONOR_INDEX)

    if good.get("status") != "emitted" or good.get("fusion") is None:
        print(f"FAILED:WFA-0100 matching insert did not emit: {good.get('reason')}")
        return 1
    if refused.get("status") != "refused" or refused.get("fusion") is not None:
        print("FAILED:WFA-0100 unsatisfiable insert was not a pre-emit refusal")
        return 1
    if refused_out.get("status") != "refused" or refused_out.get("fusion") is not None:
        print("FAILED:WFA-0100 successor mismatch was not a pre-emit refusal")
        return 1
    if mutant.get("fusion") is None:
        print("FAILED:WFA-0100 coerce mutant produced no fusion (detector dead)")
        return 1
    if not check_good.get("ok") or check_bad.get("ok"):
        print("FAILED:WFA-0100 independent checker did not both-states")
        return 1

    fusion = good["fusion"]
    ir = validate_ir(fusion)
    if not ir["ok"]:
        print(f"FAILED:WFA-0100 fused IR invalid: {ir['errors']}")
        return 1
    rows = untouched_host_stages(host, fusion, INSERT_INDEX)
    if any(not r["identical"] for r in rows):
        print("FAILED:WFA-0100 untouched host stages mutated")
        return 1
    dec = decompose(fusion)
    rebuilt = host_stages_match(host, dec)
    if not dec.get("ok") or not rebuilt.get("ok"):
        print("FAILED:WFA-0100 decompose/rehearsal failed")
        return 1

    deps = {
        "WFA-0001": (REPO / "command-center/wfa/schema/wfa-schema-pack.json").is_file(),
        "WFA-0044": (REPO / "command-center/wfa/WFA-0044-workflow-ir-spec.json").is_file(),
        "WFA-0063": (REPO / "command-center/wfa/WFA-0063-fusion-decomposability.json").is_file(),
        "WFA-0081": (REPO / "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json").is_file(),
        "WFA-0094": (REPO / "command-center/wfa/WFA-0094-semantic-diff-engine.json").is_file(),
    }

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    doc = {
        "kind": "FusionResult",
        "id": fusion.get("id"),
        "unit_id": "WFA-0100",
        "operator": "stage-splice",
        "state": "SUCCESS",
        "completion_sentinel": "SUCCESS:WFA-0100",
        "title": "Fusion operator: stage-splice, inserting one workflow's stage into another's pipeline",
        "question_or_target": QUESTION,
        "schema_id": SCHEMA_REF,
        "accepted": True,
        "sources": [host["id"], match["id"]],
        "fused": fusion,
        "insertion": {
            "semantics": "insert-at-index",
            "insert_index": INSERT_INDEX,
            "after_stage_id": declared["after_stage_id"],
            "before_stage_id": declared["before_stage_id"],
            "donor_stage_id": declared["donor_stage_id"],
            "stage_order": [s.get("id") for s in fusion["stages"]],
            "declared_order": declared["expected_order"],
            "order_matches_declaration": [s.get("id") for s in fusion["stages"]]
            == declared["expected_order"],
        },
        "rewire": fusion.get("rewire"),
        "type_satisfaction": {
            "checker": "command-center/p2-wave/probes/WFA-0100/typecheck.py",
            "matching": {
                "ok": check_good.get("ok"),
                "producer_type": check_good.get("producer_type"),
                "donor_input_type": check_good.get("donor_input_type"),
                "predecessor_id": check_good.get("predecessor_id"),
                "successor_id": check_good.get("successor_id"),
            },
            "unsatisfiable": {
                "ok": check_bad.get("ok"),
                "reason": check_bad.get("reason"),
                "producer_type": check_bad.get("producer_type"),
                "donor_input_type": check_bad.get("donor_input_type"),
                "missing_inputs": check_bad.get("missing_inputs"),
            },
            "coercion": False,
        },
        "refusals": [
            {
                "donor_id": bad["id"],
                "status": refused.get("status"),
                "reason": refused.get("reason"),
                "fusion_is_none": refused.get("fusion") is None,
                "trace": refused.get("trace"),
                "note": "donor input_type pixels is unsatisfied at a document seam",
            },
            {
                "donor_id": bad_succ["id"],
                "status": refused_out.get("status"),
                "reason": refused_out.get("reason"),
                "fusion_is_none": refused_out.get("fusion") is None,
                "note": "donor output_type pixels does not rewire into extract's document input",
            },
        ],
        "decomposition": {
            "source_ids": dec.get("source_ids"),
            "host_id": dec.get("host_id"),
            "donor_id": dec.get("donor_id"),
            "spliced_stage_id": dec.get("spliced_stage_id"),
            "host_rehearsal_ok": rebuilt.get("ok"),
            "reconstructed_host_stage_ids": dec.get("reconstructed_host_stage_ids"),
        },
        "untouched_host_stages": rows,
        "ir_validation": ir,
        "worked_splice": {
            "status": good.get("status"),
            "trace": good.get("trace"),
            "fusion_id": fusion.get("id"),
            "host_id": host["id"],
            "donor_id": match["id"],
        },
        "negative_controls": [
            {
                "id": "WFA0100-C1",
                "kind": "both-states-type-satisfaction",
                "silent_on_good": check_good.get("ok") is True and good.get("status") == "emitted",
                "fires_on_bad": check_bad.get("ok") is False and refused.get("status") == "refused",
                "good_state_output": json.dumps(
                    {"status": good.get("status"), "fusion_id": fusion.get("id")},
                    sort_keys=True,
                ),
                "bad_state_output": json.dumps(
                    {"status": refused.get("status"), "reason": refused.get("reason")},
                    sort_keys=True,
                ),
            },
            {
                "id": "WFA0100-C2",
                "kind": "coerce-mutant",
                "description": (
                    "coerce_splice rewrites donor input_type to the producer type "
                    "and emits. The shipped operator refuses with fusion=None. "
                    "The independent checker still reports the original donor as "
                    "unsatisfied."
                ),
                "mutant_emitted": mutant.get("status") == "emitted",
                "mutant_trace": mutant.get("trace"),
                "coerced_input_type": mutant.get("coerced_input_type"),
                "original_input_type": mutant.get("original_input_type"),
            },
        ],
        "tests_required": [
            {
                "id": "refusal-unsatisfiable",
                "result": "PASS" if refused.get("status") == "refused" else "FAIL",
            },
            {
                "id": "decompose-host-donor-ids",
                "result": "PASS"
                if set(dec.get("source_ids") or []) == {host["id"], match["id"]}
                else "FAIL",
            },
            {
                "id": "untouched-host-stages-byte-identical",
                "result": "PASS" if all(r["identical"] for r in rows) else "FAIL",
            },
        ],
        "dependencies_on_this_tree": deps,
        "honesty": {
            "schema_pack_absent": not deps["WFA-0001"],
            "validated_against": "local WorkflowIR subset in probes/WFA-0100/ir.py",
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "WFA-0001 schema pack consumed (absent)",
                "WFA-0044 IR spec consumed (absent); local typed subset used",
                "WFA-0063 / WFA-0081 / WFA-0094 artifacts consumed (absent)",
                "IMP-0182 replace-one-slot splice is this operator (this unit INSERTs)",
            ],
        },
        "operator_module": "command-center/p2-wave/probes/WFA-0100/stage_splice.py",
        "typecheck_module": "command-center/p2-wave/probes/WFA-0100/typecheck.py",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "fusion-engineer",
            "execution_substrate": "linux-local",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "cloud_ok": False,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:WFA-0100 artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
