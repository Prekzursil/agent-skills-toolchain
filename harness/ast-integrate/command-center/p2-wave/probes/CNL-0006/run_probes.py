#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CMDS = [
    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0006/probe1_leak_injection.py",
    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0006/probe2_both_states.py",
]


def main() -> int:
    for cmd in CMDS:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True)
        if p.returncode != 0:
            return p.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
