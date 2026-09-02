#!/usr/bin/env python3
"""Probe 2: harness self-test — a deliberately broken runtime must FAIL.

Independent of probe1's SHA256: this probe re-derives expected acts from the
fixture (flatten-then-sort recount) and asserts the detector fires on
DropRefusalRuntime while staying silent on HonestRuntime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402


def main() -> int:
    row = H.measure_probe2()
    print(json.dumps(row, sort_keys=True))
    print(
        "honest_ok={honest_ok} drop_ok={drop_ok} drop_missing={drop_missing_acts} "
        "fired_on_bad={fired_on_bad_state} silent_on_good={silent_on_good_state}".format(
            **row
        )
    )
    print("negative_control " + row["negative_control"])
    print(
        "empty_ok={empty_ok} cached_unmutated={cached_constant_matches_recorded_on_unmutated} "
        "cached_flipped={cached_constant_rejected_when_script_flipped}".format(**row)
    )
    if not row["ok"]:
        print("FAILED:CNL-0117-probe2 broken runtime was not rejected")
        return 1
    print("SUCCESS:CNL-0117-probe2 broken runtime fails harness self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
