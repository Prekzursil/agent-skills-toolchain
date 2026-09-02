#!/usr/bin/env python3
"""Run emit/write_receipts then the G-1 measure for TST-0192."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=str(REPO), env=env)
    return p.returncode


def main() -> int:
    wr = HERE / "write_receipts.py"
    measure = REPO / "command-center/p2-wave/_measure_one_delivered.py"
    rc = run([sys.executable, "-B", str(wr)])
    if rc != 0:
        return rc
    return run([sys.executable, "-B", str(measure), "TST-0192"])


if __name__ == "__main__":
    raise SystemExit(main())
