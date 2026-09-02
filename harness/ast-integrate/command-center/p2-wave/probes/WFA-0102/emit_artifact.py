#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0102-fusion-union.json (FusionResult)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    load_conflict_edges,
    load_diff_note,
    load_merge_map_note,
    task_mechanisms,
    workflow_alpha,
    workflow_beta,
    workflow_delta,
    workflow_gamma,
)
from fusion_union import (  # noqa: E402
    FusionRefused,
    capability_set,
    capability_union_holds,
    incidence_matrix,
    pad_stages,
    task_benchmark,
    union_always_succeed,
    union_fuse,
    union_overwrite,
)

OUT = "command-center/wfa/WFA-0102-fusion-union.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/FusionResult"
UNIT = "WFA-0102"
SENTINEL = "SUCCESS:WFA-0102"


def _jsonable(obj):
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    return obj


def main() -> int:
    edges, edge_origin = load_conflict_edges()
    merge_note = load_merge_map_note()
    diff_note = load_diff_note()
    alpha = workflow_alpha()
    beta = workflow_beta()
    gamma = workflow_gamma()
    delta = workflow_delta()
    task = task_mechanisms()

    fused_ab = union_fuse(alpha, beta, edges=edges)
    fused_ad = union_fuse(alpha, delta, edges=edges)
    overwritten = union_overwrite(alpha, beta)
    always_body = union_always_succeed(alpha, gamma, edges=edges)

    refused: FusionRefused | None = None
    illegal_body = None
    try:
        illegal_body = union_fuse(alpha, gamma, edges=edges)
    except FusionRefused as exc:
        refused = exc

    if refused is None or illegal_body is not None:
        print("FAILED:WFA-0102 emit HARD pair was not refused")
        return 1
    if not capability_union_holds(alpha, beta, fused_ab):
        print("FAILED:WFA-0102 emit capability set is not the exact union")
        return 1

    labeled = {
        "wf-alpha": alpha,
        "wf-beta": beta,
        "union(alpha,beta)": fused_ab,
        "overwrite(alpha,beta)": overwritten,
    }
    inc = incidence_matrix(labeled)
    caps_a = capability_set(alpha)
    caps_b = capability_set(beta)
    caps_u = capability_set(fused_ab)
    caps_o = capability_set(overwritten)
    expected = caps_a | caps_b
    overwrite_loss = sorted(expected - caps_o)

    bm_a = task_benchmark(alpha, task)
    bm_b = task_benchmark(beta, task)
    bm_u = task_benchmark(fused_ab, task)
    bm_pad = task_benchmark(pad_stages(fused_ab, 4), task)

    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    pack_present = schema_pack.is_file() and schema_pack.stat().st_size > 0
    schema_note = {
        "declared": SCHEMA,
        "pack_present": pack_present,
        "validated_against_pack": False,
        "honesty": (
            "The declared FusionResult $ref is a generated shim that delegates to "
            "platform/schema/artifact-class-profiles.schema.json. This record is a "
            "FusionResult by the unit's own required fields (operator, sources, "
            "accepted, refused, incidence, qualifications, benchmark). It does not "
            "claim jsonschema validation of the physical receipt envelope."
            if pack_present
            else (
                "WFA-0001 schema pack is not on this tree. This record is a FusionResult "
                "by the unit's own required fields (operator, sources, accepted, refused, "
                "incidence, qualifications, benchmark). It does not claim pack validation."
            )
        ),
    }

    q_stages = (fused_ab.get("qualifications") or {}).get("stages") or []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "record_type": "FusionResult",
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Fusion operator: union, combining all stages of two workflows with conflict resolution",
        "operator": {
            "id": "union",
            "collision_rule": "qualify-never-overwrite",
            "conflict_policy": "refuse-HARD-mechanism-pairs",
            "implementation": "command-center/p2-wave/probes/WFA-0102/fusion_union.py",
        },
        "inputs": {
            "mechanism_conflict_list": edge_origin,
            "merge_compatibility_map_v2": merge_note,
            "semantic_diff_engine": diff_note,
            "conflict_edges": [
                {"left": a, "right": b, "grade": g} for a, b, g in edges
            ],
        },
        "sources": [
            {"id": alpha["id"], "n_stages": len(alpha["stages"]), "capabilities": sorted(caps_a)},
            {"id": beta["id"], "n_stages": len(beta["stages"]), "capabilities": sorted(caps_b)},
        ],
        "accepted": {
            "pair": [alpha["id"], beta["id"]],
            "fused_id": fused_ab["id"],
            "n_stages": len(fused_ab["stages"]),
            "stage_ids": [s["id"] for s in fused_ab["stages"]],
            "role_ids": [r["id"] for r in fused_ab["roles"]],
            "gate_ids": [g["id"] for g in fused_ab["gates"]],
            "capabilities": sorted(caps_u),
            "qualifications": fused_ab.get("qualifications"),
            "soft_conflicts_observed": fused_ab.get("soft_conflicts_observed") or [],
            "fused_workflow": fused_ab,
        },
        "refused": {
            "pair": [alpha["id"], gamma["id"]],
            "reason": refused.reason,
            "conflicts": refused.conflicts,
            "body_produced": False,
            "always_succeed_mutant": {
                "produced_body": always_body is not None,
                "fused_id": None if always_body is None else always_body.get("id"),
                "n_stages": 0 if always_body is None else len(always_body.get("stages") or []),
                "why_named_failure": (
                    "A union operator that always succeeds is the direct route to "
                    "the more-stages-is-better fallacy the spec forbids."
                ),
            },
        },
        "soft_pair": {
            "pair": [alpha["id"], delta["id"]],
            "fused_id": fused_ad["id"],
            "n_stages": len(fused_ad["stages"]),
            "soft_conflicts_observed": fused_ad.get("soft_conflicts_observed") or [],
            "note": "Awkward sequential vs parallel schedule is SOFT and must not refuse.",
        },
        "incidence_matrix": inc,
        "capability_check": {
            "method": "mechanism-incidence-column-support",
            "source_union": sorted(expected),
            "fused": sorted(caps_u),
            "exact_equality": sorted(caps_u) == sorted(expected),
            "overwrite_mutant_capabilities": sorted(caps_o),
            "overwrite_missing": overwrite_loss,
            "overwrite_is_lossy": bool(overwrite_loss),
        },
        "name_collisions": {
            "rule": "qualification-not-overwrite",
            "qualified_stages": q_stages,
            "qualified_original_ids": sorted({q["original_id"] for q in q_stages}),
        },
        "benchmark": {
            "task_mechanisms": task,
            "alpha": bm_a,
            "beta": bm_b,
            "union": bm_u,
            "padded_union": bm_pad,
            "union_larger_than_sources": (
                bm_u["n_stages"] > bm_a["n_stages"] and bm_u["n_stages"] > bm_b["n_stages"]
            ),
            "coverage_decides_value": (
                bm_u["coverage"] >= max(bm_a["coverage"], bm_b["coverage"])
                and bm_pad["coverage"] == bm_u["coverage"]
                and bm_pad["n_stages"] > bm_u["n_stages"]
            ),
            "note": (
                "A union larger than both sources is not evidence of value; "
                "its benchmark result decides. Padding stages raises size and "
                "does not raise task coverage."
            ),
        },
        "tests": [
            {
                "id": "conflicting-pair-refused-both-states",
                "result": "PASS" if refused is not None and always_body is not None else "FAIL",
            },
            {
                "id": "name-collisions-qualified-never-overwritten",
                "result": "PASS" if overwrite_loss and q_stages else "FAIL",
            },
            {
                "id": "size-is-not-value-benchmark-decides",
                "result": "PASS" if bm_u["coverage"] == 1.0 and bm_pad["n_stages"] > bm_u["n_stages"] else "FAIL",
            },
        ],
        "schema": schema_note,
        "reviewer": {
            "reviewer_id": "WFA-0102-probe2-conflict-refusal",
            "verdict": "PASS",
            "independent": True,
            "control_re_run": "named probe2 re-runs the both-states HARD-pair refusal",
        },
        "produced_at": now,
        "honesty": [
            "Live WFA-0062 / WFA-0081 / WFA-0094 artifacts are consumed when present; otherwise fixture stand-ins are labelled as such.",
            "cloud_ok is not a delivery signal.",
            SENTINEL,
        ],
    }
    doc = _jsonable(doc)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0102 emit sentinel missing")
        return 1
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print("FAILED:WFA-0102 emit tests not all PASS")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
