"""Two-signal drift detector: sha256 AND byte-size.

Fires when any relative path differs on either signal, or exists on one side only.
Silent when every relative path is present on both sides with equal sha256 and bytes.
"""
from __future__ import annotations

from pathlib import Path

from trees import census


def detect(repo_root: Path, live_root: Path) -> dict:
    snap = census(repo_root, live_root)
    drifted = [r for r in snap["rows"] if r.get("direction") != "identical"]
    fired = bool(drifted)
    return {
        "fired": fired,
        "silent": not fired,
        "drifted_count": len(drifted),
        "union_files": snap["union_files"],
        "identical": snap["identical"],
        "repo_larger": snap["repo_larger"],
        "live_larger": snap["live_larger"],
        "signals": ["sha256", "byte-size"],
        "first_paths": [r["path"] for r in drifted[:8]],
    }
