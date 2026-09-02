"""Recover deleted bytes via git cat-file / git show. Never git archive.

Catalog evidence_requirement: git archive returns CRLF worktree bytes on the
measured Windows box (3,837 vs 3,737) and would make a byte comparison lie.
This module refuses that route. If cat-file and show disagree, the object is
BLOCKED rather than a picked winner.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

FORBIDDEN = frozenset(
    {
        "archive",
        "add",
        "commit",
        "push",
        "stash",
        "checkout",
        "rebase",
        "reset",
        "gc",
        "prune",
    }
)


class RecoveryRefused(RuntimeError):
    """Caller asked for a forbidden recovery route."""


class RecoveryBlocked(RuntimeError):
    """Two allowed routes returned different bytes."""


def _check_args(args: list[str]) -> None:
    for a in args:
        name = a.split("=")[0].lstrip("-")
        if name in FORBIDDEN or a in FORBIDDEN:
            raise RecoveryRefused(
                f"forbidden git verb {a!r}: recovery is cat-file/show only"
            )


def git(git_dir: Path, args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    _check_args(args)
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    p = subprocess.run(
        ["git", *args],
        input=input_bytes,
        capture_output=True,
        env=env,
        check=False,
    )
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", "replace")[-400:]
        raise RecoveryBlocked(f"git {args[0]} failed: {err}")
    return p.stdout


def cat_file_p(git_dir: Path, oid: str) -> bytes:
    return git(git_dir, ["cat-file", "-p", oid])


def show_path(git_dir: Path, rev: str, path: str) -> bytes:
    return git(git_dir, ["show", f"{rev}:{path}"])


def recover_deleted(git_dir: Path, *, blob_oid: str, rev: str, path: str) -> bytes:
    """Two-signal recovery. Disagreement is BLOCKED, not a chosen route."""
    a = cat_file_p(git_dir, blob_oid)
    b = show_path(git_dir, rev, path)
    if a != b:
        raise RecoveryBlocked(
            f"cat-file vs show disagree for {path}: "
            f"cat-file={len(a)}B show={len(b)}B"
        )
    return a


def refuse_archive(git_dir: Path, rev: str, path: str) -> dict:
    """Negative control: asking for git archive must raise RecoveryRefused."""
    try:
        git(git_dir, ["archive", rev, path])
    except RecoveryRefused as exc:
        return {"refused": True, "reason": str(exc)}
    return {"refused": False, "reason": "git archive was not refused"}
