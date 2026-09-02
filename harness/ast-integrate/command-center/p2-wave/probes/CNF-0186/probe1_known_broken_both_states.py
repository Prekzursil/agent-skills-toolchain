#!/usr/bin/env python3
"""Probe 1: both-states (healthy SUCCESS, no stdout noise) + known-broken pin + first-fail day."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenarios as S  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0186-p1-") as tmp:
        result = S.scenario_both_states_and_known_broken(Path(tmp))
    print(
        "both_states_ok={both_states_ok} known_broken_ok={known_broken_ok} "
        "first_fail_day={first_fail_day} first_fail_held={first_fail_held_on_later_day} "
        "day1_lines={day1[lines]} day2_lines={day2[lines]}".format(**result)
    )
    if not result["pass"]:
        print("FAILED:CNF-0186-probe1 known-broken / both-states / first-fail-day")
        return 1
    print("SUCCESS:CNF-0186-probe1 known-broken control, both-states, first-fail-day")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
