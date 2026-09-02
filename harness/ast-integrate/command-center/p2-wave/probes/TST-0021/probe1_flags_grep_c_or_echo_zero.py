#!/usr/bin/env python3
"""Named probe 1: lint flags `grep -c ... || echo 0`; live miscount is 0\\n0."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lint import IDIOM_GREP, lint_path, reproduce_grep_c_or_echo_zero  # noqa: E402

BAD = HERE / "fixtures" / "bad" / "grep_c_or_echo_zero.sh"
UID = "TST-0021"


def main() -> int:
    if not BAD.is_file():
        print("FAILED:TST-0021-probe1 planted fixture missing")
        return 1
    hits = lint_path(BAD, REPO)
    grep_hits = [h for h in hits if h["idiom"] == IDIOM_GREP]
    if len(grep_hits) < 1:
        print("FAILED:TST-0021-probe1 lint did not flag grep -c || echo 0")
        print(json.dumps(hits, indent=2)[:2000])
        return 1
    quoted = grep_hits[0]["quoted"]
    if "echo 0" not in quoted or "grep" not in quoted:
        print("FAILED:TST-0021-probe1 quoted site missing idiom text")
        print(quoted)
        return 1
    repro = reproduce_grep_c_or_echo_zero()
    if not repro["bad_double_zero"]:
        print("FAILED:TST-0021-probe1 miscount reproduction was not 0\\n0")
        print(json.dumps(repro, sort_keys=True))
        return 1
    summary = {
        "probe": "probe1-flags-grep-c-or-echo-zero",
        "unit_id": UID,
        "pass": True,
        "flagged": len(grep_hits),
        "quoted": quoted,
        "reproduction_lines": repro["bad_stdout_lines"],
        "miscount_proven": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(f"flagged={len(grep_hits)} quoted={quoted}")
    print("repro_lines=" + repr(repro["bad_stdout_lines"]))
    print("SUCCESS:TST-0021-probe1 lint flags grep -c || echo 0; miscount is 0 then 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
