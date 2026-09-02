#!/usr/bin/env python3
"""Tree inventory and sha256 helpers for CNF-0043."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

SKIP_DIRS = {".git", "__pycache__"}


def lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(lf_bytes(data)).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def iter_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return out


def snapshot_bytes(root: Path) -> dict[str, bytes]:
    snap: dict[str, bytes] = {}
    for p in iter_files(root):
        rel = p.relative_to(root).as_posix()
        snap[rel] = lf_bytes(p.read_bytes())
    return snap


def inventory(root: Path) -> list[dict[str, Any]]:
    rows = []
    for p in iter_files(root):
        rel = p.relative_to(root).as_posix()
        data = lf_bytes(p.read_bytes())
        rows.append({"path": rel, "sha256": sha256_bytes(data), "bytes": len(data)})
    return rows


def inventory_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {r["path"]: r["sha256"] for r in rows}


def compare(pre: list[dict[str, Any]], post: list[dict[str, Any]]) -> dict[str, Any]:
    a = inventory_map(pre)
    b = inventory_map(post)
    only_pre = sorted(set(a) - set(b))
    only_post = sorted(set(b) - set(a))
    content_differ = sorted(p for p in set(a) & set(b) if a[p] != b[p])
    return {
        "pre_count": len(a),
        "post_rollback_count": len(b),
        "identical": not only_pre and not only_post and not content_differ,
        "only_pre": only_pre,
        "only_post": only_post,
        "content_differ": content_differ,
    }
