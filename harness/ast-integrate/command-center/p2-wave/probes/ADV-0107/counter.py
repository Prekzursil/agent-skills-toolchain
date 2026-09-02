"""Use-vs-mention counter for UNVERIFIED tags, Sherman-Kent bands, and anchors.

Applied (USE) forms:
  [UNVERIFIED]
  confidence_band: <band>
  slash-bearing path.ext:line not in backticks
  http(s) URL whose host is not a mention host, not in backticks

Bare tokens in prose, quotes, backticks, or vocabulary lists are MENTION.
"""
from __future__ import annotations

import re
from typing import Any

BANDS = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)
MENTION_HOSTS = ("example.invalid", "example.com")
CLAIM_ID_RE = re.compile(r"\b(C-[A-Z0-9][A-Z0-9-]*)\b")
UNVERIFIED_NAIVE = re.compile(r"\bUNVERIFIED\b")
UNVERIFIED_USE = re.compile(r"\[UNVERIFIED\]")
BAND_NAIVE = re.compile(r"\b(" + "|".join(BANDS) + r")\b")
BAND_USE = re.compile(r"(?:confidence_band\s*:\s*|\[)(" + "|".join(BANDS) + r")(?:\])?")
FILE_LINE = re.compile(
    r"(?<!`)\b((?:[A-Za-z0-9_.-]+/)+\d*[A-Za-z0-9_.-]*\.[A-Za-z0-9]+:\d+)\b"
)
FILE_LINE_NAIVE = re.compile(
    r"\b([A-Za-z0-9_./-]+\.[A-Za-z][A-Za-z0-9]*:\d+)\b"
)
URL_RE = re.compile(r"https?://[^\s)\]>'\"`]+")


def _fence_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    i = 0
    while True:
        start = text.find("```", i)
        if start < 0:
            break
        end = text.find("```", start + 3)
        if end < 0:
            ranges.append((start, len(text)))
            break
        ranges.append((start, end + 3))
        i = end + 3
    return ranges


def _in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in ranges)


def _line_at(text: str, pos: int) -> str:
    a = text.rfind("\n", 0, pos) + 1
    b = text.find("\n", pos)
    if b < 0:
        b = len(text)
    return text[a:b]


def _backtick_spans(line: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(line):
        if line[i] == "`":
            j = line.find("`", i + 1)
            if j < 0:
                break
            spans.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return spans


def _in_backticks(line: str, col: int) -> bool:
    return any(a <= col < b for a, b in _backtick_spans(line))


def _claim_id_near(text: str, pos: int) -> str | None:
    line = _line_at(text, pos)
    m = CLAIM_ID_RE.search(line)
    if m:
        return m.group(1)
    # previous line
    a = text.rfind("\n", 0, pos)
    if a > 0:
        prev = _line_at(text, a - 1)
        m = CLAIM_ID_RE.search(prev)
        if m:
            return m.group(1)
    return None


def _host(url: str) -> str:
    body = url.split("://", 1)[-1]
    return body.split("/", 1)[0].split(":", 1)[0].lower()


def extract(text: str) -> list[dict[str, Any]]:
    fences = _fence_ranges(text)
    items: list[dict[str, Any]] = []

    def add(kind: str, value: str, start: int, use: bool, extra: dict | None = None) -> None:
        line = _line_at(text, start)
        col = start - (text.rfind("\n", 0, start) + 1)
        row = {
            "kind": kind,
            "value": value,
            "start": start,
            "use": use,
            "in_fence": _in_ranges(start, fences),
            "in_backticks": _in_backticks(line, col),
            "claim_id": _claim_id_near(text, start),
            "claim_id": _claim_id_near(text, start),
            "line": line.strip(),
        }
        if extra:
            row.update(extra)
        items.append(row)

    for m in UNVERIFIED_NAIVE.finditer(text):
        use_hit = UNVERIFIED_USE.match(text, m.start() - 1) if m.start() > 0 else None
        # [UNVERIFIED] — the word starts at m.start(); bracket is at m.start()-1
        is_bracket = m.start() > 0 and text[m.start() - 1] == "[" and text[m.end() : m.end() + 1] == "]"
        in_fence = _in_ranges(m.start(), fences)
        line = _line_at(text, m.start())
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1)
        in_bt = _in_backticks(line, col)
        use = bool(is_bracket or use_hit) and not in_fence and not in_bt
        add("unverified", "UNVERIFIED", m.start(), use)

    for m in BAND_NAIVE.finditer(text):
        line = _line_at(text, m.start())
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1)
        in_fence = _in_ranges(m.start(), fences)
        in_bt = _in_backticks(line, col)
        prefix = line[:col]
        is_field = bool(re.search(r"confidence_band\s*:\s*$", prefix))
        is_bracket = m.start() > 0 and text[m.start() - 1] == "["
        use = (is_field or is_bracket) and not in_fence and not in_bt
        add("band", m.group(1), m.start(), use)

    for m in FILE_LINE_NAIVE.finditer(text):
        line = _line_at(text, m.start())
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1)
        in_fence = _in_ranges(m.start(), fences)
        in_bt = _in_backticks(line, col)
        has_slash = "/" in m.group(1)
        use = has_slash and not in_fence and not in_bt
        add("file_line", m.group(1), m.start(), use)

    for m in URL_RE.finditer(text):
        raw = m.group(0).rstrip(".,;:")
        line = _line_at(text, m.start())
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1)
        in_fence = _in_ranges(m.start(), fences)
        in_bt = _in_backticks(line, col)
        mention_host = _host(raw) in MENTION_HOSTS
        use = (not mention_host) and not in_fence and not in_bt
        add("url", raw, m.start(), use, {"host": _host(raw)})

    return items


def tally(items: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = ("unverified", "band", "file_line", "url")
    naive = {k: 0 for k in kinds}
    use = {k: 0 for k in kinds}
    mention = {k: 0 for k in kinds}
    for it in items:
        k = it["kind"]
        naive[k] += 1
        if it["use"]:
            use[k] += 1
        else:
            mention[k] += 1
    return {"naive": naive, "use": use, "mention": mention, "n": len(items)}


def count_text(text: str) -> dict[str, Any]:
    items = extract(text)
    out = tally(items)
    out["items"] = items
    return out


def survival(src_use: dict[str, int], dst_use: dict[str, int]) -> dict[str, Any]:
    rows = {}
    for k in ("unverified", "band", "file_line", "url"):
        s = int(src_use.get(k) or 0)
        d = int(dst_use.get(k) or 0)
        rate = None if s == 0 else round(d / s, 6)
        lost = None if s == 0 else s - d
        rows[k] = {
            "source": s,
            "digest": d,
            "lost": lost,
            "survival_rate": rate,
            "undefined_denominator": s == 0,
        }
    return rows
