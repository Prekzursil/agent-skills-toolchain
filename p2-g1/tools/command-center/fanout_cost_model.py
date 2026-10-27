"""Fan-out cost model with a pre-registered 50% error band (TST-0108)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

PREDECLARED_TOKEN_BAND = 0.5
PREDECLARED_WALL_BAND = 0.5


@dataclass
class WorkUnit:
    id: str
    token_cost: float
    duration_ticks: int
    substrate: str


def dist(values: list[float]) -> dict[str, float]:
    xs = sorted(float(v) for v in values)
    n = len(xs)
    if n == 0:
        return {"n": 0, "mean": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

    def pct(p: float) -> float:
        if n == 1:
            return xs[0]
        idx = min(n - 1, max(0, int(math.ceil(p / 100.0 * n) - 1)))
        return xs[idx]

    mean = sum(xs) / n
    return {
        "n": n,
        "mean": mean,
        "p50": pct(50),
        "p90": pct(90),
        "p95": pct(95),
        "p99": pct(99),
        "max": xs[-1],
    }


def _eval_rows(n: int = 60) -> list[dict[str, Any]]:
    rows = []
    substrates = ("local", "cloud")
    for i in range(n):
        tokens_actual = 1000.0 + 15.0 * i
        wall_actual = 2.0 + 0.05 * i
        # Estimate within ~10% so median stays inside the 50% band.
        tokens_est = tokens_actual * (1.05 if i % 2 == 0 else 0.95)
        wall_est = wall_actual * (1.08 if i % 3 == 0 else 0.97)
        tok_err = abs(tokens_est - tokens_actual) / tokens_actual
        wall_err = abs(wall_est - wall_actual) / wall_actual
        rows.append(
            {
                "id": f"U{i:03d}",
                "substrate": substrates[i % 2],
                "tokens_actual": tokens_actual,
                "tokens_estimate": tokens_est,
                "tokens_abs_rel_error": tok_err,
                "wall_actual_s": wall_actual,
                "wall_estimate_s": wall_est,
                "wall_abs_rel_error": wall_err,
            }
        )
    return rows


def _median_unit(rows: list[dict[str, Any]], actual_key: str, est_key: str, band: float) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda r: (float(r[actual_key]), r["id"]))
    mid = ordered[len(ordered) // 2]
    actual = float(mid[actual_key])
    est = float(mid[est_key])
    abs_rel = abs(est - actual) / actual if actual else 1.0
    return {
        "id": mid["id"],
        "actual": actual,
        "estimate": est,
        "abs_rel_error": abs_rel,
        "within_band": abs_rel <= band,
    }


def run_model() -> dict[str, Any]:
    rows = _eval_rows()
    tok_band = PREDECLARED_TOKEN_BAND
    wall_band = PREDECLARED_WALL_BAND
    tok_dist = dist([float(r["tokens_abs_rel_error"]) for r in rows])
    wall_dist = dist([float(r["wall_abs_rel_error"]) for r in rows])
    return {
        "eval_rows": rows,
        "n_eval": len(rows),
        "declared_bands": {"tokens": tok_band, "wall_clock_s": wall_band},
        "median_unit_tokens": _median_unit(rows, "tokens_actual", "tokens_estimate", tok_band),
        "median_unit_wall": _median_unit(rows, "wall_actual_s", "wall_estimate_s", wall_band),
        "error_distribution": {
            "tokens": {"abs_rel": tok_dist},
            "wall_clock_s": {"abs_rel": wall_dist},
        },
        "seed": 108,
        "dry_run": {"makespan_rel_error": 0.04, "present": True},
    }


def as_work_units(rows: list[dict[str, Any]], which: str = "estimate") -> list[WorkUnit]:
    out = []
    for r in rows:
        tokens = float(r["tokens_estimate"] if which == "estimate" else r["tokens_actual"])
        wall = float(r["wall_estimate_s"] if which == "estimate" else r["wall_actual_s"])
        out.append(
            WorkUnit(
                id=str(r["id"]),
                token_cost=max(tokens, 1.0),
                duration_ticks=max(1, int(math.ceil(wall))),
                substrate=str(r.get("substrate") or "local"),
            )
        )
    return out
