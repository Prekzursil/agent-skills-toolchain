#!/usr/bin/env python3
"""Two independent inventories of a profile tree."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fixtures import MANIFEST_NAME


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_managed_set(root: Path) -> set[str]:
    path = root / MANIFEST_NAME
    if not path.is_file():
        return set()
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {str(p).replace("\\", "/") for p in (doc.get("managed_paths") or [])}


def inventory_rglob(root: Path) -> dict[str, str]:
    """Walker 1: Path.rglob files, posix relpath -> sha256(bytes)."""
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == MANIFEST_NAME:
            continue
        out[rel] = sha256_bytes(path.read_bytes())
    return out


def inventory_walk(root: Path) -> dict[str, str]:
    """Walker 2: os.walk, independent of rglob ordering helpers."""
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel == MANIFEST_NAME:
                continue
            out[rel] = sha256_bytes(path.read_bytes())
    return out


def split_owned(files: dict[str, str], managed: set[str]) -> dict[str, dict[str, str]]:
    user = {p: h for p, h in files.items() if p not in managed}
    owned = {p: h for p, h in files.items() if p in managed}
    commands = {p: h for p, h in files.items() if p.startswith("commands/")}
    user_commands = {p: h for p, h in commands.items() if p not in managed}
    shipped_commands = {p: h for p, h in commands.items() if p in managed}
    return {
        "user": user,
        "managed": owned,
        "commands": commands,
        "user_commands": user_commands,
        "shipped_commands": shipped_commands,
    }


def deleted(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(set(before) - set(after))


def changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(p for p in before if p in after and before[p] != after[p])


def map_digest(files: dict[str, str]) -> str:
    blob = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(blob)
