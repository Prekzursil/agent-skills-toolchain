#!/usr/bin/env python3
"""Probe 2: render error paths at runtime in a clean profile (static-invisible interpolation)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import dump, run_probe2  # noqa: E402


def main() -> int:
    result = run_probe2()
    dump(result)
    if not result.get("pass"):
        print("FAILED:ADV-0041-probe2 runtime error rendering")
        return 1
    print(
        "SUCCESS:ADV-0041-probe2 runtime interpolates caller paths; "
        "static templates hide them; telemetry strips planted home path"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
