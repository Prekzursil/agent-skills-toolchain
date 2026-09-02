#!/usr/bin/env python3
"""Independent sha256 of a packed archive. Does not import pack.py."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("FAILED:hash_archive usage: hash_archive.py <file>", file=sys.stderr)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"FAILED:hash_archive missing {path}", file=sys.stderr)
        return 2
    digest = sha256_path(path)
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
