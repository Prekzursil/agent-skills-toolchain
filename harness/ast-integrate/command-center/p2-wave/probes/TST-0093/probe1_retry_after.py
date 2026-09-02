#!/usr/bin/env python3
"""Probe 1: Retry-After on 429 is honoured; a naive immediate-retry mutant fails the same check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenarios as S  # noqa: E402

OUT = HERE / "probe1-retry-after.raw.json"


def main() -> int:
    row = S.test_retry_after_is_honoured()
    good = row["good"]
    mutant = row["mutant"]
    payload = {
        "probe": "probe1-retry-after",
        "unit_id": "TST-0093",
        "pass": bool(row["pass"]),
        "retry_after_s": good["retry_after_s"],
        "correct_gap_s": good["gap_s"],
        "correct_honoured": good["honoured"],
        "mutant_gap_s": mutant["gap_s"],
        "mutant_honoured": mutant["honoured"],
        "correct_events": good["events"],
        "mutant_events": mutant["events"],
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "correct_honoured="
        + str(good["honoured"])
        + " correct_gap_s="
        + str(good["gap_s"])
        + " mutant_honoured="
        + str(mutant["honoured"])
        + " mutant_gap_s="
        + str(mutant["gap_s"])
        + " retry_after_s="
        + str(good["retry_after_s"])
    )
    if not row["pass"]:
        print("FAILED:TST-0093-probe1 Retry-After not honoured or mutant did not go red")
        return 1
    print("SUCCESS:TST-0093-probe1 Retry-After honoured; naive mutant retries immediately")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
