#!/usr/bin/env python3
"""Fixture gate present in the tree and absent from every CI workflow."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orphan-lint")
    parser.add_argument("--strict", action="store_true", help="arm the lint")
    args = parser.parse_args(argv)
    if args.strict:
        print("SUCCESS:orphan-lint strict")
        return 0
    print("SUCCESS:orphan-lint bare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
