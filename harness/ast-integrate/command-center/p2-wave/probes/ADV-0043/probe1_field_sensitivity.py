#!/usr/bin/env python3
"""Probe 1: enumerate stored messages and classify each field by sensitivity."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import dumps, measure_probe1  # noqa: E402


def main() -> int:
    doc = measure_probe1()
    print(dumps(doc))
    ctrl = doc["detector_control"]
    print(
        "planted={0} benign_silent={1} naive_twin={2} messages={3}".format(
            ctrl["known_present_fired"],
            ctrl["known_absent_silent"],
            ctrl["naive_twin_fires_on_benign"],
            doc.get("message_count"),
        )
    )
    if not doc.get("pass"):
        print("FAILED:ADV-0043-probe1 field-sensitivity detector did not hold")
        return 1
    print("SUCCESS:ADV-0043-probe1 field-sensitivity classification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
