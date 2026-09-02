"""Markdown heading-id extractor and field parser for WFA-0011.

Signal A uses HEADING_ID_RE: an ATX heading whose entire title is one
backtick-delimited id. Closing-anchor: the closing backtick, then optional
whitespace, then end of line. That is the measured false-positive class —
body `id` mentions and headings that merely mention `id` must stay silent.

Signal B parses classification / licence / family from the block under each
id heading. Set equality of ids cannot see a per-field drift.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

# Honest extractor. Closing-anchor is the second backtick plus EOL.
HEADING_ID_RE = re.compile(
    r"^(#{1,6})[ \t]+`([A-Za-z][A-Za-z0-9._-]*)`[ \t]*$",
    re.MULTILINE,
)

# Measured false-positive class: any backtick-delimited token, including body
# mentions and inline heading mentions. No heading anchor, no EOL close.
NAIVE_BACKTICK_ID_RE = re.compile(r"`([A-Za-z][A-Za-z0-9._-]*)`")

# Opening backtick without requiring a close — no closing-anchor at all.
UNANCHORED_OPEN_BT_RE = re.compile(r"`([A-Za-z][A-Za-z0-9._-]*)")

_FIELD_RE = re.compile(
    r"^[-*][ \t]*(classification|licence|license|family)[ \t]*:[ \t]*(.+?)\s*$",
    re.IGNORECASE,
)
_ANY_HEADING_RE = re.compile(r"^#{1,6}[ \t]+")
_ID_HEADING_LINE_RE = re.compile(
    r"^(#{1,6})[ \t]+`([A-Za-z][A-Za-z0-9._-]*)`[ \t]*$"
)

JSON_RECORD_KEYS = ("candidates", "blueprints", "records", "items", "workflows")
COMPARE_FIELDS = ("classification", "licence", "family")


def heading_ids(markdown: str) -> list[str]:
    """Ordered unique-preserving id list from honest heading regex."""
    seen: set[str] = set()
    out: list[str] = []
    for _, ident in HEADING_ID_RE.findall(markdown):
        if ident not in seen:
            seen.add(ident)
            out.append(ident)
    return out


def naive_backtick_ids(markdown: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ident in NAIVE_BACKTICK_ID_RE.findall(markdown):
        if ident not in seen:
            seen.add(ident)
            out.append(ident)
    return out


def unanchored_open_ids(markdown: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ident in UNANCHORED_OPEN_BT_RE.findall(markdown):
        if ident not in seen:
            seen.add(ident)
            out.append(ident)
    return out


def heading_records(markdown: str) -> list[dict[str, str]]:
    """Parse id headings plus classification/licence/family field lines."""
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in markdown.splitlines():
        hm = _ID_HEADING_LINE_RE.match(line)
        if hm:
            if current is not None:
                records.append(current)
            current = {
                "id": hm.group(2),
                "classification": "",
                "licence": "",
                "family": "",
            }
            continue
        if current is not None and _ANY_HEADING_RE.match(line):
            records.append(current)
            current = None
            continue
        if current is None:
            continue
        fm = _FIELD_RE.match(line)
        if not fm:
            continue
        key = fm.group(1).lower()
        if key == "license":
            key = "licence"
        current[key] = fm.group(2).strip()
    if current is not None:
        records.append(current)
    return records


def licence_of(rec: dict[str, Any]) -> str:
    for key in ("licence", "license"):
        val = rec.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def normalize_fields(rec: dict[str, Any]) -> dict[str, str]:
    ident = str(rec.get("id") or "").strip()
    return {
        "id": ident,
        "classification": str(rec.get("classification") or "").strip(),
        "licence": licence_of(rec),
        "family": str(rec.get("family") or "").strip(),
    }


def json_record_list(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict) and x.get("id")]
    if not isinstance(doc, dict):
        return []
    for key in JSON_RECORD_KEYS:
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict) and x.get("id")]
    return []


def load_json_records(text: str) -> list[dict[str, Any]]:
    return json_record_list(json.loads(text))


def id_set_equal(md_ids: Iterable[str], json_ids: Iterable[str]) -> dict[str, Any]:
    a = [x for x in md_ids]
    b = [x for x in json_ids]
    sa, sb = set(a), set(b)
    return {
        "markdown_ids": a,
        "json_ids": b,
        "markdown_n": len(sa),
        "json_n": len(sb),
        "only_markdown": sorted(sa - sb),
        "only_json": sorted(sb - sa),
        "equal": sa == sb,
    }


def has_closing_anchor(pattern: str | None = None) -> dict[str, Any]:
    """Structural proof the heading regex closes the backtick and the line."""
    pat = HEADING_ID_RE.pattern if pattern is None else pattern
    wrapped = "`([A-Za-z]" in pat and ")`" in pat
    ends = pat.rstrip().endswith("$")
    return {
        "ends_at_eol": ends,
        "id_wrapped_in_backticks": wrapped,
        "closing_anchor": bool(ends and wrapped),
        "pattern": pat,
    }


# Dual names so gate.py and both probes import cleanly.
heading_ids = heading_ids
has_closing_anchor = has_closing_anchor
id_set_equal = id_set_equal
load_json_records = load_json_records
naive_backtick_ids = naive_backtick_ids
unanchored_open_ids = unanchored_open_ids
