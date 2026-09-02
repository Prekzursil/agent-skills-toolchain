#!/usr/bin/env python3
"""Fixture gate: --strict arms the BROKEN-token check. Bare invocation is silent."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="armed-gate")
    parser.add_argument("--strict", action="store_true", help="arm the BROKEN-token check")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    text = Path(args.path).read_text(encoding="utf-8")
    if args.strict and "BROKEN" in text:
        print("FAILED:armed-gate BROKEN token present")
        return 1
    print("SUCCESS:armed-gate silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
