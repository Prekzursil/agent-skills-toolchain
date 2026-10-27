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
def lexical_rank(query: str, caps: list, k: int = 5, seed: int = 0) -> list:
    """Deterministic lexical Jaccard ranking of caps against query.

    Rows: [{"capability_id", "score_e9", "method": "lexical-jaccard"}].
    Empty for a query with zero token overlap with every description.
    """
    qtok = tokenize(query)
    rows = []
    for cap in caps or []:
        ctok = tokenize(str(cap.get("description") or ""))
        inter = qtok & ctok
        if not inter:
            continue
        union = qtok | ctok
        score = (len(inter) * 1_000_000_000) // len(union)
        rows.append(
            {
                "capability_id": cap.get("capability_id") or cap.get("id"),
                "score_e9": int(score),
                "method": "lexical-jaccard",
            }
        )
    rows.sort(key=lambda r: (-r["score_e9"], str(r["capability_id"])))
    return rows[: max(0, int(k))]
