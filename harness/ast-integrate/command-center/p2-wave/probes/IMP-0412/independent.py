#!/usr/bin/env python3
"""Mechanically independent near-duplicate method (no stemmer, no synonym map).

Used by probe 2 as the second signal: a different tokenizer recomputes the
live catalog collision count. Agreement on an empty collision list is evidence
the primary fingerprint is not hiding a coarse bucket behind stemming.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

INDEPENDENT_THRESHOLD = 0.85
INDEPENDENT_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "and",
        "or",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "as",
        "at",
        "is",
        "are",
        "be",
        "this",
        "that",
        "it",
        "its",
    }
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def independent_target_tokens(text: str) -> frozenset[str]:
    folded = unicodedata.normalize("NFKC", text or "").lower()
    folded = _NON_ALNUM.sub(" ", folded)
    out = set()
    for word in folded.split():
        if word in INDEPENDENT_STOP or len(word) <= 1:
            continue
        out.add(word)
    return frozenset(out)


def independent_input(item: Any) -> str:
    text = unicodedata.normalize("NFKC", str(item)).strip().replace("\\", "/").lower()
    return re.sub(r"\s+", " ", text).strip()


def independent_input_set(inputs: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(sorted({independent_input(x) for x in (inputs or []) if str(x).strip()}))


def independent_jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    return (len(a & b) / union) if union else 1.0


def independent_target_text(unit: Mapping[str, Any]) -> str:
    for key in ("question_or_target", "target", "title"):
        val = unit.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def independent_collisions(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for unit in units:
        if not isinstance(unit, Mapping) or not unit.get("id"):
            continue
        rows.append(
            (
                str(unit["id"]),
                independent_input_set(unit.get("inputs")),
                independent_target_tokens(independent_target_text(unit)),
            )
        )
    buckets: dict[tuple[str, ...], list[tuple[str, frozenset[str]]]] = defaultdict(list)
    for uid, inputs, tokens in rows:
        buckets[inputs].append((uid, tokens))
    hits: list[dict[str, Any]] = []
    for group in buckets.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a_id, a_tok = group[i]
                b_id, b_tok = group[j]
                score = independent_jaccard(a_tok, b_tok)
                if score >= INDEPENDENT_THRESHOLD:
                    left, right = sorted([a_id, b_id])
                    hits.append(
                        {
                            "unit_id_a": left,
                            "unit_id_b": right,
                            "jaccard": round(score, 6),
                            "method": "independent-raw-tokens-plus-inputs",
                        }
                    )
    hits.sort(key=lambda r: (r["unit_id_a"], r["unit_id_b"]))
    return hits
