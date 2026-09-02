"""Minimal workflow IR used by fusion lineage rehearsals."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class Stage:
    id: str
    kind: str
    in_contract: str = "bundle"
    out_contract: str = "bundle"
    gate: dict[str, Any] | None = None
    tool_class: str = "op"
    anchors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Workflow:
    id: str
    stages: list[Stage]
    edges: list[tuple[str, str]] = field(default_factory=list)
    licences: tuple[str, ...] = ()
    credits: tuple[str, ...] = ()


def canonical_json(obj: Any) -> str:
    import json

    return json.dumps(obj, sort_keys=True, default=str)


def mechanism_fingerprint(wf: Workflow) -> str:
    import hashlib

    payload = canonical_json({"id": wf.id, "stages": [s.id for s in wf.stages], "edges": wf.edges})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def with_anchors(wf: Workflow, wid: str | None = None) -> Workflow:
    tag = wid or wf.id
    return replace(wf, stages=[replace(s, anchors=(tag,)) for s in wf.stages])
