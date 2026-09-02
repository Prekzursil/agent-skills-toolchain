"""Lexical Jaccard distance plus independently recorded stance Hamming."""
from __future__ import annotations

import math
import re
from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence

from common import CHANCE_ACCURACY, STANCE_AXES

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall((text or "").lower()))


def jaccard_distance(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return 1.0 - (len(sa & sb) / len(union))


def jaccard_similarity(a: Iterable[str], b: Iterable[str]) -> float:
    return 1.0 - jaccard_distance(a, b)


def stance_tuple(stance: Mapping[str, Any] | None) -> tuple[str, ...]:
    rec = stance or {}
    return tuple(str(rec.get(axis) or "") for axis in STANCE_AXES)


def stance_divergence(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> float:
    a, b = stance_tuple(left), stance_tuple(right)
    n = len(STANCE_AXES)
    if n == 0:
        return 0.0
    return sum(1 for x, y in zip(a, b) if x != y) / float(n)


def pairwise_rows(briefs: Sequence[Mapping[str, Any]], council_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for left, right in combinations(briefs, 2):
        lex = jaccard_distance(tokens(str(left.get("text") or "")), tokens(str(right.get("text") or "")))
        st = stance_divergence(left.get("stance"), right.get("stance"))
        rows.append(
            {
                "council": council_id,
                "left": str(left.get("id") or ""),
                "right": str(right.get("id") or ""),
                "lexical_divergence": lex,
                "stance_divergence": st,
                "combined_divergence": (lex + st) / 2.0,
            }
        )
    return rows


def council_summary(briefs: Sequence[Mapping[str, Any]], council_id: str) -> dict[str, Any]:
    pairs = pairwise_rows(briefs, council_id)
    n = len(pairs)
    mean_lex = sum(p["lexical_divergence"] for p in pairs) / n if n else 0.0
    mean_st = sum(p["stance_divergence"] for p in pairs) / n if n else 0.0
    mean_comb = sum(p["combined_divergence"] for p in pairs) / n if n else 0.0
    return {
        "council": council_id,
        "briefs": len(briefs),
        "pairs": n,
        "mean_lexical_divergence": mean_lex,
        "mean_stance_divergence": mean_st,
        "mean_combined_divergence": mean_comb,
        "pairs_detail": pairs,
    }


def binomial_tail_ge(k: int, n: int, p: float = CHANCE_ACCURACY) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if n <= 0:
        return 1.0
    k = max(0, min(k, n))
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p**i) * ((1.0 - p) ** (n - i))
    return total


def fmt(value: float) -> str:
    return f"{value:.6f}"
