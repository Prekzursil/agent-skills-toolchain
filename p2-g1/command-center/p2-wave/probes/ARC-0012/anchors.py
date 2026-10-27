"""Resolve path:line anchors against files on this worktree."""
from __future__ import annotations

from pathlib import Path


def find_line(path: Path, snippet: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines, 1) if snippet in ln]
    if len(hits) != 1:
        raise ValueError(f"{path}: snippet {snippet!r} hits={hits}")
    return hits[0]


def resolve_anchor(repo: Path, rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = repo / rel
    if not path.is_file():
        return False, f"missing:{rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line >= 1 and line <= len(lines) and snippet in lines[line - 1]:
        return True, f"{rel}:{line}"
    # Living files (WORK-UNIT-CATALOG.json) shift line numbers as other units
    # land. A unique snippet in the named file still binds; missing or
    # ambiguous snippets remain unresolved.
    hits = [i for i, ln in enumerate(lines, 1) if snippet in ln]
    if len(hits) == 1:
        return True, f"{rel}:{hits[0]}"
    if line < 1 or line > len(lines):
        return False, f"line-oob:{rel}:{line}:n={len(lines)}"
    return False, f"snippet-miss:{rel}:{line}"
