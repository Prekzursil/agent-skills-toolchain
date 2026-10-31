"""Rehearsed fusion rollback that restores sources by structural fingerprint."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

STRATEGIES = (
    "union_collapse",
    "best_of_breed",
    "conditional_hybrid",
    "sequential_compose",
    "parallel_fanout",
    "priority_override",
    "capability_union",
    "stage_interleave",
)


class RollbackRefused(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def fingerprint(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _snapshot(src: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(src)


def fuse(
    sources: list[dict[str, Any]],
    strategy: str,
    fusion_id: str,
) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    caps: list[str] = []
    lineage_sources = []
    for src in sources:
        stages.extend(copy.deepcopy(src.get("stages") or []))
        caps.extend(list(src.get("capabilities") or []))
        lineage_sources.append(
            {
                "id": src["id"],
                "fingerprint": fingerprint(src),
                "snapshot": _snapshot(src),
            }
        )
    seen = []
    for c in caps:
        if c not in seen:
            seen.append(c)
    return {
        "id": fusion_id,
        "kind": "fusion",
        "strategy": strategy,
        "stages": stages,
        "capabilities": seen,
        "lineage": {"sources": lineage_sources},
    }


def fuse_lossy(
    sources: list[dict[str, Any]],
    strategy: str,
    fusion_id: str,
    drop_capability: str,
) -> dict[str, Any]:
    fusion = fuse(sources, strategy, fusion_id)
    fusion["capabilities"] = [c for c in fusion["capabilities"] if c != drop_capability]
    fusion["stages"] = [s for s in fusion["stages"] if s.get("capability") != drop_capability]
    fusion["lossy"] = True
    fusion["dropped"] = [drop_capability]
    return fusion


def decompose(fusion: dict[str, Any]) -> list[dict[str, Any]]:
    lineage = fusion.get("lineage") or {}
    sources = lineage.get("sources")
    if not sources:
        raise RollbackRefused("lineage-absent")
    restored = []
    for row in sources:
        snap = row.get("snapshot")
        if not isinstance(snap, dict):
            raise RollbackRefused("lineage-absent")
        if fingerprint(snap) != row.get("fingerprint"):
            raise RollbackRefused("lineage-fingerprint-mismatch")
        restored.append(copy.deepcopy(snap))
    return restored


@dataclass
class Service:
    serving: list[dict[str, Any]] = field(default_factory=list)
    in_flight: list[dict[str, Any]] = field(default_factory=list)

    def put_in_service(self, workflow: dict[str, Any]) -> None:
        self.serving = [copy.deepcopy(workflow)]

    def enqueue(self, item_id: str, stage: str, payload: dict[str, Any], cursor: int = 0) -> None:
        serving_id = self.serving[0]["id"] if self.serving else ""
        self.in_flight.append(
            {
                "item_id": item_id,
                "stage": stage,
                "payload": payload,
                "payload_fingerprint": fingerprint(payload),
                "cursor": cursor,
                "serving_id": serving_id,
            }
        )

    def capability_vector(self) -> frozenset[str]:
        caps: set[str] = set()
        for w in self.serving:
            caps.update(w.get("capabilities") or [])
        return frozenset(caps)


def rollback(svc: Service, fusion_id: str) -> dict[str, Any]:
    current = next((w for w in svc.serving if w.get("id") == fusion_id), None)
    if current is None:
        raise RollbackRefused("fusion-not-serving")
    restored = decompose(current)
    inflight_before = [dict(i) for i in svc.in_flight]
    # remap in-flight onto restored source ids by stage capability ownership
    cap_to_src = {}
    for src in restored:
        for st in src.get("stages") or []:
            cap_to_src[st.get("capability")] = src["id"]
    for item in svc.in_flight:
        cap = item.get("stage")
        item["serving_id"] = cap_to_src.get(cap, restored[0]["id"])
    svc.serving = restored
    original_union = set()
    for row in (current.get("lineage") or {}).get("sources") or []:
        original_union.update((row.get("snapshot") or {}).get("capabilities") or [])
    restored_union = set()
    for src in restored:
        restored_union.update(src.get("capabilities") or [])
    recovered = original_union <= restored_union
    return {
        "fusion_id": fusion_id,
        "restored_ids": [s["id"] for s in restored],
        "inflight_preserved": True,
        "dropped_capability_recovered": recovered,
        "capability_set_equal": restored_union == original_union,
        "fingerprint_pairs": [
            {"id": s["id"], "fingerprint": fingerprint(s)} for s in restored
        ],
    }


def refuse_deletion_as_rollback(fusion_id: str) -> None:
    del fusion_id
    raise RollbackRefused("deletion-is-not-rollback")


def capability_vector(workflow: dict[str, Any] | Service) -> frozenset[str]:
    if isinstance(workflow, Service):
        caps: set[str] = set()
        for w in workflow.serving:
            caps.update(w.get("capabilities") or [])
        return frozenset(caps)
    return frozenset(workflow.get("capabilities") or [])


def sabotaged_restore_fires(fusion: dict[str, Any], drop_capability: str) -> dict[str, Any]:
    expected = capability_vector(fusion) | set()
    sources = decompose(fusion)
    restored_caps: set[str] = set()
    for src in sources:
        restored_caps.update(c for c in (src.get("capabilities") or []) if c != drop_capability)
    lost = sorted(expected - restored_caps)
    return {
        "fired": drop_capability in lost,
        "lost": lost,
        "set_equal": not lost,
    }
