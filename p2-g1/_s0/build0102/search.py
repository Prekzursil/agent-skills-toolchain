"""Deterministic BM25-style lexical search index over the marketplace registry.

IMP-0102 (Prompt Two, phase 6). Catalog contract (question_or_target):

    Build a BM25-style index over package name, description, tags and skill
    names with a total ordering that is stable across runs and independent of
    insertion order, and with no popularity term -- ranking must be
    explainable from the query and the document alone.

HOW DETERMINISM IS ACHIEVED (bit-exact, not "should be fine"):

  * Documents are keyed by their stable key and every corpus statistic is
    accumulated in sorted stable-key order, so plugin insertion order cannot
    reach a float.
  * Document frequencies are integers; idf is a pure function of (N, df).
  * A document's score sums per-term contributions over the query's unique
    terms in sorted term order, so query token order cannot reach a float
    either.
  * No popularity/download/star/install field is read anywhere in this
    module. POPULARITY_TERM is pinned to 0.0 and exists only so receipts can
    cite the stance; inflating downloads/stars cannot move a ranking.
  * Equal scores are broken by ascending stable key, which makes the ordering
    a total order even across genuine score ties (the corpus carries one).

Ranking is explainable: SearchIndex.explain(query, stable_key) returns the
per-term contributions and a reconstructed score that equals the reported
score exactly (both are the same sorted-order sum).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

K1 = 1.5
B = 0.75
FIELDS = ("name", "description", "tags", "skills")
FIELD_WEIGHTS = {"name": 3.0, "description": 2.0, "tags": 2.5, "skills": 2.5}
POPULARITY_TERM = 0.0

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _skill_tokens(skill: Any) -> list[str]:
    if isinstance(skill, str):
        return _tokens(skill)
    if isinstance(skill, dict):
        out: list[str] = []
        for key in ("name", "id", "path"):
            value = skill.get(key)
            if isinstance(value, str):
                out.extend(_tokens(value))
        return out
    return []


def _field_tokens(plugin: dict, field: str) -> list[str]:
    if field == "name":
        value = plugin.get("name")
        return _tokens(value) if isinstance(value, str) else []
    if field == "description":
        value = plugin.get("description")
        return _tokens(value) if isinstance(value, str) else []
    if field == "tags":
        return [
            tok
            for value in (plugin.get("tags") or [])
            if isinstance(value, str)
            for tok in _tokens(value)
        ]
    if field == "skills":
        return [tok for s in (plugin.get("skills") or []) for tok in _skill_tokens(s)]
    return []


class Hit:
    __slots__ = ("stable_key", "score", "contributions")

    def __init__(self, stable_key: str, score: float, contributions: dict[str, float]):
        self.stable_key = stable_key
        self.score = score
        self.contributions = contributions

    def as_dict(self) -> dict:
        return {
            "stable_key": self.stable_key,
            "score": self.score,
            "contributions": dict(sorted(self.contributions.items())),
        }

    def __repr__(self) -> str:
        return "Hit({0!r}, score={1:.6f})".format(self.stable_key, self.score)


class SearchResult:
    """Ordered hits. kind='hits' when non-empty, kind='empty' when the query
    matched nothing (an explicit, non-error outcome)."""

    def __init__(self, hits: list[Hit]):
        self.hits = hits
        self.ok = True
        self.kind = "hits" if hits else "empty"

    def keys(self) -> list[str]:
        return [h.stable_key for h in self.hits]

    def __len__(self) -> int:
        return len(self.hits)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "kind": self.kind,
            "keys": self.keys(),
            "scores": {h.stable_key: h.score for h in self.hits},
        }


class IndexErrorResult:
    """The registry itself could not be read: distinct from an empty result."""

    kind = "index_error"
    ok = False
    hits: tuple = ()

    def __init__(self, path: Any, error: BaseException):
        self.path = str(path)
        self.error = "{0}: {1}".format(type(error).__name__, error)

    def keys(self) -> list[str]:
        return []

    def as_dict(self) -> dict:
        return {"ok": False, "kind": self.kind, "path": self.path, "error": self.error}


class SearchIndex:
    """Immutable index over a fixed document set. All statistics are derived
    in sorted stable-key order at construction time."""

    def __init__(self, documents: list[tuple[str, dict[str, list[str]]]]):
        docs: dict[str, dict[str, list[str]]] = {}
        for key, fields in documents:
            if key in docs:
                raise ValueError("duplicate stable key {0!r}".format(key))
            docs[key] = fields
        if not docs:
            raise ValueError("refusing to build an index over an empty corpus")
        self._keys = sorted(docs)
        self._docs = docs
        self.n = len(self._keys)

        lengths = {
            key: sum(FIELD_WEIGHTS[f] * len(docs[key][f]) for f in FIELDS)
            for key in self._keys
        }
        self._dl = lengths
        self._avgdl = math.fsum(lengths[k] for k in self._keys) / self.n

        df: dict[str, int] = {}
        for key in self._keys:
            for term in {tok for f in FIELDS for tok in docs[key][f]}:
                df[term] = df.get(term, 0) + 1
        self._df = df

        weighted: dict[str, dict[str, float]] = {}
        for key in self._keys:
            bag: dict[str, float] = {}
            for f in FIELDS:
                weight = FIELD_WEIGHTS[f]
                for tok in docs[key][f]:
                    bag[tok] = bag.get(tok, 0.0) + weight
            weighted[key] = bag
        self._wtf = weighted

    @classmethod
    def from_marketplace_data(cls, data: Any) -> "SearchIndex":
        plugins = (data or {}).get("plugins")
        if not isinstance(plugins, list) or not plugins:
            raise ValueError("marketplace data carries no plugins[] array")
        documents = []
        for plugin in plugins:
            if not isinstance(plugin, dict):
                raise ValueError("plugins[] entry is not an object")
            name = plugin.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("plugin without a name: stable_key undefined")
            documents.append((name, {f: _field_tokens(plugin, f) for f in FIELDS}))
        return cls(documents)

    @classmethod
    def from_marketplace_path(cls, path: Any) -> "SearchIndex":
        raw = Path(path).read_text(encoding="utf-8")
        return cls.from_marketplace_data(json.loads(raw))

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))

    def search(self, query: str) -> SearchResult:
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        terms = sorted(set(_tokens(query)))
        hits: list[Hit] = []
        for key in self._keys:  # ascending stable key
            bag = self._wtf[key]
            score = 0.0
            contributions: dict[str, float] = {}
            for term in terms:
                wtf = bag.get(term, 0.0)
                if wtf <= 0.0:
                    continue
                denom = wtf + K1 * (1.0 - B + B * (self._dl[key] / self._avgdl))
                contribution = self._idf(term) * (wtf * (K1 + 1.0)) / denom
                contributions[term] = contribution
                score += contribution
            if contributions:
                hits.append(Hit(key, score, contributions))
        hits.sort(key=lambda h: (-h.score, h.stable_key))
        return SearchResult(hits)

    def explain(self, query: str, stable_key: str) -> dict:
        terms = sorted(set(_tokens(query)))
        for hit in self.search(query).hits:
            if hit.stable_key != stable_key:
                continue
            reconstructed = 0.0
            for term in sorted(hit.contributions):
                reconstructed += hit.contributions[term]
            return {
                "stable_key": stable_key,
                "query_terms": terms,
                "score": hit.score,
                "reconstructed_score": reconstructed,
                "contributions": dict(sorted(hit.contributions.items())),
                "document_length": self._dl[stable_key],
                "average_document_length": self._avgdl,
                "documents": self.n,
            }
        raise KeyError("{0!r} is not a hit for query {1!r}".format(stable_key, query))


def search_path(path: Any, query: str):
    """Load a marketplace.json from `path` and search it. A missing or
    unreadable registry yields an index_error result, never a fake empty."""
    try:
        index = SearchIndex.from_marketplace_path(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return IndexErrorResult(path, exc)
    return index.search(query)


__all__ = [
    "B",
    "FIELD_WEIGHTS",
    "FIELDS",
    "K1",
    "POPULARITY_TERM",
    "Hit",
    "IndexErrorResult",
    "SearchIndex",
    "SearchResult",
    "search_path",
]
