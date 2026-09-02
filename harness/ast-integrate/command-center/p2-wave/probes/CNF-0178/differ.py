#!/usr/bin/env python3
"""Filesystem differ: path, size, sha256. Proof is a diff, not an assertion."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def manifest(root: Path, *, prefix: str = "") -> dict[str, dict[str, Any]]:
    """Relative-path map of every file under root."""
    root = root.resolve()
    rows: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return rows
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        key = f"{prefix}{rel}" if prefix else rel
        rows[key] = {
            "path": key,
            "size": len(raw.replace(b"\r\n", b"\n")),
            "sha256": digest_bytes(raw),
        }
    return rows


def user_data_manifest(profile: Path) -> dict[str, dict[str, Any]]:
    return manifest(profile / "user-data", prefix="user-data/")


def full_profile_manifest(profile: Path) -> dict[str, dict[str, Any]]:
    return manifest(profile)


def diff(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> dict[str, Any]:
    bkeys = set(before)
    akeys = set(after)
    added = sorted(akeys - bkeys)
    removed = sorted(bkeys - akeys)
    changed = sorted(
        k
        for k in (bkeys & akeys)
        if before[k]["sha256"] != after[k]["sha256"] or before[k]["size"] != after[k]["size"]
    )
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "empty": not (added or removed or changed),
    }


def byte_identical(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> bool:
    return diff(before, after)["empty"] is True
