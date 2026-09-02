#!/usr/bin/env python3
"""Independent index-directory digest.

Walks files (no follow of symlinks), emits a canonical listing, then hashes
that listing. Intended to be spawned as a *separate process* from install so
the pre/post sha256 is not the install process observing its own writes.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def digest_index(index_dir: Path) -> dict:
    files: list[dict] = []
    if index_dir.is_dir():
        for path in sorted(index_dir.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            raw = path.read_bytes()
            files.append(
                {
                    "rel": path.relative_to(index_dir).as_posix(),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    listing = "\n".join(
        f"{row['rel']}:{row['bytes']}:{row['sha256']}" for row in files
    ).encode("utf-8")
    return {
        "dir": str(index_dir),
        "exists": index_dir.exists(),
        "is_dir": index_dir.is_dir(),
        "file_count": len(files),
        "listing_bytes": len(listing),
        "sha256": hashlib.sha256(listing).hexdigest(),
        "files": files,
        "pid": os.getpid(),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: index_hash.py <index-dir>", file=sys.stderr)
        return 2
    doc = digest_index(Path(sys.argv[1]))
    print(json.dumps(doc, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
