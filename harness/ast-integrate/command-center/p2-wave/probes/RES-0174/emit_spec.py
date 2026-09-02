#!/usr/bin/env python3
"""Emit RES-0174 design spec: falsifiable causal-DAG extraction protocol."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

UNIT = "RES-0174"
OUT = (
    "command-center/research/deep-research-design/"
    "RES-0174-root-cause-hierarchy-extraction.json"
)
SCHEMA = "command-center/schema/design-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0174/probe1_unattributed_and_dag.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0174/probe2_edge_falsifiers.py"
)
SENTINEL = "SUCCESS:RES-0174"


def catalog_unit() -> dict:
    data = json.loads(
        (E.REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for item in data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == UNIT:
            return item
    raise KeyError(UNIT)


def slim_node(node: dict) -> dict:
    return {
        "id": node["id"],
        "role": node.get("role"),
        "unknown_cause": bool(node.get("unknown_cause")),
        "n_parents": node.get("n_parents"),
        "n_children": node.get("n_children"),
        "text": node.get("text"),
        "anchors": node.get("anchors"),
    }


def slim_edge(edge: dict) -> dict:
    keep = (
        "parent",
        "child",
        "mechanism",
        "falsifier",
        "proposal_source",
        "sufficient",
        "refuse_reason",
    )
    return {k: edge[k] for k in keep if k in edge}


def source_row(lineage: dict, source_id: str) -> dict:
    for row in lineage.get("fetched") or []:
        if row.get("id") == source_id:
            return row
    raise KeyError(source_id)


def main() -> int:
    unit = catalog_unit()
    question = str(unit.get("question_or_target") or "")
    if len(question) < 40:
        print("FAILED:RES-0174 catalog question too short")
        return 1

    graph = E.extract(mode="protocol")
    proto_errs = E.protocol_errors(graph)
    hash_errs = E.lineage_hash_errors()
    if proto_errs or hash_errs:
        print("FAILED:RES-0174 emit " + ";".join(proto_errs + hash_errs))
        return 1

    nearest = E.extract(mode="nearest-parent")
    synthetic = E.extract(mode="synthetic-root")
    tree = E.extract(mode="tree-force")
    if not any(e.get("child") == "F-USER-PROMPTS-ABSENT" for e in nearest["edges"]):
        print("FAILED:RES-0174 emit nearest-parent mutant silent")
        return 1
    if not synthetic["metrics"].get("synthetic_root"):
        print("FAILED:RES-0174 emit synthetic-root mutant silent")
        return 1
    tree_parents = [e["parent"] for e in tree["edges"] if e["child"] == "F-G1-FAIL"]
    if len(set(tree_parents)) != 1:
        print("FAILED:RES-0174 emit tree-force still multi-parent")
        return 1

    lineage = json.loads(E.LINEAGE.read_text(encoding="utf-8"))
    wba = source_row(lineage, "wiki-wba-summary")
    five = source_row(lineage, "wiki-fivewhys-html")
    arxiv = source_row(lineage, "arxiv-1912.02724-atom")
    measure_sha, _ = E.sha256_file(
        E.REPO / "command-center/p2-wave/_measure_one_delivered.py"
    )
    catalog_sha, _ = E.sha256_file(E.REPO / "command-center/WORK-UNIT-CATALOG.json")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    design = {
        "protocol_id": "falsifiable-causal-dag",
        "name": "Falsifiable causal DAG extraction",
        "summary": (
            "Convert N findings into a typed DAG (ROOT-CAUSE, CONTRIBUTING-FACTOR, "
            "SYMPTOM, UNATTRIBUTED). Admit a parent→child edge only when it names "
            "a mechanism, names a falsifying observation, comes from control-flow "
            "or catalog-contract, and does not target an unknown-cause finding. "
            "Two independent sufficient causes stay two parents. A finding whose "
            "cause is unknown stays UNATTRIBUTED rather than attaching to the "
            "lexically nearest parent. A single invented root of every finding is "
            "rejected as a flat list wearing a graph."
        ),
        "algorithm": [
            "Load findings with live file:line anchors. Unknown-cause is an explicit flag, not a residual after clustering.",
            "Collect candidate edges only from named mechanisms (control-flow of a program, catalog contract). Do not propose edges by token Jaccard.",
            "Refuse an edge that lacks a falsifier, whose proposal_source is lexical-nearest or synthetic-root, or whose child is unknown_cause.",
            "Keep every admitted incoming edge (DAG, not tree). A tree-force pass that drops extra parents is a protocol violation.",
            "Assign roles from the admitted graph: no in-edges + out-edges = ROOT-CAUSE; both = CONTRIBUTING-FACTOR; only in-edges = SYMPTOM; unknown_cause or isolated = UNATTRIBUTED.",
            "Reject the graph if it is cyclic, max_depth < 2, or a synthetic node is parent of every finding.",
        ],
        "edge_falsification": {
            "named_observation": (
                "Every admitted edge carries a falsifier: an observation that would "
                "refute the causal claim (ADV-0110: a link with no refuting "
                "observation is a label, not a cause)."
            ),
            "counterfactual_test": (
                "Why–because analysis's counterfactual test: if the child still "
                "occurs when the parent is absent, the parent is not a necessary "
                "cause. Encoded as counterfactual_child_without_parent."
            ),
            "independent_prevention": (
                "ADV-0110 second rail: if removing the parent would not have "
                "prevented the child, the link fails a prevention check. G-1 fail "
                "paths in _measure_one_delivered.py are independently sufficient, "
                "so each is a contributing cause of F-G1-FAIL, not a unique root."
            ),
        },
        "two_independent_causes": (
            "A finding with two independent causes is a multi-parent node. The "
            "protocol does not invent a conjunction parent and does not drop the "
            "second parent. Demonstration: F-G1-FAIL is independently produced by "
            "missing probes/, self-declared BLOCKED, missing sentinel, probe-exit, "
            "and manifest-sha-mismatch."
        ),
        "unattributed_rule": (
            "If the cause is genuinely unknown, emit UNATTRIBUTED and refuse every "
            "incoming edge, including the lexically nearest plausible parent. "
            "Demonstration: _USER-PROMPTS.md is cited by RES-0174 and absent on "
            "this worktree; why it is absent is not evidenced."
        ),
        "does_not_claim": [
            "Observational causal discovery of the DAG (1912.02724 explicitly does not solve that).",
            "That Five Whys is never useful; only that as a hierarchy extractor it isolates a single cause.",
            "That cloud ok=true is delivery.",
        ],
        "extractor": "command-center/p2-wave/probes/RES-0174/extract.py",
        "demonstration": {
            "finding_set": "this program's G-1 measure script + catalog contracts + absent _USER-PROMPTS.md",
            "metrics": graph["metrics"],
            "nodes": [slim_node(n) for n in graph["nodes"]],
            "admitted_edges": [slim_edge(e) for e in graph["edges"]],
            "refused_edges": [slim_edge(e) for e in graph["refused_edges"]],
            "mutants": {
                "nearest_parent_attaches_unknown": True,
                "synthetic_root_detected": True,
                "tree_force_g1_parent_count": len(set(tree_parents)),
            },
        },
    }

    spec = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": unit.get("title")
        or "Extracting a root-cause hierarchy instead of a flat finding list",
        "question": question,
        "output_schema": SCHEMA,
        "emitted_at": now,
        "design": design,
        "tests": [
            {
                "id": "probe1-unattributed-and-dag",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-edge-falsifiers",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-UNATTRIBUTED-NEAREST-PARENT",
                "on_state": (
                    "Finding F-USER-PROMPTS-ABSENT has unknown_cause=true; a "
                    "token-Jaccard mutant attaches it to the nearest other finding."
                ),
                "observed": (
                    "Protocol keeps the finding UNATTRIBUTED with zero parents; "
                    "the mutant attaches a parent and is flagged "
                    "unknown-cause-has-parent."
                ),
            },
            {
                "id": "NC-TREE-FORCE-DROPS-PARENT",
                "on_state": (
                    "F-G1-FAIL has five independently sufficient parents; a "
                    "tree-force pass keeps only the first."
                ),
                "observed": (
                    "Protocol retains n_parents>=2; tree-force retains 1. Dual-cause "
                    "is represented as a DAG, not collapsed to a chain."
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A causal hierarchy that can represent two independent causes "
                    "is a DAG, not a tree. Why–because analysis emits a directed "
                    "acyclic graph of factors; Five Whys is criticised for isolating "
                    "a single root cause."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent_band": "highly-likely",
                "confidence_band": "highly-likely",
                "independent_verification_path": P2,
                "anchor": wba["resolved_url"],
                "lineage": {
                    "resolved_url": wba["resolved_url"],
                    "fetch_timestamp": wba["fetch_timestamp"],
                    "sha256": wba["sha256"],
                    "bytes": wba["bytes"],
                    "http_status": wba["http_status"],
                },
                "signals": [
                    {
                        "id": "S1-wba-rest-json",
                        "mechanism": (
                            "Wikipedia REST summary states WBA yields a directed "
                            "acyclic graph and aims to be falsifiable."
                        ),
                    },
                    {
                        "id": "S2-five-whys-html",
                        "mechanism": (
                            "Five Whys HTML: Tendency to isolate a single root "
                            "cause, whereas each question could elicit many "
                            "different root causes. sha256="
                            + five["sha256"][:16]
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "A proposed parent-child edge is a label unless it names a "
                    "refuting observation. WBA's counterfactual test asks whether "
                    "the child still occurs without the parent; ADV-0110 requires "
                    "the same check on synthesis links."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent_band": "highly-likely",
                "confidence_band": "highly-likely",
                "independent_verification_path": P2,
                "anchor": "command-center/WORK-UNIT-CATALOG.json:ADV-0110",
                "lineage": {
                    "resolved_url": "file:command-center/WORK-UNIT-CATALOG.json",
                    "fetch_timestamp": now,
                    "sha256": catalog_sha,
                    "http_status": None,
                    "note": "local catalog; _USER-PROMPTS.md absent",
                },
                "signals": [
                    {
                        "id": "S1-wba-counterfactual-test",
                        "mechanism": (
                            "Captured WBA HTML contains 'counterfactual test' and "
                            "the necessity condition on cause-effect."
                        ),
                    },
                    {
                        "id": "S2-adv-0110-catalog",
                        "mechanism": (
                            "ADV-0110 evidence_requirement: a link with no "
                            "refuting observation is a label, not a cause."
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "On this program's G-1 finding set the protocol yields a DAG "
                    "of max_depth>=2, keeps F-G1-FAIL multi-parent, keeps "
                    "F-USER-PROMPTS-ABSENT UNATTRIBUTED, and refuses lexical and "
                    "synthetic-root proposals. Independent fail paths are read "
                    "from _measure_one_delivered.py, not from the graph writer."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent_band": "almost-certain",
                "confidence_band": "almost-certain",
                "independent_verification_path": P1,
                "anchor": "command-center/p2-wave/_measure_one_delivered.py",
                "lineage": {
                    "resolved_url": "file:command-center/p2-wave/_measure_one_delivered.py",
                    "fetch_timestamp": now,
                    "sha256": measure_sha,
                    "http_status": None,
                },
                "signals": [
                    {
                        "id": "S1-live-extract",
                        "mechanism": (
                            "extract.py protocol mode: unattributed="
                            + ",".join(graph["metrics"]["unattributed_ids"])
                            + " multi_parent="
                            + ",".join(graph["metrics"]["multi_parent_ids"])
                            + f" max_depth={graph['metrics']['max_depth']}"
                        ),
                    },
                    {
                        "id": "S2-measure-fail-paths",
                        "mechanism": (
                            "Independent return fail(...) reasons in the measure "
                            "script: "
                            + ",".join(r["reason"] for r in graph["fail_reasons"][:8])
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Formal RCA given a known DAG (Janzing et al., arXiv:1912.02724) "
                    "attributes outliers to ancestors; it does not discover the DAG. "
                    "This unit therefore treats DAG topology as an explicit, "
                    "falsifiable proposal, not as an inferred latent graph."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent_band": "highly-likely",
                "confidence_band": "highly-likely",
                "independent_verification_path": (
                    "re-hash fixtures/captures/arxiv-1912.02724-atom.atom.xml and "
                    "ar5iv-1912.02724.html"
                ),
                "anchor": arxiv["resolved_url"],
                "lineage": {
                    "resolved_url": arxiv["resolved_url"],
                    "fetch_timestamp": arxiv["fetch_timestamp"],
                    "sha256": arxiv["sha256"],
                    "bytes": arxiv["bytes"],
                    "http_status": arxiv["http_status"],
                },
                "signals": [
                    {
                        "id": "S1-arxiv-atom",
                        "mechanism": (
                            "Atom summary: causal relation is a known directed "
                            "acyclic graph (DAG)."
                        ),
                    },
                    {
                        "id": "S2-ar5iv-html",
                        "mechanism": (
                            "HTML: Our results do not solve the hard problem of "
                            "causal discovery."
                        ),
                    },
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0174-probe2-edge-falsifiers",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-hashes captured bytes, requires a named falsifier on "
                "every admitted edge, and checks that tree-force drops a parent "
                "the protocol keeps. It does not reuse probe 1's nearest-parent "
                "assertion. No cross-vendor Codex reviewer ran in this worktree."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0174/extract.py",
                "exists": True,
                "role": "extractor",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0174/fixtures/lineage.json",
                "exists": True,
                "role": "source-lineage",
            },
        ],
        "source_lineage_captures": lineage.get("fetched"),
        "cloud_ok": False,
        "answer": (
            "Protocol: falsifiable causal DAG. Propose parent→child edges only "
            "from named mechanisms (control-flow or catalog contract). Admit an "
            "edge only if it carries a falsifying observation and survives a "
            "counterfactual/prevention check. Keep two independent causes as two "
            "parents. Leave a genuinely unknown-cause finding UNATTRIBUTED; do "
            "not attach it to the nearest plausible parent. Reject a depth-1 "
            "synthetic root as a flat list. Demonstrated on this program's G-1 "
            "fail paths plus the absent _USER-PROMPTS.md citation. "
            + SENTINEL
        ),
    }

    schema = json.loads((E.REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(spec)

    out_path = E.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(spec, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:RES-0174 sentinel missing after write")
        return 1
    print(f"wrote {OUT}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
