#!/usr/bin/env python3
"""Always-top-3 popularity stub and corpus scoring for IMP-0398.

Popularity is usage_count from the capability index, never the gold-label
histogram. Exact-set-match is the declared metric so empty expected sets are
misses (subset-recall would let negatives pass vacuously).
"""
from __future__ import annotations

from typing import Any, Iterable


def top3_from_caps(caps: Iterable[dict]) -> list[str]:
    ranked = sorted(
        caps,
        key=lambda c: (-int(c.get("usage_count") or 0), str(c.get("capability_id") or "")),
    )
    ids = [str(c["capability_id"]) for c in ranked if c.get("capability_id")]
    if len(ids) < 3:
        raise ValueError(f"need >=3 capabilities, got {len(ids)}")
    return ids[:3]


def as_set(ids: Iterable[str] | None) -> frozenset[str]:
    return frozenset(str(x) for x in (ids or []) if str(x))


def exact_match(expected: Iterable[str], predicted: Iterable[str]) -> bool:
    return as_set(expected) == as_set(predicted)


def jaccard(expected: Iterable[str], predicted: Iterable[str]) -> float:
    e, p = as_set(expected), as_set(predicted)
    if not e and not p:
        return 1.0
    union = e | p
    if not union:
        return 0.0
    return len(e & p) / len(union)


def always_top3(query_row: dict, top3: list[str]) -> list[str]:
    """Stub ignores the query and always returns the same three ids."""
    _ = query_row
    return list(top3)


def score_corpus(queries: list[dict], top3: list[str]) -> dict[str, Any]:
    n = len(queries)
    if n == 0:
        raise ValueError("empty corpus")
    hits = 0
    jacc = 0.0
    per: list[dict] = []
    pred = list(top3)
    for q in queries:
        exp = q.get("expected_capability_ids") or []
        hit = exact_match(exp, pred)
        jac = jaccard(exp, pred)
        hits += int(hit)
        jacc += jac
        per.append(
            {
                "id": q.get("id"),
                "exact": hit,
                "jaccard": jac,
                "expected": sorted(as_set(exp)),
                "predicted": sorted(as_set(pred)),
            }
        )
    acc = hits / n
    return {
        "n": n,
        "n_exact_hits": hits,
        "score": acc,
        "mean_jaccard": jacc / n,
        "top3": list(top3),
        "per_query": per,
    }


def label_frequency_top3(queries: list[dict]) -> list[str]:
    freq: dict[str, int] = {}
    for q in queries:
        for cid in q.get("expected_capability_ids") or []:
            freq[str(cid)] = freq.get(str(cid), 0) + 1
    ranked = sorted(freq, key=lambda k: (-freq[k], k))
    return ranked[:3]


def easy_mutant(queries: list[dict], top3: list[str]) -> list[dict]:
    """Too-easy corpus: every POSITIVE row expects exactly the popular top-3.

    Negatives stay empty. A popularity stub then scores well on positives,
    which is the corpus-too-easy failure class.
    """
    out = []
    for q in queries:
        row = dict(q)
        if str(q.get("polarity") or "").upper() == "NEGATIVE":
            row["expected_capability_ids"] = []
        else:
            row["expected_capability_ids"] = list(top3)
            row["polarity"] = "POSITIVE"
        out.append(row)
    return out
