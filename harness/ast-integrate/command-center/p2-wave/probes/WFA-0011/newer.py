"""Which side of an MD/JSON pair is newer, using commit time.

Never default to JSON. When git commit times are missing, say so and fall
back to mtime, still reporting a side. Injected clocks are for hermetic
probes (this worktree has no git writes).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def git_commit_unix(path: Path, repo: Path) -> int | None:
    try:
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", rel],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 or not out.isdigit():
        return None
    return int(out)


def _mtime_unix(path: Path) -> int | None:
    try:
        if path.is_file():
            return int(path.stat().st_mtime)
    except OSError:
        return None
    return None


def _winner(md_t: int | None, js_t: int | None) -> str:
    if md_t is None or js_t is None:
        return "unknown"
    if md_t > js_t:
        return "markdown"
    if js_t > md_t:
        return "json"
    return "tie"


def newer_side(
    md_path: Path | None,
    json_path: Path | None,
    repo: Path,
    clocks: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return newer side. `assumed_json` is always False on the honest path."""
    if clocks is not None:
        md_t = int(clocks["markdown"])
        js_t = int(clocks["json"])
        result = {
            "newer": _winner(md_t, js_t),
            "markdown_unix": md_t,
            "json_unix": js_t,
            "clock": "injected-commit-clocks",
            "markdown_clock": "injected-commit-clocks",
            "json_clock": "injected-commit-clocks",
            "assumed_json": False,
        }
        return result

    md_t = git_commit_unix(md_path, repo) if md_path is not None else None
    js_t = git_commit_unix(json_path, repo) if json_path is not None else None
    md_src = "git-log-%ct" if md_t is not None else None
    js_src = "git-log-%ct" if js_t is not None else None
    clock = "git-log-%ct"

    if md_t is None and js_t is None:
        md_t = _mtime_unix(md_path) if md_path is not None else None
        js_t = _mtime_unix(json_path) if json_path is not None else None
        clock = "mtime-fallback-git-absent"
        md_src = js_src = clock
    elif md_t is None and js_t is not None:
        # Untracked markdown against a committed JSON: working tree is newer.
        md_t = js_t + 1
        clock = "untracked-working-tree-treated-newer"
        md_src = clock
    elif js_t is None and md_t is not None:
        js_t = md_t + 1
        clock = "untracked-working-tree-treated-newer"
        js_src = clock

    return {
        "newer": _winner(md_t, js_t),
        "markdown_unix": md_t,
        "json_unix": js_t,
        "clock": clock,
        "markdown_clock": md_src,
        "json_clock": js_src,
        "assumed_json": False,
    }


def json_always_wins(
    md_path: Path | None = None,
    json_path: Path | None = None,
    repo: Path | None = None,
    clocks: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Mutant that always declares JSON newer. Probe 2 proves we are not this."""
    return {
        "newer": "json",
        "markdown_unix": None,
        "json_unix": None,
        "clock": "assumed-json",
        "assumed_json": True,
    }


newer_side = newer_side
json_always_wins = json_always_wins
