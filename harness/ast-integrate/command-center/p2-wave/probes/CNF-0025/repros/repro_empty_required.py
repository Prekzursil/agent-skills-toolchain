#!/usr/bin/env python3
"""Fire iff REQUIRED.txt is missing or zero bytes. Exit 2 = fired, 0 = silent."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: repro_empty_required.py <component-dir>", file=sys.stderr)
        return 2
    gate = Path(sys.argv[1]) / "REQUIRED.txt"
    if (not gate.is_file()) or gate.stat().st_size == 0:
        print("FIRE empty-or-missing-REQUIRED.txt")
        return 2
    print("silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
