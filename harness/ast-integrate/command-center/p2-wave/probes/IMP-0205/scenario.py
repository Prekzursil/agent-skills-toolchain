"""Deterministic fusion-in-service fixtures for IMP-0205 rollback rehearsal."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.workflow.fusion_rollback import (  # noqa: E402
    Service,
    fingerprint,
    fuse,
    fuse_lossy,
)


def source_research() -> dict[str, Any]:
    return {
        "id": "wf.source.research",
        "kind": "source",
        "version": "1.0.0",
        "license": "MIT",
        "stages": [
            {"id": "retrieve", "capability": "retrieve", "body": {"tool": "search", "k": 8}},
            {"id": "cite", "capability": "cite", "body": {"style": "inline"}},
        ],
        "capabilities": ["retrieve", "cite"],
    }


def source_governance() -> dict[str, Any]:
    return {
        "id": "wf.source.governance",
        "kind": "source",
        "version": "2.1.0",
        "license": "Apache-2.0",
        "stages": [
            {"id": "redact", "capability": "redact", "body": {"policy": "pii-v3"}},
            {"id": "audit", "capability": "audit", "body": {"sink": "ledger"}},
        ],
        "capabilities": ["redact", "audit"],
    }


def originals() -> list[dict[str, Any]]:
    return [source_research(), source_governance()]


def original_fingerprints() -> dict[str, str]:
    return {s["id"]: fingerprint(s) for s in originals()}


def original_capability_union() -> frozenset[str]:
    return frozenset({"retrieve", "cite", "redact", "audit"})


def fusion_in_service(strategy: str, fusion_id: str, *, lossy: bool = False) -> dict[str, Any]:
    srcs = originals()
    if lossy:
        return fuse_lossy(srcs, strategy, fusion_id, drop_capability="audit")
    return fuse(srcs, strategy, fusion_id)


def armed_service(
    strategy: str,
    fusion_id: str,
    *,
    lossy: bool = False,
    enqueue: bool = True,
) -> tuple[Service, dict[str, Any]]:
    fusion = fusion_in_service(strategy, fusion_id, lossy=lossy)
    svc = Service()
    svc.put_in_service(fusion)
    if enqueue:
        # Two in-flight items, one owned by each source. Lossy fusion drops
        # `audit`, so the governance item sits on `redact` in that variant.
        svc.enqueue("job-research-1", "retrieve", {"q": "lineage round-trip", "n": 3}, cursor=1)
        gov_stage = "redact" if lossy else "audit"
        svc.enqueue("job-gov-1", gov_stage, {"subject": "caller-42", "step": 2}, cursor=0)
    return svc, fusion
