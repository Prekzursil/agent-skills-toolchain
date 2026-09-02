#!/usr/bin/env python3
"""evidence_manifest.py — chain-of-custody hashing for DFIR triage.

Records a cryptographic digest (and optional byte-range offset/length) for each
evidence file so the DFIR stop rule "preserve hashes/offsets" is mechanical, not
manual. Read-only: it never writes, moves, or executes evidence. No network.

    python3 evidence_manifest.py <file> [<file> ...] [--json]
                                 [--algo sha256] [--offset N] [--length N]

Exit code: 0 = every path hashed cleanly; 1 = at least one path missing or
unreadable; 2 = usage error (no paths given).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone

_CHUNK = 65536


def _iso_mtime(path: str) -> str:
    ts = os.stat(path).st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def hash_range(
    path: str, algo: str = "sha256", offset: int = 0, length: int | None = None
):
    """Hash a byte range of ``path``; returns ``(hexdigest, bytes_hashed)``.

    Raises ValueError for an unknown algorithm so callers fail loud, not silent.
    """
    try:
        digest = hashlib.new(algo)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"unknown hash algorithm: {algo!r}") from exc

    remaining = length
    hashed = 0
    with open(path, "rb") as fh:
        if offset:
            fh.seek(offset)
        while True:
            want = _CHUNK if remaining is None else min(_CHUNK, remaining)
            if want <= 0:
                break
            block = fh.read(want)
            if not block:
                break
            digest.update(block)
            hashed += len(block)
            if remaining is not None:
                remaining -= len(block)
    return digest.hexdigest(), hashed


def manifest_record(
    path: str,
    algo: str = "sha256",
    offset: int = 0,
    length: int | None = None,
) -> dict:
    """Return one chain-of-custody record for ``path`` (never raises on I/O)."""
    record = {
        "path": path,
        "exists": os.path.exists(path),
        "algo": algo,
        "offset": offset,
        "length": length,
        "size": None,
        "bytes_hashed": None,
        "digest": None,
        "mtime_utc": None,
        "error": None,
    }
    if not record["exists"]:
        record["error"] = "path does not exist"
        return record
    if os.path.isdir(path):
        record["error"] = "path is a directory (hash files, not directories)"
        return record
    try:
        record["size"] = os.path.getsize(path)
        record["mtime_utc"] = _iso_mtime(path)
        record["digest"], record["bytes_hashed"] = hash_range(
            path, algo, offset, length
        )
    except ValueError:
        raise
    except OSError as exc:
        record["error"] = f"read error: {exc}"
    return record


def build_manifest(
    paths,
    algo: str = "sha256",
    offset: int = 0,
    length: int | None = None,
) -> list:
    return [manifest_record(p, algo, offset, length) for p in paths]


def render_table(records) -> str:
    lines = [f"{'DIGEST':<64}  {'ALGO':<8}  {'BYTES':>12}  PATH"]
    for r in records:
        digest = r["digest"] or f"<{r['error'] or 'error'}>"
        nbytes = "-" if r["bytes_hashed"] is None else str(r["bytes_hashed"])
        lines.append(f"{digest:<64}  {r['algo']:<8}  {nbytes:>12}  {r['path']}")
    return "\n".join(lines)


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="evidence_manifest.py",
        description="Chain-of-custody hashing for DFIR evidence (read-only, offline).",
        add_help=True,
    )
    parser.add_argument("paths", nargs="*", help="evidence file(s) to hash")
    parser.add_argument("--json", action="store_true", help="emit a JSON manifest")
    parser.add_argument(
        "--algo", default="sha256", help="hash algorithm (default: sha256)"
    )
    parser.add_argument(
        "--offset", type=int, default=0, help="byte offset to start hashing"
    )
    parser.add_argument("--length", type=int, default=None, help="byte count to hash")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if not args.paths:
        sys.stderr.write(
            "usage: evidence_manifest.py <file> [<file> ...] "
            "[--json] [--algo A] [--offset N] [--length N]\n"
        )
        return 2

    records = build_manifest(args.paths, args.algo, args.offset, args.length)

    if args.json:
        import json

        print(json.dumps(records, indent=2))
    else:
        print(render_table(records))

    return 0 if all(r["error"] is None for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
