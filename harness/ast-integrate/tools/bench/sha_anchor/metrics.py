"""Measure Phase-0 inputs at a git sha vs the live worktree (TST-0302)."""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cat_file(repo: Path, sha: str, rel: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{sha}:{rel}"],
        capture_output=True,
        check=True,
    )
    return proc.stdout


def measure_at_sha(repo: Path, sha: str) -> dict[str, Any]:
    cases = Path(repo) / "cases"
    rels = []
    blob = b""
    if cases.is_dir():
        for p in sorted(cases.glob("*.json")):
            rel = p.relative_to(repo).as_posix()
            rels.append(rel)
            blob += _cat_file(repo, sha, rel)
    return {
        "payload_sha256": _sha(blob),
        "input_cardinality": len(rels),
        "measure_source": "git-cat-file-at-sha",
        "files": rels,
    }


def measure_worktree(repo: Path) -> dict[str, Any]:
    cases = Path(repo) / "cases"
    rels = []
    blob = b""
    if cases.is_dir():
        for p in sorted(cases.glob("*.json")):
            rels.append(p.relative_to(repo).as_posix())
            blob += p.read_bytes()
    return {
        "payload_sha256": _sha(blob),
        "input_cardinality": len(rels),
        "measure_source": "worktree-walk",
        "files": rels,
    }
