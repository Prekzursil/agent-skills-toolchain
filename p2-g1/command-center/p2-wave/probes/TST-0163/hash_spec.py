#!/usr/bin/env python3
"""Independent spec-file hasher for TST-0163 fan-in (evidence signal b).

Invoked as a *separate process* so the fan-in hash is not the in-process
dispatch digest. Prints sha256 of LF-normalized bytes, then pid on stderr.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_path(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: hash_spec.py <spec-file>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"missing:{path}", file=sys.stderr)
        return 1
    sys.stdout.write(digest_path(path) + "\n")
    sys.stderr.write(f"pid={os.getpid()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
