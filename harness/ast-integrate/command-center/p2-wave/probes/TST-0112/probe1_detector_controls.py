#!/usr/bin/env python3
"""Probe 1: detector controls — aligned silent, planted defects fire, classes differ."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tests import run_tests  # noqa: E402


def main() -> int:
    rows = run_tests()
    failed = [r for r in rows if r.get("result") != "PASS"]
    for row in rows:
        print(f"{row['id']} result={row['result']}")
        if row.get("error"):
            print(f"  error={row['error']}")
    print(json.dumps({"n": len(rows), "fail": len(failed)}, sort_keys=True))
    if failed:
        print("FAILED:TST-0112-probe1 detector controls")
        return 1
    print("SUCCESS:TST-0112-probe1 detector controls aligned-silent planted-fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
