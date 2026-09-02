#!/usr/bin/env python3
"""Probe 1: catalog test cases for IMP-0046 compat diagnostics."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TEST = REPO / "tools/plugin/tests/test_compat_diagnostics.py"


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
        print("FAILED:IMP-0046-probe1 unittest")
        return 1
    needed = (
        "test_supported_cell",
        "test_unsupported_client",
        "test_unsupported_shell",
        "test_missing_interpreter",
        "test_report_names_measured_from_shell",
        "test_fabricated_unsupported_cell_has_remediation",
        "test_cmd_shim_disagreement_is_recorded",
        "test_unmodelled_shell_is_named_not_collapsed",
    )
    for name in needed:
        if f"{name} (" not in text and f"{name} " not in text:
            # unittest verbosity=2 prints "test_foo (...)"
            if name not in text:
                print(f"FAILED:IMP-0046-probe1 missing {name}")
                return 1
    print("SUCCESS:IMP-0046-probe1 catalog cases and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
