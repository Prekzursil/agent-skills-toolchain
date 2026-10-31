#!/usr/bin/env python3
"""CNF-0191 supporting extractor (wave-2 reconstruction).

Extracts shell commands from fenced code blocks in markdown docs. Rules:
  * only fences whose info string names a shell language (bash, sh, shell,
    console) yield commands — an unprompted empty-lang fence (a directory
    tree) is NOT a command;
  * leading prompts ($, >) are stripped; blank and comment-only lines are
    skipped; each remaining fence line is one command, verbatim, with the
    line number of the fence body.
"""
from __future__ import annotations

from pathlib import Path

SHELL_LANGS = {"bash", "sh", "shell", "console", "powershell", "pwsh"}


def extract_commands(md_text: str, path: str):
    rows = []
    lines = md_text.splitlines()
    in_fence = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not in_fence:
            if stripped.startswith("```"):
                info = stripped[3:].strip().lower()
                lang = info.split()[0] if info else ""
                in_fence = lang in SHELL_LANGS
            i += 1
            continue
        if stripped.startswith("```"):
            in_fence = False
            i += 1
            continue
        # continuation join: a trailing backslash glues the next fence line on
        # (backslash dropped, newline dropped, next line's leading spaces kept)
        start_line = i + 1
        cmd = lines[i]
        while cmd.rstrip().endswith(chr(92)):
            cmd = cmd.rstrip()[:-1]
            if i + 1 < len(lines) and not lines[i + 1].strip().startswith("```"):
                i += 1
                cmd = cmd + lines[i]
            else:
                break
        for prompt in ("$ ", "> "):
            if cmd.lstrip().startswith(prompt):
                cmd = cmd.lstrip()[2:]
                break
        body = cmd.strip()
        if not body or body.startswith("#"):
            i += 1
            continue
        rows.append({"path": path, "line": start_line, "command": body})
        i += 1
    return rows


def extract_paths(repo_root: Path, rel_paths):
    out = []
    for rel in rel_paths:
        p = repo_root / rel
        if p.is_file():
            out.extend(extract_commands(p.read_text(encoding="utf-8"), rel))
    return out
