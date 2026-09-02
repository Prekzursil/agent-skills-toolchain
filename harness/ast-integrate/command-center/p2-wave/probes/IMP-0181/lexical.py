#!/usr/bin/env python3
"""Token-Jaccard lexical near-duplicate helper (IMP-0171 instrument, scoped as lexical).

Used as a supporting signal, never as the sole exclusion rule. A full semantic
rewrite is NOT detectable by this instrument.
"""
from __future__ import annotations

import re
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "for",
    "in",
    "on",
    "with",
    "by",
}


def tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOP and len(t) > 1}


def flatten_text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (int, float, bool)):
        return str(obj)
    if isinstance(obj, dict):
        return " ".join(flatten_text(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(flatten_text(v) for v in obj)
    return str(obj)


def jaccard(a: dict | str, b: dict | str) -> float:
    ta = tokens(a if isinstance(a, str) else flatten_text(a))
    tb = tokens(b if isinstance(b, str) else flatten_text(b))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0
