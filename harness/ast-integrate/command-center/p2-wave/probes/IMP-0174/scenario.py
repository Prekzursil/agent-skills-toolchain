"""Shared IMP-0174 scenario: control extraction, live graph, detector AST."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.component_graph import (  # noqa: E402
    OrphanComponentError,
    assemble,
    assert_no_orphans,
    build,
    graph_public,
    is_orphan,
    orphan_count,
    plant_orphan,
    span_is_resolvable,
    valid_provenance,
    with_lookalike_named_orphan,
    with_unanchored_stage,
)

CONTROL = HERE / "fixtures" / "control.json"
SRC = REPO / "tools/workflow_foundry/component_graph.py"
ART = REPO / "command-center/receipts/IMP-0174.json"


def load_control() -> dict[str, Any]:
    return json.loads(CONTROL.read_text(encoding="utf-8"))


def live_graph() -> dict[str, Any]:
    return graph_public(build(load_control()))


def every_node_anchored(graph: dict[str, Any]) -> bool:
    nodes = graph.get("nodes") or []
    if not nodes:
        return False
    for node in nodes:
        if is_orphan(node):
            return False
        prov = node.get("provenance") or []
        if not any(valid_provenance(p) for p in prov):
            return False
        if not any(span_is_resolvable(p.get("source_span")) for p in prov if isinstance(p, dict)):
            return False
    return True


def merge_happened(graph: dict[str, Any]) -> bool:
    stats = graph.get("stats") or {}
    if int(stats.get("collapsed") or 0) < 1:
        return False
    return any(len(n.get("provenance") or []) >= 2 for n in graph.get("nodes") or [])


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _uses_const(fn: ast.AST, value: str) -> bool:
    return any(isinstance(n, ast.Constant) and n.value == value for n in ast.walk(fn))


def _forbidden_orphan_substring(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.In) for op in node.ops):
            continue
        left = node.left
        if isinstance(left, ast.Constant) and isinstance(left.value, str):
            if "orphan" in left.value.lower():
                return True
    return False


def detector_ast() -> dict[str, Any]:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    orphan_fn = _fn(tree, "is_orphan")
    prov_fn = _fn(tree, "valid_provenance")
    span_fn = _fn(tree, "span_is_resolvable")
    missing = [n for n, f in (("is_orphan", orphan_fn), ("valid_provenance", prov_fn), ("span_is_resolvable", span_fn)) if f is None]
    reads_prov = bool(orphan_fn and _uses_const(orphan_fn, "provenance"))
    reads_cand = bool(prov_fn and _uses_const(prov_fn, "candidate_id"))
    reads_span = bool(span_fn and _uses_const(span_fn, "uri") and _uses_const(span_fn, "start_line"))
    forbidden = False
    for fn in (orphan_fn, prov_fn, span_fn, _fn(tree, "orphan_nodes"), _fn(tree, "assert_no_orphans")):
        if fn is not None and _forbidden_orphan_substring(fn):
            forbidden = True
            break
    ok = (not missing) and reads_prov and reads_cand and reads_span and not forbidden
    return {
        "pass": ok,
        "missing_functions": missing,
        "is_orphan_reads_provenance": reads_prov,
        "valid_provenance_reads_candidate_id": reads_cand,
        "span_reads_uri_and_start_line": reads_span,
        "forbidden_orphan_substring_in": forbidden,
        "source": str(SRC.relative_to(REPO).as_posix()),
    }


def planted_both_states() -> dict[str, Any]:
    control = load_control()
    good = build(control)
    good_count = orphan_count(good)

    planted_graph = plant_orphan(assemble(control))
    plant_raised = False
    plant_err = None
    try:
        assert_no_orphans(planted_graph)
    except OrphanComponentError as exc:
        plant_raised = True
        plant_err = exc.error_id

    unanchored_raised = False
    try:
        build(with_unanchored_stage(control))
    except OrphanComponentError:
        unanchored_raised = True

    look = build(with_lookalike_named_orphan(control))
    look_orphans = orphan_count(look)
    look_nodes = [n for n in look["nodes"] if n["kind"] == "orphan-lookalike"]
    planted_id = planted_graph["nodes"][-1]["id"]

    ok = (
        good_count == 0
        and plant_raised
        and plant_err == "orphan-component"
        and orphan_count(planted_graph) == 1
        and "orphan" not in planted_id
        and unanchored_raised
        and look_orphans == 0
        and len(look_nodes) == 1
        and "orphan" in look_nodes[0]["id"]
    )
    return {
        "pass": ok,
        "good_orphan_count": good_count,
        "planted_raises": plant_raised,
        "planted_error_id": plant_err,
        "planted_orphan_count": orphan_count(planted_graph),
        "planted_id": planted_id,
        "planted_id_contains_orphan": "orphan" in planted_id,
        "unanchored_stage_raises": unanchored_raised,
        "lookalike_orphan_count": look_orphans,
        "lookalike_present": len(look_nodes) == 1,
        "lookalike_id": look_nodes[0]["id"] if look_nodes else None,
    }
