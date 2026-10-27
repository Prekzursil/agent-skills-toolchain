"""Typed Workflow helpers for IMP-0235 research blueprints."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

WORKFLOW_KIND = "workflow_blueprint"


def stage(sid: str, kind: str, *, inputs: Sequence[str] | None = None, outputs: Sequence[str] | None = None) -> dict[str, Any]:
    return {
        "id": sid,
        "kind": kind,
        "inputs": list(inputs or []),
        "outputs": list(outputs or []),
    }


def typed_workflow(
    wid: str,
    stages: Sequence[Mapping[str, Any]],
    *,
    discovery_only: bool = False,
    max_stages: int = 16,
    on_error: str = "halt",
) -> dict[str, Any]:
    return {
        "id": wid,
        "kind": WORKFLOW_KIND,
        "discovery_only": discovery_only,
        "stages": [dict(s) for s in stages],
        "stopping": {"max_stages": max_stages, "on_error": on_error},
    }


def fingerprint(blueprint: Mapping[str, Any]) -> str:
    wf = blueprint.get("typed_workflow") or {}
    kinds = tuple(
        str(s.get("kind") or "")
        for s in (wf.get("stages") or [])
        if isinstance(s, Mapping)
    )
    caps = tuple(
        sorted(f"{k}={v}" for k, v in (blueprint.get("capability_vector") or {}).items())
    )
    return "|".join([",".join(kinds), ",".join(caps)])


def distinct_fingerprints(blueprints: Iterable[Mapping[str, Any]]) -> bool:
    seen: set[str] = set()
    for bp in blueprints:
        fp = fingerprint(bp)
        if fp in seen:
            return False
        seen.add(fp)
    return True
