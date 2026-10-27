"""TST-0255 internal-anchor resolution: git cat-file + line-count.

An internal ``file:line`` anchor is OK only when the blob at the documented
revision actually HAS that line. A shape-only checker (``path:digits`` regex)
validates nothing. Classifications: OK / BEYOND-EOF / MISSING.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(args: list[str], git_dir: Path) -> subprocess.CompletedProcess:
    gd = git_dir / ".git" if (git_dir / ".git").is_dir() else git_dir
    return subprocess.run(
        ["git", "--git-dir", str(gd)] + args,
        capture_output=True,
        text=True,
        timeout=120,
    )


def resolve_anchor(rev: str, path: str, line: int, git_dir: Path) -> dict:
    """Classify one ``path:line`` anchor against the blob stored at ``rev``."""
    p = _git(["cat-file", "-p", f"{rev}:{path}"], git_dir)
    if p.returncode != 0:
        return {
            "rev": rev,
            "path": path,
            "line": line,
            "classification": "MISSING",
            "detail": (p.stderr or "").strip()[:200],
            "line_count": None,
        }
    text = p.stdout
    line_count = len(text.splitlines())
    if 1 <= line <= line_count:
        return {
            "rev": rev,
            "path": path,
            "line": line,
            "classification": "OK",
            "detail": text.splitlines()[line - 1][:120],
            "line_count": line_count,
        }
    return {
        "rev": rev,
        "path": path,
        "line": line,
        "classification": "BEYOND-EOF",
        "detail": f"line {line} beyond {line_count}-line blob",
        "line_count": line_count,
    }


def shape_only_accepts(path: str, line: int) -> bool:
    """The known-broken shape-only checker: regex-validates ``path:digits``."""
    import re

    return re.match(r"^\S+:\d+$", f"{path}:{line}") is not None


def worktree_has_object_store(repo: Path) -> bool:
    p = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return p.returncode == 0 and p.stdout.strip() == "true"
