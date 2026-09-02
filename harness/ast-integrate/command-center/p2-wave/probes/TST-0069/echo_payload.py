#!/usr/bin/env python3
"""Argv file-route helper: print the payload file to stdout."""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        sys.stderr.write("usage: echo_payload.py PAYLOAD_FILE\n")
        return 2
    sys.stdout.buffer.write(Path(args[0]).read_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
