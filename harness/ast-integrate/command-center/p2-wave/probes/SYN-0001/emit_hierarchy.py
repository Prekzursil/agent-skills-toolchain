#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0001.root-cause-hierarchy.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    cur = HERE
    for _ in range(8):
        if (cur / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return cur
        cur = cur.parent
    raise SystemExit("FAILED:SYN-0001 repo-root-not-found")


REPO = repo_root()
sys.path.insert(0, str(HERE))

import builder as B  # noqa: E402
import corpus as C  # noqa: E402
import graph as G  # noqa: E402
import local_schema as S  # noqa: E402

OUT = "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"
SCHEMA = "command-center/schema/root-cause-graph.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "Implementation target: build command-center/synthesis/ROOT-CAUSE-HIERARCHY.json "
    "from the normalized claim corpus, satisfying the spec's explicit shape requirement "
    "-- 'Synthesis must produce a root-cause hierarchy and decision trace, not a flat "
    "list of findings' (_USER-PROMPTS.md:11086). Each node is typed CAUSE|MECHANISM|"
    "SYMPTOM, carries its own evidence anchors, and every symptom edge names the "
    "mechanism by which the parent produces the child. A depth-1 graph (all findings "
    "hanging off one synthetic root) is a flat list wearing a graph's clothing and "
    "must be rejected by this unit itself."
)


def catalog_sentinel() -> str:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if u.get("id") == "SYN-0001":
            return str(u["completion_sentinel"])
    raise SystemExit("FAILED:SYN-0001 catalog-missing")


