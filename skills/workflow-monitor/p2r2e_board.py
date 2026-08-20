#!/usr/bin/env python3
"""Shim so `mon p2r2e` launches the live Scaleway/local Prompt Two board."""

from __future__ import annotations

import runpy
from pathlib import Path

TARGET = (
    Path.home()
    / "source"
    / "ast-integrate"
    / "command-center"
    / "p2-wave"
    / "p2_fleet_board.py"
)


def main() -> None:
    import sys

    sys.argv = [str(TARGET), "--watch", "5"]
    runpy.run_path(str(TARGET), run_name="__main__")


if __name__ == "__main__":
    main()
