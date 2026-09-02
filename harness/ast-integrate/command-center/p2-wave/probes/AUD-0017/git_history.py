"""Probe 2 helper: git log --all --diff-filter=D vs never-in-history."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


GIT_ENV = {
    "GIT_AUTHOR_NAME": "AUD-0017",
    "GIT_AUTHOR_EMAIL": "aud-0017@local",
    "GIT_COMMITTER_NAME": "AUD-0017",
    "GIT_COMMITTER_EMAIL": "aud-0017@local",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
}


def _run(repo: Path, args: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env.update(GIT_ENV)
    # Do not set GIT_DIR: that would leak onto the host worktree.
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def deleted_log(repo: Path, rel: str) -> dict:
    code, text = _run(
        repo,
        [
            "log",
            "--all",
            "--diff-filter=D",
            "--pretty=%H%x09%s",
            "--",
            rel,
        ],
    )
    hits = [ln for ln in text.splitlines() if ln.strip()] if code == 0 else []
    return {
        "rel": rel,
        "command": (
            f"git -C {repo} log --all --diff-filter=D --pretty=%H%x09%s -- {rel}"
        ),
        "exit_code": code,
        "raw": text,
        "hit_count": len(hits),
        "was_deleted_in_history": code == 0 and len(hits) > 0,
        "never_in_history": code == 0 and len(hits) == 0,
        "git_unavailable": code == 127,
        "not_a_repo": code == 128,
    }


def classify_live_only(git_repo: Path, rels: list[str]) -> list[dict]:
    return [deleted_log(git_repo, rel) for rel in rels]


def build_git_fixture(root: Path) -> dict:
    """Repo history contains deleted.txt then removes it; never.txt is live-only."""
    repo = root / "gitrepo"
    live = root / "live"
    repo.mkdir(parents=True, exist_ok=True)
    live.mkdir(parents=True, exist_ok=True)
    (repo / "kept.txt").write_text("kept\n", encoding="utf-8")
    (repo / "deleted.txt").write_text("will delete\n", encoding="utf-8")
    code, text = _run(repo, ["init", "--initial-branch=main"])
    if code != 0:
        # older git without --initial-branch
        code, text = _run(repo, ["init"])
    if code != 0:
        raise RuntimeError(f"git init failed: {text}")
    _run(repo, ["config", "user.name", "AUD-0017"])
    _run(repo, ["config", "user.email", "aud-0017@local"])
    _run(repo, ["add", "kept.txt", "deleted.txt"])
    c1, t1 = _run(repo, ["commit", "-m", "add kept and deleted"])
    if c1 != 0:
        raise RuntimeError(f"git commit1 failed: {t1}")
    _run(repo, ["rm", "deleted.txt"])
    c2, t2 = _run(repo, ["commit", "-m", "delete deleted.txt"])
    if c2 != 0:
        raise RuntimeError(f"git commit2 failed: {t2}")

    (live / "kept.txt").write_text("kept\n", encoding="utf-8")
    (live / "deleted.txt").write_text("still on live after repo delete\n", encoding="utf-8")
    (live / "never.txt").write_text("never committed\n", encoding="utf-8")

    repo_files = {"kept.txt"}
    live_files = {"kept.txt", "deleted.txt", "never.txt"}
    live_only = sorted(live_files - repo_files)
    return {
        "git_repo": str(repo),
        "live": str(live),
        "live_only": live_only,
        "expected": {
            "deleted.txt": "was_deleted_in_history",
            "never.txt": "never_in_history",
        },
    }


def host_git_status(worktree: Path) -> dict:
    proc = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {
        "worktree": str(worktree),
        "exit_code": proc.returncode,
        "raw": text,
        "is_git": proc.returncode == 0 and "true" in text.lower(),
    }
