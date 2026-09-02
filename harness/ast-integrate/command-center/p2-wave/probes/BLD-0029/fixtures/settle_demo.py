#!/usr/bin/env python3
"""Runnable named experiment used by the well-formed / jargon fixture rows."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = HERE / "settle_input.txt"


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else DEFAULT
    if not target.is_file():
        print("SETTLED:no missing-input")
        return 2
    text = target.read_text(encoding="utf-8")
    if "settle-me" in text:
        print("SETTLED:yes")
        return 0
    print("SETTLED:no")
    return 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
