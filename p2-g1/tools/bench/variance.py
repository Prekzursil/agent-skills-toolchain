"""Pinned vs unpinned variance for TST-0297."""
from __future__ import annotations

import statistics
from typing import Any, Callable


def _run(fixture: list[dict], env: dict[str, Any], seed: int, unpinned: bool) -> float:
    acc = 0.0
    for i, row in enumerate(fixture):
        w = float(row.get("weight") or 1.0)
        if unpinned:
            acc += w * ((seed + i * 17) % 13) / 13.0
        else:
            acc += w
    return acc


def inert_seed_runner(fixture: list[dict], env: dict[str, Any], seed: int) -> float:
    return sum(float(r.get("weight") or 1.0) for r in fixture)


def null_delta_distribution(
    fixture: list[dict],
    env: dict[str, Any],
    n: int = 10,
    unpinned: bool = False,
    seed: int = 20260824,
) -> dict[str, Any]:
    means = [_run(fixture, env, seed if not unpinned else seed + i, unpinned) for i in range(n)]
    stdev = float(statistics.pstdev(means)) if len(means) > 1 else 0.0
    return {
        "n": n,
        "means": means,
        "stdev": stdev,
        "variance_floor": 0.0 if not unpinned else stdev,
        "all_identical": len(set(means)) == 1,
        "env_fingerprint": str((env or {}).get("seed")),
    }


def pin_ok(dist: dict[str, Any]) -> bool:
    return dist.get("all_identical") is True and float(dist.get("stdev") or 0) == 0.0


def independent_stdev(means: list[float]) -> float:
    if len(means) < 2:
        return 0.0
    return float(statistics.pstdev(means))


def seed_wiring_proof(
    fixture: list[dict],
    env: dict[str, Any],
    seed_a: int,
    seed_b: int,
    run_fn: Callable[..., float] | None = None,
) -> dict[str, Any]:
    fn = run_fn or (lambda fix, e, s: _run(fix, e, s, unpinned=True))
    a = [fn(fixture, env, seed_a) for _ in range(3)]
    b = [fn(fixture, env, seed_b) for _ in range(3)]
    inert = a == b
    return {
        "wired": not inert,
        "inert": inert,
        "result_set_a": a,
        "result_set_b": b,
    }
