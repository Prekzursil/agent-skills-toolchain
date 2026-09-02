#!/usr/bin/env python3
"""Probe 1: live hierarchy is an acyclic typed DAG with max depth >= 2."""
from __future__ import annotations

import json
import sys
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

import anchors as A  # noqa: E402
import graph as G  # noqa: E402
import local_schema as S  # noqa: E402

OUT = REPO / "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"
SCHEMA = REPO / "command-center/schema/root-cause-graph.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def fail(why: str) -> int:
    print(f"FAILED:SYN-0001-probe1 {why}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact-missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        return fail("catalog-schema-missing")
    try:
        S.validate_graph_receipt(doc)
    except jsonschema.ValidationError as exc:
        return fail(f"schema-invalid:{exc}")

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = next(u for u in catalog["work_units"] if u["id"] == "SYN-0001")
    sentinel = unit["completion_sentinel"]
    text = OUT.read_text(encoding="utf-8")
    if sentinel not in text:
        return fail("completion-sentinel-absent")
    if "SUCCESS:SYN-0001" not in text:
        return fail("short-sentinel-absent")
    if str(doc.get("state") or "").upper() in G.NOT_DELIVERING:
        return fail(f"self-declared:{doc.get('state')}")

    errs = G.structural_errors(doc)
    if errs:
        return fail(" ".join(errs))
    m = G.metrics(doc)
    print(
        f"acyclic={m['acyclic']} max_depth={m['max_depth']} "
        f"causes={m['root_cause_count']} symptoms={m['node_count_by_type']['SYMPTOM']} "
        f"edges={m['edge_count']} median_branching={m['median_branching_factor']}"
    )
    if not m["acyclic"]:
        return fail("cycle")
    if m["max_depth"] < 2:
        return fail("flat-list-as-graph")
    ok, why = G.cause_typed_edges_to_symptoms(doc)
    print(f"cause_to_symptom={ok} {why}")
    if not ok:
        return fail(why)

    for n in doc["nodes"]:
        if n.get("type") != "CAUSE":
            continue
        for a in n.get("evidence_anchors") or []:
            rok, rwhy = A.resolve_anchor(
                REPO, a["path"], int(a["line"]), a["snippet"]
            )
            print(f"anchor {n['id']} {rwhy} ok={rok}")
            if not rok:
                return fail(rwhy)
    print("SUCCESS:SYN-0001-probe1 graph-shape acyclic depth>=2 cause-edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
