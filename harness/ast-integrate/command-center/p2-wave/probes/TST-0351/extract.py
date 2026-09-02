"""Extract tests-pass / suite-green / coverage / verified claims.

C16 use-versus-mention: a document DESCRIBING this defect class is not
making the claim. Quoted or backticked examples are mentions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

UNIT_RE = re.compile(r"\b([A-Z]{2,5}-\d{4})\b")
RUN_ID_RE = re.compile(
    r"\brun[_-]?id\s*[:=]\s*['\"]?([A-Za-z0-9._:-]+)",
    re.I,
)
COMMIT_RE = re.compile(
    r"\b(?:commit(?:_sha)?|git_sha|revision)\s*[:=]\s*['\"]?([0-9a-f]{7,40})",
    re.I,
)
UNIT_FIELD_RE = re.compile(
    r"\b(?:unit_id|authoring_unit|authored_by)\s*[:=]\s*['\"]?([A-Z]{2,5}-\d{4})",
    re.I,
)

# C16-use-versus-mention: describing the defect class is not making the claim
MENTION_LEX = re.compile(
    r"claims of the form|defect class|describing this defect|"
    r"must not be flagged|use-versus-mention|use-vs-mention|"
    r"use versus mention|meta-review for claims|"
    r"sweep every artifact|require each to resolve|"
    r"question_or_target|tests_required|implementation target|"
    r"a document describing|mentioning .+ while describing|"
    r"extractor looks for|the sweep looks for",
    re.I,
)

FORMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("tests-pass", re.compile(r"\btests?\s+pass(?:ed|es)?\b", re.I)),
    ("tests-pass", re.compile(r"\ball\s+tests?\s+pass(?:ed|es)?\b", re.I)),
    (
        "suite-green",
        re.compile(r"\b(?:the\s+)?(?:test\s+)?suite\s+is\s+green\b", re.I),
    ),
    (
        "coverage-n-percent",
        re.compile(
            r"\bcoverage\s+is\s+(\d+(?:\.\d+)?)\s*(?:%|percent)\b",
            re.I,
        ),
    ),
    (
        "coverage-n-percent",
        re.compile(
            r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\s+coverage\b",
            re.I,
        ),
    ),
    (
        "verified",
        re.compile(r"\b(?:is|was|are|were)\s+verified\b", re.I),
    ),
    (
        "verified",
        re.compile(r"\bverified\s+(?:against|on|by|via)\b", re.I),
    ),
    (
        "verified",
        re.compile(r"\bindependently\s+verified\b", re.I),
    ),
)


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def window(text: str, start: int, end: int, radius: int = 280) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def in_ticks_or_quotes(text: str, start: int, end: int) -> bool:
    left = text[start - 1] if start > 0 else ""
    right = text[end : end + 1]
    if left in "`'" and right in "`'":
        return True
    if left == '"' and right == '"':
        # JSON values look like `"summary": "tests pass"` — those quotes are
        # syntax, not a C16 mention. Prose quotes are preceded by words/space.
        before = text[: start - 1].rstrip()
        if before.endswith(":"):
            return False
        return True
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    line = text[line_start : (len(text) if line_end < 0 else line_end)]
    col = start - line_start
    if line[:col].count("`") % 2 == 1:
        return True
    return False


def is_mention(text: str, start: int, end: int, rel: str) -> bool:
    posix = rel.replace("\\", "/")
    if posix.endswith("WORK-UNIT-CATALOG.json"):
        return True
    if in_ticks_or_quotes(text, start, end):
        return True
    win = window(text, start, end)
    return bool(MENTION_LEX.search(win))


def _authoring_unit(rel: str, text: str, start: int, end: int) -> str:
    win = window(text, start, end, radius=500)
    m = UNIT_FIELD_RE.search(win)
    if m:
        return m.group(1)
    stem = Path(rel).stem
    m2 = UNIT_RE.search(stem)
    if m2:
        return m2.group(1)
    m3 = UNIT_RE.search(win)
    if m3:
        return m3.group(1)
    return "UNKNOWN"


def _nearby_field(win: str, pattern: re.Pattern[str]) -> str:
    m = pattern.search(win)
    return m.group(1) if m else ""


def extract_from_text(text: str, rel: str) -> list[dict[str, Any]]:
    """Return use-claims. Mentions are recorded only as suppressed rows."""
    uses: list[dict[str, Any]] = []
    mentions: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for form, pattern in FORMS:
        for m in pattern.finditer(text):
            key = (m.start(), form)
            if key in seen:
                continue
            seen.add(key)
            win = window(text, m.start(), m.end(), radius=500)
            row = {
                "form": form,
                "text": m.group(0),
                "path": rel.replace("\\", "/"),
                "line": line_of(text, m.start()),
                "start": m.start(),
                "end": m.end(),
                "run_id": _nearby_field(win, RUN_ID_RE),
                "commit": _nearby_field(win, COMMIT_RE).lower(),
                "authoring_unit": _authoring_unit(rel, text, m.start(), m.end()),
                "snippet": re.sub(r"\s+", " ", window(text, m.start(), m.end(), 80)).strip()[:240],
            }
            if is_mention(text, m.start(), m.end(), rel):
                row["role"] = "mention"
                mentions.append(row)
            else:
                row["role"] = "use"
                uses.append(row)
    for row in uses:
        row["mentions_suppressed_in_file"] = sum(
            1 for m in mentions if m["path"] == row["path"]
        )
    return uses


def extract_mentions(text: str, rel: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for form, pattern in FORMS:
        for m in pattern.finditer(text):
            key = (m.start(), form)
            if key in seen:
                continue
            seen.add(key)
            if is_mention(text, m.start(), m.end(), rel):
                out.append(
                    {
                        "form": form,
                        "path": rel.replace("\\", "/"),
                        "line": line_of(text, m.start()),
                        "role": "mention",
                        "text": m.group(0),
                    }
                )
    return out


def extract_path(path: Path, repo: Path) -> list[dict[str, Any]]:
    try:
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    if b"\x00" in raw[:4096]:
        return []
    text = raw.replace(b"\r\n", b"\n").decode("utf-8", errors="replace")
    return extract_from_text(text, rel)


def extract_paths(paths: Iterable[Path], repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(extract_path(path, repo))
    return rows
