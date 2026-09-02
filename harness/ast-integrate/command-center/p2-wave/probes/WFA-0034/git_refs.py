#!/usr/bin/env python3
"""Bare git refs whose commit dates are independent of any API JSON.

Objects are written with hashlib+zlib. No git add/commit/push is used.
`git log --format=%cI` is the read path (the git ref itself).
"""
from __future__ import annotations

import hashlib
import subprocess
import zlib
from datetime import datetime, timezone
from pathlib import Path

EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
EMPTY_TREE_STORE = b"tree 0\x00"


def iso_to_unix(iso: str) -> int:
    text = iso.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp())


def unix_to_iso_z(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_iso(value: str) -> str:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_store(kind: str, payload: bytes) -> tuple[str, bytes]:
    header = f"{kind} {len(payload)}".encode("ascii") + b"\x00"
    store = header + payload
    sha = hashlib.sha1(store).hexdigest()
    return sha, store


def write_object(git_dir: Path, sha: str, store: bytes) -> None:
    dest = git_dir / "objects" / sha[:2] / sha[2:]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(zlib.compress(store))


def write_bare_head(
    git_dir: Path,
    *,
    committer_iso: str,
    message: str,
    branch: str = "main",
) -> dict:
    """Create a bare repo whose HEAD commit date is committer_iso."""
    git_dir.mkdir(parents=True, exist_ok=True)
    ts = iso_to_unix(committer_iso)
    ident = f"WFA-0034 Fixture <wfa-0034@local> {ts} +0000"
    body = (
        f"tree {EMPTY_TREE_SHA}\n"
        f"author {ident}\n"
        f"committer {ident}\n"
        f"\n"
        f"{message.rstrip()}\n"
    ).encode("utf-8")
    commit_sha, commit_store = git_store("commit", body)
    write_object(git_dir, EMPTY_TREE_SHA, EMPTY_TREE_STORE)
    write_object(git_dir, commit_sha, commit_store)
    (git_dir / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    ref = git_dir / "refs" / "heads" / branch
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(commit_sha + "\n", encoding="utf-8")
    (git_dir / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = true\n",
        encoding="utf-8",
    )
    return {
        "git_dir": str(git_dir),
        "sha": commit_sha,
        "committer_iso": unix_to_iso_z(ts),
        "branch": branch,
    }


def read_head(git_dir: Path) -> dict | None:
    """Read default-branch HEAD commit date from the git ref itself."""
    if not git_dir.is_dir() or not (git_dir / "HEAD").is_file():
        return None
    cmd = [
        "git",
        "--git-dir",
        str(git_dir),
        "-c",
        f"safe.directory={git_dir}",
        "log",
        "-1",
        "--format=%H%n%cI",
        "HEAD",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    lines = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    try:
        iso = normalize_iso(lines[1])
    except ValueError:
        return None
    return {"sha": lines[0], "committer_iso": iso, "source": "git-ref-HEAD"}
