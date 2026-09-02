"""Reclassify claimed sampling methods from recorded design fields.

A 'stratified' label without a partition (per-stratum population and draw)
plus replay evidence (seed or per-draw assignments) is convenience.
"""
from __future__ import annotations

from typing import Any


def has_valid_strata(rec: dict[str, Any]) -> bool:
    strata = rec.get("strata")
    if not isinstance(strata, list) or len(strata) < 2:
        return False
    pops: list[int] = []
    draws: list[int] = []
    names: set[str] = set()
    for row in strata:
        if not isinstance(row, dict):
            return False
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            return False
        if name in names:
            return False
        names.add(name)
        if not isinstance(row.get("population"), int) or not isinstance(
            row.get("draw"), int
        ):
            return False
        p, d = int(row["population"]), int(row["draw"])
        if p < 0 or d < 0 or d > p:
            return False
        pops.append(p)
        draws.append(d)
    n_pop, n_samp = rec.get("population_size"), rec.get("sample_size")
    if isinstance(n_pop, int) and sum(pops) != n_pop:
        return False
    if isinstance(n_samp, int) and sum(draws) != n_samp:
        return False
    seed = rec.get("seed")
    assignments = rec.get("stratum_assignments")
    if seed is None and not (isinstance(assignments, list) and assignments):
        return False
    return True


def is_executed(rec: dict[str, Any]) -> bool:
    if rec.get("executed") is True:
        return True
    drawn = rec.get("drawn_ids")
    if isinstance(drawn, list) and len(drawn) > 0:
        return True
    if rec.get("execution_evidence"):
        return True
    return False


def classify_method(rec: dict[str, Any]) -> str:
    n_pop = rec.get("population_size")
    n_samp = rec.get("sample_size")
    claimed = str(rec.get("claimed_method") or "").strip().lower()
    if (
        isinstance(n_pop, int)
        and isinstance(n_samp, int)
        and n_pop > 0
        and n_samp == n_pop
    ):
        return "census"
    executed = is_executed(rec)
    if not executed:
        if "stratified" in claimed:
            return "planned-stratified-unexecuted"
        return "planned-unexecuted"
    if "stratified" in claimed:
        if has_valid_strata(rec):
            return "stratified"
        return "convenience"
    if claimed in {"simple-random", "srs", "random", "uniform"} and rec.get(
        "seed"
    ) is not None:
        return "simple-random"
    if claimed in {"census", "enumerate", "exhaustive"}:
        return "convenience"
    return "convenience"
