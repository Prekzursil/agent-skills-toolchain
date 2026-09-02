"""Promotion rules: E3 without baseline cannot promote; no search cannot promote."""
from __future__ import annotations

from typing import Any


def evidence_tier(paper: dict[str, Any]) -> str:
    effect = paper.get("effect_size")
    baseline = paper.get("baseline")
    if not isinstance(effect, dict) or effect.get("value") is None:
        return "E3"
    if not isinstance(baseline, dict) or baseline.get("value") is None:
        return "E3"
    if not paper.get("arxiv") and not paper.get("doi"):
        return "E3"
    if not paper.get("section_or_figure"):
        return "E3"
    return "E2"


def promote_row(mech: dict[str, Any], search: dict[str, Any]) -> dict[str, Any]:
    paper = mech.get("paper") or {}
    tier = evidence_tier(paper)
    reasons: list[str] = []
    if not search.get("performed"):
        reasons.append("implementation-search-not-performed")
    if tier == "E3":
        reasons.append("headline-without-baseline-is-E3")
    if not mech.get("implementable"):
        reasons.append("specification-not-clear-enough")
    if search.get("verdict") == "popular-implementation-found":
        reasons.append("popular-implementation-exists")
    if search.get("verdict") not in {
        "no-popular-implementation",
        "popular-implementation-found",
    }:
        reasons.append(f"search-verdict-{search.get('verdict')}")
    gem = (
        mech.get("role") == "candidate"
        and not reasons
        and search.get("verdict") == "no-popular-implementation"
        and tier != "E3"
        and bool(mech.get("implementable"))
        and bool(search.get("performed"))
    )
    if gem:
        status = "PROMOTED-GEM"
    elif "popular-implementation-exists" in reasons:
        status = "CONTROL-OR-ADOPTED"
    elif "headline-without-baseline-is-E3" in reasons:
        status = "E3-NOT-PROMOTED"
    else:
        status = "NOT-PROMOTED"
    return {
        "status": status,
        "is_gem": gem,
        "evidence_tier": tier,
        "blockers": reasons,
    }
