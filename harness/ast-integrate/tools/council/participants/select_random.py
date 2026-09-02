"""Deterministic uniform and stratified council samplers (IMP-0270)."""
from __future__ import annotations

import random
import secrets
from typing import Any


class SamplingError(RuntimeError):
    """Loud under-fill: requested quota exceeds the available stratum."""


def roster_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return list(left.get("roster_ids") or []) == list(right.get("roster_ids") or [])


def _ordered(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(pool, key=lambda p: str(p["id"]))


def _result(
    ids: list[str],
    seed: int,
    seed_source: str,
    *,
    quotas: dict[str, int] | None = None,
    pool: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    census: dict[str, int] = {}
    if pool is not None:
        by_id = {p["id"]: p for p in pool}
        for pid in ids:
            vendor = str(by_id[pid]["vendor"])
            census[vendor] = census.get(vendor, 0) + 1
    elif quotas is not None:
        census = dict(quotas)
    return {
        "roster_ids": ids,
        "seed": seed,
        "seed_source": seed_source,
        "stratum_census": census,
        "kind": "stratified" if quotas is not None else "uniform",
        "quotas": dict(quotas) if quotas is not None else None,
        "k": len(ids),
    }


def _resolve_seed(seed: int | None) -> tuple[int, str]:
    if seed is None:
        value = secrets.randbits(32)
        return int(value), "fresh-entropy"
    return int(seed), "caller"


def select_uniform(pool: list[dict[str, Any]], k: int, seed: int | None = None) -> dict[str, Any]:
    resolved, source = _resolve_seed(seed)
    rng = random.Random(resolved)
    ordered = _ordered(pool)
    ids = [p["id"] for p in rng.sample(ordered, k)]
    return _result(ids, resolved, source, pool=pool)


def select_stratified(
    pool: list[dict[str, Any]],
    quotas: dict[str, int],
    seed: int | None = None,
) -> dict[str, Any]:
    resolved, source = _resolve_seed(seed)
    rng = random.Random(resolved)
    by_stratum: dict[str, list[dict[str, Any]]] = {}
    for participant in _ordered(pool):
        by_stratum.setdefault(str(participant["vendor"]), []).append(participant)
    chosen: list[dict[str, Any]] = []
    for key in sorted(quotas):
        need = int(quotas[key])
        available = by_stratum.get(key) or []
        if need > len(available):
            raise SamplingError(
                f"refusing to under-fill stratum {key}: requested {need} available {len(available)}"
            )
        chosen.extend(rng.sample(available, need))
    rng.shuffle(chosen)
    ids = [p["id"] for p in chosen]
    return _result(ids, resolved, source, quotas=quotas, pool=pool)


def reproduce(prior: dict[str, Any], pool: list[dict[str, Any]]) -> dict[str, Any]:
    seed = prior.get("seed")
    if prior.get("kind") == "stratified" or prior.get("quotas"):
        quotas = prior.get("quotas") or prior.get("stratum_census") or {}
        return select_stratified(pool, {k: int(v) for k, v in quotas.items()}, seed=int(seed))
    return select_uniform(pool, int(prior.get("k") or len(prior.get("roster_ids") or [])), seed=int(seed))


def accumulate_stratum_counts(runs: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for run in runs:
        for key, n in (run.get("stratum_census") or {}).items():
            out[key] = out.get(key, 0.0) + float(n)
    return out


def stratum_expected_from_quotas(quotas: dict[str, int], n_draws: int) -> dict[str, float]:
    return {k: float(int(v) * n_draws) for k, v in quotas.items()}


def chi_square_gof(observed: dict[str, float], expected: dict[str, float]) -> dict[str, Any]:
    chi2 = 0.0
    for key, exp in expected.items():
        obs = float(observed.get(key, 0.0))
        if exp == 0:
            continue
        chi2 += (obs - exp) ** 2 / exp
    return {
        "chi_square": chi2,
        "proportions_match": chi2 == 0.0,
        "observed": dict(observed),
        "expected": dict(expected),
    }
