"""GitHub Actions strategy.matrix expansion (cartesian + exclude + include).

Unexpanded matrix jobs under-count runtime legs. This module materialises
the cartesian product GitHub would schedule for a static matrix (no
fromJSON / runtime-computed include).
"""
from __future__ import annotations

from itertools import product
from typing import Any


def _as_list(needs: Any) -> list[str]:
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    if isinstance(needs, list):
        return [str(x) for x in needs]
    return [str(needs)]


def matrix_axes(strategy: dict | None) -> dict[str, list[Any]]:
    if not isinstance(strategy, dict):
        return {}
    matrix = strategy.get("matrix")
    if not isinstance(matrix, dict):
        return {}
    axes: dict[str, list[Any]] = {}
    for key, val in matrix.items():
        if key in {"include", "exclude"}:
            continue
        if isinstance(val, list):
            axes[str(key)] = list(val)
        else:
            axes[str(key)] = [val]
    return axes


def _match(leg: dict[str, Any], spec: dict[str, Any]) -> bool:
    return all(leg.get(k) == v for k, v in spec.items())


def expand_matrix(job: dict | None) -> list[dict[str, Any]]:
    """Return concrete matrix legs. No strategy → one empty leg."""
    job = job or {}
    strategy = job.get("strategy") if isinstance(job.get("strategy"), dict) else {}
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not isinstance(matrix, dict) or not matrix:
        return [{}]
    axes = matrix_axes(strategy)
    if not axes:
        legs: list[dict[str, Any]] = []
    else:
        keys = list(axes.keys())
        legs = [dict(zip(keys, combo)) for combo in product(*(axes[k] for k in keys))]
    exclude = matrix.get("exclude") or []
    if isinstance(exclude, dict):
        exclude = [exclude]
    if isinstance(exclude, list):
        filtered = []
        for leg in legs:
            dropped = False
            for spec in exclude:
                if isinstance(spec, dict) and _match(leg, spec):
                    dropped = True
                    break
            if not dropped:
                filtered.append(leg)
        legs = filtered
    include = matrix.get("include") or []
    if isinstance(include, dict):
        include = [include]
    if isinstance(include, list):
        for spec in include:
            if not isinstance(spec, dict):
                continue
            if spec not in legs:
                legs.append(dict(spec))
    return legs or [{}]


def unexpanded_job_count(jobs: dict) -> int:
    return len(jobs or {})


def expanded_job_count(jobs: dict) -> int:
    n = 0
    for job in (jobs or {}).values():
        if isinstance(job, dict):
            n += len(expand_matrix(job))
        else:
            n += 1
    return n


def leg_suffix(leg: dict[str, Any]) -> str:
    if not leg:
        return ""
    parts = [f"{k}={leg[k]}" for k in sorted(leg)]
    return ",".join(parts)


normalize_needs = _as_list
