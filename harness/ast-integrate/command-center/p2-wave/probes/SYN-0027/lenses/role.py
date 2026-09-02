"""USE vs MENTION by structural role, not substring presence.

A document ABOUT a defect necessarily contains that defect's text. Wrapping
(quotes, fences, blockquotes) and JSON mention-keys are how this estate
separates a quoted example from an assertion in the author's own voice.

The known-broken matcher (substring_as_use) treats any located span as USE.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

MENTION_KEYS = frozenset(
    {
        "quoted",
        "quote",
        "quoted_span",
        "quoted_example",
        "quoted_phrase",
        "example",
        "examples",
        "mention",
        "mention_only",
        "sample",
        "fixture_quote",
        "illustration",
        "excerpt",
        "raw_excerpt",
        "discussed",
        "discussed_text",
        "example_text",
    }
)

ANCHOR_RE = re.compile(
    r"(?:command-center|tools|hooks|platform|rules)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,8}"
    r"(?::\d+)?"
    r"|[A-Za-z0-9_./-]+\.[A-Za-z]{1,8}:\d+"
    r"|\[(?:E|C|F|SYN|IMP|CNF)-?\d+\]"
)


def _fence_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    i = 0
    while True:
        a = text.find("```", i)
        if a < 0:
            break
        b = text.find("```", a + 3)
        if b < 0:
            ranges.append((a, len(text)))
            break
        ranges.append((a, b + 3))
        i = b + 3
    return ranges


def _quote_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for q in ('"', "'"):
        i = 0
        while True:
            a = text.find(q, i)
            if a < 0:
                break
            b = text.find(q, a + 1)
            if b < 0:
                break
            if b - a > 1:
                ranges.append((a + 1, b))
            i = b + 1
    return ranges


def _inside(ranges: list[tuple[int, int]], start: int, end: int) -> bool:
    for a, b in ranges:
        if a <= start and end <= b:
            return True
    return False


def _line_at(text: str, pos: int) -> str:
    a = text.rfind("\n", 0, pos) + 1
    b = text.find("\n", pos)
    if b < 0:
        b = len(text)
    return text[a:b]


def classify_text_span(
    text: str,
    start: int,
    end: int,
    *,
    ignore_wrappers: bool = False,
) -> str:
    if start < 0 or end > len(text) or start >= end:
        return "ABSENT"
    if ignore_wrappers:
        return "USE"
    if _inside(_fence_ranges(text), start, end):
        return "MENTION"
    line = _line_at(text, start)
    if line.lstrip().startswith(">"):
        return "MENTION"
    if _inside(_quote_ranges(text), start, end):
        return "MENTION"
    return "USE"


def substring_as_use(text: str, span: str) -> str:
    """Known-broken detector: presence of the bytes is treated as an assertion."""
    if not span:
        return "ABSENT"
    return "USE" if span in text else "ABSENT"


def path_role(path: list[Any]) -> str:
    for part in path:
        if isinstance(part, str) and part.lower() in MENTION_KEYS:
            return "MENTION"
    return "USE"


def iter_json_strings(obj: Any, path: list[Any] | None = None) -> Iterator[tuple[list[Any], str]]:
    if path is None:
        path = []
    if isinstance(obj, str):
        yield path, obj
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_json_strings(v, path + [str(k)])
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_json_strings(v, path + [i])


def record_anchors(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key in ("anchors", "evidence", "anchor", "source_anchor"):
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                found.append(val.strip())
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.strip():
                        found.append(item.strip())
                    elif isinstance(item, dict):
                        loc = item.get("locator") or item.get("path") or item.get("anchor")
                        if isinstance(loc, str) and loc.strip():
                            found.append(loc.strip())
    return found


def anchors_in_text(text: str) -> list[str]:
    return [m.group(0) for m in ANCHOR_RE.finditer(text)]


def load_subject(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    kind = "json" if path.suffix.lower() == ".json" else "text"
    parsed: Any = None
    if kind == "json":
        parsed = json.loads(raw)
    return {"path": path, "text": raw, "kind": kind, "parsed": parsed}
