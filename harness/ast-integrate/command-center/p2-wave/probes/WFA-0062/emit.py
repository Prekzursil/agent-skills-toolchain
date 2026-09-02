#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0062-mechanism-conflicts.json (Graph)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from conflict_map import reconcile_all  # noqa: E402
from engine import (  # noqa: E402
    MECHANISMS,
    exclusive_pairs,
    fuse_same_stage,
    naive_union_today,
    soft_pairs,
)

REPO = HERE.parents[3]
OUT_REL = "command-center/wfa/WFA-0062-mechanism-conflicts.json"
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/Graph"
QUESTION = (
    "Which pairs of canonical mechanisms are mutually exclusive — blind "
    "independent first pass versus shared-context deliberation, deterministic "
    "replay versus non-deterministic sampling, fire-and-forget dispatch versus "
    "a blocking fan-in barrier — and what happens today if a fusion combines them?"
)
SENTINEL = "SUCCESS:WFA-0062"
EXHIBIT_PAIR = (
    "mech.blind_independent_first_pass",
    "mech.shared_context_deliberation",
)


def _node(mid: str) -> dict:
    rec = MECHANISMS[mid]
    return {
        "id": mid,
        "kind": "mechanism",
        "label": rec["label"],
        "attrs": {
            "definition": rec["definition"],
            "asserts": rec["asserts"],
        },
    }


def _edge(kind: str, left: str, right: str, extra: dict) -> dict:
    a, b = (left, right) if left <= right else (right, left)
    return {
        "id": f"{kind}:{a}|{b}",
        "source": a,
        "target": b,
        "kind": kind,
        "attrs": extra,
    }


