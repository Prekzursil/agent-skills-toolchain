#!/usr/bin/env python3
"""Named probe 2: stripping atomic-append mode must produce torn lines.

Catalog tests_required: a mutation removing the atomic-append mode must produce
torn lines and turn the (8x500 clean-parse) test red. This probe is the
both-states control: atomic=True stays silent (already proven by probe 1's
contract); atomic=False must fire.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import event_log as elog  # noqa: E402

WRITERS = 8
PER = 500
EXPECTED = WRITERS * PER


def _clean_enough(result: dict) -> bool:
    return (
        result["line_count"] == EXPECTED
        and result["parsed"] == EXPECTED
        and result["torn"] == 0
        and result["unique_writer_seq"] == EXPECTED
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0429-p2-") as tmp:
        tmp_path = Path(tmp)
        good = elog.run_fanout(
            tmp_path / "good.jsonl", writers=WRITERS, per_writer=PER, atomic=True
        )
        bad = elog.run_fanout(
            tmp_path / "bad.jsonl", writers=WRITERS, per_writer=PER, atomic=False
        )

    silent_on_good = _clean_enough(good)
    # The 8x500 clean-parse test turns RED on the mutant: torn lines, or lost
    # records, or a line count that is not 4000 parseable objects.
    fired_on_bad = (not _clean_enough(bad)) and bad["torn"] > 0

    summary = {
        "good": {k: good[k] for k in ("line_count", "parsed", "torn", "all_present", "wall_seconds", "atomic")},
        "bad": {
            k: bad[k]
            for k in (
                "line_count",
                "parsed",
                "torn",
                "all_present",
                "wall_seconds",
                "atomic",
                "mutant_chunk",
            )
        },
        "bad_torn_samples": bad.get("torn_samples", [])[:4],
        "silent_on_good_state": silent_on_good,
        "fired_on_bad_state": fired_on_bad,
        "concurrency_test_red_under_mutation": not _clean_enough(bad),
    }
    print(json.dumps(summary, sort_keys=True))

    if not silent_on_good:
        print(
            f"FAILED:IMP-0429-probe2 good state not clean "
            f"lines={good['line_count']} parsed={good['parsed']} torn={good['torn']}"
        )
        return 1
    if bad["torn"] <= 0:
        print("FAILED:IMP-0429-probe2 mutation produced zero torn lines (inert detector)")
        return 1
    if _clean_enough(bad):
        print("FAILED:IMP-0429-probe2 mutation still passes 8x500 (test did not turn red)")
        return 1
    if not fired_on_bad:
        print("FAILED:IMP-0429-probe2 both-states control did not fire on the mutant")
        return 1
    print(
        f"good torn={good['torn']} bad torn={bad['torn']} "
        f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good}"
    )
    print("SUCCESS:IMP-0429-probe2 mutation removing atomic-append produces torn lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
