#!/usr/bin/env python3
"""Two mechanically different translation paths for CNF-0073.

Path recorded-inventory-gloss is the stored first translation. It is never
recomputed by calling this module as a second service.

Path hedge-tag-transfer-v1 is a live tagged-transfer translator: longest-match
glossary plus hedge extraction/reattach. Same-name reuse is same-path-rerun.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
GLOSS_PATH = HERE / "fixtures" / "glossary.json"

PATH_RECORDED = "recorded-inventory-gloss"
PATH_INDEPENDENT = "hedge-tag-transfer-v1"

_PUNCT = set("。．.!?？、,，;；:：\"'“”«»()（）[]【】")


class SamePathRerun(ValueError):
    classification = "same-path-rerun"


def load_glossary() -> dict[str, str]:
    doc = json.loads(GLOSS_PATH.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in (doc.get("entries") or {}).items()}


def longest_match_tokens(text: str, keys: list[str]) -> list[str]:
    i = 0
    n = len(text)
    out: list[str] = []
    while i < n:
        ch = text[i]
        if ch.isspace() or ch in _PUNCT:
            i += 1
            continue
        matched = None
        for key in keys:
            if text.startswith(key, i):
                matched = key
                break
        if matched:
            out.append(matched)
            i += len(matched)
            continue
        # Consume a Latin/Cyrillic word if present, else one code point.
        m = re.match(r"[A-Za-z0-9\-]+|[\u00C0-\u024F]+|[\u0400-\u04FF]+", text[i:])
        if m:
            out.append(m.group(0))
            i += len(m.group(0))
        else:
            out.append(text[i])
            i += 1
    return out


def _hedge_source_forms() -> set[str]:
    from qualifiers import load_hedges

    forms: set[str] = set()
    for row in load_hedges():
        for form in row.get("source_forms") or []:
            forms.add(str(form))
    return forms


def hedge_tag_transfer(original_span: str, language: str | None = None) -> str:
    """Live second path. language is accepted for the call site, unused in lookup."""
    del language
    gloss = load_glossary()
    keys = sorted(gloss.keys(), key=len, reverse=True)
    tokens = longest_match_tokens(original_span, keys)
    hedge_forms = _hedge_source_forms()
    hedges: list[str] = []
    content: list[str] = []
    for tok in tokens:
        english = gloss.get(tok)
        if tok in hedge_forms:
            label = english if english else tok
            if label and label not in hedges:
                hedges.append(label)
            continue
        if english is None:
            content.append(tok)
            continue
        if english == "":
            continue
        content.append(english)
    parts = hedges + content
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def refuse_same_path(first_path: str, second_path: str) -> dict:
    if first_path == second_path:
        raise SamePathRerun(
            f"second path {second_path!r} is the first path re-run"
        )
    return {"rejected": False, "first": first_path, "second": second_path}


def run_second_path(original_span: str, language: str, first_path: str, second_path: str) -> str:
    refuse_same_path(first_path, second_path)
    if second_path != PATH_INDEPENDENT:
        raise ValueError(f"unknown second path {second_path!r}")
    return hedge_tag_transfer(original_span, language)


def paths_are_mechanically_different(first: str, second: str) -> bool:
    return first != second and {first, second} == {PATH_RECORDED, PATH_INDEPENDENT}
