"""Canonical sha256 fingerprint of a generated file map."""
from __future__ import annotations

import hashlib
import json


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fingerprint(files: dict[str, bytes]) -> dict:
    rows = []
    for path in sorted(files):
        data = files[path].replace(b"\r\n", b"\n")
        rows.append(
            {
                "path": path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return {
        "files": rows,
        "file_count": len(rows),
        "tree_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
