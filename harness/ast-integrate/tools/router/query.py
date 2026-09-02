"""Route a query against the cached capability index (IMP-0402).

``route_next`` is the read path of the router: fingerprint the capability
roots, serve or rebuild the cache through ``tools/router/index_cache``, then
rank the indexed capabilities lexically against the query. Because every call
re-validates the cache, an edited description shows up in the very next
answer, and the answer carries the cache action/reason so a probe can see
*that* it rebuilt and *why*.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Sequence

from .index_cache import load_or_rebuild

VERDICT_SELECTED = "SELECTED"
VERDICT_AMBIGUOUS = "AMBIGUOUS"
VERDICT_NO_MATCH = "NO-MATCH"

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lower-cased alphanumeric tokens; hyphenated terms split into parts."""
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _document_tokens(cap: dict[str, Any]) -> set[str]:
    return set(tokenize(f"{cap.get('name') or ''} {cap.get('description') or ''}"))


def rank_capabilities(
    query: str, capabilities: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Score every capability against ``query``; highest first, ties by id.

    Score = sum over matched query tokens of idf(token) / number of distinct
    query tokens, where idf is computed over the capability set. Rare terms
    therefore dominate common ones, and the score lies in [0, max_idf].
    """
    q_tokens = set(tokenize(query))
    if not q_tokens:
        raise ValueError("query has no alphanumeric tokens to route on")
    docs = [(cap, _document_tokens(cap)) for cap in capabilities]
    n_docs = len(docs)
    df: dict[str, int] = {}
    for _, toks in docs:
        for t in q_tokens & toks:
            df[t] = df.get(t, 0) + 1
    ranked: list[dict[str, Any]] = []
    for cap, toks in docs:
        matched = sorted(q_tokens & toks)
        score = 0.0
        for t in matched:
            score += math.log((n_docs + 1) / (df[t] + 0.5)) + 1.0
        score = round(score / len(q_tokens), 9)
        ranked.append(
            {
                "capability_id": str(cap.get("capability_id") or ""),
                "score": score,
                "matched_tokens": matched,
                "description": str(cap.get("description") or ""),
                "source_path": cap.get("source_path"),
            }
        )
    ranked.sort(key=lambda r: (-r["score"], r["capability_id"]))
    return ranked


def route_next(
    query: str,
    *,
    cache_path: Path | str,
    roots: Sequence[Path | str],
    top_n: int = 3,
) -> dict[str, Any]:
    """Answer ``query`` from the current capability sources.

    Returns ``verdict`` (``SELECTED`` / ``AMBIGUOUS`` / ``NO-MATCH``), the
    selected ``capability_id`` and its description as ``answer`` (both ``None``
    unless selected), the ranked ``candidates``, and the cache bookkeeping
    (``cache_action``, ``cache_reason``, ``content_hash``, ``mtime_token``).
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    load = load_or_rebuild(cache_path, roots)
    ranked = rank_capabilities(query, load.capabilities)
    best = ranked[0] if ranked else None
    verdict = VERDICT_NO_MATCH
    selected: dict[str, Any] | None = None
    if best is not None and best["score"] > 0:
        tied = [r for r in ranked if r["score"] == best["score"]]
        if len(tied) == 1:
            verdict = VERDICT_SELECTED
            selected = best
        else:
            verdict = VERDICT_AMBIGUOUS
    return {
        "query": query,
        "verdict": verdict,
        "capability_id": selected["capability_id"] if selected else None,
        "answer": selected["description"] if selected else None,
        "score": best["score"] if best else 0.0,
        "candidates": ranked[:top_n],
        "capability_count": len(load.capabilities),
        "cache_action": load.action,
        "cache_reason": load.reason,
        "content_hash": load.fingerprint.content_hash,
        "mtime_token": load.fingerprint.mtime_token,
    }


__all__ = [
    "VERDICT_AMBIGUOUS",
    "VERDICT_NO_MATCH",
    "VERDICT_SELECTED",
    "rank_capabilities",
    "route_next",
    "tokenize",
]
