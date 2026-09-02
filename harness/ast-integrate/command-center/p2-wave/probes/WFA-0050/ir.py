"""Local Workflow IR subset used because WFA-0044 is absent on this worktree.

Not an execution runtime. Every node carries a source_anchor. Constructs the
subset cannot express are recorded NON-TRANSFERABLE rather than approximated.
"""
from __future__ import annotations

from typing import Any


def node(kind: str, ident: str, payload: dict[str, Any], anchor: str) -> dict[str, Any]:
    if not anchor:
        raise ValueError(f"IR node {ident} missing source_anchor")
    return {
        "kind": kind,
        "id": ident,
        "source_anchor": anchor,
        "payload": payload,
        "execution_entrypoint": None,
    }


def workflow_ir(
    ident: str,
    *,
    roles: list[dict],
    stages: list[dict],
    turn_policy: dict,
    stopping: dict,
    gates: list[dict],
    edges: list[dict],
    non_transferable: list[dict],
    lineage: dict,
) -> dict[str, Any]:
    return {
        "ir_id": ident,
        "ir_subset": "WFA-0050-local-because-WFA-0044-absent",
        "execution_semantics": False,
        "roles": roles,
        "stages": stages,
        "turn_policy": turn_policy,
        "stopping": stopping,
        "gates": gates,
        "edges": edges,
        "non_transferable": non_transferable,
        "lineage": lineage,
    }
