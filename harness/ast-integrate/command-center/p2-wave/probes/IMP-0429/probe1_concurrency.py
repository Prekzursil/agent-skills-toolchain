#!/usr/bin/env python3
"""Named probe 1: 8 concurrent writers x 500 events, atomic append.

Exact catalog question: under 8 concurrent writers emitting 500 events each,
are all 4000 lines present and is any line interleaved or truncated?
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0429-p1-") as tmp:
        path = Path(tmp) / "EVENTS.jsonl"
        result = elog.run_fanout(path, writers=WRITERS, per_writer=PER, atomic=True)

    print(json.dumps(result, sort_keys=True))
    if result.get("writer_failures"):
        print("FAILED:IMP-0429-probe1 writer process failure")
        return 1
    if result["line_count"] != EXPECTED:
        print(f"FAILED:IMP-0429-probe1 line_count={result['line_count']} want={EXPECTED}")
        return 1
    if result["parsed"] != EXPECTED:
        print(f"FAILED:IMP-0429-probe1 parsed={result['parsed']} want={EXPECTED}")
        return 1
    if result["torn"] != 0:
        print(f"FAILED:IMP-0429-probe1 torn={result['torn']} samples={result['torn_samples']}")
        return 1
    if result["unique_writer_seq"] != EXPECTED:
        print(
            f"FAILED:IMP-0429-probe1 unique_writer_seq={result['unique_writer_seq']} want={EXPECTED}"
        )
        return 1
    if not result["all_present"]:
        print("FAILED:IMP-0429-probe1 all_present is false")
        return 1
    print(
        f"lines={result['line_count']} parses={result['parsed']} torn={result['torn']} "
        f"wall={result['wall_seconds']}s atomic={result['atomic']}"
    )
    print("SUCCESS:IMP-0429-probe1 8x500 atomic append: 4000 lines, 4000 parses, zero torn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
