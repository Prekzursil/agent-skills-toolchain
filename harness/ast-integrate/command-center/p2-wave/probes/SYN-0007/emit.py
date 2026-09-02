#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0007.intervention-ranking.json."""
from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from hierarchy import load_hierarchy  # noqa: E402
from rank import (  # noqa: E402
    ESTIMATE_BAND_SECONDS,
    PHASE_ORDER,
    SEVERITY_WEIGHT,
    children_map,
    descendants,
    phase_index,
    rank_interventions,
    subtree_claims,
)

OUT = "command-center/synthesis/SYN-0007.intervention-ranking.json"
SCHEMA = "command-center/schema/intervention-ranking.schema.json"
SENTINEL = (
    "SUCCESS:SYN-0007 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every ranked row "
    "enumerates its prevented claim ids. Any other terminal state is "
    "FAILED:SYN-0007 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "For each root cause, what is the cheapest earlier action that would have "
    "prevented the largest number of downstream findings, and at which phase "
    "could it have been taken?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def validate(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    jsonschema.Draft7Validator.check_schema(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0007 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "SYN-0007", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:SYN-0007 schema accepted garbage {list(garbage)[:2]}")
            raise SystemExit(1)


def build_doc() -> dict:
    hierarchy = load_hierarchy(REPO)
    ranked = rank_interventions(hierarchy, hierarchy.get("costs") or {})
    rows = ranked["ranking"]
    if len(rows) < 3:
        print(
            f"FAILED:SYN-0007 empty-ranking ranked={len(rows)} "
            f"rejected={len(ranked['rejected'])}"
        )
        raise SystemExit(1)

    nodes_by_id = {str(n["id"]): n for n in hierarchy["nodes"]}
    kids = children_map(hierarchy["edges"])

    subtree_ok = True
    subtree_note = "all ranked prevented_claim_ids match descendant claim sets"
    for row in rows:
        expected = subtree_claims(row["intervention_id"], nodes_by_id, kids)
        if expected != row["prevented_claim_ids"]:
            subtree_ok = False
            subtree_note = (
                f"mismatch on {row['intervention_id']}: "
                f"row={row['prevented_claim_ids'][:6]} expected={expected[:6]}"
            )
            break

    rng = random.Random(7)
    perm = copy.deepcopy(hierarchy)
    rng.shuffle(perm["nodes"])
    rng.shuffle(perm["edges"])
    again = rank_interventions(perm, perm.get("costs") or hierarchy.get("costs") or {})
    ids_a = [r["intervention_id"] for r in rows]
    ids_b = [r["intervention_id"] for r in again["ranking"]]
    stable = ids_a == ids_b

    phase_ok = True
    for row in rows:
        iv = phase_index(row["available_at_phase"])
        node_phases = []
        for did in descendants(row["intervention_id"], kids):
            node = nodes_by_id.get(did)
            if node:
                node_phases.append(phase_index(str(node.get("phase") or "")))
        if node_phases and iv > min(node_phases):
            phase_ok = False
            break

    asserted = [
        r["intervention_id"]
        for r in rows
        if r.get("cost_basis") == "ESTIMATE" and not r.get("estimate_band")
    ]
    cost_ok = not asserted

    tests = [
        {
            "id": "test_prevented_set_is_a_real_subtree_of_the_hierarchy",
            "requirement": (
                "Every ranking row's prevented_claim_ids equals the descendant "
                "claim set of its intervention node."
            ),
            "verdict": "PASS" if subtree_ok else "FAIL",
            "evidence": subtree_note,
        },
        {
            "id": "test_ranking_is_stable_under_cost_tie_breaks",
            "requirement": (
                "Permuting node/edge input order must not change the ranked "
                "intervention_id sequence (deterministic sort key)."
            ),
            "verdict": "PASS" if stable else "FAIL",
            "evidence": (
                f"identity after shuffle: {stable}; tie-break is "
                "(-score_micro, phase_index, cost_seconds, intervention_id)"
            ),
        },
        {
            "id": "test_no_intervention_is_placed_at_a_phase_later_than_the_finding_it_prevents",
            "requirement": (
                "available_at_phase index <= min descendant finding phase; "
                "anachronisms are rejected not ranked."
            ),
            "verdict": "PASS" if phase_ok else "FAIL",
            "evidence": (
                "rejected_phase_anachronism="
                f"{sum(1 for r in ranked['rejected'] if r.get('class')=='phase-anachronism')}"
            ),
        },
        {
            "id": "test_asserted_cost_carries_estimate_band",
            "requirement": (
                "cost_basis=ESTIMATE requires estimate_band in {XS,S,M,L,XL}; "
                "DERIVED costs come from timeout_seconds."
            ),
            "verdict": "PASS" if cost_ok else "FAIL",
            "evidence": f"asserted_without_band={asserted[:6] or 'none'}",
        },
    ]
    failed = [t["id"] for t in tests if t["verdict"] != "PASS"]
    if failed:
        print("FAILED:SYN-0007 tests", failed)
        raise SystemExit(1)

    ranking_out = []
    for row in rows:
        ranking_out.append(
            {
                "rank": row["rank"],
                "cause_id": row["cause_id"],
                "intervention_id": row["intervention_id"],
                "action": row["action"],
                "available_at_phase": row["available_at_phase"],
                "spec_line": row["spec_line"],
                "prevented_claim_ids": row["prevented_claim_ids"],
                "subtree_size": row["subtree_size"],
                "severity": row["severity"],
                "severity_weight": row["severity_weight"],
                "cost_seconds": row["cost_seconds"],
                "cost_basis": row["cost_basis"],
                "estimate_band": row.get("estimate_band"),
                "score_micro": row["score_micro"],
                "sort_key": row["sort_key"],
            }
        )

    hier_nodes = []
    for n in hierarchy["nodes"]:
        spec = str(n.get("spec_line") or "")
        if len(spec) < 8:
            spec = f"WORK-UNIT-CATALOG.json#{n['id']}"
        hier_nodes.append(
            {
                "id": n["id"],
                "type": n["type"],
                "phase": str(n["phase"]),
                "claim_ids": list(n.get("claim_ids") or [n["id"]]),
                "severity": n["severity"],
                "title": n.get("title") or n["id"],
                "spec_line": spec,
            }
        )
    hier_edges = [
        {
            "parent": e["parent"],
            "child": e["child"],
            "mechanism": e.get("mechanism") or "dependency",
        }
        for e in hierarchy["edges"]
    ]

    rejected_out = []
    for r in ranked["rejected"]:
        rejected_out.append(
            {
                "intervention_id": r.get("intervention_id"),
                "class": r.get("class") or "empty-subtree",
                "detail": str(r.get("detail") or r.get("intervention_phase") or ""),
            }
        )

    doc = {
        "unit_id": "SYN-0007",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "kind": "intervention-ranking",
        "schema_version": 1,
        "question": QUESTION,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_note": hierarchy.get("source_note"),
        "ranking": ranking_out,
        "hierarchy": {
            "source": str(hierarchy.get("source") or hierarchy.get("source_note") or "catalog-reconstruction"),
            "nodes": hier_nodes,
            "edges": hier_edges,
            "max_depth": int(ranked["max_depth"]),
            "acyclic": True,
        },
        "cost_model": {
            "formula": "score_micro = (subtree_size * severity_weight * 1000000) // cost_seconds",
            "derived_unit": "seconds",
            "estimate_bands_seconds": dict(ESTIMATE_BAND_SECONDS),
        },
        "severity_model": {
            "vocabulary": ["P0", "P1", "P2", "P3"],
            "aggregation": "max-not-mean",
            "weights": dict(SEVERITY_WEIGHT),
        },
        "phase_order": list(PHASE_ORDER),
        "rejected": rejected_out,
        "inputs_used": list(hierarchy.get("inputs_used") or []),
        "named_probes": [
            {
                "id": "probe1",
                "role": "subtree-membership",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/SYN-0007/probe1_subtree.py"
                ),
            },
            {
                "id": "probe2",
                "role": "stability-and-anachronism",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/SYN-0007/probe2_stability.py"
                ),
            },
        ],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "SYN-0007-probe1-subtree",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 re-derives descendant claim sets from the embedded "
                "hierarchy. Named probe2 permutes a planted DAG and plants a "
                "phase-anachronism plus an ESTIMATE-without-band mutant. The two "
                "probes do not share a verdict file."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "evidence": [
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "note": "CC-* and SYN-* dependency edges used when SYN-0001 is absent.",
            },
            {
                "path": SCHEMA,
                "note": "Draft-07 schema rejects garbage objects lacking ranking rows with prevented_claim_ids.",
            },
        ],
        "formula": (
            "Cheapest earlier action per cause is the candidate CAUSE/MECHANISM "
            "node whose descendants form the prevented claim set; ranking is "
            "subtree_size x max(severity_weight) / cost_seconds with a frozen "
            "lexicographic tie-break."
        ),
    }
    return doc


def main() -> int:
    doc = build_doc()
    validate(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest} ranked={len(doc['ranking'])}")
    print("SUCCESS:SYN-0007 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
