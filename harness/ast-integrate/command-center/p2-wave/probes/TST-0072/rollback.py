#!/usr/bin/env python3
"""Rollback modes: additive-restore vs naive tree-replace.

Additive restore mutates only paths listed in the prior managed snapshot.
It never unlinks a path that is not in that managed set — including
user-owned files that live inside the same directory tree.
Naive replace wipes the live tree and copies the snapshot, which deletes
any user-owned path that was not in the snapshot.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fixtures import MANIFEST_NAME, write_managed_manifest
from inventory import load_managed_set


def snapshot_managed_bytes(root: Path, managed_rels: list[str]) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for rel in managed_rels:
        path = root / rel
        out[rel] = path.read_bytes() if path.is_file() else b""
    return out


def additive_restore(
    live: Path,
    prior_managed: dict[str, bytes],
    *,
    prior_managed_rels: list[str],
) -> dict:
    """Restore prior managed bytes. Delete only upgrade-added managed paths."""
    writes = 0
    deletes = 0
    skipped_user: list[str] = []
    live_managed_now = load_managed_set(live)
    prior_set = set(prior_managed_rels)

    for rel, data in prior_managed.items():
        dest = live / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        writes += 1

    for rel in sorted(live_managed_now - prior_set):
        path = live / rel
        if path.is_file():
            path.unlink()
            deletes += 1

    write_managed_manifest(live, prior_managed_rels)

    # Anything not in prior_set is user-owned and must remain.
    for path in live.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(live).as_posix()
        if rel == MANIFEST_NAME:
            continue
        if rel not in prior_set:
            skipped_user.append(rel)

    return {
        "mode": "additive",
        "writes": writes,
        "managed_deletes": deletes,
        "user_paths_left_in_place": sorted(set(skipped_user)),
    }


def naive_replace(live: Path, snapshot_tree: Path) -> dict:
    """Wipe live and copy the prior snapshot. Collateral for in-tree user files."""
    if live.exists():
        shutil.rmtree(live)
    shutil.copytree(snapshot_tree, live)
    return {"mode": "naive-replace", "writes": "tree-copy", "wiped": True}
