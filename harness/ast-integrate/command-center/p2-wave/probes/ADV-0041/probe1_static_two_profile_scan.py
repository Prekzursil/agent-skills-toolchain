#!/usr/bin/env python3
"""Probe 1: string-scan the packed plugin (minified + source maps) under two profiles."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import dump, run_probe1  # noqa: E402


def main() -> int:
    result = run_probe1()
    dump(result)
    if not result.get("pass"):
        print("FAILED:ADV-0041-probe1 static two-profile pack scan")
        return 1
    print(
        "SUCCESS:ADV-0041-probe1 packed plugin scanned; minified+map canaries "
        "recalled; two-profile tokens classified; absent token stayed zero"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
