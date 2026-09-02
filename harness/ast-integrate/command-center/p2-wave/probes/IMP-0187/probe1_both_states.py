#!/usr/bin/env python3
"""Probe 1: correlated ensemble flagged; independent ensemble not flagged (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ensemble as E  # noqa: E402


def main() -> int:
    report = E.evaluate_correlation_contract()
    print(
        json.dumps(
            {
                "probe": "probe1-both-states-correlation",
                "unit_id": "IMP-0187",
                "correlated_flagged": report["correlated_flagged"],
                "independent_not_flagged": report["independent_not_flagged"],
                "planted_shared_briefing_flagged": report[
                    "planted_shared_briefing_flagged"
                ],
                "correlated_raw_n": report["correlated_raw_n"],
                "correlated_effective_n": report["correlated_effective_n"],
                "independent_raw_n": report["independent_raw_n"],
                "independent_effective_n": report["independent_effective_n"],
                "independent_flagged_ids": report["independent_flagged_ids"],
                "naive_count_agents_choice": report["naive_count_agents_choice"],
                "collapsed_choice": report["collapsed_choice"],
            },
            sort_keys=True,
        )
    )
    print(
        f"correlated_flagged={report['correlated_flagged']} "
        f"independent_not_flagged={report['independent_not_flagged']} "
        f"planted_fires={report['planted_shared_briefing_flagged']} "
        f"effective_n={report['correlated_effective_n']}/{report['correlated_raw_n']}"
    )
    if not report["both_states"]:
        print("FAILED:IMP-0187-probe1 both-states correlation detector")
        return 1
    if report["independent_flagged_ids"]:
        print("FAILED:IMP-0187-probe1 false-positive on independent members")
        return 1
    if report["correlated_effective_n"] != 1:
        print("FAILED:IMP-0187-probe1 correlated trio must collapse to effective_n=1")
        return 1
    if report["independent_effective_n"] != 3:
        print("FAILED:IMP-0187-probe1 independent trio must keep effective_n=3")
        return 1
    print(
        "SUCCESS:IMP-0187-probe1 correlated flagged; independent not flagged; "
        "planted shared briefing fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
