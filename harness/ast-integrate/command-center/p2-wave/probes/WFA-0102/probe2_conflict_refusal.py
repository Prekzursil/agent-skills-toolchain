#!/usr/bin/env python3
"""Named probe 2 (evidence B): HARD conflict pair is refused (both-states).

Good state: compatible alpha+beta unions. Bad state: alpha+gamma (independent
first-pass vs shared-context deliberation, plus replay vs sampling) is refused.
The always-succeed mutant still emits a body — that is the more-stages-is-better
fallacy the spec forbids.

Also: SOFT sequential vs parallel does not refuse; stage-count of a union is not
a value claim (padded stages raise size, not task coverage).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    load_conflict_edges,
    task_mechanisms,
    workflow_alpha,
    workflow_beta,
    workflow_delta,
    workflow_gamma,
)
from fusion_union import (  # noqa: E402
    FusionRefused,
    pad_stages,
    task_benchmark,
    union_always_succeed,
    union_fuse,
)

UNIT = "WFA-0102"
ART = REPO / "command-center/wfa/WFA-0102-fusion-union.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def artifact_status() -> str:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact-missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return "artifact-unparseable"
    if not isinstance(doc, dict):
        return "artifact-not-object"
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return f"self-declared:{st}"
    if "SUCCESS:WFA-0102" not in text:
        return "sentinel-absent"
    return "ok"


def fail(msg: str, payload: dict | None = None) -> int:
    if payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    edges, origin = load_conflict_edges()
    alpha = workflow_alpha()
    beta = workflow_beta()
    gamma = workflow_gamma()
    delta = workflow_delta()
    task = task_mechanisms()

    compatible = union_fuse(alpha, beta, edges=edges)
    refused: FusionRefused | None = None
    illegal_body = None
    try:
        illegal_body = union_fuse(alpha, gamma, edges=edges)
    except FusionRefused as exc:
        refused = exc

    mutant_body = union_always_succeed(alpha, gamma, edges=edges)

    soft_ok = None
    soft_err = None
    try:
        soft_ok = union_fuse(alpha, delta, edges=edges)
    except FusionRefused as exc:
        soft_err = str(exc)

    bm_a = task_benchmark(alpha, task)
    bm_b = task_benchmark(beta, task)
    bm_u = task_benchmark(compatible, task)
    padded = pad_stages(compatible, 4)
    bm_pad = task_benchmark(padded, task)

    larger = bm_u["n_stages"] > bm_a["n_stages"] and bm_u["n_stages"] > bm_b["n_stages"]
    coverage_decides = (
        bm_u["coverage"] >= max(bm_a["coverage"], bm_b["coverage"])
        and bm_pad["coverage"] == bm_u["coverage"]
        and bm_pad["n_stages"] > bm_u["n_stages"]
    )
    size_only_would_prefer_pad = bm_pad["n_stages"] > bm_u["n_stages"]

    qualifications = compatible.get("qualifications") or {}
    q_stages = qualifications.get("stages") or []
    colliding_names = {q["original_id"] for q in q_stages}
    receipt = artifact_status()

    report = {
        "probe": "probe2-conflict-refusal",
        "unit_id": UNIT,
        "conflict_edge_origin": origin,
        "compatible_fused": compatible.get("id"),
        "compatible_stage_count": bm_u["n_stages"],
        "hard_pair_refused": refused is not None,
        "hard_pair_reason": None if refused is None else refused.reason,
        "hard_pair_conflicts": None if refused is None else refused.conflicts,
        "illegal_body_produced": illegal_body is not None,
        "always_succeed_mutant_produced_body": mutant_body is not None,
        "always_succeed_mutant_id": None if mutant_body is None else mutant_body.get("id"),
        "soft_pair_fused": soft_ok is not None,
        "soft_pair_error": soft_err,
        "qualified_original_ids": sorted(colliding_names),
        "benchmark": {
            "alpha": bm_a,
            "beta": bm_b,
            "union": bm_u,
            "padded_union": bm_pad,
            "union_larger_than_sources": larger,
            "coverage_decides_value": coverage_decides,
            "size_only_would_prefer_pad": size_only_would_prefer_pad,
        },
        "artifact": receipt,
        "pass": False,
    }

    ok = (
        refused is not None
        and illegal_body is None
        and mutant_body is not None
        and soft_ok is not None
        and "ingest" in colliding_names
        and "emit" in colliding_names
        and larger
        and coverage_decides
        and size_only_would_prefer_pad
        and bm_u["coverage"] == 1.0
        and receipt == "ok"
    )
    report["pass"] = ok
    print(json.dumps(report, indent=2, sort_keys=True))
    if not ok:
        return fail("conflict refusal or benchmark-size-is-not-value control")
    print(
        f"SUCCESS:{UNIT}-probe2 HARD pair refused; always-succeed mutant still "
        f"emits a body; size-only pad does not raise task coverage"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
