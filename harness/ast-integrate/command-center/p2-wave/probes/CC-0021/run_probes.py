#!/usr/bin/env python3
"""Run both named probes (after emit_registry.py)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CMDS = [
    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CC-0021/probe1_known_present.py",
    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CC-0021/probe2_gate_controls.py",
]


def main() -> int:
    rc = 0
    for cmd in CMDS:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True)
        print(f"rc={p.returncode} {cmd}")
        if p.returncode != 0:
            rc = p.returncode
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
