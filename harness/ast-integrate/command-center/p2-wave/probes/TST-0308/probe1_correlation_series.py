#!/usr/bin/env python3
"""Probe 1: metric-to-outcome correlation series across >=5 iterations.

Both states: a faithful proxy that improves with the end-state must NOT
raise P1; a gamed proxy that rises while the end-state falls MUST raise
P1. A single-iteration snapshot is rejected as insufficient evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.goodhart import (  # noqa: E402
    MIN_ITERATIONS,
    correlation_series,
    detect_goodhart,
    evaluate_metric_gain,
)
from bench.simulate import (  # noqa: E402
    FAITHFUL_METRIC,
    GAMEABLE_METRIC,
    OUTCOME_ID,
    simulate_campaign,
)

UNIT = "TST-0308"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    goodhart_rows = simulate_campaign("goodhart", n_cases=32, n_iters=6, seed=308)
    faithful_rows = simulate_campaign("faithful", n_cases=32, n_iters=6, seed=308)
    g_series = correlation_series(
        goodhart_rows, metric_id=GAMEABLE_METRIC, outcome_id=OUTCOME_ID
    )
    f_series = correlation_series(
        faithful_rows, metric_id=FAITHFUL_METRIC, outcome_id=OUTCOME_ID
    )
    if len(g_series) < MIN_ITERATIONS or len(f_series) < MIN_ITERATIONS:
        return fail(
            f"series too short goodhart={len(g_series)} faithful={len(f_series)}"
        )

    g_find = detect_goodhart(g_series)
    f_find = detect_goodhart(f_series)
    g_live = evaluate_metric_gain(g_series)
    g_vacuous = evaluate_metric_gain(g_series, ignore_decay=True)
    f_live = evaluate_metric_gain(f_series)

    if not g_find.fired or g_find.severity != "P1":
        return fail(f"synthetic Goodhart did not raise P1: {g_find.reason}")
    if g_live["celebrate"]:
        return fail("live evaluator celebrated a decayed proxy")
    if not g_vacuous["celebrate"]:
        return fail("vacuous twin did not celebrate metric-up (control silent)")
    if f_find.fired:
        return fail(f"faithful series raised P1: {f_find.reason}")
    if not f_live["celebrate"]:
        return fail("faithful metric gain was not celebrable")

    snap = detect_goodhart(g_series[:1])
    if snap.fired:
        return fail("single-iteration snapshot must not be enough to claim decay")

    payload = {
        "probe": "probe1-correlation-series",
        "unit_id": UNIT,
        "n_iterations": len(g_series),
        "outcome_id": OUTCOME_ID,
        "outcome_kind": "deterministic-end-state",
        "outcome_is_not_the_metric": True,
        "goodhart": {
            "metric_id": GAMEABLE_METRIC,
            "series": g_series,
            "finding": g_find.as_dict(),
            "celebrate_live": g_live["celebrate"],
            "celebrate_vacuous_twin": g_vacuous["celebrate"],
        },
        "faithful": {
            "metric_id": FAITHFUL_METRIC,
            "series": f_series,
            "finding": f_find.as_dict(),
            "celebrate_live": f_live["celebrate"],
        },
        "snapshot_insufficient": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0308-probe1 "
        f"iters={len(g_series)} goodhart_P1={g_find.fired} "
        f"faithful_P1={f_find.fired} "
        f"series[0].r={g_series[0]['pearson_r']} "
        f"series[-1].r={g_series[-1]['pearson_r']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
