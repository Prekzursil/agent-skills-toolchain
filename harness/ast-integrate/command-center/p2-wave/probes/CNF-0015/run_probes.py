#!/usr/bin/env python3
"""Run both named CNF-0015 probes. Exit 0 only if both exit 0."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = (
    HERE / "probe1_both_states.py",
    HERE / "probe2_detector_control.py",
)


def main() -> int:
    rc = 0
    for script in PROBES:
        p = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(HERE.parents[3]),
        )
        print(f"{script.name} exit={p.returncode}")
        if p.returncode != 0:
            rc = p.returncode or 1
    if rc == 0:
        print("SUCCESS:CNF-0015 named probes")
    else:
        print("FAILED:CNF-0015 named probes")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
