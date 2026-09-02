#!/usr/bin/env python3
"""Shared staging trees for TST-0207 named probes."""
from __future__ import annotations

from pathlib import Path

JUNK_BYTES = 200 * 1024 * 1024

FIXTURE_ALLOWLIST = {
    "mode": "allowlist",
    "globs": [
        "plugin.json",
        "README.md",
        "src/**/*.py",
        "payload.bin",
    ],
    "size_ceiling_bytes": 1_048_576,
    "on_ceiling_exceeded": "fail",
}


def write_clean(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "plugin.json").write_text('{"name":"tst-0207-fixture","version":"0.0.1"}\n', encoding="utf-8")
    (root / "README.md").write_text("allowlisted payload for TST-0207\n", encoding="utf-8")
    (root / "src" / "app.py").write_text("print('tst-0207')\n", encoding="utf-8")


def plant_git(root: Path) -> list[str]:
    git = root / ".git"
    git.mkdir(parents=True, exist_ok=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    return [".git/HEAD", ".git/config"]


def plant_junk(root: Path, nbytes: int = JUNK_BYTES) -> dict:
    junk = root / "junk.bin"
    with junk.open("wb") as fh:
        fh.truncate(nbytes)
    size = int(junk.stat().st_size)
    if size != nbytes:
        raise RuntimeError(f"junk.bin st_size={size} wanted={nbytes}")
    return {"path": "junk.bin", "bytes": size}


def denylist_would_select(rel: str) -> bool:
    """Naive denylist mutant: skip typical junk names, include everything else.

    junk.bin is NOT a typical denylist entry, so a denylist packer would ship it.
    """
    posix = rel.replace("\\", "/")
    parts = [p for p in posix.split("/") if p]
    if any(p in {".git", "node_modules", "__pycache__", ".cache"} for p in parts):
        return False
    lower = parts[-1].lower() if parts else ""
    if lower.endswith((".log", ".pyc")):
        return False
    return True
