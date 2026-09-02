"""Mechanical gates for RES-0114: silent-download catch, promotion, impossibility.

Comments are not evidence. A headline number without a baseline is E3 and
cannot promote a mechanism. An agent run whose inputs include a live model
and a live web cannot satisfy closed-world bit-identity (Lamb Definition 1
over the complete input set).
"""
from __future__ import annotations

from typing import Any, Mapping

import contract as C

OFFLINE_MARKERS = (
    "never download",
    "never downloads",
    "fully offline",
    "never touches the network",
    "does not download",
    "no network",
)


def comment_claims_offline(comment: str) -> bool:
    text = (comment or "").lower()
    return any(m in text for m in OFFLINE_MARKERS)


def classify_blocked_run(
    *,
    comment: str,
    attempted_destinations: list,
    claims_offline: bool | None = None,
) -> str:
    """Classify a run that executed under egress block.

    Destination list is the evidence. A comment that asserts offline is
    ignored except to distinguish silent-download from a declared dependency.
    """
    dests = list(attempted_destinations or [])
    offline = bool(claims_offline) or comment_claims_offline(comment)
    if dests:
        return "silent-download" if offline else "declared-network-dependency"
    return "hermetic"


def can_promote(mechanism: Mapping[str, Any]) -> tuple[bool, str]:
    """Promotion rule from the catalog evidence_requirement.

    A headline number without its baseline is recorded as E3 and cannot
    promote a mechanism. E4 inferences cannot promote. Surviving promotions
    require E1 or E2 plus both effect_size and baseline.
    """
    effect = mechanism.get("effect_size")
    baseline = mechanism.get("baseline")
    if not effect:
        return False, "headline-without-effect-size"
    if not baseline:
        return False, "headline-without-baseline-E3"
    tier = str(mechanism.get("evidence_tier") or "")
    if tier == "E4":
        return False, "E4-inferred-cannot-promote"
    if tier == "E3":
        return False, "E3-single-source-cannot-promote"
    if tier not in {"E1", "E2"}:
        return False, f"tier-{tier or 'missing'}-cannot-promote"
    return True, "ok"


def agent_run_can_satisfy(property_id: str, profile: Mapping[str, Any]) -> bool:
    """Which hermeticity properties an agent-run profile can satisfy.

    Live model + live web: can still declare egress and pin tools.
    Cannot close the world over model weights/logits and live web bytes.
    """
    live_model = bool(profile.get("live_model"))
    live_web = bool(profile.get("live_web"))
    if property_id == C.IMPOSSIBLE_PROPERTY_ID:
        return not (live_model or live_web)
    if property_id in {
        C.CATCHING_PROPERTY_ID,
        "P-DECLARED-INPUT-PIN",
        "P-COMMENT-IS-NOT-EVIDENCE",
        "P-CACHE-AS-DECLARED-INPUT",
        "P-ADVERSARIAL-TWO-ENV-REBUILD",
    }:
        return True
    return False
