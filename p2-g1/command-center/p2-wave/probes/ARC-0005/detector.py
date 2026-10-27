"""Repo-vs-live config drift detector for the ARC-0005 stop-hook surface.

Restored 2026-10-24: stop_hook.py imports `detector.detect` with the
contract `detect(repo, live) -> payload` where payload carries
``fired`` (bool), ``drifted_count`` (int) and ``first_paths`` (list[str]).
This module reconstructs that contract from the stop_hook caller and the
committed control fixtures: every relative path present in one tree but
missing from the other, or present in both with differing bytes, is drift.

stdlib-only by design: this module is imported in-process under
measurement PYTHONPATHs that carry stdlib-shadowing domain packages, so it
must never import dataclasses/inspect/ast transitively.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def _tree_files(root: Path) -> dict[str, bytes]:
    """Relative path -> bytes for every file under root (stable order)."""
    out: dict[str, bytes] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def detect(repo: Path | str, live: Path | str) -> dict:
    """Diff the repo-side canonical tree against the live-side tree.

    A missing side is treated as fully drifted relative to the other (the
    stop hook must fire, not silently pass, when a tree is absent).
    """
    repo_path = Path(repo)
    live_path = Path(live)
    repo_files = _tree_files(repo_path)
    live_files = _tree_files(live_path)

    drifted: list[str] = []
    kinds: dict[str, str] = {}
    for rel in sorted(set(repo_files) | set(live_files)):
        in_repo = rel in repo_files
        in_live = rel in live_files
        if in_repo and not in_live:
            drifted.append(rel)
            kinds[rel] = "missing-in-live"
        elif in_live and not in_repo:
            drifted.append(rel)
            kinds[rel] = "missing-in-repo"
        elif repo_files[rel] != live_files[rel]:
            drifted.append(rel)
            kinds[rel] = "content-differs"

    return {
        "repo_root": str(repo_path),
        "live_root": str(live_path),
        "repo_file_count": len(repo_files),
        "live_file_count": len(live_files),
        "repo_sha256": hashlib.sha256(
            b"".join(repo_files[k] for k in sorted(repo_files))
        ).hexdigest(),
        "live_sha256": hashlib.sha256(
            b"".join(live_files[k] for k in sorted(live_files))
        ).hexdigest(),
        "drifted_count": len(drifted),
        "first_paths": drifted[:8],
        "drift_kinds": kinds,
        "fired": bool(drifted),
    }
