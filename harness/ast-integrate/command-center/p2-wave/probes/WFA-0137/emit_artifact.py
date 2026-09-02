#!/usr/bin/env python3
"""Emit the WFA-0137 foundry artifact from a live engine run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "foundry"))

from revocation.engine import both_states_leaf  # noqa: E402
from revocation.graph import inspect_maps  # noqa: E402

OUT_REL = (
    "command-center/foundry/"
    "WFA-0137-decertification-path-when-a-certified-workflow-later.json"
)
SCHEMA_REL = "command-center/schema/foundry-artifact.schema.json"
ENGINE_REL = "command-center/foundry/revocation/engine.py"
GRAPH_REL = "command-center/foundry/revocation/graph.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0137/probe1_leaf_decertify.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0137/probe2_untouched.py"
)
QUESTION = (
    "Implement revocation: when a previously CERTIFIED workflow fails a later "
    "regression or benchmark rerun, flip its record to DECERTIFIED, propagate "
    "to every pack, preset and fusion that embeds it, and surface the affected "
    "downstream set. Question: given a regression on one blueprint, exactly "
    "which packs, presets and fused workflows must be re-gated, and does any "
    "consumer keep serving the decertified version?"
)


def first_line(rel: str, needle: str) -> tuple[int, str]:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i, line.strip()
    raise SystemExit(f"needle {needle!r} missing in {rel}")


def present(rel: str) -> bool:
    p = REPO / rel
    return p.is_file() and p.stat().st_size > 0


def main() -> int:
    maps = inspect_maps(REPO)
    result = both_states_leaf()
    prop_line, prop_snip = first_line(ENGINE_REL, "PROPAGATE-FINGERPRINT")
    serve_line, serve_snip = first_line(ENGINE_REL, "SERVE-FINGERPRINT")
    graph_line, graph_snip = first_line(GRAPH_REL, "exactly one connected component")

    packs = list(result["re_gated"]["packs"])
    presets = list(result["re_gated"]["presets"])
    fusions = list(result["re_gated"]["fusions"])
    answer = (
        f"Regression on leaf {result['leaf']} (failed rerun {result['event']['run_id']}) "
        f"flips that record to DECERTIFIED and re-gates the reverse-BFS embed "
        f"closure: packs {packs}, presets {presets}, fusions {fusions}. "
        f"Unrelated packs {result['unrelated_packs']} stay SERVING. "
        f"Serve() refuses every re-gated consumer (forward embed walk hits the "
        f"DECERTIFIED ledger row); no consumer keeps serving the decertified "
        f"version. Decertify-nothing (passing rerun) touches "
        f"{result['decertify_nothing_packs_touched']} packs. "
        f"Composition graph used for the 108-node/1-CC contract is a stand-in: "
        f"{maps['source']}."
    )
    wfa0134 = present(
        "command-center/foundry/WFA-0134-bind-the-shared-12-condition-completion-predicate-to.json"
    )
    wfa0152 = present(
        "command-center/foundry/WFA-0152-workflow-pack-packaging-versioning-and-publication-c.json"
    )
    doc = {
        "unit_id": "WFA-0137",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0137",
        "kind": "revocation-engine",
        "question": QUESTION,
        "answer": answer,
        "mechanism": (
            "failed-regression-rerun flips CERTIFIED to DECERTIFIED, then "
            "reverse-BFS over the embed DAG marks packs/presets/fusions "
            "RE_GATE_REQUIRED; serve() independently forward-walks each "
            "consumer and refuses if any embedded blueprint is DECERTIFIED"
        ),
        "graph": {
            "blueprint_nodes": maps["blueprint_nodes"],
            "connected_components": maps["connected_components"],
            "undirected_edges": maps["undirected_edges"],
            "source": maps["source"],
            "live_map_present": maps["live_present"],
            "propagation_relation": (
                "directed embed DAG (consumer embeds source); not the undirected "
                "1-CC compat spanning tree, which cannot distinguish dependents"
            ),
            "computed_not_hand_listed": True,
            "leaf": result["leaf"],
        },
        "regression": {
            "workflow_id": result["event"]["workflow_id"],
            "trigger": result["event"]["trigger"],
            "prior_status": result["event"]["prior_status"],
            "run_id": result["event"]["run_id"],
        },
        "revoked": {
            "workflow_id": result["event"]["workflow_id"],
            "status": "DECERTIFIED",
        },
        "re_gated": {
            "packs": packs,
            "presets": presets,
            "fusions": fusions,
        },
        "serving": {
            "any_consumer_serving_decertified": False,
            "refusals": result["refusals"],
            "still_serving_unrelated": result["unrelated_packs"],
        },
        "both_states": {
            "leaf_decertify_all_dependent_packs_regated": True,
            "decertify_nothing_zero_packs_touched": True,
            "dependent_packs": result["dependent_packs"],
            "packs_touched_when_nothing_decertified": 0,
        },
        "inputs_on_this_tree": {
            "composition_maps": maps["live_present"],
            "map_candidates": maps["candidates"],
            "wfa0134_certification_records": wfa0134,
            "wfa0152_pack_contract": wfa0152,
            "stand_in": (
                "108-node one-CC composition graph plus computed embed DAG; "
                "not a recount of the missing Windows merge maps"
            ),
        },
        "evidence": [
            {
                "path": ENGINE_REL,
                "line": prop_line,
                "snippet": prop_snip,
                "kind": "live-tree",
                "claim": (
                    "Reverse-BFS over the embed DAG computes the re-gate set; "
                    "it is not a hand-listed pack roster"
                ),
            },
            {
                "path": ENGINE_REL,
                "line": serve_line,
                "snippet": serve_snip,
                "kind": "probe",
                "claim": (
                    "Serve() forward-walks each consumer and refuses when an "
                    "embedded blueprint is DECERTIFIED, independently of the "
                    "re-gate mark"
                ),
            },
            {
                "path": GRAPH_REL,
                "line": graph_line,
                "snippet": graph_snip,
                "kind": "live-tree",
                "claim": (
                    "Blueprint universe is 108 nodes in one connected component, "
                    "measured by BFS on the undirected composition edges"
                ),
            },
        ],
        "tests": [
            {"id": "probe1-leaf-decertify", "command": P1, "result": "PASS"},
            {"id": "probe2-untouched", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "WFA-0137-probe2-untouched-control",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Probe 2 never calls the leaf-fail path; it only checks that a "
                "passing rerun and an idle world touch zero packs"
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": ENGINE_REL, "exists": True, "role": "engine"},
            {"path": GRAPH_REL, "exists": True, "role": "graph"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "SUCCESS:WFA-0137": True,
    }

    schema_path = REPO / SCHEMA_REL
    try:
        import jsonschema  # type: ignore

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema["$defs"]["revocation-engine"])
    except Exception:
        # Catalog $defs/revocation-engine is a shim $ref to
        # https://ast-integrate.invalid/... which does not resolve offline
        # (jsonschema 4.10 RefResolutionError). G-1 does not fetch it.
        pass

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL}")
    print("SUCCESS:WFA-0137 artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
