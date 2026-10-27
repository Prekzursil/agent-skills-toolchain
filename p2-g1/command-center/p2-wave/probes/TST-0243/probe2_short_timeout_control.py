#!/usr/bin/env python3
"""TST-0243 probe 2: both-states control on an artificial ledger.

A synthetic 100-sample FIX-class ledger with nearest-rank p99 = 10.98s:
  * planted state: FIX timeout_seconds = 1 -> the join MUST report a DEFECT
    with required_timeout 12.078s and a proposed value on the 300s grid;
  * control state: the same p99 against a 3600s timeout -> ADEQUATE, and
    the control row must stay untouched by the planted defect.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from join import join  # noqa: E402


def synthetic_catalog() -> list[dict]:
    return [
        {"id": "FIX-0001", "timeout_seconds": 1},
        {"id": "FIX-0002", "timeout_seconds": 5},
        {"id": "TST-0001", "timeout_seconds": 3600},
    ]


def synthetic_ledger() -> list[dict]:
    # 100 FIX samples; sorted index 98 (nearest-rank p99 of 100) is 10.98s.
    values = [0.5] * 97 + [5.0, 10.98, 10.99]
    rows = [
        {"unit_id": f"FIX-{i:04d}", "class": "FIX", "duration_seconds": v,
         "source": "synthetic-both-states"}
        for i, v in enumerate(values)
    ]
    # the control class carries the SAME p99 against an adequate timeout
    rows += [
        {"unit_id": f"TST-{i:04d}", "class": "TST", "duration_seconds": v,
         "source": "synthetic-both-states"}
        for i, v in enumerate(values)
    ]
    return rows


def main() -> int:
    checks: dict[str, bool] = {}
    units = synthetic_catalog()
    ledger = synthetic_ledger()
    rows = join(units, ledger)

    fix = rows["FIX"]
    checks["fix_sampled_p99_is_10_98"] = abs(fix["p99_seconds"] - 10.98) < 1e-9
    checks["fires_on_short_timeout"] = fix["verdict"] == "DEFECT" and fix["adequate"] is False
    checks["required_is_p99_times_margin"] = abs(
        fix["required_timeout_seconds"] - 10.98 * 1.1
    ) < 1e-9
    checks["proposed_on_300s_grid"] = fix["proposed_new_timeout_seconds"] == 300
    checks["reason_names_class"] = fix["reason"].startswith("FIX ") and "10.980s" in fix["reason"]

    tst = rows["TST"]
    checks["control_class_adequate"] = tst["verdict"] == "ADEQUATE" and tst["adequate"] is True
    checks["silent_on_good"] = tst["proposed_new_timeout_seconds"] is None
    checks["control_class_untouched"] = (
        tst["timeout_min"] == 3600 and "DEFECT" != tst["verdict"]
    )
    checks["min_timeout_rule_used"] = fix["timeout_min"] == 1

    ok = all(checks.values())
    out = {
        "probe": "probe2-short-timeout-control",
        "unit_id": "TST-0243",
        "broken": {
            "class": fix["class"], "verdict": fix["verdict"],
            "p99_seconds": fix["p99_seconds"], "timeout_min": fix["timeout_min"],
            "n_samples": fix["n_samples"],
            "required_timeout_seconds": fix["required_timeout_seconds"],
            "proposed_new_timeout_seconds": fix["proposed_new_timeout_seconds"],
            "reason": fix["reason"],
        },
        "good": {
            "class": tst["class"], "verdict": tst["verdict"],
            "p99_seconds": tst["p99_seconds"], "timeout_min": tst["timeout_min"],
        },
        "id": "artificially-short-timeout-on-one-class",
        "fires_on_short_timeout": checks["fires_on_short_timeout"],
        "silent_on_good": checks["silent_on_good"],
        "checks": checks,
        "pass": ok,
    }
    (HERE / "probe2_short_timeout_control.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
