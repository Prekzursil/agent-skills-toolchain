"""Publication gate for the weighting audit.

A weighted decision that omits the equal-weight counterfactual is incomplete.
A published flip flag that disagrees with a live recompute is also incomplete.
This module is the detector probe 2 fires on the planted-unpublished fixture
and keeps silent on a complete audit.
"""
from __future__ import annotations

from typing import Any

AUDIT_KEYS = (
    "weighted_result",
    "equal_weight_counterfactual",
    "weighting_delta",
    "weighting_flip",
)


def defects(published: dict[str, Any], live: dict[str, Any] | None = None) -> list[str]:
    found: list[str] = []
    if published.get("rejected"):
        return found
    for key in AUDIT_KEYS:
        if key not in published:
            found.append(f"missing:{key}")
    cf = published.get("equal_weight_counterfactual")
    if not isinstance(cf, dict) and "missing:equal_weight_counterfactual" not in found:
        found.append("counterfactual-not-object")
    if "weighting_flip" in published and not isinstance(
        published.get("weighting_flip"), bool
    ):
        found.append("flip-not-bool")
    if live and not live.get("rejected"):
        if bool(published.get("weighting_flip")) != bool(live.get("weighting_flip")):
            found.append("flip-disagrees-with-recompute")
        pub_w = (published.get("weighted_result") or {}).get("winner")
        live_w = (live.get("weighted_result") or {}).get("winner")
        if pub_w != live_w:
            found.append("weighted-winner-disagrees-with-recompute")
        pub_e = (published.get("equal_weight_counterfactual") or {}).get("winner")
        live_e = (live.get("equal_weight_counterfactual") or {}).get("winner")
        if "missing:equal_weight_counterfactual" not in found and pub_e != live_e:
            found.append("equal-winner-disagrees-with-recompute")
    return found


def fires(published: dict[str, Any], live: dict[str, Any] | None = None) -> bool:
    """True when the publication check rejects the document."""
    return bool(defects(published, live))
