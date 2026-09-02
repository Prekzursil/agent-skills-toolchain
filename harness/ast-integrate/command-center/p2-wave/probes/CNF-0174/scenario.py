#!/usr/bin/env python3
"""Confirmer-authored nested-council scenarios for CNF-0174.

These fixtures are written by the confirmer, not copied from an implementer
receipt. Production nested runtime is absent; the fan-in under test is
probes/CNF-0174/fanin.py.
"""
from __future__ import annotations

from typing import Any

DONE_REASON = (
    "Subcouncil-alpha: work is complete. Receipt exists at "
    "artifacts/alpha.json, tests T1-T4 passed, shared reducer returned COMPLETE."
)
BLOCKED_REASON = (
    "Subcouncil-beta: work is NOT complete. Blocking gap: nested fan-in "
    "never read beta's evidence that the completion predicate is unsatisfied "
    "(missing condition-12 consumer proof). Do not average this away."
)
INCOMPLETE_REASON = (
    "Subcouncil-gamma: still in progress. Two of five required artifacts are "
    "unwritten; exit_code 0 on the worker is not success."
)
AGREE_REASON_A = (
    "Subcouncil-alpha: deliberated four rounds; dissent empty; both artifacts "
    "present; reducer COMPLETE."
)
AGREE_REASON_B = (
    "Subcouncil-beta: independently reached COMPLETE on the same receipt pair "
    "after reading alpha's evidence rather than counting votes."
)


def _child(
    cid: str,
    completion: str,
    reasoning: str,
    *,
    present: bool = True,
    exit_code: int = 0,
    digest: str = "sha256:fixture",
    dissent: list[str] | None = None,
    confidence: float = 0.7,
    artifact_path: str = "artifacts/child.json",
) -> dict[str, Any]:
    return {
        "id": cid,
        "completion": completion,
        "exit_code": exit_code,
        "artifact_present": present,
        "artifact_digest": digest if present else "",
        "artifact_path": artifact_path if present else "",
        "reasoning": reasoning,
        "dissent": list(dissent or []),
        "confidence": confidence,
    }


def split_two() -> list[dict[str, Any]]:
    """Deliberate completion split: COMPLETE vs BLOCKED."""
    return [
        _child("sub-alpha", "COMPLETE", DONE_REASON, confidence=0.91),
        _child(
            "sub-beta",
            "BLOCKED",
            BLOCKED_REASON,
            present=True,
            exit_code=1,
            dissent=["minority: completion predicate unsatisfied on consumer proof"],
            confidence=0.82,
        ),
    ]


def agree_complete() -> list[dict[str, Any]]:
    return [
        _child("sub-alpha", "COMPLETE", AGREE_REASON_A, confidence=0.88),
        _child("sub-beta", "COMPLETE", AGREE_REASON_B, confidence=0.86),
    ]


def agree_blocked() -> list[dict[str, Any]]:
    return [
        _child(
            "sub-alpha",
            "BLOCKED",
            "Both subcouncils blocked: shared reducer INCOMPLETE.",
            exit_code=2,
            confidence=0.6,
        ),
        _child(
            "sub-beta",
            "BLOCKED",
            "Beta agrees blocked after reading alpha's missing artifact.",
            exit_code=2,
            confidence=0.61,
        ),
    ]


def three_way() -> list[dict[str, Any]]:
    """Reviewer-required three-way subcouncil split."""
    return [
        _child("sub-alpha", "COMPLETE", DONE_REASON, confidence=0.9),
        _child(
            "sub-beta",
            "BLOCKED",
            BLOCKED_REASON,
            exit_code=1,
            dissent=["beta-minority: do not merge"],
            confidence=0.8,
        ),
        _child(
            "sub-gamma",
            "INCOMPLETE",
            INCOMPLETE_REASON,
            present=False,
            exit_code=0,
            digest="deadbeef" * 8,
            artifact_path="artifacts/gamma.json",
            dissent=["gamma-minority: exit-zero is not success"],
            confidence=0.55,
        ),
    ]


def persistent_split() -> list[dict[str, Any]]:
    """Same split fingerprint on every retry — the deadlock fixture."""
    return split_two()
