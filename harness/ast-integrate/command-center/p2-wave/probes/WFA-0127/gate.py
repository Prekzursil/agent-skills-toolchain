"""Anti-rebuild gate: refuse BUILD-NEW when an existing candidate covers the goal."""
from __future__ import annotations

from typing import Any

from constants import ANTI_REBUILD_COVERAGE


def coverage(goal_mechs: list[str], cand_mechs: list[str]) -> float:
    need = [m for m in goal_mechs if m]
    if not need:
        return 0.0
    have = set(cand_mechs)
    return sum(1 for m in need if m in have) / float(len(need))


def nearest_existing(
    goal_mechs: list[str],
    verified: list[dict[str, Any]],
    threshold: float = ANTI_REBUILD_COVERAGE,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_cov = -1.0
    for row in verified:
        cov = coverage(goal_mechs, list(row.get("mechanisms") or []))
        if cov < threshold:
            continue
        quality = float(row.get("quality") or 0.0)
        key = (cov, quality)
        prev = (
            (best_cov, float(best.get("quality") or 0.0)) if best is not None else (-1.0, -1.0)
        )
        if key > prev:
            best = row
            best_cov = cov
    return best


def check(
    goal_mechs: list[str],
    verified: list[dict[str, Any]],
    *,
    skip: bool = False,
) -> dict[str, Any]:
    """Return a gate verdict. skip=True is the mutant path probes refute."""
    if skip:
        return {
            "fired": False,
            "skipped": True,
            "block_build": False,
            "cited_id": None,
            "coverage": 0.0,
            "reason": "gate-skipped-mutant",
        }
    hit = nearest_existing(goal_mechs, verified)
    if hit is None:
        return {
            "fired": True,
            "skipped": False,
            "block_build": False,
            "cited_id": None,
            "coverage": 0.0,
            "reason": "no-close-existing",
        }
    cov = coverage(goal_mechs, list(hit.get("mechanisms") or []))
    return {
        "fired": True,
        "skipped": False,
        "block_build": True,
        "cited_id": hit.get("id"),
        "coverage": cov,
        "reason": "existing-covers-goal",
        "cited_licence_class": hit.get("licence_class"),
        "cited_provenance": (hit.get("provenance") or {}).get("src"),
        "cited_source_class": hit.get("source_class"),
    }
