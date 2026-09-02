"""Known-good file-package: prompts + scripts, LF blobs, CRLF-on-archive attrs.

The package is files, not resolved library versions. `.gitattributes` sets
`text eol=crlf` so `git archive` converts while `git cat-file -p` stays LF —
the Windows autocrlf trap, reproduced on this Linux box.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

PACKAGE_NAME = "res0052-prompts-scripts"
PACKAGE_VERSION = "1.0.0"

# Exact blob bytes (LF). Do not convert on write.
PACKAGE_FILES: dict[str, bytes] = {
    ".gitattributes": b"* text eol=crlf\n",
    "prompts/system.md": (
        b"# system prompt\n"
        b"You are a lockfile installer for prompt/script packages.\n"
        b"Never rewrite line endings. The blob is the contract.\n"
    ),
    "prompts/user-template.md": (
        b"# user template\n"
        b"Install {{package}} at {{commit}} in resolution order.\n"
        b"Hash each file with sha256 of `git cat-file -p` bytes.\n"
    ),
    "scripts/hello.sh": (
        b"#!/bin/sh\n"
        b"echo RES-0052-hello\n"
    ),
}

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "RES-0052",
    "GIT_AUTHOR_EMAIL": "res-0052@fixture.local",
    "GIT_COMMITTER_NAME": "RES-0052",
    "GIT_COMMITTER_EMAIL": "res-0052@fixture.local",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=RES-0052",
            "-c",
            "user.email=res-0052@fixture.local",
            "-c",
            "core.autocrlf=false",
            *args,
        ],
        env=GIT_ENV,
        capture_output=True,
        check=check,
    )


def write_package_tree(root: Path) -> list[str]:
    root.mkdir(parents=True, exist_ok=True)
    order: list[str] = []
    for rel in sorted(PACKAGE_FILES):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(PACKAGE_FILES[rel])
        order.append(rel.replace("\\", "/"))
    return order


def build_package_repo(root: Path) -> dict:
    """Create a fresh git repo whose blobs are PACKAGE_FILES (LF)."""
    if root.exists():
        # Caller passes a clean temp or empty dir; do not delete arbitrary trees.
        if any(root.iterdir()):
            raise RuntimeError(f"fixture root not empty: {root}")
    write_package_tree(root)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "RES-0052 file-package fixture")
    commit = git(root, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    return {
        "repo": str(root),
        "commit": commit,
        "name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "files": sorted(PACKAGE_FILES),
    }
