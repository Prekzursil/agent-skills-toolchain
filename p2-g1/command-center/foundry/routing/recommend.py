#!/usr/bin/env python3
"""WFA-0146 find / repair / merge / compose / build recommendation function.

Typed decision function converting a scout result (a feature vector over the
candidate registry) plus constraints into exactly one of FIND, REPAIR, MERGE,
COMPOSE or BUILD, with the deciding feature and an audit record per call.

Re-materialized 2026-10-26 by the shard22 wave-4 builder: the prior builder's
recommend.py was lost with its probe dir; the decision semantics were recovered
from the artifact's stored thresholds + deciding_feature taxonomy and verified
to reproduce all 284 stored predictions exactly (0 mismatches).

Route order (first gate wins):
  1. BUILD  - no eligible hits (empty registry hit set, retired-only, or
              licence-blocked candidates): nothing to recommend, build new.
  2. FIND   - a single high-quality, low-defect, well-covered candidate exists.
  3. MERGE  - several complementary candidates whose union coverage clears the
              bar while no single one covers everything.
  4. COMPOSE- mechanisms overlap partially; composition completes the gaps.
  5. REPAIR - one eligible candidate is salvageable at a fraction of build cost.
  6. BUILD  - default when every salvage gate fails.
"""
from __future__ import annotations

from typing import Any

ROUTES = ("FIND", "REPAIR", "MERGE", "COMPOSE", "BUILD")

THRESHOLDS: dict[str, float] = {
    "find_min_quality": 0.78,
    "find_max_defect": 0.18,
    "find_min_coverage": 0.8,
    "repair_min_quality": 0.45,
    "repair_max_defect": 0.58,
    "repair_min_coverage": 0.65,
    "repair_cost_ratio_max": 0.55,
    "merge_min_hits": 2.0,
    "merge_max_single_coverage": 0.7,
    "merge_min_union_coverage": 0.8,
    "compose_min_overlap": 0.6,
}

FEATURE_KEYS = (
    "hit_count", "eligible_count", "best_id", "best_quality", "best_defect",
    "best_coverage", "repair_cost", "build_cost", "repair_cost_ratio",
    "n_mergeable", "union_coverage", "mechanism_overlap",
    "n_mechanism_sources", "retired_only", "license_blocked",
)

DECIDING_FEATURES = (
    "no_eligible_hits",
    "find_quality_coverage_defect",
    "complementary_hits_union_coverage",
    "mechanism_overlap_incomplete_coverage",
    "repair_vs_build_within_gates",
    "repair_vs_build_threshold",
)


def _f(features: dict[str, Any], key: str, default: float = 0.0) -> float:
    v = features.get(key)
    return default if v is None else float(v)


def no_eligible_hits(features: dict[str, Any]) -> bool:
    """Nothing in the registry is recommendable: empty hits, retired-only or
    licence-blocked. The only honest route left is BUILD."""
    if features.get("retired_only") or features.get("license_blocked"):
        return True
    return _f(features, "hit_count") <= 0 or _f(features, "eligible_count") <= 0


def find_gate(features: dict[str, Any], t: dict[str, float] = THRESHOLDS) -> bool:
    """FIND: one candidate already is the tool - high quality, low defect,
    coverage above the bar. Adopting beats building."""
    return (
        _f(features, "best_quality") >= t["find_min_quality"]
        and _f(features, "best_defect") <= t["find_max_defect"]
        and _f(features, "best_coverage") >= t["find_min_coverage"]
    )


def merge_gate(features: dict[str, Any], t: dict[str, float] = THRESHOLDS) -> bool:
    """MERGE: >=2 complementary hits whose union covers the target while no
    single hit does - the union coverage is the measured complementary delta."""
    return (
        _f(features, "n_mergeable") >= t["merge_min_hits"]
        and _f(features, "union_coverage") >= t["merge_min_union_coverage"]
        and _f(features, "best_coverage") <= t["merge_max_single_coverage"]
    )


def compose_gate(features: dict[str, Any], t: dict[str, float] = THRESHOLDS) -> bool:
    """COMPOSE: mechanisms overlap substantially but coverage is incomplete -
    composing the overlapping mechanisms completes the workflow."""
    return _f(features, "mechanism_overlap") >= t["compose_min_overlap"]


def repair_gate(features: dict[str, Any], t: dict[str, float] = THRESHOLDS) -> bool:
    """REPAIR: a salvageable candidate - quality and coverage above the repair
    floor, defects within the repair ceiling, and the repair cost is at most
    the cost-ratio fraction of building."""
    return (
        _f(features, "best_quality") >= t["repair_min_quality"]
        and _f(features, "best_defect") <= t["repair_max_defect"]
        and _f(features, "best_coverage") >= t["repair_min_coverage"]
        and _f(features, "repair_cost_ratio") <= t["repair_cost_ratio_max"]
    )


# ---------------------------------------------------------------------------
# WFA-0146-REPAIR-VS-BUILD
# The REPAIR/BUILD separator is this pair of NUMERIC gates, applied after
# FIND/MERGE/COMPOSE all miss: REPAIR iff quality >= repair_min_quality AND
# defect <= repair_max_defect AND coverage >= repair_min_coverage AND
# repair_cost/build_cost <= repair_cost_ratio_max; otherwise BUILD. The two
# deciding features are best_defect and repair_cost_ratio (with the quality
# and coverage floors as gates) - a class lookup must never decide this.
# ---------------------------------------------------------------------------
def repair_vs_build(features: dict[str, Any],
                    t: dict[str, float] = THRESHOLDS) -> tuple[str, str]:
    if repair_gate(features, t):
        return "REPAIR", "repair_vs_build_within_gates"
    return "BUILD", "repair_vs_build_threshold"


def decide(features: dict[str, Any],
           thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    """Route one scout feature vector to exactly one of the five routes.

    Returns {route, deciding_feature, audit} - the audit record carries the
    feature values and the gate booleans so every call is explicable.
    """
    t = dict(THRESHOLDS)
    if thresholds:
        t.update(thresholds)
    audit = {
        "thresholds": t,
        "gates": {
            "no_eligible_hits": no_eligible_hits(features),
            "find": find_gate(features, t),
            "merge": merge_gate(features, t),
            "compose": compose_gate(features, t),
            "repair": repair_gate(features, t),
        },
        "features": {k: features.get(k) for k in FEATURE_KEYS},
    }
    if audit["gates"]["no_eligible_hits"]:
        audit["route"] = "BUILD"
        audit["deciding_feature"] = "no_eligible_hits"
        return {"route": "BUILD", "deciding_feature": "no_eligible_hits", "audit": audit}
    if find_gate(features, t):
        return {"route": "FIND", "deciding_feature": "find_quality_coverage_defect",
                "audit": audit}
    if merge_gate(features, t):
        return {"route": "MERGE", "deciding_feature": "complementary_hits_union_coverage",
                "audit": audit}
    if compose_gate(features, t):
        return {"route": "COMPOSE",
                "deciding_feature": "mechanism_overlap_incomplete_coverage",
                "audit": audit}
    route, feat = repair_vs_build(features, t)
    return {"route": route, "deciding_feature": feat, "audit": audit}


def route_histogram(rows: list[dict]) -> dict[str, int]:
    hist = {r: 0 for r in ROUTES}
    for r in rows:
        hist[r.get("predicted_route") or "BUILD"] = \
            hist.get(r.get("predicted_route") or "BUILD", 0) + 1
    return hist
