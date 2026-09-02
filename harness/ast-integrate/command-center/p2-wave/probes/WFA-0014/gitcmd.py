"""Read-only git helpers. Never git add/commit/push on the worktree.

Fixture repos may commit; they are TemporaryDirectory clones, not this estate.
`git archive` is forbidden: on this estate it has been measured to return CRLF.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

FORBIDDEN = ("archive",)


class GitError(RuntimeError):
    pass


def _argv_ok(args: list[str]) -> None:
    if args and args[0] in FORBIDDEN:
        raise GitError(f"forbidden git subcommand: {args[0]}")
    joined = " ".join(args)
    if "archive" in args:
        raise GitError(f"git archive is forbidden: {joined}")


def git(repo: Path, args: list[str], *, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    _argv_ok(args)
    e = os.environ.copy()
    if env:
        e.update(env)
    e.setdefault("GIT_OPTIONAL_LOCKS", "0")
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
        env=e,
    )
    if check and proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")[-800:]
        raise GitError(f"git {args} rc={proc.returncode}: {err}")
    return proc


def git_bytes(repo: Path, args: list[str], *, check: bool = True) -> bytes:
    proc = git(repo, args, check=check)
    return proc.stdout


def git_text(repo: Path, args: list[str], *, check: bool = True) -> str:
    return git_bytes(repo, args, check=check).decode("utf-8", "replace")


def rev_exists(repo: Path, rev: str) -> bool:
    proc = git(repo, ["rev-parse", "--verify", "--quiet", rev], check=False)
    return proc.returncode == 0


def is_git_repo(repo: Path) -> bool:
    proc = git(repo, ["rev-parse", "--is-inside-work-tree"], check=False)
    return proc.returncode == 0 and proc.stdout.strip() == b"true"


def cat_file_p(repo: Path, rev: str, path: str) -> bytes | None:
    """Committed blob bytes via `git cat-file -p`. Missing path -> None."""
    proc = git(repo, ["cat-file", "-p", f"{rev}:{path}"], check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_show_path(repo: Path, rev: str, path: str) -> bytes | None:
    """Independent blob read via `git show rev:path` (not cat-file)."""
    proc = git(repo, ["show", f"{rev}:{path}"], check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def three_dot_names(repo: Path, main: str, branch: str) -> list[str]:
    text = git_text(repo, ["diff", "--name-only", f"{main}...{branch}"])
    return [ln.replace("\\", "/") for ln in text.splitlines() if ln.strip()]


def two_tree_names(repo: Path, main: str, branch: str) -> list[str]:
    """Two-tree diff (not three-dot). Used only as a control, never as signal A."""
    text = git_text(repo, ["diff", "--name-only", main, branch])
    return [ln.replace("\\", "/") for ln in text.splitlines() if ln.strip()]


def ls_tree_names(repo: Path, rev: str) -> list[str]:
    text = git_text(repo, ["ls-tree", "-r", "--name-only", rev])
    return [ln.replace("\\", "/") for ln in text.splitlines() if ln.strip()]


def ahead_count(repo: Path, main: str, branch: str) -> int:
    text = git_text(repo, ["rev-list", "--count", f"{main}..{branch}"]).strip()
    return int(text or "0")


def remote_branches(repo: Path) -> list[str]:
    text = git_text(repo, ["for-each-ref", "--format=%(refname)", "refs/remotes/"])
    refs = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.endswith("/HEAD"):
            continue
        refs.append(ln)
    return refs


def pick_main(repo: Path) -> str | None:
    for cand in (
        "refs/remotes/origin/main",
        "refs/remotes/origin/master",
        "origin/main",
        "origin/master",
        "refs/heads/main",
        "main",
        "master",
    ):
        if rev_exists(repo, cand):
            return cand
    return None
