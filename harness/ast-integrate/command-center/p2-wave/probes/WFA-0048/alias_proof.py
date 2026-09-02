"""Independent alias proof (evidence B).

Does not call adapter.extract_stages or adapter.classify. Resolves a skill
id from the command text, strips invoke sentences, and checks that no
ordered-stage markers remain. That is a content comparison: leftover body
after removing the invoke must not add stages.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

STAGE_MARK_RE = re.compile(
    r"(?m)^\s*(?:\d+\.\s+\S|#{1,3}\s+(?:Step|Stage|Phase)\b|(?:Gate|Barrier)\s*:)",
    re.IGNORECASE,
)
SKILL_NAME_RE = re.compile(
    r"(?i)(?:^|\n)\s*(?:skill|invoke-skill|delegate-to|alias-of)\s*:\s*"
    r"([a-z0-9._/-]+)"
    r"|(?:use|run|invoke|launch|call)\s+(?:the\s+)?[`'\"]?([a-z0-9._/-]+)[`'\"]?\s+skill"
)
INVOKE_LINE_RE = re.compile(
    r"(?i)\b(?:use|run|invoke|launch|call|wraps?|delegates?\s+to)\s+"
    r"(?:the\s+)?[`'\"]?[a-z0-9._/-]+[`'\"]?\s+skill\b"
    r"|^\s*(?:skill|invoke-skill|delegate-to|alias-of)\s*:\s*[a-z0-9._/-]+"
)
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)


def _skill_id(name: str) -> str:
    name = name.strip().strip("`\"'").replace("\\", "/")
    if name.startswith("skill:"):
        return name
    if name.startswith("skill/"):
        return "skill:" + name.split("/", 1)[1]
    return "skill:" + name


def resolve_skill_id(text: str) -> str | None:
    m = SKILL_NAME_RE.search(text)
    if not m:
        return None
    name = next(g for g in m.groups() if g)
    return _skill_id(name)


def leftover_body(text: str) -> str:
    body = text
    fm = FRONTMATTER_RE.match(text)
    if fm:
        body = text[fm.end() :]
    lines = []
    for line in body.splitlines():
        if INVOKE_LINE_RE.search(line):
            continue
        if re.search(r"\$ARGUMENTS", line):
            # drop pure argument-passthrough lines
            rest = re.sub(r"\$ARGUMENTS", " ", line)
            if not re.search(r"[A-Za-z]{3,}", rest):
                continue
        lines.append(line)
    return "\n".join(lines).strip()


def leftover_adds_stages(leftover: str) -> bool:
    if not leftover:
        return False
    return STAGE_MARK_RE.search(leftover) is not None


def prove_alias(path: Path, expected_skill: str | None = None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    skill = resolve_skill_id(text)
    leftover = leftover_body(text)
    adds = leftover_adds_stages(leftover)
    ok = skill is not None and not adds
    if expected_skill and skill != expected_skill:
        ok = False
    return {
        "path": path.as_posix(),
        "skill_id": skill,
        "leftover": leftover[:400],
        "leftover_adds_stages": adds,
        "added_stage_count": 1 if adds else 0,
        "alias_ok": ok,
        "method": "strip-invoke-then-scan-stage-markers (not adapter.extract_stages)",
    }
