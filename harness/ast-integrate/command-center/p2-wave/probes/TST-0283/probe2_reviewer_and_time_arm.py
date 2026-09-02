#!/usr/bin/env python3
"""Probe 2: statistics reviewer + time-arm interaction.

Recomputes mean fire_effort, bootstrap CI, and Cohen's d from the raw
per-trial rows (does not trust the module's summary object). Confirms
the OR with time_minutes cannot mask a never-firing detector: timeout
is logged as time_budget, not evidence_saturation.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from typing import Mapping, Sequence

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.stopping.evidence_saturation import (  # noqa: E402
    BOOT_N,
    BOOT_SEED,
    TIME_MINUTES_FLOOR,
    experiment_time_arm,
    experiment_trials,
)

# Independent copies of the summary formulas (reviewer, not the author's object).


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / float(len(xs))


def _sd(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / float(n - 1))


def reviewer_bootstrap_ci(
    values: Sequence[float],
    *,
    n_boot: int = BOOT_N,
    alpha: float = 0.05,
    seed: int = BOOT_SEED,
) -> tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / float(n))
    means.sort()
    lo_i = int(alpha / 2.0 * n_boot)
    hi_i = min(n_boot - 1, int((1.0 - alpha / 2.0) * n_boot))
    return _mean(list(values)), means[lo_i], means[hi_i]


def reviewer_cohens_d(a: Sequence[float], b: Sequence[float]) -> float:
    na, nb = len(a), len(b)
    pooled = math.sqrt(
        ((na - 1) * _sd(a) ** 2 + (nb - 1) * _sd(b) ** 2) / float(na + nb - 2)
    )
    if pooled == 0.0:
        return 0.0
    return (_mean(a) - _mean(b)) / pooled


def reviewer_from_rows(by_n: Mapping[str, Sequence[Mapping]]) -> dict:
    per = {}
    efforts: dict[str, list[float]] = {}
    for key, rows in by_n.items():
        e = [
            float(r["fire_effort"])
            for r in rows
            if r.get("fired") and r.get("fire_effort") is not None
        ]
        c = [float(r["coverage"]) for r in rows if r.get("fired")]
        efforts[key] = e
        mean_e, lo_e, hi_e = reviewer_bootstrap_ci(e)
        mean_c, lo_c, hi_c = reviewer_bootstrap_ci(c)
        per[key] = {
            "n_fired": sum(1 for r in rows if r.get("fired")),
            "n_premature": sum(1 for r in rows if r.get("premature")),
            "mean_fire_effort": mean_e,
            "fire_effort_ci95": [lo_e, hi_e],
            "mean_coverage": mean_c,
            "coverage_ci95": [lo_c, hi_c],
        }
    d = reviewer_cohens_d(efforts["n24"], efforts["n6"])
    return {"per_n": per, "d_n24_vs_n6": d}


def close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    trials = experiment_trials()
    time_arm = experiment_time_arm(seed=28312)
    author = trials["summary"]
    reviewer = reviewer_from_rows(trials["rows"])

    mismatches: list[str] = []
    for key in ("n6", "n12", "n24"):
        a = author["per_n"][key]
        r = reviewer["per_n"][key]
        if a["n_fired"] != r["n_fired"]:
            mismatches.append(f"{key}.n_fired")
        if not close(a["mean_fire_effort"], r["mean_fire_effort"]):
            mismatches.append(f"{key}.mean_fire_effort")
        if not close(a["fire_effort_ci95"][0], r["fire_effort_ci95"][0]):
            mismatches.append(f"{key}.ci_lo")
        if not close(a["fire_effort_ci95"][1], r["fire_effort_ci95"][1]):
            mismatches.append(f"{key}.ci_hi")
        if not close(a["mean_coverage"], r["mean_coverage"]):
            mismatches.append(f"{key}.mean_coverage")
        if r["n_premature"] != 0:
            mismatches.append(f"{key}.premature")
    if not close(author["effect_size"]["d"], reviewer["d_n24_vs_n6"]):
        mismatches.append("cohens_d")

    report = {
        "probe": "probe2-reviewer-and-time-arm",
        "unit_id": "TST-0283",
        "n_trials": trials["n_trials"],
        "author_summary": author,
        "reviewer_summary": reviewer,
        "mismatches": mismatches,
        "reviewer_agrees": not mismatches,
        "time_minutes_floor": TIME_MINUTES_FLOOR,
        "time_arm": {
            "passed": time_arm["passed"],
            "checks": time_arm["checks"],
            "sat_only_reason": time_arm["cases"]["sat_only"]["stop_reason"],
            "time_only_reason": time_arm["cases"]["time_only"]["stop_reason"],
            "time_only_arms": time_arm["cases"]["time_only"]["arms_logged"],
            "time_only_silent_detector": time_arm["cases"]["time_only"][
                "detector_silent_at_timeout"
            ],
            "neither_stops": time_arm["cases"]["neither"]["stop"],
            "both_reason": time_arm["cases"]["both"]["stop_reason"],
            "live_silent_plus_timeout_reason": time_arm["cases"][
                "live_silent_plus_timeout"
            ]["stop_reason"],
            "timeout_masked_as_saturation": time_arm["cases"]["time_only"][
                "timeout_masked_as_saturation"
            ],
            "stream_fired": time_arm["stream_fired"],
        },
        "pass": (not mismatches) and trials["passed"] and time_arm["passed"],
    }
    print(json.dumps(report, indent=2, sort_keys=True, default=str))

    if mismatches:
        print("FAILED:TST-0283-probe2 reviewer mismatch:", ",".join(mismatches))
        return 1
    if not trials["passed"]:
        print("FAILED:TST-0283-probe2 trial contract (coverage/monotonic/d)")
        return 1
    if not time_arm["passed"]:
        print("FAILED:TST-0283-probe2 time-arm interaction")
        return 1
    if time_arm["cases"]["time_only"]["stop_reason"] != "time_budget":
        print("FAILED:TST-0283-probe2 timeout not logged as time_budget")
        return 1
    if time_arm["cases"]["time_only"]["timeout_masked_as_saturation"]:
        print("FAILED:TST-0283-probe2 timeout masked as saturation")
        return 1
    if time_arm["stream_fired"]:
        print("FAILED:TST-0283-probe2 still-yielding stream fired")
        return 1
    if reviewer["d_n24_vs_n6"] < 0.8:
        print("FAILED:TST-0283-probe2 Cohen's d < 0.8")
        return 1

    print(
        "SUCCESS:TST-0283-probe2 reviewer d={d:.4f} time_arm=time_budget "
        "silent_at_timeout=True".format(d=reviewer["d_n24_vs_n6"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
