#!/usr/bin/env python3
"""Shared parsers and recency checks for ARC-0039 cost probes."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"

WINDOW_START = date(2026, 3, 13)
WINDOW_END = date(2026, 8, 24)
RETRIEVED_ON = date(2026, 8, 24)
FORECAST_UNTIL = date(2026, 11, 22)

SURFACES = (
    "prompt_transport",
    "tool_permission_model",
    "output_schema",
    "progress_streaming",
    "timeout",
    "session_state",
    "model_naming",
)

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
MON3 = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

RULES: dict[str, tuple[re.Pattern[str], ...]] = {
    "prompt_transport": (
        re.compile(r"prompt cach", re.I),
        re.compile(r"messages api", re.I),
        re.compile(r"\bhttpx2?\b", re.I),
        re.compile(r"anthropic-version", re.I),
        re.compile(r"system prompt", re.I),
        re.compile(r"prefixed domain", re.I),
        re.compile(r"regional processing", re.I),
    ),
    "tool_permission_model": (
        re.compile(r"\btools?\b", re.I),
        re.compile(r"permission", re.I),
        re.compile(r"computer_toolset|computer use", re.I),
        re.compile(r"\bmcp\b", re.I),
        re.compile(r"function call", re.I),
        re.compile(r"sandbox", re.I),
        re.compile(r"tool_choice|strict tool", re.I),
        re.compile(r"code execution", re.I),
    ),
    "output_schema": (
        re.compile(r"structured output", re.I),
        re.compile(r"json[_ ]schema", re.I),
        re.compile(r"output_format|output_config", re.I),
        re.compile(r"output_config", re.I),
        re.compile(r"strict:\s*true", re.I),
    ),
    "progress_streaming": (
        re.compile(r"\bstream", re.I),
        re.compile(r"\bsse\b", re.I),
        re.compile(r"event_delta|event deltas", re.I),
        re.compile(r"keepalive", re.I),
        re.compile(r"message_delta", re.I),
    ),
    "timeout": (
        re.compile(r"\btimeout", re.I),
        re.compile(r"\bidle\b", re.I),
        re.compile(r"90-second|90 second", re.I),
        re.compile(r"\bdeadline\b", re.I),
        re.compile(r"spend limit", re.I),
        re.compile(r"\b429\b"),
    ),
    "session_state": (
        re.compile(r"\bsession", re.I),
        re.compile(r"compact", re.I),
        re.compile(r"\bresume\b", re.I),
        re.compile(r"memory store", re.I),
        re.compile(r"conversation state", re.I),
        re.compile(r"compaction_control", re.I),
    ),
    "model_naming": (
        re.compile(r"\bclaude-[a-z0-9.-]+", re.I),
        re.compile(r"\bgpt-[a-z0-9.-]+", re.I),
        re.compile(r"model (id|alias|family|snapshot)", re.I),
        re.compile(r"retir(e|ed|ement)", re.I),
        re.compile(r"deprecat", re.I),
        re.compile(r"we've launched \*\*Claude", re.I),
        re.compile(r"released the GPT-", re.I),
    ),
}

BREAKING = re.compile(
    r"breaking|retir(e|ed|ement)|deprecat|removed|no longer|migrate|"
    r"returns an error|breaking change|will now return an error",
    re.I,
)

ANTHROPIC_H1 = re.compile(
    r"^###\s+([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,\s+(\d{4})\s*$"
)
OPENAI_MONTH = re.compile(r"^###\s+([A-Za-z]+),\s+(\d{4})\s*$")
OPENAI_DAY = re.compile(r"^([A-Z][a-z]{2})\s+(\d{1,2})\s*$")


def in_window(d: date) -> bool:
    return WINDOW_START <= d <= WINDOW_END


def classify(text: str) -> list[str]:
    hits = [sid for sid, pats in RULES.items() if any(p.search(text) for p in pats)]
    return hits


def parse_anthropic_headings_strptime(text: str) -> list[date]:
    """Measure A: datetime.strptime on ordinal-stripped headings."""
    out: list[date] = []
    for line in text.splitlines():
        m = ANTHROPIC_H1.match(line.strip())
        if not m:
            continue
        month, day, year = m.group(1), int(m.group(2)), int(m.group(3))
        dt = datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date()
        out.append(dt)
    return out


def parse_anthropic_headings_fields(text: str) -> list[date]:
    """Measure B: month-name dict + integer day/year fields (no strptime)."""
    out: list[date] = []
    for line in text.splitlines():
        m = ANTHROPIC_H1.match(line.strip())
        if not m:
            continue
        month = MONTHS[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3))
        out.append(date(year, month, day))
    return out


def parse_anthropic_entries(text: str) -> list[dict]:
    lines = text.splitlines()
    entries: list[dict] = []
    i = 0
    while i < len(lines):
        m = ANTHROPIC_H1.match(lines[i].strip())
        if not m:
            i += 1
            continue
        month = MONTHS[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3))
        d = date(year, month, day)
        i += 1
        body: list[str] = []
        while i < len(lines) and not lines[i].startswith("### "):
            body.append(lines[i])
            i += 1
        blob = "\n".join(body).strip()
        entries.append(
            {
                "vendor": "anthropic",
                "source": "api-release-notes",
                "entry_date": d.isoformat(),
                "url": "https://platform.claude.com/docs/en/release-notes/overview",
                "text": blob,
                "surfaces": classify(blob),
                "breaking": bool(BREAKING.search(blob)),
            }
        )
    return entries


def parse_openai_entries(text: str) -> list[dict]:
    year = None
    month = None
    entries: list[dict] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        sm = OPENAI_MONTH.match(lines[i].strip())
        if sm and sm.group(1).lower() in MONTHS:
            month = MONTHS[sm.group(1).lower()]
            year = int(sm.group(2))
            i += 1
            continue
        dm = OPENAI_DAY.match(lines[i].strip())
        if dm and year and month and dm.group(1).lower() in MON3:
            day = int(dm.group(2))
            d = date(year, MON3[dm.group(1).lower()], day)
            i += 1
            body: list[str] = []
            while i < len(lines):
                if OPENAI_MONTH.match(lines[i].strip()) or OPENAI_DAY.match(
                    lines[i].strip()
                ):
                    break
                body.append(lines[i])
                i += 1
            blob = "\n".join(body).strip()
            entries.append(
                {
                    "vendor": "openai",
                    "source": "api-changelog",
                    "entry_date": d.isoformat(),
                    "url": "https://developers.openai.com/api/docs/changelog",
                    "text": blob,
                    "surfaces": classify(blob),
                    "breaking": bool(BREAKING.search(blob)),
                }
            )
            continue
        i += 1
    return entries


def load_compact(name: str) -> list[dict]:
    path = RAW / name
    return json.loads(path.read_text(encoding="utf-8"))


def github_counts(rows: list[dict], field: str) -> int:
    n = 0
    for row in rows:
        raw = row.get(field) or ""
        if not raw:
            continue
        d = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        if in_window(d):
            n += 1
    return n


def windowed(entries: list[dict]) -> list[dict]:
    out = []
    for e in entries:
        d = date.fromisoformat(e["entry_date"])
        if in_window(d):
            item = dict(e)
            item["retrieved_on"] = RETRIEVED_ON.isoformat()
            item["staleness_days"] = (RETRIEVED_ON - d).days
            out.append(item)
    return out


def recency_ok(entry: dict) -> tuple[bool, str]:
    if not isinstance(entry.get("entry_date"), str) or not isinstance(
        entry.get("retrieved_on"), str
    ):
        return False, "missing-date-or-retrieval"
    try:
        ed = date.fromisoformat(entry["entry_date"][:10])
        rd = date.fromisoformat(entry["retrieved_on"][:10])
    except ValueError:
        return False, "unparseable-date"
    if rd < ed:
        return False, "retrieved-before-entry"
    if "staleness_days" in entry and entry["staleness_days"] != (rd - ed).days:
        return False, "stale-math"
    return True, "ok"


def anthropic_text() -> str:
    return (RAW / "anthropic-api-release-notes.md").read_text(encoding="utf-8")


def openai_text() -> str:
    return (RAW / "openai-api-changelog.md").read_text(encoding="utf-8")


def two_anthropic_heading_counts() -> tuple[int, int]:
    text = anthropic_text()
    a = sum(1 for d in parse_anthropic_headings_strptime(text) if in_window(d))
    b = sum(1 for d in parse_anthropic_headings_fields(text) if in_window(d))
    return a, b


def two_openai_entry_counts() -> tuple[int, int]:
    """Measure A: entry splitter. Measure B: day-header count under month headings."""
    text = openai_text()
    a = sum(1 for e in parse_openai_entries(text) if in_window(date.fromisoformat(e["entry_date"])))
    year = None
    month = None
    b = 0
    for line in text.splitlines():
        sm = OPENAI_MONTH.match(line.strip())
        if sm and sm.group(1).lower() in MONTHS:
            month = MONTHS[sm.group(1).lower()]
            year = int(sm.group(2))
            continue
        dm = OPENAI_DAY.match(line.strip())
        if dm and year and month and dm.group(1).lower() in MON3:
            d = date(year, MON3[dm.group(1).lower()], int(dm.group(2)))
            if in_window(d):
                b += 1
    return a, b
