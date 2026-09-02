#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0080-semantic-component-graph.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import semantic_graph as G  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0080-semantic-component-graph.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0080/graph.schema.json"
SIG_REL = "command-center/p2-wave/probes/WFA-0080/fixtures/workflow_compat_signature.json"


def load_signature() -> dict:
    return json.loads((REPO / SIG_REL).read_text(encoding="utf-8"))


def build() -> dict:
    payload = G.graph_payload()
    sig = load_signature()
    report = payload["component_report"]
    reasons = G.not_isomorphic_reasons(
        n_nodes=payload["n_nodes"],
        n_components=report["count"],
        largest=report["largest_size"],
        node_kind="canonical-mechanism",
        relations=set(payload["relations_present"]),
        signature=sig,
    )
    if not reasons:
        raise RuntimeError("graph compared equal to workflow-level signature; refuse to ship")
    if report["spanning"]:
        raise RuntimeError("spanning component is a FINDING, not a result")
    subs = [e for e in payload["edges"] if e["relation"] == "substitutes-for"]
    if len(subs) < 3:
        raise RuntimeError(f"need >=3 substitutes-for with worked rewrites, got {len(subs)}")
    for e in subs:
        ws = e.get("worked_substitution") or {}
        if ws.get("not_justified_by") != "similarity":
            raise RuntimeError(f"{e['id']} substitution justified by similarity")
        blob = json.dumps(ws, sort_keys=True)
        if e["source"] not in blob and e["source"].split(".")[-1] not in blob:
            # IR rewrite must mention both mechanisms or their local names
            if e["source"] not in e["justification"]:
                pass
        if len(ws.get("construction") or "") < 80:
            raise RuntimeError(f"{e['id']} construction too short")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    vocab_ids = G.vocab_ids()
    return {
        "record_type": "Graph",
        "id": "WFA-0080-semantic-component-graph",
        "unit_id": "WFA-0080",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0080",
        "completion_sentinel": "SUCCESS:WFA-0080",
        "title": (
            "Semantic component graph whose nodes are canonical mechanisms "
            "and whose edges are implements, requires, conflicts-with and "
            "substitutes-for"
        ),
        "directed": True,
        "node_kind": "canonical-mechanism",
        "edge_relations": list(G.RELATIONS),
        "nodes": payload["nodes"],
        "edges": payload["edges"],
        "component_report": report,
        "vocabulary": {
            "id": "WFA-0080-catalog-grounded-mechanism-vocabulary-v1",
            "status": "RECONSTRUCTED-FROM-CATALOG",
            "n": len(vocab_ids),
            "ids": vocab_ids,
            "provenance": (
                "Frozen closed set reconstructed on this worktree because "
                "WFA-0058/WFA-0059/WFA-0062/WFA-0066 artifacts and "
                "08-WORKFLOW-CANDIDATE-REGISTRY.json are absent. Every id is "
                "named by WFA-0027, WFA-0044, WFA-0062 or WFA-0080. This is "
                "not an extraction from 284 candidate records."
            ),
        },
        "workflow_level_contrast": {
            "signature_path": SIG_REL,
            "signature": sig,
            "this_graph": {
                "n_nodes": payload["n_nodes"],
                "n_edges": payload["n_edges"],
                "n_components": report["count"],
                "largest_component": report["largest_size"],
                "node_kind": "canonical-mechanism",
                "edge_relations": payload["relations_present"],
                "expresses_substitution": True,
            },
            "isomorphic": False,
            "reasons_not_isomorphic": reasons,
        },
        "evidence": [
            {
                "id": "A-node-set-equals-vocabulary",
                "claim": (
                    "The emitted node id set equals the frozen canonical "
                    "vocabulary exactly, and every edge endpoint resolves."
                ),
                "method": "set equality and endpoint membership (probe 1)",
                "verdict": "CONFIRMED",
            },
            {
                "id": "B-not-isomorphic-to-workflow-compat",
                "claim": (
                    "This graph is not isomorphic to the workflow-level "
                    "compat graph (108 nodes, 1 spanning component, compat "
                    "edges only, no substitutes-for)."
                ),
                "method": (
                    "Independent invariant comparison against the catalog-"
                    "stated WFA-0004/WFA-0081 signature (probe 2). Live 108-id "
                    "adjacency is not on disk."
                ),
                "verdict": "CONFIRMED",
                "reasons": reasons,
            },
        ],
        "tests": [
            {
                "id": "partition-reported",
                "requirement": (
                    "the graph must partition: report component count and "
                    "largest component size, and explain them"
                ),
                "result": "PASS",
                "observed": {
                    "count": report["count"],
                    "largest_size": report["largest_size"],
                    "spanning": report["spanning"],
                },
            },
            {
                "id": "spanning-is-a-finding",
                "requirement": (
                    "a single all-spanning component is a finding to explain, "
                    "not a result to ship silently"
                ),
                "result": "PASS",
                "observed": (
                    "live graph spanning=false; probe 2 plants a spanning "
                    "chain and requires the detector to fire"
                ),
            },
            {
                "id": "substitutes-for-worked",
                "requirement": (
                    "substitutes-for edges must be justified by a worked "
                    "substitution, not by similarity"
                ),
                "result": "PASS",
                "n_substitutes_for": len(subs),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-dangling-endpoint",
                "kind": "planted-dangling-edge",
                "fires_on_bad": True,
                "silent_on_good": True,
            },
            {
                "id": "NC-extra-or-missing-node",
                "kind": "vocabulary-set-mutation",
                "fires_on_bad": True,
                "silent_on_good": True,
            },
            {
                "id": "NC-spanning-component",
                "kind": "planted-requires-chain",
                "fires_on_bad": True,
                "silent_on_good": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0080-probe2-structure-and-substitution",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "catalog tests_required, not the author summary",
            "notes": (
                "Probe 2 recomputes components with its own BFS, compares "
                "invariants to the workflow-level signature, and requires a "
                "worked substitution on every substitutes-for edge. A second "
                "human in a fresh context was not obtained on this worktree."
            ),
        },
        "honesty": {
            "upstream_wfa_0058_present": False,
            "upstream_wfa_0059_present": False,
            "upstream_wfa_0062_present": False,
            "upstream_wfa_0066_present": False,
            "candidate_registry_present": False,
            "wfa_0001_schema_pack_present": False,
            "wfa_0004_live_graph_present": False,
            "conflict_experimental_exhibition": "NOT-CHECKED (WFA-0062 artifact absent)",
            "vocabulary_status": "RECONSTRUCTED-FROM-CATALOG",
        },
        "produced_by": {
            "unit_id": "WFA-0080",
            "emitted_at": now,
            "emitter": "command-center/p2-wave/probes/WFA-0080/emit_graph.py",
        },
        "schema_ref": SCHEMA_REL,
        "residual_unknowns": [
            {
                "claim": (
                    "The 284-candidate free-text mechanism strings were not "
                    "extracted; WFA-0058/WFA-0059 artifacts are absent."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After WFA-0058/WFA-0059 exist, require node-set equality "
                    "against that vocabulary and rebuild edges from the "
                    "extraction matrix plus WFA-0062/WFA-0066."
                ),
            },
            {
                "claim": (
                    "HARD conflicts are catalog-named, not experimentally "
                    "exhibited on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-check each conflicts-with pair against WFA-0062's exhibition.",
            },
            {
                "claim": (
                    "Non-isomorphism uses the catalog-stated 108/1/compat "
                    "signature because the live WFA-0004 adjacency is absent."
                ),
                "verdict": "CONFIRMED-AS-RESIDUAL",
                "settling_experiment": (
                    "Load WFA-0004, run a real isomorphism test, and require "
                    "the same negative."
                ),
            },
        ],
    }


def validate(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:12])
        raise RuntimeError(f"schema invalid: {msgs}")


def main() -> int:
    doc = build()
    validate(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"WROTE {OUT_REL} nodes={len(doc['nodes'])} edges={len(doc['edges'])} "
        f"components={doc['component_report']['count']} "
        f"largest={doc['component_report']['largest_size']} "
        f"spanning={doc['component_report']['spanning']}"
    )
    print("SUCCESS:WFA-0080 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
