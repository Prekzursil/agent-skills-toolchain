#!/usr/bin/env python3
"""SKILL.md procedural-prose adapter: ordered stages or NOT-EXTRACTABLE.

Frontmatter is intent (use), never a stage list (mention). Fenced code is
mention. A skill without two consecutive ordinals starting at 1 is refused.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

NOT_EXTRACTABLE = "NOT-EXTRACTABLE"
EXTRACTED = "EXTRACTED"

FENCE_OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})")
OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(\S.*)$")
HEADING_NUM_RE = re.compile(r"^(\s*)#{1,6}\s+(\d+)\.\s+(\S.*)$")
LABELED_RE = re.compile(
    r"^(\s*)(?:#{1,6}\s+)?(?:Step|Stage|Phase)\s+(\d+)\s*[:.)\-]?\s*(.*)$",
    re.IGNORECASE,
)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


@dataclass(frozen=True)
class Marker:
    line: int
    indent: int
    number: int
    title: str
    kind: str
    snippet: str


def clean_title(raw: str) -> str:
    text = BOLD_RE.sub(r"\1", raw or "")
    text = re.sub(r"^#+\s*", "", text)
    return " ".join(text.split()).strip()


def split_frontmatter(text: str) -> tuple[str, str, int]:
    """Return (frontmatter, body, body_start_line 1-indexed)."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == "" or stripped.startswith("<!--"):
            i += 1
            continue
        break
    if i < len(lines) and lines[i].strip() == "---":
        i += 1
        fm_lines: list[str] = []
        while i < len(lines):
            if lines[i].strip() == "---":
                body_lines = lines[i + 1 :]
                body_start = i + 2
                return "\n".join(fm_lines), "\n".join(body_lines), body_start
            fm_lines.append(lines[i])
            i += 1
    return "", text, 1


def iter_body_lines(text: str) -> Iterable[tuple[int, str, bool]]:
    """Yield (line_no, line, in_fence) for the BODY only, with file line numbers."""
    _fm, _body, body_start = split_frontmatter(text)
    lines = text.splitlines()
    in_fence = False
    fence_token = ""
    start_idx = body_start - 1
    if start_idx < 0:
        start_idx = 0
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        m = FENCE_OPEN.match(line)
        if m:
            token = m.group(2)[0]
            if not in_fence:
                in_fence = True
                fence_token = token
                yield idx + 1, line, True
                continue
            if token == fence_token:
                in_fence = False
                fence_token = ""
                yield idx + 1, line, True
                continue
        yield idx + 1, line, in_fence


def collect_markers(text: str) -> list[Marker]:
    markers: list[Marker] = []
    for line_no, line, in_fence in iter_body_lines(text):
        if in_fence:
            continue
        hm = HEADING_NUM_RE.match(line)
        if hm:
            markers.append(
                Marker(
                    line=line_no,
                    indent=len(hm.group(1).replace("\t", "    ")),
                    number=int(hm.group(2)),
                    title=clean_title(hm.group(3)),
                    kind="heading",
                    snippet=line.strip()[:200],
                )
            )
            continue
        lm = LABELED_RE.match(line)
        if lm:
            title = clean_title(lm.group(3)) or f"Phase {lm.group(2)}"
            markers.append(
                Marker(
                    line=line_no,
                    indent=len(lm.group(1).replace("\t", "    ")),
                    number=int(lm.group(2)),
                    title=title,
                    kind="labeled",
                    snippet=line.strip()[:200],
                )
            )
            continue
        om = OL_RE.match(line)
        if om:
            markers.append(
                Marker(
                    line=line_no,
                    indent=len(om.group(1).replace("\t", "    ")),
                    number=int(om.group(2)),
                    title=clean_title(om.group(3)),
                    kind="ol",
                    snippet=line.strip()[:200],
                )
            )
    return markers


def consecutive_from_one(markers: list[Marker]) -> list[Marker]:
    ordered = sorted(markers, key=lambda m: m.line)
    best: list[Marker] = []
    current: list[Marker] = []
    expected = 1
    for m in ordered:
        if m.number == expected:
            current.append(m)
            expected += 1
            continue
        if len(current) > len(best):
            best = current
        if m.number == 1:
            current = [m]
            expected = 2
        else:
            current = []
            expected = 1
    if len(current) > len(best):
        best = current
    return best if len(best) >= 2 else []


def pick_sequence(markers: list[Marker]) -> list[Marker]:
    for kind in ("labeled", "heading", "ol"):
        subset = [m for m in markers if m.kind == kind]
        if not subset:
            continue
        if kind == "ol":
            min_indent = min(m.indent for m in subset)
            subset = [m for m in subset if m.indent == min_indent]
        seq = consecutive_from_one(subset)
        if seq:
            return seq
    return []


def stage_id(n: int) -> str:
    return f"stage-{n}"


def extract_text(path: Path, text: str | None = None) -> dict:
    path = Path(path)
    if text is None:
        text = path.read_text(encoding="utf-8")
    rel = path.as_posix()
    markers = collect_markers(text)
    seq = pick_sequence(markers)
    if not seq:
        return {
            "skill_id": path.parent.name if path.name.upper() == "SKILL.MD" else path.stem,
            "path": rel,
            "verdict": NOT_EXTRACTABLE,
            "reason": (
                "body has no ordered procedure of two or more consecutive "
                "ordinals starting at 1; frontmatter and fenced examples ignored"
            ),
            "stages": [],
            "lossy_fields": lossy_fields(),
        }
    stages = []
    for m in seq:
        stages.append(
            {
                "id": stage_id(m.number),
                "order": m.number,
                "title": m.title,
                "kind": m.kind,
                "source_anchor": {
                    "path": rel,
                    "line": m.line,
                    "snippet": m.snippet,
                },
            }
        )
    return {
        "skill_id": path.parent.name if path.name.upper() == "SKILL.MD" else path.stem,
        "path": rel,
        "verdict": EXTRACTED,
        "reason": f"extracted {len(stages)} ordered stages from body prose",
        "stages": stages,
        "ir": to_ir(path, stages),
        "lossy_fields": lossy_fields(),
    }


def extract_skill(path: Path) -> dict:
    return extract_text(Path(path))


def to_ir(path: Path, stages: list[dict]) -> dict:
    return {
        "record_type": "WorkflowIR",
        "id": f"skill:{path.parent.name}",
        "native": "SKILL.md",
        "execution_semantics": False,
        "stages": [
            {
                "id": s["id"],
                "order": s["order"],
                "title": s["title"],
                "source_anchor": s["source_anchor"],
            }
            for s in stages
        ],
    }


def lossy_fields() -> list[dict]:
    return [
        {
            "native": "frontmatter.description",
            "ir": None,
            "disposition": "INTENT-NOT-STAGES",
            "why": "use-versus-mention: description is when-to-use text, not a stage list",
        },
        {
            "native": "fenced-code-examples",
            "ir": None,
            "disposition": "MENTION",
            "why": "example SKILL.md bodies inside fences are not this skill's procedure",
        },
        {
            "native": "roles/gates/fan-out/retries/resume/stop",
            "ir": None,
            "disposition": "ABSENT-IN-SKILL-MD",
            "why": "SKILL.md prose does not carry those IR constructs; not invented",
        },
    ]


def find_skill_md(root: Path) -> list[Path]:
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("SKILL.md") if p.is_file())


if __name__ == "__main__":
    import json
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if target.is_file():
        print(json.dumps(extract_skill(target), indent=2))
    else:
        rows = [extract_skill(p) for p in find_skill_md(target)]
        print(json.dumps(rows, indent=2))
