"""Git helpers for the Phase-0 baseline store (TST-0302)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        env=env,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).decode("utf-8", "replace"))
    return proc


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True, capture_output=True)
    _run(path, "config", "user.email", "tst0302@test.invalid")
    _run(path, "config", "user.name", "TST-0302")
    _run(path, "config", "commit.gpgsign", "false")
    return path


def commit_files(repo: Path, files: dict[str, bytes], message: str) -> str:
    for rel, body in files.items():
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        _run(repo, "add", rel)
    _run(repo, "commit", "-q", "-m", message)
    return _run(repo, "rev-parse", "HEAD").stdout.decode().strip()


@dataclass
class RepoInspection:
    dirty: bool
    commit_sha: str
    porcelain: str
    is_git: bool = True
    reason: str = ""


def inspect_repo(repo: Path) -> RepoInspection:
    git_dir = Path(repo) / ".git"
    if not git_dir.exists():
        return RepoInspection(dirty=False, commit_sha="", porcelain="", is_git=False, reason="no-git-anchor")
    sha = _run(repo, "rev-parse", "HEAD").stdout.decode().strip()
    porcelain = _run(repo, "status", "--porcelain").stdout.decode()
    return RepoInspection(dirty=bool(porcelain.strip()), commit_sha=sha, porcelain=porcelain, is_git=True, reason="")
