#!/usr/bin/env python3
"""Probe 2: sample commit-proxy VmSize, fds and threads from outside the child."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import dumps, measure_probe2  # noqa: E402


def main() -> int:
    doc = measure_probe2()
    print(dumps(doc))
    print(
        "control_ok={0} json_cap_trip={1} bomb_cap_trip={2} threads_flat={3}".format(
            doc["control"].get("completed_ok"),
            doc["json_1e7"].get("cap_trip"),
            doc["gzip_bomb"].get("cap_trip"),
            doc.get("scheduler_thread_counts_flat"),
        )
    )
    if not doc.get("pass"):
        print("FAILED:ADV-0034-probe2 external commit observer did not hold")
        return 1
    print("SUCCESS:ADV-0034-probe2 external commit/handle observer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
