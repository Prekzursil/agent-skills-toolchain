#!/usr/bin/env python3
"""Run both named TST-0011 probes. Exit 0 only if both exit 0."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = (
    HERE / "probe1_close_and_controls.py",
    HERE / "probe2_live_sweep.py",
)


def main() -> int:
    rc = 0
    for script in PROBES:
        proc = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(HERE.parents[3]),
        )
        print(f"{script.name} exit={proc.returncode}")
        if proc.returncode != 0:
            rc = proc.returncode or 1
    if rc == 0:
        print("SUCCESS:TST-0011 named probes")
    else:
        print("FAILED:TST-0011 named probes")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
