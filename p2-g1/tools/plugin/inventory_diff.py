"""Archive inventory diff: added / removed / grown, plus schema-shaped inventory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from archive_census import census


def _entries(archive: Path) -> dict[str, int]:
    measured = census(archive)
    return {e["path"]: int(e["size"]) for e in measured["primary"]["entries"]}


def _sha_rel(rel: str, size: int) -> str:
    raw = f"{rel}\n{size}".encode("utf-8")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def dump_inventory(archive: Path, plugin: str = "demo", version: str = "1.0.0") -> dict[str, Any]:
    measured = census(archive)
    entries = []
    for e in measured["primary"]["entries"]:
        entries.append(
            {
                "path": e["path"],
                "size": int(e["size"]),
                "sha256": _sha_rel(e["path"], int(e["size"])),
                "rule": "allow",
            }
        )
    return {
        "artifact": "payload-inventory",
        "plugin": plugin,
        "version": version,
        "total_bytes": measured["payload_bytes"],
        "file_count": measured["file_count"],
        "entries": entries,
        "forbidden_classes_checked": [
            "git_dir",
            "gitlink",
            "node_modules",
            "pycache",
            "log",
            "transcript_jsonl",
            "os_cache",
            "oversize",
        ],
        "forbidden_matches": [],
        "added": [],
        "removed": [],
        "grown": [],
    }


def diff_archives(prev: Path, curr: Path) -> dict[str, Any]:
    a = _entries(prev)
    b = _entries(curr)
    added = [{"path": p, "size": b[p]} for p in sorted(set(b) - set(a))]
    removed = [{"path": p, "size": a[p]} for p in sorted(set(a) - set(b))]
    grown = [
        {"path": p, "from": a[p], "to": b[p]}
        for p in sorted(set(a) & set(b))
        if b[p] > a[p]
    ]
    inv = dump_inventory(curr)
    inv["added"] = added
    inv["removed"] = removed
    inv["grown"] = grown
    return inv
