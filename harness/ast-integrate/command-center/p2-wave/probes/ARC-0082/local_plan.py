#!/usr/bin/env python3
"""Host-free execution-plan projection for ARC-0082 dry-run.

agentspec.plan.compile_plan is not on this worktree (IMP-0129 artifact). This
module is the consumer call site: same input workflow bytes => same plan bytes.
When agentspec.plan is present, dsl.py prefers it.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.canonical import dumpb  # noqa: E402

STRIP_FROM_NODES = frozenset({"role", "max_retries", "inputs", "outputs"})

WORKFLOW_KEYS = frozenset(
    {
        "id",
        "spec_version",
        "entry",
        "params",
        "nodes",
        "stages",
        "prompt_transport",
        "replayable",
        "certified_executable",
        "failure_policy",
        "roles",
        "tool_policy",
        "parameters",
        "retries",
        "resume",
        "dry_run",
        "source_path",
        "discovery_only",
        "_generated",
    }
)

_COMMON = frozenset({"id", "kind", "on_failure", "prompt_ref", "params"})

NODE_KEYS: dict[str, frozenset[str]] = {
    "WorkUnit": _COMMON,
    "work": _COMMON,
    "static-scan": _COMMON,
    "write-config": _COMMON,
    "gate": _COMMON | frozenset({"role"}),
    "Pipeline": _COMMON | frozenset({"steps"}),
    "FanOut": _COMMON | frozenset({"units"}),
    "fan-out": _COMMON | frozenset({"units"}),
    "Barrier": _COMMON | frozenset({"wait_for"}),
    "barrier": _COMMON | frozenset({"wait_for"}),
    "Subworkflow": _COMMON
    | frozenset({"workflow_ref", "param_bindings", "id_namespace"}),
    "Loop": _COMMON
    | frozenset({"body", "convergence_expr", "max_iterations", "on_bound_reached"}),
    "RepairLoop": _COMMON
    | frozenset({"body", "max_attempts", "on_impossibility"}),
    "HumanCheckpoint": _COMMON
    | frozenset(
        {
            "pause_token",
            "default_if_unanswered",
            "allowed_responses",
        }
    ),
    "checkpoint": _COMMON
    | frozenset({"pause_token", "default_if_unanswered", "allowed_responses"}),
    "DynamicFanOut": _COMMON
    | frozenset(
        {"producer_unit", "item_path", "unit_template", "max_cardinality"}
    ),
}

KNOWN_NODE_KINDS = frozenset(NODE_KEYS)


def canonical_bytes(value: Any) -> bytes:
    return dumpb(value)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def compile_plan(wf: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Deterministic walk from entry. No clock, no host, no I/O."""
    nodes_raw = wf.get("nodes") if isinstance(wf.get("nodes"), list) else wf.get("stages")
    if not isinstance(nodes_raw, list):
        return []
    by_id: dict[str, Mapping[str, Any]] = {}
    for node in nodes_raw:
        if isinstance(node, Mapping) and isinstance(node.get("id"), str):
            by_id[str(node["id"])] = node
    entry = str(wf.get("entry") or "")
    plan: list[dict[str, Any]] = []
    seen: set[str] = set()

    def project(node: Mapping[str, Any]) -> dict[str, Any]:
        kind = str(node.get("kind") or "")
        allowed = NODE_KEYS.get(kind, frozenset({"id", "kind"}))
        out: dict[str, Any] = {"id": str(node.get("id") or ""), "kind": kind}
        for key in sorted(allowed):
            if key in {"id", "kind"} or key in STRIP_FROM_NODES:
                continue
            if key in node:
                out[key] = node[key]
        return out

    def children_of(node: Mapping[str, Any]) -> list[str]:
        kind = str(node.get("kind") or "")
        if kind == "Pipeline":
            steps = node.get("steps")
            return [str(x) for x in steps] if isinstance(steps, list) else []
        if kind in {"Loop", "RepairLoop"}:
            body = node.get("body")
            if isinstance(body, str) and body:
                return [body]
            if isinstance(body, list):
                return [str(x) for x in body]
            return []
        if kind in {"FanOut", "fan-out"}:
            units = node.get("units")
            return [str(x) for x in units] if isinstance(units, list) else []
        return []

    def visit(nid: str) -> None:
        if not nid or nid in seen:
            return
        node = by_id.get(nid)
        if node is None:
            return
        seen.add(nid)
        plan.append(project(node))
        for child in children_of(node):
            visit(child)

    visit(entry)
    return plan
