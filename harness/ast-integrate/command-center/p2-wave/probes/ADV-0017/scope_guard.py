#!/usr/bin/env python3
"""Refuse sync invocation. ADV-0017 is measurement-only."""
from __future__ import annotations

import sys
from pathlib import Path

from audit_common import BANNED_SYNC, REPO, sha256_file


def argv_mentions_sync() -> list[str]:
    blob = " ".join(sys.argv).lower()
    hits = []
    for name in BANNED_SYNC:
        if name.lower() in blob:
            hits.append(name)
    return hits


def sync_scripts_on_disk() -> list[dict]:
    names = ("scripts/sync-from-live.ps1", "scripts/sync-rules.ps1")
    rows = []
    for rel in names:
        p = REPO / rel
        rows.append({"path": rel, "exists": p.is_file()})
    return rows


def tree_fingerprint(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            sha, _n = sha256_file(p)
            out[p.relative_to(root).as_posix()] = sha
    return out


def no_write_report(repo_root: Path, live_root: Path, before: dict, after: dict) -> dict:
    hits = argv_mentions_sync()
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    ok = not hits and not changed
    return {
        "id": "no-write-measurement-only",
        "sync_argv_hits": hits,
        "sync_scripts": sync_scripts_on_disk(),
        "hash_changed_paths": changed,
        "pass": ok,
        "result": "PASS" if ok else "FAIL",
        "note": (
            "Probes must not invoke either-direction sync. Any hash change in "
            "the measured trees is a unit failure."
        ),
        "repo_root": str(repo_root),
        "live_root": str(live_root),
    }
