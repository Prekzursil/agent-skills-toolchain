#!/usr/bin/env python3
"""Run both named ARC-0003 probes. Exit 0 only if both exit 0."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = (
    HERE / "probe1_independent_replication.py",
    HERE / "probe2_negative_control.py",
)


def main() -> int:
    rc = 0
    for script in PROBES:
        p = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(HERE.parents[4]),
        )
        print(f"{script.name} exit={p.returncode}")
        if p.returncode != 0:
            rc = p.returncode or 1
    if rc == 0:
        print("SUCCESS:ARC-0003 named probes")
    else:
        print("FAILED:ARC-0003 named probes")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
