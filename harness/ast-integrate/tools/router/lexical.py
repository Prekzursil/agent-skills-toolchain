"""Lexical (token-Jaccard) capability matcher - the first-stage instrument (IMP-0390).

This is the stage the semantic matcher is measured *against*.  It tokenizes
exactly like the IMP-0388 description linter (``router.desc_lint``): lower-cased
``[A-Za-z0-9_]+`` runs, stop words dropped, single characters dropped.  Two texts
that share no such token have Jaccard 0 and are invisible to this stage by
construction; that is the property the planted paraphrase control relies on.

Everything here is a deterministic set computation.  ``seed`` parameters are
accepted for call symmetry with :func:`router.semantic_matcher.match` and are
echoed into the rows so a receipt can tie a lexical ranking to the control-set
seed; no randomness is involved.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

METHOD = "lexical-jaccard"
E9 = 1_000_000_000

# Mirrors router.desc_lint.STOP so the lexical stage sees what the linter sees.
STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "the",
        "for",
        "to",
        "of",
        "in",
        "on",
        "or",
        "is",
        "as",
        "by",
        "with",
        "from",
        "when",
        "use",
        "user",
        "asks",
        "that",
        "this",
        "it",
        "into",
        "via",
        "plus",
        "not",
    }
)
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> frozenset[str]:
    """Content tokens of ``text``: lower-cased, stop words and 1-char runs dropped."""
    if text is None:
        return frozenset()
    if not isinstance(text, str):
        raise TypeError(f"tokenize expects str, got {type(text).__name__}")
    return frozenset(
        t.lower() for t in TOKEN_RE.findall(text) if len(t) > 1 and t.lower() not in STOP
    )


def _as_set(tokens: Iterable[str]) -> frozenset[str]:
    if isinstance(tokens, str):
        return tokenize(tokens)
    return frozenset(str(t) for t in tokens)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """|a & b| / |a | b| over token sets; 0.0 when both are empty."""
    sa, sb = _as_set(a), _as_set(b)
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def jaccard_int(a: Iterable[str], b: Iterable[str]) -> int:
    """Jaccard scaled to an integer in [0, 1e9] for byte-stable receipts."""
    return int(round(jaccard(a, b) * E9))


def shared_tokens(a: Iterable[str], b: Iterable[str]) -> list[str]:
    """Sorted tokens common to both texts/token sets."""
    return sorted(_as_set(a) & _as_set(b))


def cap_id(cap: Mapping[str, Any]) -> str:
    return str(cap.get("capability_id") or cap.get("id") or cap.get("name") or "")


def cap_text(cap: Mapping[str, Any]) -> str:
    return str(cap.get("description") or "")


def lexical_rank(
    query: str,
    caps: Iterable[Mapping[str, Any]],
    k: int = 5,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Top-``k`` capabilities by token Jaccard with ``query``; zero-overlap rows are excluded.

    Rows are sorted by descending ``jaccard_e9`` then ``capability_id`` and carry
    ``method="lexical-jaccard"`` so a downstream consumer can never mistake them
    for semantic results.
    """
    if int(k) < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise TypeError("seed must be an int or None")
    qtok = tokenize(query)
    scored: list[tuple[int, str, list[str]]] = []
    for cap in caps:
        if not isinstance(cap, Mapping):
            raise TypeError(f"capabilities must be mappings, got {type(cap).__name__}")
        ctok = tokenize(cap_text(cap))
        score = jaccard_int(qtok, ctok)
        if score > 0:
            scored.append((score, cap_id(cap), sorted(qtok & ctok)))
    scored.sort(key=lambda row: (-row[0], row[1]))
    rows: list[dict[str, Any]] = []
    for rank, (score, cid, shared) in enumerate(scored[: int(k)], 1):
        rows.append(
            {
                "rank": rank,
                "capability_id": cid,
                "jaccard_e9": score,
                "shared_tokens": shared,
                "method": METHOD,
                "seed": seed,
            }
        )
    return rows


def lexical_top(query: str, caps: Iterable[Mapping[str, Any]], k: int = 5) -> list[str]:
    """Capability ids of :func:`lexical_rank`, in rank order."""
    return [row["capability_id"] for row in lexical_rank(query, caps, k=k)]


__all__ = [
    "E9",
    "METHOD",
    "STOP",
    "TOKEN_RE",
    "cap_id",
    "cap_text",
    "jaccard",
    "jaccard_int",
    "lexical_rank",
    "lexical_top",
    "shared_tokens",
    "tokenize",
]
