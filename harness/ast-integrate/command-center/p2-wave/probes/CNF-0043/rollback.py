#!/usr/bin/env python3
"""Restore a disposable target to a captured pre-upgrade snapshot.

Inverse of installer phases: restore bytes for every snapshotted path,
remove paths the installer created that were not in the snapshot.
Never deletes a user-owned path that the snapshot recorded.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from hashes import inventory, iter_files, sha256_bytes
from scenario import USER_RELS


def restore(root: Path, snapshot: dict[str, bytes]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    current = {p.relative_to(root).as_posix() for p in iter_files(root)}
    snap_paths = set(snapshot)

    for rel in sorted(current - snap_paths):
        if rel in USER_RELS:
            steps.append(
                {
                    "op": "refuse-remove-user",
                    "path": rel,
                    "reason": "installer inverse must not remove pre-existing user data",
                }
            )
            continue
        (root / rel).unlink()
        steps.append({"op": "remove-installer-residue", "path": rel})

    for rel in sorted(snap_paths):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(snapshot[rel])
        steps.append(
            {
                "op": "restore",
                "path": rel,
                "sha256": sha256_bytes(snapshot[rel]),
                "bytes": len(snapshot[rel]),
            }
        )

    # Drop empty dirs left by residue removal (cache/blobs/2.0.0).
    for d in sorted(root.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    post = inventory(root)
    want = {rel: sha256_bytes(data) for rel, data in snapshot.items()}
    got = {row["path"]: row["sha256"] for row in post}
    return {
        "ok": got == want,
        "steps": steps,
        "restored_paths": sorted(snap_paths),
        "removed_residue": sorted(current - snap_paths),
        "user_paths_preserved": [rel for rel in USER_RELS if rel in got],
    }
