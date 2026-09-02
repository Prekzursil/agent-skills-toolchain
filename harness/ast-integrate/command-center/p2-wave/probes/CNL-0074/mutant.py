#!/usr/bin/env python3
"""Negative-control scorer: the state CNL-0074 must reject.

Treats every statement that has a stated_confidence as RESOLVED with y=1
(the 'we were not contradicted so we were right' cheat). That launders
UNSCOREABLE and PENDING rows into a fake calibration number.
"""
from __future__ import annotations

from typing import Any


def score_run(trajectory: dict, resolution_doc: dict | None = None) -> dict:
    del resolution_doc  # cheat ignores the resolution document
    statements = [s for s in (trajectory.get("statements") or []) if isinstance(s, dict)]
    rows = []
    briers: list[float] = []
    for stmt in statements:
        p_raw = stmt.get("stated_confidence")
        p = float(p_raw) if isinstance(p_raw, (int, float)) and not isinstance(p_raw, bool) else 1.0
        y = 1
        brier = (p - y) ** 2
        briers.append(brier)
        rows.append(
            {
                "participant_id": stmt.get("participant_id"),
                "proposition_id": stmt.get("proposition_id"),
                "status": "RESOLVED",
                "stated_confidence": p,
                "outcome": y,
                "brier": brier,
            }
        )
    n = len(rows) or 1
    return {
        "n_statements": len(rows),
        "n_resolved": len(rows),
        "n_pending": 0,
        "n_unscoreable": 0,
        "n_rejected_resolution": 0,
        "mean_brier": sum(briers) / n if rows else None,
        "not_yet_meaningful": False,
        "unscoreable_counted_as_calibrated": True,
        "rows": rows,
        "cheat": "treat_unscoreable_and_pending_as_resolved_correct",
    }
