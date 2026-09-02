#!/usr/bin/env python3
"""Probe 2: 429 storm does not duplicate work; 529 does not self-throttle concurrency.

Mechanically different from probe 1: this entry point never inspects Retry-After
gaps. It joins work-run counts to mock status codes and compares the concurrency
setting before vs after an overload (529) storm.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenarios as S  # noqa: E402

OUT = HERE / "probe2-storm-concurrency.raw.json"


def main() -> int:
    dup = S.test_no_duplicate_execution_after_a_429_storm()
    conc = S.test_concurrency_setting_is_not_self_throttled()
    storm = conc["good"]
    payload = {
        "probe": "probe2-storm-concurrency",
        "unit_id": "TST-0093",
        "pass": bool(dup["pass"] and conc["pass"]),
        "work_runs_correct": dup["good"]["work_runs"],
        "n_workers_correct": dup["good"]["n_workers"],
        "mutant_duplicate": dup["mutant"]["duplicate"],
        "mutant_work_runs": dup["mutant"]["work_runs"],
        "storm_n_429": storm["n_429"],
        "storm_n_529": storm["n_529"],
        "storm_n_200": storm["n_200"],
        "concurrency_initial": storm["concurrency_initial"],
        "concurrency_final": storm["concurrency_final"],
        "concurrency_unchanged": storm["unchanged"],
        "mutant_concurrency_final": conc["mutant"]["concurrency_final"],
        "duplicate_units": storm["duplicate_units"],
        "missing": storm["missing"],
        "timeline": storm["events"],
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "duplicate_units="
        + str(len(storm["duplicate_units"]))
        + " work_runs_correct="
        + str(dup["good"]["work_runs"])
        + " mutant_work_runs="
        + str(dup["mutant"]["work_runs"])
        + " n_429="
        + str(storm["n_429"])
        + " n_529="
        + str(storm["n_529"])
        + " concurrency="
        + str(storm["concurrency_initial"])
        + "->"
        + str(storm["concurrency_final"])
        + " mutant_concurrency_final="
        + str(conc["mutant"]["concurrency_final"])
    )
    if not dup["pass"]:
        print("FAILED:TST-0093-probe2 duplicate execution after 429 storm")
        return 1
    if not conc["pass"]:
        print("FAILED:TST-0093-probe2 concurrency was self-throttled or mutant silent")
        return 1
    print(
        "SUCCESS:TST-0093-probe2 no duplicate work; concurrency unchanged after 529; "
        "mutants go red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
