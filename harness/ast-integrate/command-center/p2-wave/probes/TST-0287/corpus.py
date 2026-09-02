#!/usr/bin/env python3
"""Scripted council forecast corpus for TST-0287.

tools/council/simulate.py exists as a replacement-scoped vote kernel
(TST-0278). Its ballots have choice, not stated_p, so they cannot be
scored with Brier/log. This module is the forecast -> later ground-truth
table the scoring pipeline actually consumes. It is not a live
production-council measurement.

Construction (seed=287, no RNG in the table itself):
  five confidence bands {0.50, 0.60, 0.70, 0.80, 0.90} x 10 forecasts
  with exactly round(10 * p) positives per band (perfect in-bin rates).
  six additional forecasts have no later outcome (unresolved).
"""
from __future__ import annotations

from typing import Any

SEED = 287
BANDS = (0.50, 0.60, 0.70, 0.80, 0.90)
N_PER_BAND = 10
N_UNRESOLVED = 6
ALWAYS95 = 0.95
BOOTSTRAP_DRAWS = 2000
WILSON_Z = 1.96


def _fid(n: int) -> str:
    return f"F-{n:04d}"


def build_forecasts_and_outcomes() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    forecasts: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    n = 0
    for p in BANDS:
        n_yes = int(round(N_PER_BAND * p))
        for i in range(N_PER_BAND):
            n += 1
            fid = _fid(n)
            y = 1 if i < n_yes else 0
            forecasts.append(
                {
                    "forecast_id": fid,
                    "council_run_id": f"scripted-band-{p:.2f}",
                    "issued_at": "2026-01-01T00:00:00Z",
                    "stated_p": p,
                    "stated_confidence_pct": int(round(p * 100)),
                    "proposition": f"band-{p:.2f}-item-{i}",
                    "forecaster": "council-scripted-calibrated",
                }
            )
            outcomes.append(
                {
                    "forecast_id": fid,
                    "resolved_at": "2026-08-01T00:00:00Z",
                    "resolution_source": "scripted-ground-truth",
                    "outcome": y,
                }
            )
    for i in range(N_UNRESOLVED):
        n += 1
        fid = _fid(n)
        forecasts.append(
            {
                "forecast_id": fid,
                "council_run_id": "scripted-unresolved",
                "issued_at": "2026-08-20T00:00:00Z",
                "stated_p": 0.80,
                "stated_confidence_pct": 80,
                "proposition": f"unresolved-item-{i}",
                "forecaster": "council-scripted-calibrated",
            }
        )
    return forecasts, outcomes


def resolve(
    forecasts: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Join forecast -> later ground truth. Unresolved items are excluded, never scored."""
    by_id = {row["forecast_id"]: row for row in outcomes}
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for f in forecasts:
        hit = by_id.get(f["forecast_id"])
        if hit is None or hit.get("outcome") is None:
            unresolved.append(dict(f))
            continue
        row = dict(f)
        row["y"] = int(hit["outcome"])
        row["resolved_at"] = hit.get("resolved_at")
        row["resolution_source"] = hit.get("resolution_source")
        resolved.append(row)
    return resolved, unresolved


HAND_CASES = (
    {"p": 0.8, "y": 1},
    {"p": 0.8, "y": 0},
    {"p": 0.5, "y": 1},
)
# (0.8-1)^2 + (0.8-0)^2 + (0.5-1)^2 = 0.04+0.64+0.25 = 0.93; mean = 0.31
HAND_BRIER = 0.31
