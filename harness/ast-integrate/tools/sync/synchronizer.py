"""Apply a classified sync: refuse both-unique, permit one-directional."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .classifier import DIVERGED_BOTH_UNIQUE, classify_trees

PERMIT = "PERMIT"
REFUSE = "REFUSE"


def _fingerprint(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def apply_sync(
    repo_root: Path,
    live_root: Path,
    direction: str = "repo-to-live",
    apply: bool = False,
) -> dict[str, Any]:
    repo_root, live_root = Path(repo_root), Path(live_root)
    before_repo = _fingerprint(repo_root)
    before_live = _fingerprint(live_root)
    census = classify_trees(repo_root, live_root)
    rows = list(census["rows"])
    both = [r for r in rows if r["classification"] == DIVERGED_BOTH_UNIQUE]
    if both:
        for r in rows:
            r["action"] = REFUSE if r["classification"] == DIVERGED_BOTH_UNIQUE else PERMIT
        return {
            "ok": False,
            "tree_action": REFUSE,
            "writes_executed": 0,
            "live_unchanged": True,
            "repo_unchanged": True,
            "rows": rows,
        }
    writes = 0
    if apply:
        src_root, dest_root = (repo_root, live_root) if direction == "repo-to-live" else (live_root, repo_root)
        src_fp = _fingerprint(src_root)
        for rel, data in src_fp.items():
            dest = dest_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.is_file() or dest.read_bytes() != data:
                dest.write_bytes(data)
                writes += 1
    after_repo = _fingerprint(repo_root)
    after_live = _fingerprint(live_root)
    for r in rows:
        r["action"] = PERMIT
    return {
        "ok": True,
        "tree_action": PERMIT,
        "writes_executed": writes,
        "live_unchanged": after_live == before_live,
        "repo_unchanged": after_repo == before_repo,
        "rows": rows,
    }
