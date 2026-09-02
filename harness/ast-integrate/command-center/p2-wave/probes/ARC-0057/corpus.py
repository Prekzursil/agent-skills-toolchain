#!/usr/bin/env python3
"""Extract documented commands from markdown and Python module docstrings."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SKIP_COMMENT = re.compile(r'doc-test:skip\s+reason="([^"]+)"')
FENCE_OPEN = re.compile(r"^```(?:bash|sh|shell|console)?\s*$")
PY_CMD = re.compile(r"^\s*(python3?)\s+(tools/command-center/\S+.*)$")
PROMPT = re.compile(r"^\$\s+")
MUTATING = re.compile(
    r"(?:--write\b|--open\b|--dropped\b|--defer\b|--superseded-by\b|"
    r"--note\b|--evidence\b|\brm\b|\bcurl\b|\bssh\b|\bgit\s+push\b)"
)
PLACEHOLDER = re.compile(r"[<]|\bTODO\b|\bpath to\b")
SKIP_DIRS = {".git", "node_modules", "__pycache__", "runtime", "vendor"}


@dataclass
class DocCommand:
    source: str
    command: str
    skip_reason: str | None = None


def _norm_cmd(raw: str) -> str:
    line = PROMPT.sub("", raw.strip())
    if line.startswith("python "):
        line = "python3 " + line[len("python ") :]
    return line


def extract_markdown(path: Path, repo: Path) -> list[DocCommand]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(repo).as_posix()
    out: list[DocCommand] = []
    pending_skip: str | None = None
    in_fence = False
    for i, raw in enumerate(text.splitlines(), 1):
        mskip = SKIP_COMMENT.search(raw)
        if mskip:
            pending_skip = mskip.group(1)
            continue
        stripped = raw.strip()
        if FENCE_OPEN.match(stripped) or stripped == "```":
            if in_fence:
                in_fence = False
                pending_skip = None
            else:
                in_fence = True
            continue
        if not in_fence:
            continue
        line = stripped
        if not line or line.startswith("#"):
            continue
        cmd = _norm_cmd(line)
        if not cmd:
            continue
        reason = pending_skip
        if reason is None and MUTATING.search(cmd):
            reason = "mutating or destructive documented command; not executed"
        out.append(DocCommand(source=f"{rel}:{i}", command=cmd, skip_reason=reason))
    return out


def extract_python_docstring(path: Path, repo: Path) -> list[DocCommand]:
    text = path.read_text(encoding="utf-8")
    if not (text.startswith('\"\"\"') or text.startswith("\'\'\'")):
        return []
    quote = '\"\"\"' if text.startswith('\"\"\"') else "\'\'\'"
    end = text.find(quote, 3)
    if end < 0:
        return []
    doc = text[3:end]
    rel = path.relative_to(repo).as_posix()
    out: list[DocCommand] = []
    for i, raw in enumerate(doc.splitlines(), 1):
        if not PY_CMD.match(raw.strip()):
            continue
        cmd = _norm_cmd(raw)
        reason = None
        if MUTATING.search(cmd):
            reason = "mutating documented command; not executed on the live catalog"
        elif PLACEHOLDER.search(cmd):
            reason = "placeholder in documented command; not executable as written"
        out.append(DocCommand(source=f"{rel}:doc:{i}", command=cmd, skip_reason=reason))
    return out


def iter_live_files(repo: Path) -> list[Path]:
    """Only tools/command-center module docs — not probe markdown prose."""
    py_dir = repo / "tools" / "command-center"
    if not py_dir.is_dir():
        return []
    return sorted(py_dir.glob("*.py"))


def product_commands(repo: Path) -> list[DocCommand]:
    user = (
        repo
        / "command-center"
        / "p2-wave"
        / "probes"
        / "ARC-0057"
        / "docs"
        / "USER.md"
    )
    return extract_markdown(user, repo)


def live_commands(repo: Path) -> list[DocCommand]:
    out: list[DocCommand] = []
    seen: set[tuple[str, str]] = set()
    for path in iter_live_files(repo):
        if path.suffix == ".py":
            rows = extract_python_docstring(path, repo)
        else:
            if path.name == "USER.md" and "ARC-0057" in path.parts:
                continue
            rows = extract_markdown(path, repo)
        for row in rows:
            key = (row.source, row.command)
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out
