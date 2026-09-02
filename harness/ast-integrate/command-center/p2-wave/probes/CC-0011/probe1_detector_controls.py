#!/usr/bin/env python3
"""Probe 1: catalog detector / false-positive / clean / historical-scope controls."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import controls  # noqa: E402


def main() -> int:
    doc = controls.run_all()
    for r in doc["results"]:
        print(
            f"{r['id']}: pass={r['pass']} "
            + " ".join(
                f"{k}={v}"
                for k, v in r.items()
                if k not in {"id", "pass"}
            )
        )
        if not r["pass"]:
            print(f"FAILED:CC-0011-probe1 {r['id']}")
            return 1
    if not doc["all_pass"]:
        print("FAILED:CC-0011-probe1 all_pass")
        return 1
    print("SUCCESS:CC-0011-probe1 detector-control false-positive known-clean historical-scope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
