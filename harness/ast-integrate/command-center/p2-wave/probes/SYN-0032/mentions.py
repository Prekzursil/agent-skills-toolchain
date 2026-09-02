"""Synthesis mention counting that ignores table-of-contents text (use-vs-mention)."""
from __future__ import annotations

import json
import re
from pathlib import Path

TOC_HEADING = re.compile(
    r"^(#{1,6}\s*)?(table of contents|contents)\s*$",
    re.IGNORECASE,
)
TOC_JSON_KEYS = frozenset(
    {"toc", "table_of_contents", "table-of-contents", "contents"}
)
BUCKET_TOKEN = re.compile(r"\bB(?:0[1-9]|1[0-3])\b")
PREFIX_ID = re.compile(
    r"\b(ADV|ARC|AUD|BLD|CC|CNF|CNL|IMP|REL|RES|SYN|TST|WFA)-\d{4}\b"
)
PHASE_TOKEN = re.compile(
    r"(?i)\bphase\s+(16|15|14|13|12|11|10|9|8|7A|7|6|5|4|3|2C|2B|2A|2|1|0)\b"
)


def strip_markdown_toc(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    in_toc = False
    for line in lines:
        stripped = line.strip()
        if TOC_HEADING.match(stripped):
            in_toc = True
            continue
        if in_toc:
            if stripped.startswith("#") and not TOC_HEADING.match(stripped):
                in_toc = False
                kept.append(line)
                continue
            if stripped == "":
                continue
            if stripped[:1] in "-*+" or re.match(r"^\d+[.)]", stripped):
                continue
            if stripped.startswith("["):
                continue
            in_toc = False
            kept.append(line)
            continue
        kept.append(line)
    return "\n".join(kept)


def json_body_text(obj: object, skip: bool = False) -> str:
    chunks: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            child_skip = skip or str(key).lower() in TOC_JSON_KEYS
            chunks.append(json_body_text(val, child_skip))
    elif isinstance(obj, list):
        for item in obj:
            chunks.append(json_body_text(item, skip))
    elif isinstance(obj, str) and not skip:
        chunks.append(obj)
    return "\n".join(c for c in chunks if c)


def body_text_for_path(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            return strip_markdown_toc(raw)
        return json_body_text(doc)
    return strip_markdown_toc(raw)


def body_text_for_string(text: str, kind: str = "markdown") -> str:
    if kind == "json":
        try:
            return json_body_text(json.loads(text))
        except json.JSONDecodeError:
            return strip_markdown_toc(text)
    return strip_markdown_toc(text)


def count_tokens(body: str, prefix_to_bucket: dict[str, str]) -> tuple[dict[str, int], dict[str, int]]:
    buckets = {bid: 0 for bid in prefix_to_bucket.values()}
    phases: dict[str, int] = {}
    for match in BUCKET_TOKEN.finditer(body):
        token = match.group(0)
        if token in buckets:
            buckets[token] += 1
    for match in PREFIX_ID.finditer(body):
        pref = match.group(1)
        bid = prefix_to_bucket.get(pref)
        if bid:
            buckets[bid] += 1
    for match in PHASE_TOKEN.finditer(body):
        ph = match.group(1)
        # Normalize the captured alternative (already canonical).
        phases[ph] = phases.get(ph, 0) + 1
    return buckets, phases
