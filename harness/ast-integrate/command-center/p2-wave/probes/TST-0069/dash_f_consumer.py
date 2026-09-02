#!/usr/bin/env python3
"""Stand-in for git commit -F: read payload bytes from a file argument.

The apostrophe-bearing content never appears on the command line. The
Bash-tool wrap therefore has nothing to close against.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dash_f_consumer")
    parser.add_argument(
        "-F",
        dest="path",
        required=True,
        help="file whose entire contents are the payload (git commit -F shape)",
    )
    args = parser.parse_args(argv)
    data = Path(args.path).read_bytes()
    sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
