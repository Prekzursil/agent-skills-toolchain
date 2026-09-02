#!/usr/bin/env python3
"""Probe 2: synthetic Normal vs analytic answer; FPR over 100 no-change runs.

Signal (b): inverse-CDF samples from a known Normal; gate median/p95 are
checked against the closed-form population values, and the 20% / 2%
verdicts match the analytic answers. False-positive rate is measured
over 100 seeded no-change redraws.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import distribution_gate as G  # noqa: E402

UNIT = "TST-0231"
STAT_TOL = 0.01
FPR_LIMIT = 0.05


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def check_stats(label: str, observed: dict, population: dict) -> str | None:
    for field in ("median", "p95"):
        err = G.rel_err(float(observed[field]), float(population[field]))
        if err > STAT_TOL:
            return f"{label} {field} rel_err={err} obs={observed[field]} pop={population[field]}"
    return None


def main() -> int:
    syn = G.synthetic_known_distribution()
    g20 = syn["gate_20pct"]
    g2 = syn["gate_2pct"]
    if g20["verdict"] != syn["analytic_verdict_20pct"]:
        return fail(f"20pct gate={g20['verdict']} analytic={syn['analytic_verdict_20pct']}")
    if g2["verdict"] != syn["analytic_verdict_2pct"]:
        return fail(f"2pct gate={g2['verdict']} analytic={syn['analytic_verdict_2pct']}")
    if not g20.get("issued") or not g2.get("issued"):
        return fail("synthetic n>=k should issue a verdict")

    err = check_stats("baseline", g20["baseline"], syn["population_baseline"])
    if err:
        return fail(err)
    err = check_stats("candidate_20pct", g20["candidate"], syn["population_20pct"])
    if err:
        return fail(err)
    err = check_stats("candidate_2pct", g2["candidate"], syn["population_2pct"])
    if err:
        return fail(err)

    # Independent recompute of sample median/p95 (not taken from the gate return).
    base = syn["baseline_samples"]
    live_base = G.summarize(base)
    if abs(live_base["median"] - g20["baseline"]["median"]) > 1e-12:
        return fail("baseline median drift vs independent summarize")
    if abs(live_base["p95"] - g20["baseline"]["p95"]) > 1e-12:
        return fail("baseline p95 drift vs independent summarize")
    if live_base["variance"] is None:
        return fail("independent summarize omitted variance")

    fpr = G.no_change_false_positive_rate()
    rate = float(fpr["false_positive_rate"])
    if fpr["n_runs"] != G.FPR_RUNS:
        return fail(f"fpr runs {fpr['n_runs']}")
    if fpr["refused"] != 0:
        return fail(f"no-change runs refused: {fpr['refused']}")
    if rate >= FPR_LIMIT:
        return fail(f"FPR={rate} over 100 no-change runs (limit {FPR_LIMIT})")

    payload = {
        "probe": "probe2-analytic-and-fpr",
        "unit_id": UNIT,
        "family": "Normal",
        "n": syn["n"],
        "analytic_median": syn["population_baseline"]["median"],
        "analytic_p95": syn["population_baseline"]["p95"],
        "gate_median": g20["baseline"]["median"],
        "gate_p95": g20["baseline"]["p95"],
        "gate_variance": g20["baseline"]["variance"],
        "verdict_20pct": g20["verdict"],
        "verdict_2pct": g2["verdict"],
        "false_positive_rate": rate,
        "false_positive_flags": fpr["regression_flags"],
        "fpr_runs": fpr["n_runs"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"analytic_p95={syn['population_baseline']['p95']} "
        f"gate_p95={g20['baseline']['p95']} "
        f"20pct={g20['verdict']} 2pct={g2['verdict']} FPR={rate}"
    )
    print(f"SUCCESS:{UNIT}-probe2 analytic Normal agrees; FPR over 100 no-change runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
