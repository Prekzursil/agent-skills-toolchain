"""Abandoned-work salvage: ancestry is never sufficient (IMP-0242)."""
from __future__ import annotations

from typing import Any

AUTHORIZE = "AUTHORIZE"
REFUSE = "REFUSE"


def ancestry_proof(*, is_ancestor_of_main: bool) -> dict[str, Any]:
    return {"kind": "ancestry", "is_ancestor_of_main": bool(is_ancestor_of_main)}


def content_equality_proof(*, local_sha256: str, preserved_sha256: str) -> dict[str, Any]:
    return {
        "kind": "content-equality",
        "local_sha256": local_sha256,
        "preserved_sha256": preserved_sha256,
        "equal": local_sha256 == preserved_sha256,
    }


def pr_merged_proof(*, merged: bool) -> dict[str, Any]:
    return {"kind": "pr-merged", "merged": bool(merged)}


def ancestry_only_would_authorize(proofs: list[dict[str, Any]]) -> bool:
    return any(p.get("kind") == "ancestry" and p.get("is_ancestor_of_main") for p in proofs)


def decide(candidate: dict[str, Any], proofs: list[dict[str, Any]]) -> dict[str, Any]:
    naive = ancestry_only_would_authorize(proofs)
    content = next((p for p in proofs if p.get("kind") == "content-equality"), None)
    pr = next((p for p in proofs if p.get("kind") == "pr-merged"), None)
    if content and content.get("equal"):
        return {
            "decision": AUTHORIZE,
            "authorized_by": "content-equality",
            "ancestry_sufficient": False,
            "naive_ancestry_would_authorize": naive,
            "refused_because": None,
            "candidate_id": candidate.get("id"),
        }
    if pr and pr.get("merged"):
        return {
            "decision": AUTHORIZE,
            "authorized_by": "pr-merged",
            "ancestry_sufficient": False,
            "naive_ancestry_would_authorize": naive,
            "refused_because": None,
            "candidate_id": candidate.get("id"),
        }
    reason = "ancestry-only-insufficient"
    if content and not content.get("equal"):
        reason = "content-mismatch"
    return {
        "decision": REFUSE,
        "authorized_by": None,
        "ancestry_sufficient": False,
        "naive_ancestry_would_authorize": naive,
        "refused_because": reason,
        "candidate_id": candidate.get("id"),
    }
