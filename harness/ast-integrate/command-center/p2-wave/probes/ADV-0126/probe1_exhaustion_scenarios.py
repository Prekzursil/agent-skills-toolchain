#!/usr/bin/env python3
"""Probe 1: run disk-full, quota-exhausted, and commit-pressure scenarios.

Exit 0 when the bounded protocol completed (controls fired, host not touched).
Findings of REFUTED preservation are recorded; they are not a probe failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import UNIT, run_probe1  # noqa: E402


def main() -> int:
    doc = run_probe1()
    print(json.dumps(doc, sort_keys=True, default=str))
    if doc.get("pass") is True:
        print(f"SUCCESS:{UNIT}-probe1 exhaustion scenarios completed inside bounds")
        return 0
    print(f"FAILED:{UNIT}-probe1 protocol did not complete")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
