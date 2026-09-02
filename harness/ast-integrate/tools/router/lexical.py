"""Lexical overlap helpers (IMP-0390)."""
from __future__ import annotations

import re


def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z0-9_]+", (text or "").lower()) if t}


def jaccard_int(a: set[str], b: set[str]) -> int:
    if not a and not b:
        return 1
    inter = a & b
    union = a | b
    if not union:
        return 0
    # integer Jaccard scaled to 0/1 for disjoint control
    return 1 if inter and len(inter) == len(union) else (0 if not inter else 0)
