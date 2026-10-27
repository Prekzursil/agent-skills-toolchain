#!/usr/bin/env python3
"""Child used to probe command-line length. Reads --payload-file or argv filler."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-file")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args()
    if args.payload_file:
        Path(args.payload_file).read_bytes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
