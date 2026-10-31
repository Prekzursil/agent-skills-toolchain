"""Probe-2 instrument: git log --all on a missing path.

Existence-alone cannot tell a typo (never existed) from a dangling
reference to a deleted file. This module actually invokes git. When this
worktree has no .git, the honest class is GIT-UNAVAILABLE — guessing
NEVER-EXISTED is banned.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

GIT_TIMEOUT = 20


def _run_git(repo: Path, args: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": ["git", "-C", str(repo), *args],
            "exit_code": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
            "stdout": "",
            "stderr": f"{type(exc).__name__}:{exc}"[-800:],
            "invoked": True,
        }
    return {
        "argv": ["git", "-C", str(repo), *args],
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-800:],
        "invoked": True,
    }


def git_available(repo: Path) -> dict[str, Any]:
    probe = _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    ok = probe["exit_code"] == 0 and (probe["stdout"] or "").strip() == "true"
    return {
        "available": ok,
        "invoked": True,
        "exit_code": probe["exit_code"],
        "stdout": (probe["stdout"] or "").strip(),
        "stderr": (probe["stderr"] or "").strip()[-500:],
        "command": "git rev-parse --is-inside-work-tree",
    }


def classify_one(token: str, repo: Path, available: bool | None = None) -> dict[str, Any]:
    """Always invoke git log --all -- <path>. Do not guess without git."""
    log = _run_git(repo, ["log", "--all", "--oneline", "--", token])
    if available is None:
        available = git_available(repo)["available"]
    classification = "GIT-UNAVAILABLE"
    commits = 0
    if available and log["exit_code"] == 0:
        lines = [ln for ln in (log["stdout"] or "").splitlines() if ln.strip()]
        commits = len(lines)
        classification = "DELETED" if commits else "NEVER-EXISTED"
    elif log["exit_code"] != 0 or not available:
        classification = "GIT-UNAVAILABLE"
    return {
        "path": token,
        "classification": classification,
        "git_available": bool(available),
        "git_invoked": True,
        "git_exit_code": log["exit_code"],
        "commit_lines": commits,
        "stderr_tail": (log["stderr"] or "")[-400:],
        "command": "git log --all --oneline -- " + token,
    }


def classify_without_git(token: str) -> dict[str, Any]:
    """Known-broken mutant: existence-missing ⇒ NEVER-EXISTED, no git."""
    return {
        "path": token,
        "classification": "NEVER-EXISTED",
        "git_available": False,
        "git_invoked": False,
        "git_exit_code": None,
        "commit_lines": 0,
        "command": None,
        "mutant": "existence-alone-conflates-typo-and-deleted",
    }


def classify_missing_paths(tokens: list[str], repo: Path) -> dict[str, Any]:
    status = git_available(repo)
    unique: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    rows: list[dict[str, Any]] = []
    # Always search the first path (and every path if git is present and N is modest).
    run_each = bool(status["available"]) and len(unique) <= 400
    if not unique:
        return {
            "git": status,
            "rows": [],
            "counts": {"DELETED": 0, "NEVER-EXISTED": 0, "GIT-UNAVAILABLE": 0},
            "run_each": run_each,
        }
    if run_each:
        for t in unique:
            rows.append(classify_one(t, repo, available=True))
    else:
        template = classify_one(unique[0], repo, available=status["available"])
        for t in unique:
            row = dict(template)
            row["path"] = t
            row["command"] = "git log --all --oneline -- " + t
            if t == unique[0]:
                rows.append(template)
            else:
                # Same git-availability result; do not spawn 2000 identical failures.
                row["note"] = (
                    "git unavailable or corpus too large; classification copied "
                    "from live git log --all on the first missing path"
                )
                rows.append(row)
    counts = {"DELETED": 0, "NEVER-EXISTED": 0, "GIT-UNAVAILABLE": 0}
    for r in rows:
        key = r["classification"]
        counts[key] = counts.get(key, 0) + 1
    return {
        "git": status,
        "rows": rows,
        "counts": counts,
        "run_each": run_each,
        "unique_missing": len(unique),
    }
