#!/usr/bin/env python3
"""Independent reviewer: re-run both-states probes; do not rubber-stamp emit."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0093/probe1_planted_bad.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0093/probe2_known_good.py"
)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    fire = "fires_on_planted_bad=True" in t1 and "detector_control_known_present_found=True" in t1
    silent = "silent_on_known_good=True" in t2 and "silent_on_honest_revision=True" in t2
    fp0 = "false_positive_rate=0.0" in t2
    ok = c1 == 0 and c2 == 0 and fire and silent and fp0
    print(f"reran_probe1_exit={c1}")
    print(f"reran_probe2_exit={c2}")
    print(f"planted_bad_fires={fire}")
    print(f"known_good_and_revision_silent={silent}")
    print(f"false_positive_rate_zero={fp0}")
    if not ok:
        print("FAILED:CNL-0093 reviewer both-states")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    print(
        "scope=re-ran planted-bad and known-good/honest-revision controls; "
        "agreement with the design prose is not required for PASS"
    )
    print("SUCCESS:CNL-0093-reviewer PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