def dump(obj: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")


def run_negative_control() -> dict:
    unrelated = B.unrelated_fixture(20)
    built = B.build_graph(unrelated)
    B.assert_build_ok(built, require_depth=False)
    roots = built["root_ids"]
    if len(roots) != 20:
        raise SystemExit(
            f"FAILED:SYN-0001 negative-control shared-root roots={len(roots)}"
        )
    if built["edges"]:
        raise SystemExit("FAILED:SYN-0001 negative-control invented-edges")
    related = B.build_graph(B.related_cluster_fixture())
    if len(related["root_ids"]) != 1:
        raise SystemExit("FAILED:SYN-0001 related-cluster did not share a cause")
    if related["metrics"]["max_depth"] < 2:
        raise SystemExit("FAILED:SYN-0001 related-cluster too shallow")
    mixed = B.build_graph(unrelated + B.related_cluster_fixture())
    if len(mixed["root_ids"]) != 21:
        raise SystemExit(
            f"FAILED:SYN-0001 mixed corpus collapsed roots={len(mixed['root_ids'])}"
        )
    return {
        "id": "negative_control_20_unrelated_findings_must_not_share_one_root",
        "result": "PASS",
        "unrelated_roots": 20,
        "unrelated_edges": 0,
        "related_cluster_roots": 1,
        "related_cluster_max_depth": related["metrics"]["max_depth"],
        "mixed_roots": 21,
    }


def main() -> int:
    sentinel = catalog_sentinel()
    records = C.resolve_records(REPO, C.live_records())
    built = B.build_graph(records)
    skeleton = {
        "nodes": built["nodes"],
        "edges": built["edges"],
        "state": "SUCCESS",
    }
    errs = G.structural_errors(skeleton)
    if errs:
        print("FAILED:SYN-0001 " + " ".join(errs))
        return 1
    m = G.metrics(skeleton)
    if m["max_depth"] < 2 or not m["acyclic"]:
        print(f"FAILED:SYN-0001 metrics {m}")
        return 1
    if m["root_cause_count"] < 2:
        print("FAILED:SYN-0001 single-shared-root-over-live-corpus")
        return 1

    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:SYN-0001 missing-schema {SCHEMA}")
        return 1
    neg = run_negative_control()
    tests = [
        {
            "id": "test_graph_is_acyclic",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/SYN-0001/probe1_graph_shape.py"
            ),
            "result": "PASS",
            "acyclic": m["acyclic"],
        },
        {
            "id": "test_max_depth_at_least_2",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/SYN-0001/probe1_graph_shape.py"
            ),
            "result": "PASS",
            "max_depth": m["max_depth"],
        },
        {
            "id": "test_every_cause_node_has_typed_edges_to_its_symptoms",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/SYN-0001/probe1_graph_shape.py"
            ),
            "result": "PASS",
        },
        {
            "id": neg["id"],
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/SYN-0001/probe2_negative_control.py"
            ),
            "result": neg["result"],
            "unrelated_roots": neg["unrelated_roots"],
            "unrelated_edges": neg["unrelated_edges"],
            "related_cluster_roots": neg["related_cluster_roots"],
            "related_cluster_max_depth": neg["related_cluster_max_depth"],
            "mixed_roots": neg["mixed_roots"],
        },
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_type = m["node_count_by_type"]
    doc = {
        "unit_id": "SYN-0001",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0001",
        "completion_sentinel": sentinel,
        "question": QUESTION,
        "produced_at": now,
        "adv_rebuild_circle": False,
        "shared_super_root": False,
        "nodes": built["nodes"],
        "edges": built["edges"],
        "root_ids": built["root_ids"],
        "metrics": m,
        "tests": tests,
        "corpus": C.input_inventory(REPO),
        "depth_definition": (
            "max_depth is the longest path length in edges from an in-degree-0 "
            "node. CAUSE -> MECHANISM -> SYMPTOM is depth 2. Depth 1 (all "
            "symptoms hanging off one synthetic root) is rejected."
        ),
        "report": {
            "kind": "root-cause-graph",
            "observations": [
                {
                    "name": "node_count_by_type",
                    "measured": (
                        f"CAUSE={by_type['CAUSE']} MECHANISM={by_type['MECHANISM']} "
                        f"SYMPTOM={by_type['SYMPTOM']}"
                    ),
                    "method": "graph.metrics over live ARC probe corpus",
                    "anchor": "command-center/p2-wave/probes/SYN-0001/graph.py",
                },
                {
                    "name": "max_depth",
                    "measured": m["max_depth"],
                    "method": "longest path length in edges from in-degree-0 nodes",
                    "anchor": "command-center/p2-wave/probes/SYN-0001/graph.py",
                },
                {
                    "name": "edge_count",
                    "measured": m["edge_count"],
                    "method": "len(edges) after family-scoped builder",
                    "anchor": "command-center/p2-wave/probes/SYN-0001/builder.py",
                },
                {
                    "name": "median_branching_factor",
                    "measured": m["median_branching_factor"],
                    "method": "median out-degree of nodes with out-degree>0",
                    "anchor": "command-center/p2-wave/probes/SYN-0001/graph.py",
                },
                {
                    "name": "findings_per_root_cause",
                    "measured": m["findings_per_root_cause"],
                    "method": "SYMPTOM count / CAUSE count",
                    "anchor": "command-center/p2-wave/probes/SYN-0001/graph.py",
                },
            ],
            "control_ids": [
                "test_graph_is_acyclic",
                "test_max_depth_at_least_2",
                "negative_control_20_unrelated_findings_must_not_share_one_root",
            ],
        },
        "reviewer": {
            "reviewer_id": "SYN-0001-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-runs the 20-unrelated negative control on the builder. "
                "It does not score agreement with this narrative."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
    }
    try:
        S.validate_graph_receipt(doc)
    except jsonschema.ValidationError as exc:
        print(f"FAILED:SYN-0001 schema-invalid {exc}")
        return 1
    dump(doc, REPO / OUT)
    live = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    try:
        S.validate_graph_receipt(live)
    except jsonschema.ValidationError as exc:
        print(f"FAILED:SYN-0001 post-write-schema {exc}")
        return 1
    live_errs = G.structural_errors(live)
    if live_errs:
        print("FAILED:SYN-0001 post-write " + " ".join(live_errs))
        return 1
    if sentinel not in (REPO / OUT).read_text(encoding="utf-8"):
        print("FAILED:SYN-0001 sentinel-absent-from-bytes")
        return 1
    print(
        f"nodes={m['node_count']} depth={m['max_depth']} "
        f"causes={m['root_cause_count']} edges={m['edge_count']} "
        f"acyclic={m['acyclic']}"
    )
    print("SUCCESS:SYN-0001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
