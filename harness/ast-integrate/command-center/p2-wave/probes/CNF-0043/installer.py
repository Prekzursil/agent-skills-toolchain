#!/usr/bin/env python3
"""Three-phase upgrade installer with named kill points.

Phases (ordered):
  1. file_copy            — place N payload over plugin files
  2. manifest_write       — record N in manifest.json
  3. cache_invalidation   — point cache at N and drop the N-1 blob

kill_after=<phase> stops immediately after that phase commits, leaving
the on-disk hybrid that rollback must undo.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scenario import N, N1, PHASES, read_core_version, write_cache, write_manifest, write_payload


def _versions(root: Path) -> dict[str, str]:
    import json

    files = read_core_version(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["version"]
    cache = json.loads((root / "cache" / "resolved.json").read_text(encoding="utf-8"))[
        "version"
    ]
    return {"files": files, "manifest": manifest, "cache": cache}


def kill_signature(root: Path, phase: str) -> dict[str, Any]:
    """Prove the kill landed in the named window, not before or after it."""
    v = _versions(root)
    expected = {
        "file_copy": {"files": N, "manifest": N1, "cache": N1},
        "manifest_write": {"files": N, "manifest": N, "cache": N1},
        "cache_invalidation": {"files": N, "manifest": N, "cache": N},
    }
    want = expected[phase]
    ok = v == want
    hybrid = len(set(v.values())) > 1
    return {
        "ok": ok,
        "phase": phase,
        "observed": v,
        "expected": want,
        "hybrid": hybrid,
        "reason": (
            "kill landed: files/manifest/cache match the named window"
            if ok
            else "kill did not land in the named window"
        ),
    }


def upgrade(root: Path, kill_after: str | None) -> dict[str, Any]:
    if kill_after is not None and kill_after not in PHASES:
        raise ValueError(f"unknown kill_after {kill_after}")
    journal: list[dict[str, Any]] = []

    write_payload(root, N)
    journal.append({"phase": "file_copy", "committed": True})
    if kill_after == "file_copy":
        return {
            "killed_after": kill_after,
            "completed_phases": ["file_copy"],
            "journal": journal,
            "complete": False,
            "versions": _versions(root),
        }

    write_manifest(root, N)
    journal.append({"phase": "manifest_write", "committed": True})
    if kill_after == "manifest_write":
        return {
            "killed_after": kill_after,
            "completed_phases": ["file_copy", "manifest_write"],
            "journal": journal,
            "complete": False,
            "versions": _versions(root),
        }

    write_cache(root, N)
    journal.append({"phase": "cache_invalidation", "committed": True})
    complete = kill_after is None
    return {
        "killed_after": kill_after,
        "completed_phases": list(PHASES),
        "journal": journal,
        "complete": complete,
        "versions": _versions(root),
    }
