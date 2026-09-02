"""Snapshot restore over ROLLBACK-MANIFEST trees.

Complete rollback rewrites snapshot bytes and deletes extras.
Incomplete rollback (detector control) restores snapshot bytes and
leaves planted extras in place.
"""
from __future__ import annotations

from pathlib import Path

from walker import hash_trees, read_bytes


def snapshot_bytes(root: Path, trees: list[str]) -> dict[str, bytes]:
    hashed = hash_trees(root, trees, extended=True)
    out: dict[str, bytes] = {}
    for rel in hashed:
        out[rel] = read_bytes(root / rel, extended=True)
    return out


def restore(
    root: Path,
    trees: list[str],
    snap: dict[str, bytes],
    *,
    delete_extras: bool,
) -> None:
    for rel, data in snap.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    if not delete_extras:
        return
    current = hash_trees(root, trees, extended=True)
    for rel in current:
        if rel not in snap:
            (root / rel).unlink()
