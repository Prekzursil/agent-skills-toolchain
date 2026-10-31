"""Compile a workflow dict into an ordered execution plan (IMP-0147)."""
from __future__ import annotations

from typing import Any


def compile_plan(workflow: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(workflow, dict):
        return []
    nodes = {str(n.get("id")): n for n in (workflow.get("nodes") or []) if isinstance(n, dict) and n.get("id")}
    entry = str(workflow.get("entry") or "")
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    def emit(nid: str) -> None:
        if nid in seen or nid not in nodes:
            return
        seen.add(nid)
        node = nodes[nid]
        kind = str(node.get("kind") or "WorkUnit")
        if kind == "Pipeline":
            for step in node.get("steps") or []:
                emit(str(step))
            ordered.append({"id": nid, "kind": "Pipeline", "steps": list(node.get("steps") or [])})
            return
        if kind == "FanOut":
            for unit in node.get("units") or []:
                emit(str(unit))
            ordered.append({"id": nid, "kind": "FanOut", "units": list(node.get("units") or [])})
            return
        if kind == "Barrier":
            for dep in node.get("wait_for") or []:
                emit(str(dep))
            ordered.append({"id": nid, "kind": "Barrier", "wait_for": list(node.get("wait_for") or [])})
            return
        ordered.append({"id": nid, "kind": kind, "params": dict(node.get("params") or {})})

    if entry:
        emit(entry)
    for nid in nodes:
        emit(nid)
    return ordered


def plan_loop(loop) -> list[dict[str, Any]]:
    """Unroll a Loop into a static plan of at most max_iterations steps."""
    cap = getattr(loop, "max_iterations", None)
    if cap is None:
        cap = 0
    body = tuple(getattr(loop, "body", ()) or ())
    return [{"iteration": i, "body": list(body)} for i in range(int(cap))]


def plan_length(loop) -> int:
    return len(plan_loop(loop))
