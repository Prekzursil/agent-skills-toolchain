#!/usr/bin/env python3
"""Probe 2: hang-bound detector control — planted prompt caught, good command silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402


def main() -> int:
    ctrl = H.measure_hang_control()
    print(json.dumps(ctrl, sort_keys=True))
    planted = ctrl["planted"]
    good = ctrl["good_status"]
    print(
        f"planted timed_out={planted['timed_out']} elapsed={planted['elapsed_s']} "
        f"caught={planted['caught_by_hang_bound']}"
    )
    print(
        f"good_status timed_out={good['timed_out']} elapsed={good['elapsed_s']} "
        f"silent={good['silent_on_good_state']} rc={good['returncode']}"
    )
    if not ctrl["fired_on_bad_state"]:
        print("FAILED:TST-0248-probe2 planted prompting command was not caught by hang bound")
        return 1
    if not ctrl["silent_on_good_state"]:
        print("FAILED:TST-0248-probe2 hang bound fired on the good status command")
        return 1
    if not ctrl["pass"]:
        print("FAILED:TST-0248-probe2 detector control did not pass both states")
        return 1
    print(
        "BOTH-STATES planted=CAUGHT good=SILENT "
        f"bound={ctrl['hang_bound_s']} planted_timeout={ctrl['planted_timeout_s']}"
    )
    print("SUCCESS:TST-0248-probe2 hang-bound detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
