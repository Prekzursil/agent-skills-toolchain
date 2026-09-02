#!/usr/bin/env python3
"""Run emit then write_receipts for WFA-0017 (G-1)."""
from __future__ import annotations

import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    emit = runpy.run_path(str(HERE / "emit.py"), run_name="not_main")
    rc = int(emit["main"]())
    if rc != 0:
        return rc
    wr = runpy.run_path(str(HERE / "write_receipts.py"), run_name="not_main")
    return int(wr["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
