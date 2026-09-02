#!/usr/bin/env python3
"""Probe 1: one unittest per failure class plus negative control and reserved-code check."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TEST = REPO / "tools/plugin/tests/test_exit_codes.py"
NEEDED = (
    "test_usage_error",
    "test_precondition_failed",
    "test_validation_failed",
    "test_permission_denied",
    "test_blocked_needs_owner",
    "test_internal_error",
    "test_negative_control_failed_prints_report_never_exits_zero",
    "test_no_collision_with_shell_reserved_values",
    "test_posix_shell_observes_the_same_integers",
    "test_success_is_zero_only_when_verified",
)


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
        print("FAILED:IMP-0055-probe1 unittest")
        return 1
    for name in NEEDED:
        if name not in text:
            print(f"FAILED:IMP-0055-probe1 missing {name}")
            return 1
    print("SUCCESS:IMP-0055-probe1 catalog cases, negative control, reserved-code check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
