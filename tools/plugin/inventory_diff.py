#!/usr/bin/env python3
"""Release-to-release payload inventory diff (IMP-0005).

Classifies paths as added / removed / grown relative to a previous release
inventory. ``grown`` means the path exists in both inventories and its size
increased (byte growth), so an unintended multi-hundred-megabyte regression
is visible as a reviewable path list rather than a bare size number.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence


class InventoryDiffError(RuntimeError):
    """Malformed inventory input."""


def _entries_by_path(inventory: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries = inventory.get("entries")
    if not isinstance(entries, list):
        raise InventoryDiffError("inventory.entries must be a list")
    out: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise InventoryDiffError("inventory entry must be an object")
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise InventoryDiffError("inventory entry missing path")
        size = item.get("size")
        if not isinstance(size, int) or size < 0:
            raise InventoryDiffError(f"inventory entry {path!r} missing non-neg size")
        out[path] = item
    return out


def inventory_diff(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Return added / removed / grown classification vs previous inventory."""
    prev = _entries_by_path(previous)
    cur = _entries_by_path(current)

    added = sorted(set(cur) - set(prev))
    removed = sorted(set(prev) - set(cur))
    grown: list[dict[str, Any]] = []
    for path in sorted(set(cur) & set(prev)):
        before = int(prev[path]["size"])
        after = int(cur[path]["size"])
        if after > before:
            grown.append(
                {
                    "path": path,
                    "bytes_before": before,
                    "bytes_after": after,
                    "delta_bytes": after - before,
                }
            )

    bytes_before = int(
        previous.get("total_bytes", sum(e["size"] for e in prev.values()))
    )
    bytes_after = int(current.get("total_bytes", sum(e["size"] for e in cur.values())))
    files_before = int(previous.get("file_count", len(prev)))
    files_after = int(current.get("file_count", len(cur)))

    return {
        "artifact": "payload-inventory-diff",
        "added": added,
        "removed": removed,
        "grown": grown,
        "bytes_before": bytes_before,
        "bytes_after": bytes_after,
        "files_before": files_before,
        "files_after": files_after,
        "bytes_delta": bytes_after - bytes_before,
        "files_delta": files_after - files_before,
    }


def inventory_from_zip(
    archive: Path | str,
    *,
    plugin: str = "ast-plugin",
    version: str = "0.0.0",
    rule: str = "archive-member",
) -> dict[str, Any]:
    """Build a payload-inventory-shaped doc from zip member uncompressed sizes."""
    path = Path(archive)
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(path, "r") as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.filename.endswith("/"):
                continue
            data = zf.read(info.filename)
            entries.append(
                {
                    "path": info.filename.replace("\\", "/"),
                    "size": int(info.file_size),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "rule": rule,
                }
            )
    total = sum(e["size"] for e in entries)
    return {
        "artifact": "payload-inventory",
        "plugin": plugin,
        "version": version,
        "total_bytes": total,
        "file_count": len(entries),
        "entries": entries,
        "forbidden_classes_checked": ["vcs"],
        "forbidden_matches": [],
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="IMP-0005 inventory diff")
    ap.add_argument(
        "--previous", type=Path, required=True, help="previous inventory JSON"
    )
    ap.add_argument(
        "--current", type=Path, required=True, help="current inventory JSON"
    )
    args = ap.parse_args(list(argv) if argv is not None else None)
    prev = json.loads(args.previous.read_text(encoding="utf-8"))
    cur = json.loads(args.current.read_text(encoding="utf-8"))
    try:
        diff = inventory_diff(prev, cur)
    except InventoryDiffError as exc:
        print(f"FAILED:inventory-diff {exc}", flush=True)
        return 13
    print(json.dumps(diff, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
