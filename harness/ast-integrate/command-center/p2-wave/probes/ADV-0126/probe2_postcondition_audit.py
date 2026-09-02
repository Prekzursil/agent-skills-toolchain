#!/usr/bin/env python3
"""Probe 2: post-condition audit of preexisting artifacts after exhaustion.

Mechanically different from probe 1: re-seeds, exhausts, then only checks
byte identity and JSON parseability. A planted truncated JSON must fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import UNIT, run_probe2  # noqa: E402


def main() -> int:
    doc = run_probe2()
    print(json.dumps(doc, sort_keys=True, default=str))
    if doc.get("pass") is True:
        print(f"SUCCESS:{UNIT}-probe2 postcondition audit completed")
        return 0
    print(f"FAILED:{UNIT}-probe2 protocol did not complete")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
