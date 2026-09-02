#!/usr/bin/env python3
"""Read-only git helpers for isolated repos. Never git-archive. Never touch the host index."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "WFA-0013",
            "GIT_AUTHOR_EMAIL": "wfa-0013@invalid.example",
            "GIT_COMMITTER_NAME": "WFA-0013",
            "GIT_COMMITTER_EMAIL": "wfa-0013@invalid.example",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0",
            "EMAIL": "wfa-0013@invalid.example",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def git(repo: Path, *args: str, check: bool = True, extra_env: dict[str, str] | None = None) -> str:
    if any(a == "archive" for a in args):
        raise RuntimeError("git archive is forbidden on this estate (CRLF vs blob)")
    env = git_env()
    if extra_env:
        env.update(extra_env)
    cmd = ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {list(args)} rc={proc.returncode} stderr={(proc.stderr or '').strip()[:800]}"
        )
    return proc.stdout or ""


def is_git_repo(path: Path) -> bool:
    if not path.is_dir():
        return False
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        env=git_env(),
    )
    return proc.returncode == 0 and (proc.stdout or "").strip() == "true"


def rev_parse(repo: Path, ref: str = "HEAD") -> str:
    return git(repo, "rev-parse", ref).strip()


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    obj_type: str
    blob_sha: str
    path: str


def ls_tree(repo: Path, ref: str = "HEAD") -> list[TreeEntry]:
    """Enumerate committed paths from the named tree. Working-tree files cannot enter."""
    raw = git(repo, "ls-tree", "-r", "-z", ref)
    out: list[TreeEntry] = []
    for rec in raw.split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        parts = meta.split()
        if len(parts) != 3:
            continue
        mode, obj_type, blob_sha = parts
        if obj_type != "blob":
            continue
        out.append(TreeEntry(mode=mode, obj_type=obj_type, blob_sha=blob_sha, path=path))
    return out


def cat_file_p(repo: Path, blob_sha: str) -> bytes:
    """Read the committed blob. Never git-archive (measured to return CRLF on Windows)."""
    env = git_env()
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", "cat-file", "-p", blob_sha],
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"git cat-file -p {blob_sha} rc={proc.returncode} stderr={err}")
    return proc.stdout or b""