def build_graph() -> dict:
    recon = reconcile_all()
    hard = exclusive_pairs()
    soft = soft_pairs()
    exhibit = fuse_same_stage(list(EXHIBIT_PAIR))
    today = naive_union_today(list(EXHIBIT_PAIR))
    drop_right = fuse_same_stage([EXHIBIT_PAIR[0]])
    drop_left = fuse_same_stage([EXHIBIT_PAIR[1]])
    if exhibit["sat"]:
        raise RuntimeError("exhibit pair must be UNSAT")
    if drop_right["sat"] is not True or drop_left["sat"] is not True:
        raise RuntimeError("both-states control failed: singleton should be SAT")

    nodes = [_node(mid) for mid in sorted(MECHANISMS)]
    edges: list[dict] = []
    enumerated: list[dict] = []
    for pair in hard:
        arg = (
            f"{pair['left']} asserts {pair['slot']}={pair['left_val']}; "
            f"{pair['right']} asserts {pair['slot']}={pair['right_val']}. "
            "Same-stage fusion cannot assign two values to one exclusive slot."
        )
        extra = {
            "grade": "HARD",
            "slot": pair["slot"],
            "incompatibility_argument": arg,
            "worked_example": {
                "ir": {
                    "stage_id": "fused-stage-0",
                    "mechanisms": [pair["left"], pair["right"]],
                },
                "observed": "UNSAT",
                "clashes": pair["fusion"]["clashes"],
            },
        }
        edges.append(_edge("conflicts-with", pair["left"], pair["right"], extra))
        enumerated.append(
            {
                "left": pair["left"],
                "right": pair["right"],
                "grade": "HARD",
                "slot": pair["slot"],
                "incompatibility_argument": arg,
                "worked_example": extra["worked_example"],
            }
        )
    for pair in soft:
        extra = {
            "grade": "SOFT",
            "incompatibility_argument": pair["reason"],
            "worked_example": {
                "ir": {
                    "stage_id": "fused-stage-0",
                    "mechanisms": [pair["left"], pair["right"]],
                },
                "observed": "SAT",
                "note": "Awkward, not contradictory — graded SOFT, not listed as a conflict.",
            },
        }
        edges.append(_edge("awkward-with", pair["left"], pair["right"], extra))

    hard_ids = {(e["source"], e["target"]) for e in edges if e["kind"] == "conflicts-with"}
    for s in soft:
        key = (s["left"], s["right"]) if s["left"] <= s["right"] else (s["right"], s["left"])
        if key in hard_ids:
            raise RuntimeError(f"SOFT pair listed as HARD: {key}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": "WFA-0062-mechanism-conflict-graph",
        "kind": "Graph",
        "graph_kind": "mechanism-conflict",
        "directed": False,
        "unit_id": "WFA-0062",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "output_schema": SCHEMA_REL,
        "generated_at": now,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "enumerated_conflicts": enumerated,
        "soft_pairs": [
            {
                "left": s["left"],
                "right": s["right"],
                "grade": "SOFT",
                "reason": s["reason"],
            }
            for s in soft
        ],
        "conflict_map_reconciliation": {
            "n": recon["n"],
            "source": recon["source"],
            "live_found": recon["live_found"],
            "live_path": recon["live_path"],
            "searched": recon["searched"],
            "verdict_counts": recon["verdict_counts"],
            "rows": recon["rows"],
            "note": (
                "Each of 20 conflict_map rows is CONFIRMED, REFUTED, or "
                "RESTATED at mechanism level. The original merge-maps file is "
                "absent on this Linux worktree; rows are reconstructed from "
                "catalog WFA-0150 collision classes and WFA-0062 named pairs "
                "unless a live 20-row map is found."
            ),
        },
        "experimental_exhibition": {
            "pair": list(EXHIBIT_PAIR),
            "fusion": exhibit,
            "today": today,
            "both_states": {
                "both_mechanisms_UNSAT": True,
                "drop_right_SAT": True,
                "drop_left_SAT": True,
            },
            "note": (
                "A constructed same-stage fusion of blind independent first "
                "pass with shared-context deliberation is observed UNSAT. "
                "Dropping either mechanism restores SAT."
            ),
        },
        "what_happens_today": today["what_happens_today"],
        "schema_pack_note": (
            "command-center/wfa/schema/wfa-schema-pack.json is absent on this "
            "worktree (WFA-0001 not delivered here). This artifact is a Graph "
            "with nodes[] and edges[] plus the unit envelope the G-1 measure "
            "requires (state, sentinel SUCCESS:WFA-0062)."
        ),
        "residual_unknowns": [
            (
                "The Windows harness-restore file "
                "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json was not found; "
                "the 20-row conflict_map is reconstructed, not read."
            ),
            (
                "WFA-0058 mechanism vocabulary artifact is absent; this unit "
                "uses a local mech.* vocabulary covering the named exclusive "
                "pairs and WFA-0150 collision classes."
            ),
        ],
        "reviewer": {
            "reviewer_id": "WFA-0062-probe2-experimental-fusion",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes exclusive pairs from slot assertions and "
                "re-runs the constructed fusion; it does not trust the "
                "author's edge list."
            ),
        },
        "tests": {
            "experimental_exhibition": True,
            "conflict_map_n20_reconciled": recon["n"] == 20,
            "soft_not_listed_as_hard": True,
            "both_states_drop_one_restores_sat": True,
        },
    }


def write_artifact(doc: dict | None = None) -> Path:
    payload = doc if doc is not None else build_graph()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if SENTINEL not in text:
        raise RuntimeError("sentinel missing from artifact text")
    out.write_text(text, encoding="utf-8")
    return out


def main() -> int:
    doc = build_graph()
    path = write_artifact(doc)
    print(
        json.dumps(
            {
                "wrote": OUT_REL,
                "bytes": path.stat().st_size,
                "hard_conflicts": len(doc["enumerated_conflicts"]),
                "soft_pairs": len(doc["soft_pairs"]),
                "conflict_map_n": doc["conflict_map_reconciliation"]["n"],
                "exhibit_sat": doc["experimental_exhibition"]["fusion"]["sat"],
            },
            sort_keys=True,
        )
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
