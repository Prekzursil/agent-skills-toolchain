#!/usr/bin/env python3
"""Stand-ins for git commit -F, gh --body-file, and --prompt-file.

Each mode reads the named file as bytes and writes them to stdout.
The prose never appears on argv except as a path.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def emit(path: Path) -> int:
    sys.stdout.buffer.write(path.read_bytes())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tst0186-consumers")
    sub = parser.add_subparsers(dest="mode", required=True)

    c = sub.add_parser("commit")
    c.add_argument("-F", dest="path", required=True)

    p = sub.add_parser("pr")
    p.add_argument("--body-file", dest="path", required=True)

    q = sub.add_parser("prompt")
    q.add_argument("--prompt-file", dest="path", required=True)

    args = parser.parse_args(argv)
    return emit(Path(args.path))


if __name__ == "__main__":
    raise SystemExit(main())
