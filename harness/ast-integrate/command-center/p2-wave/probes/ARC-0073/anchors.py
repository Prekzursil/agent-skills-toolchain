#!/usr/bin/env python3
"""Line-anchored snippets that must resolve on disk."""
from __future__ import annotations

from pathlib import Path


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if snippet in line:
            return i
    # Allow multi-line by searching a collapsed window.
    collapsed = "\n".join(lines)
    idx = collapsed.find(snippet)
    if idx < 0:
        return 0
    return collapsed[:idx].count("\n") + 1


def resolve_anchor(repo: Path, rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = repo / rel
    if not path.is_file():
        return False, f"missing:{rel}"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if line < 1 or line > len(lines):
        return False, f"line-oob:{rel}:{line}"
    if snippet not in lines[line - 1] and snippet not in text:
        return False, f"snippet-miss:{rel}:{line}"
    if snippet not in lines[line - 1]:
        return False, f"snippet-not-on-line:{rel}:{line}"
    return True, f"{rel}:{line}"
