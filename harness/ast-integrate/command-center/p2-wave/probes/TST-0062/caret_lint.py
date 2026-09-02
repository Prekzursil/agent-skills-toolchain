#!/usr/bin/env python3
"""Lint: unquoted caret in a git ref passed from PowerShell.

PowerShell argument mode treats `{...}` as a scriptblock. An unquoted peel
`tag^{commit}` is therefore not one argv; this box's pwsh 7.4.6 delivered
`tag^` to git and git failed. cmd.exe additionally treats `^` as escape, so
the same source is unsafe on Windows even when `{` is not the issue.

The lint flags a git invocation in PowerShell source whose *unquoted* remainder
still contains `^`. Quoted peels (`'tag^{commit}'` / `"tag^{commit}"`) and the
sanctioned `git rev-list -n 1 <tag>` form are silent. Comments are mention,
not use.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

GIT_HEAD = re.compile(r"(?i)(?:^|[|&(;]\s*)(?:&\s*)?git(?:\.exe)?\b")
CARET = "^"

PS_SHELLS = {
    "powershell",
    "pwsh",
    "powershell.exe",
    "pwsh.exe",
    "ps",
}


def _unquoted_code(line: str) -> str:
    """Drop comments and quoted spans; leftover is what PowerShell would parse as code."""
    out: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "#":
            break
        if ch == "'":
            i += 1
            while i < n:
                if line[i] == "'":
                    if i + 1 < n and line[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" ")
            continue
        if ch == '"':
            i += 1
            while i < n:
                if line[i] == "`":
                    i += 2
                    continue
                if line[i] == '"':
                    i += 1
                    break
                i += 1
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _statements(code: str) -> list[str]:
    parts = re.split(r"[;&|\n]+", code)
    return [p.strip() for p in parts if p.strip()]


def lint_text(text: str, *, source: str = "<command>", language: str = "powershell") -> list[dict]:
    """Return findings for PowerShell (or .ps1) text."""
    lang = (language or "powershell").lower().lstrip(".")
    if lang in {"ps1", "psm1", "psd1"}:
        lang = "powershell"
    if lang not in PS_SHELLS and lang not in {"powershell", "pwsh"}:
        return []
    findings: list[dict] = []
    for lineno, raw in enumerate(text.splitlines() or [text], start=1):
        code = _unquoted_code(raw)
        if CARET not in code:
            continue
        for stmt in _statements(code):
            if CARET not in stmt:
                continue
            if not GIT_HEAD.search(stmt):
                continue
            findings.append(
                {
                    "source": source,
                    "line": lineno,
                    "statement": " ".join(stmt.split()),
                    "reason": "unquoted-caret-in-git-ref-from-powershell",
                    "snippet": raw.strip()[:240],
                }
            )
    return findings


def lint_command(command: str, *, shell: str = "pwsh") -> list[dict]:
    sh = (shell or "pwsh").split()[-1].lower()
    if sh not in PS_SHELLS:
        return []
    return lint_text(command, source="<command>", language="powershell")


def lint_path(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    return lint_text(text, source=str(path), language=path.suffix.lstrip(".") or "powershell")


def lint_paths(paths: Iterable[Path]) -> list[dict]:
    out: list[dict] = []
    for p in paths:
        out.extend(lint_path(p))
    return out


def naive_caret_present(text: str) -> bool:
    """Known-broken control: any caret, including quoted and commented mentions."""
    return CARET in text
