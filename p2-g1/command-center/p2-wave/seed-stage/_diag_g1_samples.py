#!/usr/bin/env python3
"""Print G-1 measure tails for a handful of known-fail units."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT", Path(__file__).resolve().parents[3]))
MEASURE = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
UNITS = ["ADV-0005", "ADV-0010", "ADV-0004", "ADV-0003", "BLD-0055"]


def main() -> int:
    os.chdir(ROOT)
    os.environ["AST_INTEGRATE_ROOT"] = str(ROOT)
    print(f"ROOT={ROOT} py={sys.executable}", flush=True)
    for uid in UNITS:
        print(f"\n===== {uid} =====", flush=True)
        p = subprocess.run(
            [sys.executable, str(MEASURE), uid],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        text = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
        lines = text.splitlines()
        for line in lines[-40:]:
            print(line)
        print(f"exit={p.returncode}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
