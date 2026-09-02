"""Enumerate headings and verdict-tagged sentences. Classification lives in extract.py."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contract import JSON_HEADING_KEYS, VERDICT_TAGS

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
VERDICT_RE = re.compile(r"\b(" + "|".join(VERDICT_TAGS) + r")\b")
JSON_KEY_VAL = re.compile(
    r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s*:\s*"(?P<val>(?:\\.|[^"\\])*)"\s*,?\s*$'
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def read_lines(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    return raw.split("\n")


def json_unescape(inner: str) -> str:
    try:
        return json.loads(f'"{inner}"')
    except json.JSONDecodeError:
        return inner.replace('\\"', '"').replace("\\\\", "\\")


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def _md_body_lines(lines: list[str]):
    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield i, line


def enumerate_markdown(path: Path, rel: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for lineno, line in _md_body_lines(read_lines(path)):
        hm = HEADING_RE.match(line)
        if hm:
            spans.append(
                {
                    "kind": "heading",
                    "path": rel,
                    "line": lineno,
                    "text": hm.group(2).strip(),
                    "snippet": hm.group(2).strip(),
                    "raw": line,
                }
            )
            continue
        for sent in split_sentences(line.strip()):
            tags = VERDICT_RE.findall(sent)
            if not tags:
                continue
            spans.append(
                {
                    "kind": "verdict",
                    "path": rel,
                    "line": lineno,
                    "text": sent,
                    "snippet": sent,
                    "raw": line,
                    "tags": tags,
                }
            )
    return spans


def enumerate_json_text(path: Path, rel: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for lineno, line in enumerate(read_lines(path), 1):
        m = JSON_KEY_VAL.match(line)
        if not m:
            continue
        key = json_unescape(m.group("key"))
        val = json_unescape(m.group("val")).strip()
        if not val:
            continue
        if key in JSON_HEADING_KEYS:
            spans.append(
                {
                    "kind": "heading",
                    "path": rel,
                    "line": lineno,
                    "text": val,
                    "snippet": val,
                    "raw": line,
                    "json_key": key,
                }
            )
        for sent in split_sentences(val):
            tags = VERDICT_RE.findall(sent)
            if not tags:
                continue
            spans.append(
                {
                    "kind": "verdict",
                    "path": rel,
                    "line": lineno,
                    "text": sent,
                    "snippet": sent,
                    "raw": line,
                    "tags": tags,
                    "json_key": key,
                }
            )
    return spans


def enumerate_file(path: Path, rel: str) -> list[dict[str, Any]]:
    name = path.name.lower()
    if name.endswith(".json"):
        return enumerate_json_text(path, rel)
    return enumerate_markdown(path, rel)
