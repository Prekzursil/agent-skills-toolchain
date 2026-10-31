"""Marketplace search: deterministic skill-weighted ranking (IMP-0102).

Recovered 2026-10-25 by builder shard 11 wave 2 from the delivery receipt
`command-center/receipts/IMP-0102.json` (the stub this replaces carried no
logic). Receipt-pinned contract:

  * ranking is a function of the plugin LIST, never of insertion order:
    the same query over rebuilds from shuffled insertion orders yields ONE
    distinct ordering
  * field weights: name > skills > description; popularity (downloads/stars)
    is NOT a ranking input
  * equal scores are broken by stable key (package id), so a score tie is a
    true tie with a deterministic order
  * skills[] are indexed: a package is findable by a token that appears only
    in skills[]
  * outcomes are typed: no-match -> kind="empty" (ok=true); a missing
    registry file -> kind="index_error" (ok=false, error="missing:<path>")
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# field weights: name dominates, then skills, then description
W_NAME = 6.0
W_SKILL = 3.0
W_DESC = 1.0

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(str(text or "").lower())


class SearchIndex:
    """Deterministic inverted index over a plugin list."""

    def __init__(self, plugins: list[dict[str, Any]]) -> None:
        # canonical insertion order: stable key, never the caller's order
        rows = sorted(plugins, key=lambda p: str(p.get("id") or p.get("name") or ""))
        self._by_token: dict[str, dict[str, float]] = {}
        self._docs: dict[str, dict[str, Any]] = {}
        for p in rows:
            pid = str(p.get("id") or p.get("name"))
            score_terms: dict[str, float] = {}
            for tok in _tokens(str(p.get("name") or "")):
                score_terms[tok] = score_terms.get(tok, 0.0) + W_NAME
            for skill in p.get("skills") or []:
                for tok in _tokens(str(skill)):
                    score_terms[tok] = score_terms.get(tok, 0.0) + W_SKILL
            for tok in _tokens(str(p.get("description") or "")):
                score_terms[tok] = score_terms.get(tok, 0.0) + W_DESC
            for tok, w in score_terms.items():
                self._by_token.setdefault(tok, {})[pid] = w
            self._docs[pid] = p

    def query(self, q: str) -> dict[str, Any]:
        toks = _tokens(q)
        scores: dict[str, float] = {}
        for tok in toks:
            for pid, w in self._by_token.get(tok, {}).items():
                scores[pid] = scores.get(pid, 0.0) + w
        hits = [
            {
                "id": pid,
                "name": (self._docs[pid].get("name") or pid),
                "score": round(s, 6),
                "matched_by": sorted(
                    t for t in toks
                    if pid in self._by_token.get(t, {})
                ),
            }
            for pid, s in scores.items()
        ]
        # stable order: descending score, ties broken by package id
        hits.sort(key=lambda h: (-h["score"], h["id"]))
        return {
            "ok": True,
            "kind": "empty" if not hits else "hits",
            "query": q,
            "hit_count": len(hits),
            "hits": hits,
        }


def search_path(path: str | Path, q: str) -> dict[str, Any]:
    """Query the registry at ``path``; a missing file is kind=index_error."""
    p = Path(path)
    if not p.is_file():
        return {
            "ok": False,
            "kind": "index_error",
            "error": f"missing:{p.as_posix()}",
            "hit_count": 0,
            "keys": [],
            "hits": [],
        }
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "kind": "index_error",
            "error": f"unparseable:{type(exc).__name__}:{p.as_posix()}",
            "hit_count": 0,
            "keys": [],
            "hits": [],
        }
    plugins = doc.get("plugins") if isinstance(doc, dict) else doc
    index = SearchIndex(plugins or [])
    return index.query(q)
