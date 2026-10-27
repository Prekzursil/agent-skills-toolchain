"""Deterministic git fixture used by IMP-0002 pack probes."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

BLOB_LF = b"payload-body-lf\nsecond-line\n"
CRLF_REL = "payload/notes.txt"
WORKTREE_CRLF = b"payload-body-lf\r\nsecond-line\r\n"


def _git(repo: Path, *args: str) -> None:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "imp0002")
    env.setdefault("GIT_AUTHOR_EMAIL", "imp0002@example.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "imp0002")
    env.setdefault("GIT_COMMITTER_EMAIL", "imp0002@example.invalid")
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"git {' '.join(args)}")


def create_pack_fixture(root: Path, crlf_worktree: bool = False) -> Path:
    root = Path(root)
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "imp0002@example.invalid")
    _git(repo, "config", "user.name", "imp0002")
    payload = repo / "payload"
    payload.mkdir(parents=True, exist_ok=True)
    (payload / "notes.txt").write_bytes(BLOB_LF)
    (payload / "keep.bin").write_bytes(b"keep-bytes\n")
    allow = root / "payload-allowlist.json"
    allow.write_text(
        '{"include":["payload/**"]}\n',
        encoding="utf-8",
    )
    (repo / "payload-allowlist.json").write_text(
        '{"include":["payload/**"]}\n',
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "imp0002 fixture")
    if crlf_worktree:
        (repo / CRLF_REL).write_bytes(WORKTREE_CRLF)
    return repo
