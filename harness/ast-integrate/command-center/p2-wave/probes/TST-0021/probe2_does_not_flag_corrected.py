#!/usr/bin/env python3
"""Named probe 2 (reviewer): lint is silent on the corrected forms.

Mechanically different from probe 1: does not use the planted broken fixture.
Re-lints fixtures/good/corrected.sh and re-runs the corrected reproduction.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lint import lint_path, reproduce_grep_c_or_echo_zero  # noqa: E402

GOOD = HERE / "fixtures" / "good" / "corrected.sh"
UID = "TST-0021"


def main() -> int:
    if not GOOD.is_file():
        print("FAILED:TST-0021-probe2 corrected fixture missing")
        return 1
    text = GOOD.read_text(encoding="utf-8")
    if "|| echo 0" in text:
        print("FAILED:TST-0021-probe2 corrected fixture still contains || echo 0")
        return 1
    hits = lint_path(GOOD, REPO)
    if hits:
        print("FAILED:TST-0021-probe2 lint flagged the corrected form")
        print(json.dumps(hits, indent=2)[:3000])
        return 1
    repro = reproduce_grep_c_or_echo_zero()
    if not repro["good_single_zero"]:
        print("FAILED:TST-0021-probe2 corrected reproduction was not a single 0")
        print(json.dumps(repro, sort_keys=True))
        return 1
    if not repro["miscount_proven"]:
        print("FAILED:TST-0021-probe2 both-states miscount proof failed")
        return 1
    summary = {
        "probe": "probe2-does-not-flag-corrected",
        "unit_id": UID,
        "pass": True,
        "flagged": 0,
        "corrected_stdout_lines": repro["good_stdout_lines"],
        "silent_on_good_state": True,
        "fired_on_bad_state": repro["bad_double_zero"],
    }
    print(json.dumps(summary, sort_keys=True))
    print("flagged=0 corrected_lines=" + repr(repro["good_stdout_lines"]))
    print("SUCCESS:TST-0021-probe2 lint silent on corrected form; single 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
