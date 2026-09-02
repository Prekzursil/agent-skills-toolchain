"""Two independent rollback-guide extractors.

Reviewer A sees fenced code only. Reviewer B sees dollar-prompt / checkbox /
`Run:` lines only. Neither function is passed the other's result.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

FENCE = re.compile(r"```(?:[\w+-]*)[ \t]*\n(.*?)```", re.DOTALL)
DOLLAR = re.compile(r"^[ \t]*\$[ \t]+(\S.*)$")
CHECKBOX = re.compile(r"^[ \t]*[-*][ \t]+\[[ xX]\][ \t]+(\S.*)$")
RUN_LABEL = re.compile(r"^[ \t]*(?:run|execute)[ \t]*:[ \t]+(\S.*)$", re.I)
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*)$")
ROLLBACK_WORD = re.compile(r"\brollback\b", re.I)


def normalize_command(text: str) -> str:
    body = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if body.startswith("$ "):
        body = body[2:].strip()
    return body


def _looks_like_command(text: str) -> bool:
    body = normalize_command(text)
    if not body:
        return False
    first = body.splitlines()[0].strip()
    if HEX64.fullmatch(first):
        return False
    if first.startswith("#") and len(body.splitlines()) == 1:
        return False
    return True


def _line_of(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def extract_fenced(text: str, source: str) -> list[dict[str, Any]]:
    """Reviewer A: fenced blocks only."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in FENCE.finditer(text):
        body = normalize_command(match.group(1))
        if not _looks_like_command(body):
            continue
        key = body
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "reviewer": "A-fenced",
                "source": source,
                "line": _line_of(text, match.group(0)[:80]),
                "command": body,
                "extractor": "fenced-code",
            }
        )
    return out


def extract_prompt(text: str, source: str) -> list[dict[str, Any]]:
    """Reviewer B: $ prompts, checkboxes, Run: lines. Never fenced bodies."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, raw in enumerate(text.splitlines(), 1):
        cmd = None
        kind = None
        m = DOLLAR.match(raw)
        if m:
            cmd, kind = m.group(1), "dollar-prompt"
        else:
            m = CHECKBOX.match(raw)
            if m:
                cmd, kind = m.group(1), "checkbox"
            else:
                m = RUN_LABEL.match(raw)
                if m:
                    cmd, kind = m.group(1), "run-label"
        if cmd is None:
            continue
        body = normalize_command(cmd)
        if not _looks_like_command(body) or body in seen:
            continue
        seen.add(body)
        out.append(
            {
                "reviewer": "B-prompt",
                "source": source,
                "line": i,
                "command": body,
                "extractor": kind,
            }
        )
    return out


def rollback_section(text: str) -> tuple[str | None, int | None]:
    """Return (section_text, start_line) or (None, None) if no rollback heading."""
    lines = text.splitlines()
    start = None
    level = None
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if m and ROLLBACK_WORD.search(m.group(2)):
            start = i
            level = len(m.group(1))
            break
    if start is None or level is None:
        return None, None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = HEADING.match(lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    return "\n".join(lines[start:end]), start + 1


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")
