#!/usr/bin/env python3
"""Two-reviewer capture gate for CNL-0105.

When only two reviewers are seated, dual-ACCEPT is not consensus. Capture
fires on seal-break, rationale clone, sybil prompt-hash, or shared COI.
Split ballots recruit R3 (not a capture fire). Independent dual-ACCEPT is
silent on capture and still requires editor nocapture attestation.
"""
from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[a-z0-9]+")
JACCARD_FIRE_AT = 0.85


def tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall((text or "").lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def capture_check(seating: dict, fire_at: float = JACCARD_FIRE_AT) -> dict:
    reviewers = list(seating.get("reviewers") or [])
    n = len(reviewers)
    if n != 2:
        return {
            "applicable": False,
            "fire": False,
            "action": "not-two-reviewer",
            "n_reviewers": n,
            "reasons": [],
        }
    r1, r2 = reviewers[0], reviewers[1]
    reasons: list[str] = []
    jac = jaccard(tokens(r1.get("rationale") or ""), tokens(r2.get("rationale") or ""))
    if r1.get("seen_peer") or r2.get("seen_peer"):
        reasons.append("seal-broken")
    if r1.get("recommendation") == r2.get("recommendation") and jac >= fire_at:
        reasons.append("rationale-clone")
    if (
        r1.get("vendor") == r2.get("vendor")
        and r1.get("prompt_hash")
        and r1.get("prompt_hash") == r2.get("prompt_hash")
    ):
        reasons.append("sybil-same-prompt")
    c1 = set(r1.get("coi_cluster") or [])
    c2 = set(r2.get("coi_cluster") or [])
    if c1 & c2:
        reasons.append("shared-coi")

    split = r1.get("recommendation") != r2.get("recommendation")
    if split:
        return {
            "applicable": True,
            "fire": False,
            "action": "recruit-R3",
            "n_reviewers": 2,
            "reasons": [],
            "split": True,
            "jaccard": jac,
            "accept_blocked": True,
            "note": "disagreement cannot be resolved by the two seated reviewers",
        }
    fire = bool(reasons)
    if fire:
        action = "halt-capture"
        accept_blocked = True
    else:
        action = "editor-nocapture-then-accept"
        accept_blocked = False
    return {
        "applicable": True,
        "fire": fire,
        "action": action,
        "n_reviewers": 2,
        "reasons": reasons,
        "split": False,
        "jaccard": jac,
        "accept_blocked": accept_blocked,
        "note": (
            "dual-ACCEPT is not sufficient; editor cannot vote accept/reject "
            "and must attest nocapture"
            if not fire
            else "capture detector fired; ACCEPT refused"
        ),
    }


NEGATIVE_CONTROL_VERBATIM = (
    "On seating planted.seal-broken-clone, reviewer-2 copies reviewer-1's "
    "recommendation and rationale after seeing the peer ballot (seen_peer=true, "
    "identical rationale, same vendor and prompt_hash, shared COI). capture_check "
    "MUST fire (reasons include seal-broken and rationale-clone) and ACCEPT is "
    "refused. On seating clean.independent-sealed, ballots are sealed, vendors "
    "differ, rationales differ, recommendations split: capture_check MUST be "
    "silent and action=recruit-R3. A detector that is silent on the planted "
    "clone, or that fires on the sealed split, has not measured capture."
)
