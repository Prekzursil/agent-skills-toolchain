#!/usr/bin/env python3
"""Evidence-saturation detector vs search fatigue.

Saturation is NOT elapsed time, NOT query count, and NOT 'we got tired'.
It is the collapse of marginal yield of *new independent mechanisms* per
additional *diverse* query, after a minimum search budget.

Search fatigue is yield collapse caused by repeating the same query family
while the search log has not earned a diverse zero-yield streak.

Independent evidence uses mechanism_id, not source_id string equality
(mirrored copies of one paper do not count as 12 sources).
"""
from __future__ import annotations

from typing import Any

STREAK_K = 3
YIELD_FLOOR = 0
MIN_QUERIES = 6
MIN_INDEPENDENT = 1


def _mech(fixture: dict[str, Any], source_id: str) -> str:
    for row in fixture["corpus_sources"]:
        if row["source_id"] == source_id:
            return str(row["mechanism_id"])
    raise KeyError(source_id)


def ground_truth_independent(fixture: dict[str, Any]) -> int:
    return len({row["mechanism_id"] for row in fixture["corpus_sources"]})


def detect(fixture: dict[str, Any]) -> dict[str, Any]:
    seen: set[str] = set()
    curve: list[dict[str, Any]] = []
    zero_families: list[str] = []
    fire_after_query_index: int | None = None
    last_sat = False
    last_reason = "empty_log"

    queries = list(fixture.get("queries") or [])
    if not queries:
        return {
            "evidence_saturation": False,
            "reason": "empty_log",
            "independent_mechanisms_found": 0,
            "ground_truth_independent_count": ground_truth_independent(fixture),
            "fire_after_query_index": None,
            "yield_curve": [],
            "source_ids_seen": 0,
            "missed_independent_if_stop_here": ground_truth_independent(fixture),
            "params": {
                "STREAK_K": STREAK_K,
                "YIELD_FLOOR": YIELD_FLOOR,
                "MIN_QUERIES": MIN_QUERIES,
                "MIN_INDEPENDENT": MIN_INDEPENDENT,
            },
        }

    source_ids_seen: set[str] = set()
    for i, q in enumerate(queries):
        family = str(q["query_family"])
        retrieved = list(q.get("retrieved_source_ids") or [])
        new_mechs: list[str] = []
        for sid in retrieved:
            source_ids_seen.add(sid)
            m = _mech(fixture, sid)
            if m not in seen:
                new_mechs.append(m)
                seen.add(m)
        new_count = len(new_mechs)
        if new_count <= YIELD_FLOOR:
            zero_families.append(family)
        else:
            zero_families = []

        sat = False
        fatigue = False
        if (
            i + 1 >= MIN_QUERIES
            and len(seen) >= MIN_INDEPENDENT
            and len(zero_families) >= STREAK_K
        ):
            window = zero_families[-STREAK_K:]
            if len(set(window)) == STREAK_K:
                sat = True
            else:
                fatigue = True
        elif len(zero_families) >= STREAK_K and len(set(zero_families[-STREAK_K:])) < STREAK_K:
            fatigue = True

        if sat and fire_after_query_index is None:
            fire_after_query_index = i
        last_sat = sat
        if sat:
            last_reason = "saturated"
        elif fatigue:
            last_reason = "search_fatigue"
        elif new_count > YIELD_FLOOR:
            last_reason = "still_yielding"
        else:
            last_reason = last_reason if last_reason != "empty_log" else "still_yielding"

        curve.append(
            {
                "i": i,
                "query_id": q["query_id"],
                "query_family": family,
                "retrieved_source_ids": retrieved,
                "new_independent": new_count,
                "cumulative_independent": len(seen),
                "zero_streak": len(zero_families),
                "saturated_this_tick": sat,
                "fatigue_this_tick": fatigue,
            }
        )

    gt = ground_truth_independent(fixture)
    found = len(seen)
    return {
        "evidence_saturation": bool(last_sat),
        "reason": last_reason,
        "independent_mechanisms_found": found,
        "ground_truth_independent_count": gt,
        "fire_after_query_index": fire_after_query_index,
        "yield_curve": curve,
        "source_ids_seen": len(source_ids_seen),
        "missed_independent_if_stop_here": max(0, gt - found),
        "params": {
            "STREAK_K": STREAK_K,
            "YIELD_FLOOR": YIELD_FLOOR,
            "MIN_QUERIES": MIN_QUERIES,
            "MIN_INDEPENDENT": MIN_INDEPENDENT,
        },
    }
