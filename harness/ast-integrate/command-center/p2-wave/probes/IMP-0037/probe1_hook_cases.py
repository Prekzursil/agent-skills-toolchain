#!/usr/bin/env python3
"""Probe 1: catalog unittest battery for IMP-0037."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TEST = REPO / "tools/plugin/tests/test_deployed_copy_guard.py"


def main() -> int:
    p = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    print(text)
    if p.returncode != 0:
        print("FAILED:IMP-0037-probe1 unittest")
        return 1
    needed = (
        "test_deployed_path_warns",
        "test_live_only_path_silent",
        "test_repo_path_silent",
        "test_negative_control_record_not_prefix",
        "test_inject_never_block",
        "test_fail_open_on_forced_exception",
    )
    for name in needed:
        if name not in text:
            print(f"FAILED:IMP-0037-probe1 missing {name}")
            return 1
    print("SUCCESS:IMP-0037-probe1 catalog cases, negative control, fail-open")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
