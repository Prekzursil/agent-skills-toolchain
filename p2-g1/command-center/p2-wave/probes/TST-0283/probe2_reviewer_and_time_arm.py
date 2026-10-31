#!/usr/bin/env python3
"""TST-0283 probe 2: the OR time-arm cannot mask a silent detector.

T3: forced-timeout logs the time arm ONLY (stop_reason=timeout,
evidence_saturation=False, timeout NOT relabeled as saturation); a saturated
corpus finishing before any budget logs the saturation arm only; a saturated
corpus AT the budget logs both arms distinctly. T4: the fire-point
distribution over 40 seeds is reported (mean/min/max).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
from council.stopping.evidence_saturation import (  # noqa: E402
    experiment_time_arm,
    experiment_trials,
)


def main() -> int:
    checks: dict[str, bool] = {}

    ta = experiment_time_arm()
    cases = ta["cases"]
    checks["forced_is_timeout_not_saturation"] = (
        cases["forced"]["stop_reason"] == "timeout"
        and cases["forced"]["evidence_saturation"] is False
    )
    checks["forced_not_masked"] = (
        cases["forced"]["timeout_masked_as_saturation"] is False
    )
    checks["forced_arms_time_only"] = cases["forced"]["arms_logged"] == [
        "time_budget"
    ]
    checks["both_logs_both_arms"] = cases["both"]["arms_logged"] == [
        "evidence_saturation",
        "time_budget",
    ]
    checks["both_reason_both"] = cases["both"]["stop_reason"] == "both"
    checks["early_saturation_only"] = (
        cases["early"]["stop_reason"] == "saturation"
        and cases["early"]["time_arm"] is False
    )

    tr = experiment_trials(n=40)
    checks["trials_all_fire"] = tr["passed"]
    checks["trials_mean_reported"] = tr["mean_fire_effort"] is not None
    checks["trials_fire_after_collapse"] = tr["min_fire_effort"] > 12

    out = {
        "probe": "probe2_reviewer_and_time_arm",
        "unit": "TST-0283",
        "arm_cases": ta["cases"],
        "trials": tr,
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-time-arm.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True)[:2000])
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
