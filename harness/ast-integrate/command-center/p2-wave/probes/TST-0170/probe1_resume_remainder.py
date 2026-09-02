#!/usr/bin/env python3
"""Named probe 1: both-states control + live resume remainder + e2e tally.

Signal (a): budget ledger remaining before suspend vs after resume.
Signal (b): sum of consume-event deltas across both legs vs the declared cap.

Both-states: a fresh create() starts at the full declared cap on every axis.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import evaluate_two_leg, two_leg  # noqa: E402

UNIT = "TST-0170"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0170-p1-") as tmp:
        path = Path(tmp) / "budget-ledger.json"
        rep = two_leg(path)
        verdict = evaluate_two_leg(rep)
        compact = {
            "pass": verdict["pass"],
            "failed": verdict["failed"],
            "fresh_full": rep["fresh_full"],
            "pre_suspend_remaining": rep["pre_suspend"]["remaining"],
            "post_resume_remaining": rep["post_resume"]["remaining"],
            "tally": rep["tally"],
            "caps": rep["caps"],
            "tally_plus_remaining": rep["tally_plus_remaining"],
        }
    print(json.dumps({"probe": "probe1-resume-remainder", "unit_id": UNIT, **compact}, sort_keys=True))
    if not verdict["pass"]:
        print(json.dumps(verdict["checks"], indent=2, sort_keys=True))
        print(f"FAILED:{UNIT}-probe1 {verdict['failed']}")
        return 1
    print(
        "fresh_full=True resume_equals_pre_suspend=True "
        "tally_plus_remaining_equals_cap=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 resume continues remainder; fresh run starts at cap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
